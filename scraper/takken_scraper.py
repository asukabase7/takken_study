"""
takken_scraper.py — 宅建試験問題スクレイパー（ステルスモード実装）

■ 安全装備
  - fake-useragent による動的User-Agent生成
  - ページ取得ごとのランダムウェイト（人間行動模倣）
  - 403/429 検知→自動バックオフ or アラート
  - robots.txt 遵守チェック
  - 指数バックオフ付きリトライ
"""

import sqlite3
import json
import os
import time
import random
import logging
import urllib.robotparser
from urllib.parse import urlparse
from typing import Any

import requests
from bs4 import BeautifulSoup

try:
    from fake_useragent import UserAgent
    _UA = UserAgent()
    def _get_user_agent() -> str:
        return _UA.random
except Exception:
    # fake-useragent が使えない場合はハードコードリストにフォールバック
    _UA_LIST = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.4 Safari/605.1.15",
        "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 Edg/123.0.0.0",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 "
        "(KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    ]
    def _get_user_agent() -> str:
        return random.choice(_UA_LIST)

# ─────────────────────────────────────────────
# パス設定
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH  = os.path.join(BASE_DIR, "database", "takken_questions.db")

# TODO: 実際のスクレイピング先URLに差し替える
FETCH_URL = "https://example.com/takken/questions"

# ─────────────────────────────────────────────
# ロガー設定
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# robots.txt 遵守チェック
# ─────────────────────────────────────────────
_robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}

def _can_fetch(url: str) -> bool:
    """
    ターゲットURLが robots.txt で許可されているか確認する。
    ネットワーク取得に失敗した場合は許可とみなす（安全寄り）。
    結果はドメインごとにキャッシュする。
    """
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}"

    if origin not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        robots_url = f"{origin}/robots.txt"
        try:
            rp.set_url(robots_url)
            rp.read()
            logger.info("robots.txt 取得: %s", robots_url)
        except Exception as exc:
            logger.warning("robots.txt 取得失敗（許可として扱います）: %s", exc)
            rp = None
        _robots_cache[origin] = rp

    rp = _robots_cache[origin]
    if rp is None:
        return True
    allowed = rp.can_fetch("*", url)
    if not allowed:
        logger.warning("robots.txt が Disallow: %s", url)
    return allowed


# ─────────────────────────────────────────────
# インテリジェント・ウェイト
# ─────────────────────────────────────────────
# ウェイト設定（秒）
WAIT_BETWEEN_PAGES  = (3.0, 7.0)   # ページ遷移間（人間が問題を読む時間）
WAIT_ON_RATE_LIMIT  = 600          # 429/403 受信時の強制待機（10分）
WAIT_RETRY_BASE     = 5.0          # リトライ指数バックオフの基底（秒）

def _human_sleep(label: str = "") -> float:
    """ランダムウェイトを実行し、待機秒数を返す。"""
    wait = random.uniform(*WAIT_BETWEEN_PAGES)
    logger.info("待機中 %.1f 秒 %s", wait, f"({label})" if label else "")
    time.sleep(wait)
    return wait


# ─────────────────────────────────────────────
# HTTPリクエスト（リトライ付き）
# ─────────────────────────────────────────────
MAX_RETRIES = 3

def _fetch_page(url: str, session: requests.Session, attempt: int = 0) -> str | None:
    """
    指定URLのHTMLを取得して返す。
    403/429 の場合は WAIT_ON_RATE_LIMIT 秒待機後にリトライ（最大 MAX_RETRIES 回）。
    それ以上の場合は None を返す。
    """
    ua = _get_user_agent()
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ja-JP,ja;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Referer": url,
    }
    logger.info("GET %s  UA: %s...", url, ua[:60])

    try:
        resp = session.get(url, headers=headers, timeout=15)
    except requests.RequestException as exc:
        logger.error("ネットワークエラー: %s", exc)
        return None

    if resp.status_code in (403, 429):
        if attempt < MAX_RETRIES:
            logger.warning(
                "HTTP %d 検知。%d 秒待機後にリトライ（試行 %d/%d）...",
                resp.status_code, WAIT_ON_RATE_LIMIT, attempt + 1, MAX_RETRIES
            )
            time.sleep(WAIT_ON_RATE_LIMIT)
            return _fetch_page(url, session, attempt + 1)
        else:
            logger.error(
                "HTTP %d: リトライ上限到達。スクレイピングを中断します。"
                " 時間を置いて再実行してください。", resp.status_code
            )
            return None

    if not resp.ok:
        logger.error("HTTP エラー %d: %s", resp.status_code, url)
        return None

    resp.encoding = resp.apparent_encoding
    return resp.text


