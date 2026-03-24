import requests
from bs4 import BeautifulSoup
import sqlite3
import json
import time
import random
import logging
import re
import os
from fake_useragent import UserAgent

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler("logs/scrape.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 設定
DB_PATH = "database/takken_questions.db"
# 収集対象年度 (2014-2025)
YEARS = range(2014, 2026)

def parse_question_page(html, url, year):
    """takken-siken.com の静的解説ページをパース"""
    soup = BeautifulSoup(html, 'lxml')
    
    # 問題文
    mondai_div = soup.select_one('div.mondai')
    if not mondai_div:
        return None
    # 不要な要素（問題番号など）を除去
    for tag in mondai_div.select('.num, .ans-link'):
        tag.decompose()
    question_text = mondai_div.get_text(strip=True)

    # 選択肢
    options = []
    select_list = soup.select('ol.selectList li')
    for li in select_list:
        # data-answer="t" が正解
        options.append(li.get_text(strip=True))

    # 正解
    ans_char_el = soup.select_one('#answerChar')
    correct_answer = 0
    if ans_char_el:
        try:
            correct_answer = int(ans_char_el.get_text(strip=True))
        except:
            pass
    
    # 正解が #answerChar にない場合、li[data-answer="t"] から取得
    if correct_answer == 0:
        for i, li in enumerate(select_list):
            if li.get('data-answer') == 't':
                correct_answer = i + 1
                break

    # 解説
    kaisetsu_div = soup.select_one('div.kaisetsu')
    explanation = kaisetsu_div.get_text("\n", strip=True) if kaisetsu_div else ""

    # カテゴリ (暫定)
    q_num = int(re.search(r'/(\d+)\.html', url).group(1))
    category = "その他"
    if 1 <= q_num <= 14: category = "権利等"
    elif 15 <= q_num <= 25: category = "制限"
    elif 26 <= q_num <= 45: category = "業法"
    elif 46 <= q_num <= 50: category = "制限"

    return {
        "year": f"令和{year-2018}年度" if year >= 2019 else f"平成{year-1988}年度",
        "category": category,
        "question_text": question_text,
        "options": options,
        "correct_answer": correct_answer,
        "explanation": explanation
    }

def save_to_db(data):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO questions (year, category, question_text, options, correct_answer, explanation)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            data['year'],
            data['category'],
            data['question_text'],
            json.dumps(data['options'], ensure_ascii=False),
            data['correct_answer'],
            data['explanation']
        ))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"DB Save Error: {e}")
        return False

def human_wait(min_s=3, max_s=7):
    time.sleep(random.uniform(min_s, max_s))

def main():
    if not os.path.exists("logs"):
        os.makedirs("logs")

    ua = UserAgent()
    session = requests.Session()

    total_count = 0
    for year in YEARS:
        logger.info(f"--- Starting Year: {year} ---")
        
        for q_num in range(1, 51):
            q_str = f"{q_num:02d}"
            url = f"https://takken-siken.com/kakomon/{year}/{q_str}.html"
            logger.info(f"Fetching Q{q_num}: {url}")
            
            try:
                headers = {"User-Agent": ua.random}
                response = session.get(url, headers=headers, timeout=15)
                
                if response.status_code == 200:
                    data = parse_question_page(response.text, url, year)
                    if data and data['question_text'] and len(data['options']) >= 4:
                        if save_to_db(data):
                            logger.info(f"  Saved: {year} Q{q_num}")
                            total_count += 1
                        else:
                            logger.error(f"  Failed to save: {url}")
                    else:
                        logger.warning(f"  Parse failed or incomplete: {url}")
                elif response.status_code == 404:
                    logger.warning(f"  Page not found (404): {url}")
                else:
                    logger.error(f"  Error {response.status_code}: {url}")
                
            except Exception as e:
                logger.error(f"  Request Error: {e}")
            
            human_wait(3, 7)

        logger.info(f"Finished {year}. Waiting 300s before next year...")
        time.sleep(300)

    logger.info(f"Done! Total questions collected: {total_count}")

if __name__ == "__main__":
    main()
