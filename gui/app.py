"""
app.py — 宅建試験学習ツール GUIアプリケーション

Phase 6:
  ① 年度別フィルター
  ② 間違え問題の復習モード
  ③ 〇×一問一答 別ウィンドウ
"""

import sqlite3
import json
import os
import random
import tkinter as tk
from tkinter import ttk, messagebox, font as tkfont

# ─────────────────────────────────────────────
# パス設定
# ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "takken_questions.db")

# ─────────────────────────────────────────────
# カラーパレット
# ─────────────────────────────────────────────
COLORS = {
    "bg":      "#1E2030",
    "surface": "#2A2D3E",
    "card":    "#2F3447",
    "primary": "#7C83FD",
    "accent":  "#56CFE1",
    "success": "#4CAF50",
    "error":   "#F44336",
    "text":    "#E0E0E0",
    "subtext": "#9E9EB8",
    "border":  "#454875",
    "gold":    "#E8A838",
    "review":  "#9B59B6",
}

CATEGORIES = ["すべて", "業法", "制限", "権利等"]


# ─────────────────────────────────────────────
# DB 初期化
# ─────────────────────────────────────────────
def init_study_logs():
    if not os.path.exists(DB_PATH):
        return
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS study_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                question_id INTEGER NOT NULL,
                is_correct  INTEGER NOT NULL,
                answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()


