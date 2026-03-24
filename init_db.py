"""
init_db.py — 宅建試験学習ツール データベース初期化スクリプト

このスクリプトを実行すると database/takken_questions.db が作成され、
サンプル問題データが挿入されます。
"""

import sqlite3
import json
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "database", "takken_questions.db")


def create_tables(conn: sqlite3.Connection) -> None:
    """テーブルスキーマを作成する"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            year            INTEGER NOT NULL,           -- 出題年 (例: 2023)
            category        TEXT    NOT NULL,           -- 分野: 業法 / 制限 / 権利等
            question_text   TEXT    NOT NULL,           -- 問題文
            options         TEXT    NOT NULL,           -- 選択肢 (JSON配列: ["選択肢1", ...])
            correct_answer  INTEGER NOT NULL,           -- 正解番号 (0始まり)
            explanation     TEXT    DEFAULT ''          -- 解説文
        )
    """)
    conn.commit()
    print("[init_db] テーブル 'questions' を作成しました。")


def seed_sample_data(conn: sqlite3.Connection) -> None:
    """サンプル問題データを挿入する"""

    samples = [
        {
            "year": 2023,
            "category": "業法",
            "question_text": (
                "宅地建物取引業者が行う広告に関する次の記述のうち、"
                "宅地建物取引業法の規定によれば、正しいものはどれか。"
            ),
            "options": json.dumps([
                "宅地建物取引業者は、宅地の造成工事の完了前においても広告をすることができる。",
                "宅地建物取引業者は、依頼者の依頼がなくても広告費用を請求することができる。",
                "宅地建物取引業者は、誇大広告をしてはならないが、将来の環境・交通等の利便については"
                "その旨表示すれば誇大広告とはならない。",
                "宅地建物取引業者は、取引態様を広告に明示しなければならない。",
            ], ensure_ascii=False),
            "correct_answer": 3,
            "explanation": (
                "正解は4番。宅建業法第34条により、広告には取引態様（売主・代理・媒介の別）を"
                "明示する義務がある。"
            ),
        },
        {
            "year": 2023,
            "category": "権利等",
            "question_text": (
                "民法における売買契約に関する次の記述のうち、正しいものはどれか。"
            ),
            "options": json.dumps([
                "売買契約は、書面によらなければ効力を生じない。",
                "売買契約において、買主は代金を支払う義務を負う。",
                "売買の目的物に瑕疵があった場合、売主は常に損害賠償責任を負う。",
                "売買契約は、買主が代金を支払った時点で成立する。",
            ], ensure_ascii=False),
            "correct_answer": 1,
            "explanation": (
                "正解は2番。民法第555条により、売買は当事者の合意のみで成立し（諾成契約）、"
                "買主は代金支払義務を負う。書面は不要。"
            ),
        },
        {
            "year": 2022,
            "category": "制限",
            "question_text": (
                "都市計画法に関する次の記述のうち、正しいものはどれか。"
            ),
            "options": json.dumps([
                "市街化区域は、すでに市街地を形成している区域及び概ね10年以内に優先的かつ計画的に"
                "市街化を図るべき区域である。",
                "市街化調整区域では、一切の開発行為が禁止される。",
                "準都市計画区域は、都市計画区域外において指定することができない。",
                "開発許可が不要な行為として、農業・林業・漁業用の建築物の建築はいかなる場合も含まれる。",
            ], ensure_ascii=False),
            "correct_answer": 0,
            "explanation": (
                "正解は1番。都市計画法第7条の規定のとおり。市街化区域は「すでに市街地を形成している区域」"
                "および「概ね10年以内に優先的かつ計画的に市街化を図るべき区域」をいう。"
            ),
        },
        {
            "year": 2022,
            "category": "業法",
            "question_text": (
                "宅地建物取引士に関する次の記述のうち、宅地建物取引業法の規定によれば、"
                "誤っているものはどれか。"
            ),
            "options": json.dumps([
                "宅地建物取引士は、取引の関係者から請求があったときは、宅地建物取引士証を提示しなければならない。",
                "宅地建物取引士証の有効期間は5年であり、更新することができる。",
                "宅地建物取引士は、重要事項の説明をするときは、説明の相手方に対し宅地建物取引士証を提示しなければならない。",
                "宅地建物取引士でない者は、重要事項の説明をすることができない。",
            ], ensure_ascii=False),
            "correct_answer": 1,
            "explanation": (
                "正解（誤り）は2番。宅地建物取引士証の有効期間は5年ではなく、登録から5年以内に交付申請が必要だが"
                "証の有効期間自体は交付日から5年。更新可能は正しい。"
                "（なお、この問題はやや紛らわしい設問例です。）"
            ),
        },
        {
            "year": 2021,
            "category": "権利等",
            "question_text": (
                "借地借家法に関する次の記述のうち、正しいものはどれか。"
            ),
            "options": json.dumps([
                "普通借地権の存続期間は、最短30年である。",
                "定期借地権の存続期間は、最短10年である。",
                "普通借地権では、更新後の期間は最初から最低30年となる。",
                "建物譲渡特約付借地権の存続期間は、50年以上でなければならない。",
            ], ensure_ascii=False),
            "correct_answer": 0,
            "explanation": (
                "正解は1番。借地借家法第3条により、借地権の存続期間は30年を下回ることができない。"
                "定期借地権（一般）の存続期間は50年以上（法22条）。"
            ),
        },
    ]

    conn.executemany(
        """
        INSERT INTO questions (year, category, question_text, options, correct_answer, explanation)
        VALUES (:year, :category, :question_text, :options, :correct_answer, :explanation)
        """,
        samples,
    )
    conn.commit()
    print(f"[init_db] サンプル問題を {len(samples)} 件挿入しました。")


def main() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    print(f"[init_db] データベースパス: {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        create_tables(conn)
        # 既にデータがある場合はスキップ
        count = conn.execute("SELECT COUNT(*) FROM questions").fetchone()[0]
        if count == 0:
            seed_sample_data(conn)
        else:
            print(f"[init_db] データが既に存在します（{count} 件）。シードをスキップします。")

    print("[init_db] 初期化完了。")


if __name__ == "__main__":
    main()
