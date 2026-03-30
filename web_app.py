import os
import sqlite3
import json
import random
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "takken_questions.db")

@app.route("/")
def index():
    years = []
    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute("SELECT DISTINCT year FROM questions ORDER BY year DESC").fetchall()
            years = [str(r[0]) for r in rows]
    except sqlite3.Error:
        pass
    return render_template("index.html", years=years)

def _build_where_clause(base_where=""):
    category = request.args.get("category", "すべて")
    year = request.args.get("year", "すべて")
    
    conditions = []
    params = []
    
    if base_where:
        conditions.append(base_where)
        
    if category != "すべて":
        conditions.append("category = ?")
        params.append(category)
        
    if year != "すべて":
        conditions.append("year = ?")
        params.append(year)
        
    if conditions:
        return "WHERE " + " AND ".join(conditions), params
    return "", params

@app.route("/api/question")
def get_question():
    """
    DBからランダムに1問取り、選択肢を1つランダムに選んで○×問題として返す
    """
    EXCLUDE_PATTERNS = [
        "%一つ%", "%二つ%", "%三つ%", "%四つ%",
        "%個%", "%アとイ%", "%ア、イ%",
        "%組合せ%", "%正しいものはいくつ%",
    ]
    base_where = " AND ".join(f"options NOT LIKE '{p}'" for p in EXCLUDE_PATTERNS)
    
    where_sql, params = _build_where_clause(base_where)
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            query = f"SELECT id, question_text, options, correct_answer, explanation FROM questions {where_sql} ORDER BY RANDOM() LIMIT 1"
            row = conn.execute(query, params).fetchone()
    except sqlite3.Error as e:
        return jsonify({"error": str(e)}), 500

    if row is None:
        return jsonify({"error": "No valid questions found"}), 404

    q_id, q_text, opts_json, correct_1based, expl = row
    
    try:
        opts = json.loads(opts_json)
    except json.JSONDecodeError:
        opts = []
        
    if not opts:
        return jsonify({"error": "Invalid options format"}), 500

    correct_0 = correct_1based - 1

    idx = random.randint(0, len(opts) - 1)
    option_text = opts[idx]
    is_correct = (idx == correct_0)

    return jsonify({
        "id": q_id,
        "main_question": q_text,
        "sub_question": option_text,
        "is_correct": is_correct,
        "explanation": expl or "",
        "correct_option_index": correct_0,
        "chosen_option_index": idx,
        "options": opts
    })

@app.route("/api/question/4choice")
def get_4choice():
    """
    DBからランダムに1問取り、4択問題としてフルデータを返す
    """
    where_sql, params = _build_where_clause()
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            query = f"SELECT id, question_text, options, correct_answer, explanation FROM questions {where_sql} ORDER BY RANDOM() LIMIT 1"
            row = conn.execute(query, params).fetchone()
    except sqlite3.Error as e:
        return jsonify({"error": str(e)}), 500

    if row is None:
        return jsonify({"error": "No valid questions found"}), 404

    q_id, q_text, opts_json, correct_1based, expl = row
    
    try:
        opts = json.loads(opts_json)
    except json.JSONDecodeError:
        opts = []
        
    if not opts:
        return jsonify({"error": "Invalid options format"}), 500

    correct_0 = correct_1based - 1

    return jsonify({
        "id": q_id,
        "main_question": q_text,
        "options": opts,
        "correct_option_index": correct_0,
        "explanation": expl or ""
    })

@app.route("/api/stats")
def get_stats():
    category = request.args.get("category", "すべて")
    year = request.args.get("year", "すべて")
    
    conditions = []
    params = []
    if category != "すべて":
        conditions.append("q.category = ?")
        params.append(category)
    if year != "すべて":
        conditions.append("q.year = ?")
        params.append(year)
        
    where_sql = "WHERE " + " AND ".join(conditions) if conditions else ""
    
    try:
        with sqlite3.connect(DB_PATH) as conn:
            # 総問題数
            total_q = f"SELECT COUNT(*) FROM questions q {where_sql}"
            total = conn.execute(total_q, params).fetchone()[0]
            
            # 回答済み問題数（study_logsにある問題の種類数）
            ans_q = f"""
                SELECT COUNT(DISTINCT s.question_id) 
                FROM study_logs s
                JOIN questions q ON s.question_id = q.id
                {where_sql}
            """
            answered = conn.execute(ans_q, params).fetchone()[0]
            
            # 正解数（最新の解答が正解である問題の数）
            correct_q = f"""
                SELECT COUNT(*) FROM (
                    SELECT s.question_id, s.is_correct,
                           ROW_NUMBER() OVER (PARTITION BY s.question_id ORDER BY s.answered_at DESC) as rn
                    FROM study_logs s
                    JOIN questions q ON s.question_id = q.id
                    {where_sql}
                ) WHERE rn = 1 AND is_correct = 1
            """
            correct = conn.execute(correct_q, params).fetchone()[0]
            
            return jsonify({
                "total": total,
                "answered": answered,
                "correct": correct
            })
    except sqlite3.Error as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