# ─────────────────────────────────────────────
# DB 操作
# ─────────────────────────────────────────────
def _build_where(category: str, year: str) -> tuple[str, list]:
    """WHERE句とパラメータを生成するヘルパー"""
    clauses, params = [], []
    if category != "すべて":
        clauses.append("category = ?")
        params.append(category)
    if year != "すべて":
        clauses.append("year = ?")
        params.append(year)
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def get_years() -> list[str]:
    """DBに存在する年度一覧を返す (表示用に年度を付与してはダメ、コンボボックスの選択値と一致させるため)"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT DISTINCT year FROM questions ORDER BY year"
            ).fetchall()
        return ["すべて"] + [str(r[0]) for r in rows]
    except sqlite3.Error:
        return ["すべて"]


def get_random_question(category: str = "すべて", year: str = "すべて") -> dict | None:
    if not os.path.exists(DB_PATH):
        return None
    try:
        where, params = _build_where(category, year)
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                f"SELECT id, year, category, question_text, options, correct_answer, explanation "
                f"FROM questions {where} ORDER BY RANDOM() LIMIT 1",
                params,
            ).fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    return {
        "id": row[0], "year": row[1], "category": row[2],
        "question_text": row[3], "options": json.loads(row[4]),
        "correct_answer": row[5], "explanation": row[6],
    }


def get_review_question(category: str = "すべて", year: str = "すべて") -> dict | None:
    """直近の回答で間違えた問題からランダムに 1 問返す"""
    if not os.path.exists(DB_PATH):
        return None
    try:
        where_q, params_q = _build_where(category, year)
        # _build_where が WHERE ... を返すので、AND ... に変換して結合する
        and_clause = where_q.replace("WHERE", "AND") if where_q else ""

        sql = f"""
            SELECT q.id, q.year, q.category, q.question_text, q.options,
                   q.correct_answer, q.explanation
            FROM questions q
            WHERE q.id IN (
                SELECT question_id FROM (
                    SELECT question_id, is_correct,
                           ROW_NUMBER() OVER (PARTITION BY question_id ORDER BY answered_at DESC) AS rn
                    FROM study_logs
                ) WHERE rn = 1 AND is_correct = 0
            )
            {and_clause}
            ORDER BY RANDOM() LIMIT 1
        """
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(sql, params_q).fetchone()
    except sqlite3.Error:
        return None
    if row is None:
        return None
    return {
        "id": row[0], "year": row[1], "category": row[2],
        "question_text": row[3], "options": json.loads(row[4]),
        "correct_answer": row[5], "explanation": row[6],
    }


def get_review_count() -> int:
    """復習対象（最後の回答が不正解）の問題数を返す"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute("""
                SELECT COUNT(*) FROM (
                    SELECT question_id, is_correct,
                           ROW_NUMBER() OVER (PARTITION BY question_id ORDER BY answered_at DESC) AS rn
                    FROM study_logs
                ) WHERE rn = 1 AND is_correct = 0
            """).fetchone()
            return row[0] if row else 0
    except sqlite3.Error:
        return 0


def log_answer(question_id: int, is_correct: bool):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO study_logs (question_id, is_correct) VALUES (?, ?)",
                (question_id, 1 if is_correct else 0),
            )
            conn.commit()
    except sqlite3.Error:
        pass


def get_accuracy_stats() -> tuple[int, int]:
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT COUNT(*), SUM(is_correct) FROM study_logs"
            ).fetchone()
            return (row[0] or 0), int(row[1] or 0)
    except sqlite3.Error:
        return 0, 0


def get_question_count(category: str = "すべて", year: str = "すべて") -> int:
    try:
        where, params = _build_where(category, year)
        with sqlite3.connect(DB_PATH) as conn:
            return conn.execute(
                f"SELECT COUNT(*) FROM questions {where}", params
            ).fetchone()[0]
    except sqlite3.Error:
        return 0


# ─────────────────────────────────────────────
# ○× 一問一答ウィンドウ
# ─────────────────────────────────────────────
class TrueFalseWindow(tk.Toplevel):
    """4択問題の選択肢を 1 つずつ○×問題として出題するウィンドウ"""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("⭕❌ 一問一答モード")
        self.geometry("760x520")
        self.resizable(True, True)
        self.configure(bg=COLORS["bg"])
        self.minsize(560, 420)

        self._score = [0, 0]  # [correct, total]
        self._current: dict | None = None  # {text, is_correct, q_id, explanation}
        self._answered = False

        self._setup_fonts()
        self._build_ui()
        self._load_item()

    def _setup_fonts(self):
        self.f_body  = tkfont.Font(family="TakaoPGothic", size=10)
        self.f_small = tkfont.Font(family="TakaoPGothic", size=8)
        self.f_bold  = tkfont.Font(family="TakaoPGothic", size=11, weight="bold")

    def _build_ui(self):
        # ヘッダー
        hdr = tk.Frame(self, bg=COLORS["surface"], pady=6)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="⭕❌ 一問一答モード",
                 bg=COLORS["surface"], fg=COLORS["accent"],
                 font=("TakaoPGothic", 12, "bold")).pack(side=tk.LEFT, padx=16)
        self.lbl_score = tk.Label(hdr, text="",
                                  bg=COLORS["surface"], fg=COLORS["subtext"],
                                  font=self.f_small)
        self.lbl_score.pack(side=tk.RIGHT, padx=16)

        # 説明
        tk.Label(self, text="この文章は正しいですか？",
                 bg=COLORS["bg"], fg=COLORS["subtext"],
                 font=self.f_small).pack(pady=(10, 2))

        # 問題カード
        card = tk.Frame(self, bg=COLORS["card"], pady=14)
        card.pack(fill=tk.X, padx=24, pady=(0, 12))

        self.lbl_item = tk.Label(card, text="",
                                 bg=COLORS["card"], fg=COLORS["text"],
                                 font=self.f_body, wraplength=660,
                                 justify=tk.LEFT)
        self.lbl_item.pack(fill=tk.X, padx=16)

        def _wrap_q(e):
            self.lbl_item.config(wraplength=max(200, e.width - 32))
        card.bind("<Configure>", _wrap_q)

        # ○×ボタン
        btn_row = tk.Frame(self, bg=COLORS["bg"])
        btn_row.pack(pady=6)

        self.btn_true = tk.Button(
            btn_row, text="⭕  正しい", width=14,
            command=lambda: self._answer(True),
            bg=COLORS["success"], fg="white",
            font=("TakaoPGothic", 13, "bold"),
            relief=tk.FLAT, pady=12, cursor="hand2")
        self.btn_true.pack(side=tk.LEFT, padx=16)

        self.btn_false = tk.Button(
            btn_row, text="❌  誤り", width=14,
            command=lambda: self._answer(False),
            bg=COLORS["error"], fg="white",
            font=("TakaoPGothic", 13, "bold"),
            relief=tk.FLAT, pady=12, cursor="hand2")
        self.btn_false.pack(side=tk.LEFT, padx=16)

        # フィードバック
        self.lbl_fb = tk.Label(self, text="",
                               bg=COLORS["bg"], fg=COLORS["text"],
                               font=self.f_body, wraplength=680, justify=tk.LEFT)
        self.lbl_fb.pack(fill=tk.X, padx=24, pady=(6, 4))

        def _wrap_fb(e):
            self.lbl_fb.config(wraplength=max(200, e.width - 48))
        self.bind("<Configure>", _wrap_fb)

        # 次へボタン
        self.btn_next = tk.Button(
            self, text="▶  次の問題",
            command=self._load_item,
            bg=COLORS["surface"], fg=COLORS["text"],
            font=("TakaoPGothic", 11),
            relief=tk.FLAT, padx=18, pady=8, cursor="hand2")
        self.btn_next.pack(pady=4)

    def _load_item(self):
        """全問題DBからランダムに1問取り、選択肢を1つランダムに選んで出題"""
        self._answered = False
        self.lbl_fb.config(text="")
        self.btn_true.config(state=tk.NORMAL, relief=tk.FLAT)
        self.btn_false.config(state=tk.NORMAL, relief=tk.FLAT)

        # ランダムに元問題を取得
        try:
            with sqlite3.connect(DB_PATH) as conn:
                row = conn.execute(
                    "SELECT id, question_text, options, correct_answer, explanation "
                    "FROM questions ORDER BY RANDOM() LIMIT 1"
                ).fetchone()
        except sqlite3.Error:
            return

        if row is None:
            return

        q_id, q_text, opts_json, correct_1based, expl = row
        opts = json.loads(opts_json)
        correct_0 = correct_1based - 1

        # 選択肢をランダムに1つ選ぶ
        idx = random.randint(0, len(opts) - 1)
        option_text = opts[idx]
        is_correct = (idx == correct_0)

        labels = ["①", "②", "③", "④"]
        display = f"{labels[idx]}  {option_text}"

        self._current = {
            "text": display,
            "is_correct": is_correct,
            "q_id": q_id,
            "explanation": expl or "",
            "label": labels[idx],
            "correct_label": labels[correct_0],
        }
        self.lbl_item.config(text=display)

    def _answer(self, user_says_true: bool):
        if self._answered or self._current is None:
            return
        self._answered = True
        self.btn_true.config(state=tk.DISABLED)
        self.btn_false.config(state=tk.DISABLED)

        actually_correct = self._current["is_correct"]
        user_correct = (user_says_true == actually_correct)

        self._score[1] += 1
        if user_correct:
            self._score[0] += 1
            verdict = "⭕  正解！"
            fg = COLORS["success"]
        else:
            verdict = "❌  不正解！"
            fg = COLORS["error"]

        # 説明を付加
        if actually_correct:
            result_note = f"この記述は「正しい」でした。"
        else:
            result_note = (
                f"この記述は「誤り」でした。\n"
                f"（正解選択肢は {self._current['correct_label']} です）"
            )
        expl = self._current["explanation"][:200] + "…" if len(self._current["explanation"]) > 200 else self._current["explanation"]

        self.lbl_fb.config(
            text=f"{verdict}  {result_note}\n{expl}",
            fg=fg,
        )

        total, correct = self._score[1], self._score[0]
        pct = correct / total * 100
        self.lbl_score.config(text=f"正答率: {pct:.1f}%  ({correct}/{total})")


# ─────────────────────────────────────────────
# メイン GUIアプリ
# ─────────────────────────────────────────────
class TakkenApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("宅建試験 学習ツール")
        self.geometry("860x700")
        self.resizable(True, True)
        self.configure(bg=COLORS["bg"])
        self.minsize(660, 540)

        init_study_logs()
        self._setup_fonts()

        # 状態変数
        self.current_question: dict | None = None
        self.selected_answer = tk.IntVar(value=-1)
        self.answered = False
        self.selected_category = tk.StringVar(value="すべて")
        self.selected_year = tk.StringVar(value="すべて")
        self.review_mode = tk.BooleanVar(value=False)

        self._build_ui()
        self.load_question()

    def _setup_fonts(self):
        self.font_title  = tkfont.Font(family="TakaoPGothic", size=11, weight="bold")
        self.font_body   = tkfont.Font(family="TakaoPGothic", size=10)
        self.font_option = tkfont.Font(family="TakaoPGothic", size=10)
        self.font_small  = tkfont.Font(family="TakaoPGothic", size=8)
        self.font_badge  = tkfont.Font(family="TakaoPGothic", size=9, weight="bold")

    def _build_ui(self):
        self.columnconfigure(0, weight=1)

        # ─── ヘッダー ───
        header = tk.Frame(self, bg=COLORS["surface"], pady=8)
        header.pack(fill=tk.X)

        tk.Label(
            header, text="📚  宅建試験 学習ツール",
            bg=COLORS["surface"], fg=COLORS["primary"],
            font=("TakaoPGothic", 13, "bold"),
        ).pack(side=tk.LEFT, padx=16)

        self.lbl_accuracy = tk.Label(
            header, text="",
            bg=COLORS["surface"], fg=COLORS["accent"],
            font=("TakaoPGothic", 10, "bold"),
        )
        self.lbl_accuracy.pack(side=tk.RIGHT, padx=16)

        self.lbl_count = tk.Label(
            header, text="",
            bg=COLORS["surface"], fg=COLORS["subtext"],
            font=self.font_small,
        )
        self.lbl_count.pack(side=tk.RIGHT, padx=4)

        # ─── フィルターバー ───
        filter_bar = tk.Frame(self, bg=COLORS["card"], pady=6)
        filter_bar.pack(fill=tk.X)

        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure(
            "Dark.TCombobox",
            fieldbackground=COLORS["surface"],
            background=COLORS["surface"],
            foreground=COLORS["text"],
            arrowcolor=COLORS["primary"],
            bordercolor=COLORS["border"],
            selectbackground=COLORS["primary"],
            selectforeground="white",
        )
        style.map("Dark.TCombobox",
                  fieldbackground=[("readonly", COLORS["surface"])],
                  foreground=[("readonly", COLORS["text"])],
                  )

        # 分野コンボ
        tk.Label(filter_bar, text="📂 分野：",
                 bg=COLORS["card"], fg=COLORS["subtext"],
                 font=self.font_small).pack(side=tk.LEFT, padx=(16, 2))

        self.combo_category = ttk.Combobox(
            filter_bar, textvariable=self.selected_category,
            values=CATEGORIES, state="readonly",
            style="Dark.TCombobox", width=9, font=self.font_body,
        )
        self.combo_category.pack(side=tk.LEFT, padx=(0, 12))
        self.combo_category.bind("<<ComboboxSelected>>", self._on_filter_change)

        # 年度コンボ
        tk.Label(filter_bar, text="📅 年度：",
                 bg=COLORS["card"], fg=COLORS["subtext"],
                 font=self.font_small).pack(side=tk.LEFT, padx=(0, 2))

        self.combo_year = ttk.Combobox(
            filter_bar, textvariable=self.selected_year,
            values=get_years(), state="readonly",
            style="Dark.TCombobox", width=12, font=self.font_body,
        )
        self.combo_year.pack(side=tk.LEFT, padx=(0, 12))
        self.combo_year.bind("<<ComboboxSelected>>", self._on_filter_change)

        # 復習モードボタン
        self.btn_review = tk.Button(
            filter_bar, text="🔁 復習モード",
            command=self._toggle_review,
            bg=COLORS["surface"], fg=COLORS["subtext"],
            font=self.font_small, relief=tk.FLAT,
            padx=10, pady=3, cursor="hand2",
        )
        self.btn_review.pack(side=tk.LEFT, padx=(0, 8))

        review_count = get_review_count()
        self.lbl_review_count = tk.Label(
            filter_bar, text=f"（要復習: {review_count}問）",
            bg=COLORS["card"], fg=COLORS["review"],
            font=self.font_small,
        )
        self.lbl_review_count.pack(side=tk.LEFT)

        # 〇×モードボタン（右端）
        tk.Button(
            filter_bar, text="⭕❌ 一問一答",
            command=self._open_truefalse,
            bg=COLORS["accent"], fg=COLORS["bg"],
            font=("TakaoPGothic", 9, "bold"),
            relief=tk.FLAT, padx=10, pady=3, cursor="hand2",
        ).pack(side=tk.RIGHT, padx=16)

        # ─── メインコンテンツ ───
        main = tk.Frame(self, bg=COLORS["bg"])
        main.pack(fill=tk.BOTH, expand=True, padx=24, pady=12)
        main.columnconfigure(0, weight=1)

        # バッジ行
        badge_row = tk.Frame(main, bg=COLORS["bg"])
        badge_row.pack(fill=tk.X, pady=(0, 8))

        self.lbl_mode_badge = tk.Label(
            badge_row, text="",
            bg=COLORS["review"], fg="white",
            font=self.font_badge, padx=8, pady=2,
        )
        # 通常は非表示
        self.lbl_year_badge = tk.Label(
            badge_row, text="",
            bg=COLORS["primary"], fg="white",
            font=self.font_badge, padx=8, pady=2,
        )
        self.lbl_year_badge.pack(side=tk.LEFT, padx=(0, 6))
        self.lbl_category = tk.Label(
            badge_row, text="",
            bg=COLORS["accent"], fg="#1E2030",
            font=self.font_badge, padx=8, pady=2,
        )
        self.lbl_category.pack(side=tk.LEFT)

        # 問題文カード
        q_frame = tk.Frame(main, bg=COLORS["card"], pady=12, relief=tk.FLAT)
        q_frame.pack(fill=tk.X, pady=(0, 10))
        q_frame.columnconfigure(0, weight=1)

        tk.Label(q_frame, text="問題",
                 bg=COLORS["card"], fg=COLORS["subtext"],
                 font=self.font_small).pack(anchor=tk.W, padx=16)

        self.lbl_question = tk.Label(
            q_frame, text="",
            bg=COLORS["card"], fg=COLORS["text"],
            font=self.font_body, wraplength=680, justify=tk.LEFT,
        )
        self.lbl_question.pack(fill=tk.X, padx=16, pady=(4, 8))

        def _update_wrap(event):
            w = max(200, event.width - 32)
            self.lbl_question.config(wraplength=w)
        q_frame.bind("<Configure>", _update_wrap)

        # 選択肢
        options_outer = tk.LabelFrame(
            main, text="  選択肢  ",
            bg=COLORS["bg"], fg=COLORS["subtext"],
            font=self.font_small, bd=1, relief=tk.GROOVE,
        )
        options_outer.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        options_outer.columnconfigure(0, weight=1)

        self.radio_buttons: list[tk.Radiobutton] = []
        self.option_frames: list[tk.Frame] = []

        for i in range(4):
            opt_frame = tk.Frame(options_outer, bg=COLORS["surface"], pady=6)
            opt_frame.pack(fill=tk.X, padx=8, pady=3)
            opt_frame.columnconfigure(0, weight=1)
            self.option_frames.append(opt_frame)

            rb = tk.Radiobutton(
                opt_frame, text="",
                variable=self.selected_answer, value=i,
                bg=COLORS["surface"], fg=COLORS["text"],
                activebackground=COLORS["card"],
                activeforeground=COLORS["primary"],
                selectcolor=COLORS["card"],
                font=self.font_option,
                anchor=tk.W, justify=tk.LEFT, wraplength=680,
                padx=10,
                command=self._on_option_select,
            )
            rb.pack(fill=tk.X)
            self.radio_buttons.append(rb)

        def _update_option_wrap(event, rbs=self.radio_buttons):
            w = max(200, event.width - 60)
            for rb in rbs:
                rb.config(wraplength=w)
        options_outer.bind("<Configure>", _update_option_wrap)

        # フィードバック
        self.lbl_feedback = tk.Label(
            main, text="",
            bg=COLORS["bg"], fg=COLORS["text"],
            font=("TakaoPGothic", 10, "bold"),
            wraplength=700, justify=tk.LEFT,
        )
        self.lbl_feedback.pack(fill=tk.X, pady=(0, 6))

        def _update_feedback_wrap(event):
            self.lbl_feedback.config(wraplength=max(200, event.width - 10))
        main.bind("<Configure>", _update_feedback_wrap)

        # ── ボタン行 ──
        btn_row = tk.Frame(main, bg=COLORS["bg"])
        btn_row.pack(fill=tk.X)

        self.btn_answer = tk.Button(
            btn_row, text="✅  回答する",
            command=self.check_answer,
            bg=COLORS["primary"], fg="white",
            font=("TakaoPGothic", 11, "bold"),
            relief=tk.FLAT, padx=18, pady=8,
            cursor="hand2", state=tk.DISABLED,
        )
        self.btn_answer.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_next = tk.Button(
            btn_row, text="▶  次の問題",
            command=self.load_question,
            bg=COLORS["surface"], fg=COLORS["text"],
            font=("TakaoPGothic", 11),
            relief=tk.FLAT, padx=18, pady=8, cursor="hand2",
        )
        self.btn_next.pack(side=tk.LEFT, padx=(0, 8))

        self.btn_copy_ai = tk.Button(
            btn_row, text="📋  AIに質問 (コピー)",
            command=self.copy_for_ai,
            bg=COLORS["gold"], fg="#1E2030",
            font=("TakaoPGothic", 11, "bold"),
            relief=tk.FLAT, padx=18, pady=8, cursor="hand2",
        )
        self.btn_copy_ai.pack(side=tk.LEFT)

    # ─────────────────────────────────────────
    # イベントハンドラ
    # ─────────────────────────────────────────
    def _on_option_select(self):
        if not self.answered:
            self.btn_answer.config(state=tk.NORMAL)

    def _on_filter_change(self, _event=None):
        if self.review_mode.get():
            self._toggle_review(force_off=True)
        self.load_question()

    def _toggle_review(self, force_off: bool = False):
        if force_off:
            self.review_mode.set(False)
        else:
            self.review_mode.set(not self.review_mode.get())

        if self.review_mode.get():
            count = get_review_count()
            if count == 0:
                messagebox.showinfo("復習モード", "復習対象の問題がありません。\n問題を解いてから試してください。")
                self.review_mode.set(False)
                return
            self.btn_review.config(bg=COLORS["review"], fg="white", text="🔁 復習中")
            self.lbl_mode_badge.config(text=" 復習モード ")
            self.lbl_mode_badge.pack(side=tk.LEFT, before=self.lbl_year_badge, padx=(0, 6))
            self.load_question()
        else:
            self.btn_review.config(bg=COLORS["surface"], fg=COLORS["subtext"], text="🔁 復習モード")
            self.lbl_mode_badge.pack_forget()
            self.load_question()

    def _open_truefalse(self):
        TrueFalseWindow(self)

    def _update_accuracy_label(self):
        total, correct = get_accuracy_stats()
        if total == 0:
            self.lbl_accuracy.config(text="正答率: ―")
        else:
            pct = correct / total * 100
            self.lbl_accuracy.config(text=f"正答率: {pct:.1f}%  ({correct}/{total})")

    def _update_review_count(self):
        count = get_review_count()
        self.lbl_review_count.config(text=f"（要復習: {count}問）")

    def load_question(self):
        self.answered = False
        self.selected_answer.set(-1)
        self.btn_answer.config(state=tk.DISABLED)
        self.lbl_feedback.config(text="", bg=COLORS["bg"])

        cat  = self.selected_category.get()
        year = self.selected_year.get()

        if self.review_mode.get():
            q = get_review_question(cat, year)
            if q is None:
                messagebox.showinfo("復習モード", "条件に合う復習問題がありません。")
                self.review_mode.set(False)
                self.btn_review.config(bg=COLORS["surface"], fg=COLORS["subtext"], text="🔁 復習モード")
                self.lbl_mode_badge.pack_forget()
                q = get_random_question(cat, year)
        else:
            q = get_random_question(cat, year)

        if q is None:
            messagebox.showerror("エラー", f"「{cat}／{year}」の問題が見つかりません。")
            return

        self.current_question = q
        self.lbl_year_badge.config(text=f" {q['year']}年度 ")
        self.lbl_category.config(text=f" {q['category']} ")
        self.lbl_question.config(text=q["question_text"])

        options = q["options"]
        labels = ["①", "②", "③", "④"]
        for i, rb in enumerate(self.radio_buttons):
            text = options[i] if i < len(options) else ""
            rb.config(
                text=f"  {labels[i]}  {text}",
                fg=COLORS["text"], bg=COLORS["surface"], state=tk.NORMAL,
            )
            self.option_frames[i].config(bg=COLORS["surface"])

        total_q = get_question_count(cat, year)
        self.lbl_count.config(text=f"問題数: {total_q} 件　")
        self._update_accuracy_label()
        self._update_review_count()

    def check_answer(self):
        if self.current_question is None or self.answered:
            return

        chosen   = self.selected_answer.get()
        correct_0 = self.current_question["correct_answer"] - 1
        explanation = self.current_question.get("explanation", "")

        self.answered = True
        self.btn_answer.config(state=tk.DISABLED)

        labels = ["①", "②", "③", "④"]
        is_correct = (chosen == correct_0)

        log_answer(self.current_question["id"], is_correct)

        if is_correct:
            self.lbl_feedback.config(
                text=f"⭕  正解！ 正答は {labels[correct_0]} です。\n{explanation}",
                fg=COLORS["success"], bg=COLORS["bg"],
            )
            self.option_frames[correct_0].config(bg="#1B4332")
            self.radio_buttons[correct_0].config(bg="#1B4332", fg="#81C784")
        else:
            self.lbl_feedback.config(
                text=f"❌  不正解。正答は {labels[correct_0]} です。\n{explanation}",
                fg=COLORS["error"], bg=COLORS["bg"],
            )
            self.option_frames[chosen].config(bg="#3B1A1A")
            self.radio_buttons[chosen].config(bg="#3B1A1A", fg="#EF9A9A")
            self.option_frames[correct_0].config(bg="#1B4332")
            self.radio_buttons[correct_0].config(bg="#1B4332", fg="#81C784")

        for rb in self.radio_buttons:
            rb.config(state=tk.DISABLED)

        self._update_accuracy_label()
        self._update_review_count()

    def copy_for_ai(self):
        if self.current_question is None:
            return
        q = self.current_question
        labels = ["①", "②", "③", "④"]
        options = q["options"]
        option_lines = "\n".join(f"  {labels[i]} {options[i]}" for i in range(len(options)))

        correct_0    = q["correct_answer"] - 1
        correct_label = labels[correct_0]
        explanation  = q.get("explanation") or "（解説なし）"

        chosen_raw   = self.selected_answer.get()
        chosen_label = labels[chosen_raw] if 0 <= chosen_raw <= 3 else "未選択"

        prompt = (
            "【宅建試験の解説をお願いします】\n"
            "以下の問題で間違えてしまいました。\n"
            f"特に、私は「選択肢{chosen_label}」を選んでしまいましたが、なぜこれが間違いなのか、"
            f"そしてなぜ正解が「選択肢{correct_label}」になるのか、"
            "関連する宅建業法や民法などの知識を含めて分かりやすく解説してください。\n\n"
            f"■ 分野: {q['category']}\n"
            f"■ 年度: {q['year']}年度\n"
            f"■ 問題: {q['question_text']}\n"
            f"■ 選択肢:\n{option_lines}\n"
            f"■ あなたの回答: {chosen_label}\n"
            f"■ 正解: {correct_label}\n"
            f"■ アプリの簡易解説: {explanation}"
        )
        self.clipboard_clear()
        self.clipboard_append(prompt)

        self.btn_copy_ai.config(text="✅  コピーしました!", bg=COLORS["success"], fg="white")
        self.after(2000, lambda: self.btn_copy_ai.config(
            text="📋  AIに質問 (コピー)", bg=COLORS["gold"], fg="#1E2030"
        ))


# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = TakkenApp()
    app.mainloop()