# ─────────────────────────────────────────────
# パーサー (実装待ち)
# ─────────────────────────────────────────────
def parse_page(html: str) -> list[dict[str, Any]]:
    """
    HTMLをパースして問題リストを返す。

    Returns:
        list of dict with keys:
            year, category, question_text, options (list[str]),
            correct_answer (int, 0-indexed), explanation
    """
    soup = BeautifulSoup(html, "lxml")
    questions: list[dict[str, Any]] = []

    # TODO: 実際のサイト構造に合わせてセレクタを調整する
    for block in soup.select(".question-block"):
        try:
            question_text = block.select_one(".question-text").get_text(strip=True)
            option_tags   = block.select(".option")
            options       = [tag.get_text(strip=True) for tag in option_tags]
            correct_raw   = block.get("data-correct", "1")
            correct_answer = int(correct_raw) - 1  # 1-indexed → 0-indexed
            explanation = (
                block.select_one(".explanation").get_text(strip=True)
                if block.select_one(".explanation")
                else ""
            )
            questions.append({
                "year":          2024,
                "category":      "業法",
                "question_text": question_text,
                "options":       options,
                "correct_answer": correct_answer,
                "explanation":   explanation,
            })
        except Exception as exc:
            logger.warning("問題のパースに失敗: %s", exc)

    return questions


# ─────────────────────────────────────────────
# DB保存
# ─────────────────────────────────────────────
def save_questions(questions: list[dict[str, Any]]) -> int:
    """問題リストをDBに保存し、保存件数を返す。"""
    if not questions:
        return 0
    with sqlite3.connect(DB_PATH) as conn:
        conn.executemany(
            """
            INSERT INTO questions
                (year, category, question_text, options, correct_answer, explanation)
            VALUES
                (:year, :category, :question_text, :options, :correct_answer, :explanation)
            """,
            [{**q, "options": json.dumps(q["options"], ensure_ascii=False)} for q in questions],
        )
        conn.commit()
    return len(questions)


# ─────────────────────────────────────────────
# モックデータ生成
# ─────────────────────────────────────────────
def _generate_mock_questions(n: int = 3) -> list[dict[str, Any]]:
    """ダミー問題データを生成する（スクレイピング先URL確定前の動作確認用）。"""
    categories = ["業法", "制限", "権利等"]
    return [
        {
            "year":          2024,
            "category":      categories[i % len(categories)],
            "question_text": f"【モック問題 {i + 1}】{categories[i % len(categories)]}に関するサンプル問題文です。",
            "options":       [f"選択肢{j + 1}（{categories[i % len(categories)]}）" for j in range(4)],
            "correct_answer": random.randint(0, 3),
            "explanation":   f"これはモックデータの解説 {i + 1} です。",
        }
        for i in range(n)
    ]


# ─────────────────────────────────────────────
# メインエントリポイント
# ─────────────────────────────────────────────
def fetch_and_save_questions(
    url: str  = FETCH_URL,
    mock: bool = True,
    n_mock: int = 3,
) -> int:
    """
    指定URLから問題を取得してDBに保存する。

    Args:
        url:    スクレイピング先URL（デフォルト: FETCH_URL定数）
        mock:   True のとき実際のHTTPリクエストを行わずモックデータを使用する
        n_mock: モック時に生成する問題数

    Returns:
        保存した問題数
    """
    if mock:
        logger.info("━━ モードMOCK: %d 問生成 ━━", n_mock)
        questions = _generate_mock_questions(n=n_mock)
        for i, q in enumerate(questions, 1):
            wait = _human_sleep(f"問題 {i}/{n_mock} 読了シミュレーション")
            logger.info(
                "安全に取得完了（待機時間: %.1f 秒）: [%s] %s",
                wait, q["category"], q["question_text"][:30]
            )
        saved = save_questions(questions)
        logger.info("━━ 保存完了: %d 件 ━━", saved)
        return saved

    # ── 実スクレイピング ──
    logger.info("━━ スクレイピング開始: %s ━━", url)

    # robots.txt チェック
    if not _can_fetch(url):
        logger.error("robots.txt により %s へのアクセスは禁止されています。中断します。", url)
        return 0

    session = requests.Session()
    all_questions: list[dict[str, Any]] = []

    # 単一ページ取得の例（複数ページ対応は urls リストを渡す拡張で対応可能）
    urls_to_fetch = [url]  # 将来: ページネーションで複数URL

    for i, page_url in enumerate(urls_to_fetch, 1):
        if i > 1:
            wait = _human_sleep(f"次ページへ移動 {i}/{len(urls_to_fetch)}")
        else:
            wait = 0.0

        if not _can_fetch(page_url):
            logger.warning("robots.txt Disallow: %s をスキップ", page_url)
            continue

        html = _fetch_page(page_url, session)
        if html is None:
            continue

        questions = parse_page(html)
        all_questions.extend(questions)
        logger.info(
            "安全に取得完了（待機時間: %.1f 秒）: %d 問パース — %s",
            wait, len(questions), page_url
        )

    saved = save_questions(all_questions)
    logger.info("━━ 保存完了: %d 件 ━━", saved)
    return saved


# ─────────────────────────────────────────────
if __name__ == "__main__":
    n = fetch_and_save_questions(mock=True, n_mock=3)
    print(f"\n保存件数: {n}")
