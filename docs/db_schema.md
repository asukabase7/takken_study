# データベース設計書

## 概要

| 項目 | 値 |
|------|-----|
| DBエンジン | SQLite 3 |
| ファイルパス | `database/takken_questions.db` |
| 文字コード | UTF-8 |
| 初期化スクリプト | `init_db.py` |

---

## テーブル: `questions`

宅建試験の過去問・練習問題を格納するメインテーブル。

### スキーマ

```sql
CREATE TABLE IF NOT EXISTS questions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    year            INTEGER NOT NULL,
    category        TEXT    NOT NULL,
    question_text   TEXT    NOT NULL,
    options         TEXT    NOT NULL,
    correct_answer  INTEGER NOT NULL,
    explanation     TEXT    DEFAULT ''
);
```

### カラム定義

| カラム名 | 型 | 制約 | 説明 |
|----------|----|------|------|
| `id` | INTEGER | PK, AUTOINCREMENT | 主キー（自動採番） |
| `year` | INTEGER | NOT NULL | 出題年（例: 2023） |
| `category` | TEXT | NOT NULL | 分野（`業法` / `制限` / `権利等`） |
| `question_text` | TEXT | NOT NULL | 問題文 |
| `options` | TEXT | NOT NULL | 選択肢（JSON配列文字列）例: `["選択肢1", "選択肢2", "選択肢3", "選択肢4"]` |
| `correct_answer` | INTEGER | NOT NULL | 正解番号（**0始まり**、例: `0` = 選択肢①） |
| `explanation` | TEXT | DEFAULT `''` | 解説文 |

### `options` フィールドのJSON形式

```json
[
  "選択肢①のテキスト",
  "選択肢②のテキスト",
  "選択肢③のテキスト",
  "選択肢④のテキスト"
]
```

> [!NOTE]
> `options` は最大4要素を想定しています。将来的に選択肢数が変動する場合も JSON 形式で柔軟に対応できます。

### `category` の値域

| 値 | 対応分野 | 主な出題範囲 |
|----|---------|------------|
| `業法` | 宅地建物取引業法 | 免許、宅建士、広告、媒介契約、重要事項説明等 |
| `制限` | 法令上の制限 | 都市計画法、建築基準法、農地法、土地区画整理法等 |
| `権利等` | 権利関係 | 民法（契約、物権、相続）、借地借家法、区分所有法等 |

---

## ER図

```
questions
─────────────────────────────────────
PK  id              INTEGER
    year            INTEGER
    category        TEXT
    question_text   TEXT
    options         TEXT (JSON)
    correct_answer  INTEGER
    explanation     TEXT
```

> [!TIP]
> 将来的に学習履歴機能を追加する場合は `study_logs` テーブルを別途作成し、`question_id` で外部キー参照することを推奨します。

---

## 初期化手順

```bash
# プロジェクトルートで実行
python init_db.py
```

実行すると `database/takken_questions.db` が生成され、5件のサンプル問題が挿入されます。

---

## 将来の拡張案

| テーブル | 用途 |
|---------|------|
| `study_logs` | 回答履歴（question_id, answered_at, is_correct） |
| `bookmarks` | ブックマーク問題管理 |
| `tags` | 問題へのタグ付け |
