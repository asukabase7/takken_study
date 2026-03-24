import sqlite3
import re
import os

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "database", "takken_questions.db")

def parse_year(year_str):
    year_str = str(year_str).strip()
    
    # Check for Reiwa (令和)
    reiwa_match = re.search(r'令和(.*?)[年|年度]', year_str)
    if reiwa_match:
        val = reiwa_match.group(1)
        if val == '元':
            return 2019
        else:
            try:
                return 2018 + int(val)
            except ValueError:
                pass

    # Check for Heisei (平成)
    heisei_match = re.search(r'平成(.*?)[年|年度]', year_str)
    if heisei_match:
        val = heisei_match.group(1)
        if val == '元':
            return 1989
        else:
            try:
                return 1988 + int(val)
            except ValueError:
                pass
                
    # Check for Gregorian (e.g. 2023)
    gregorian_match = re.search(r'(\d{4})', year_str)
    if gregorian_match:
        return int(gregorian_match.group(1))

    return None

def main():
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            
            # Fetch all rows
            cursor.execute("SELECT id, year FROM questions")
            rows = cursor.fetchall()
            
            updates = []
            for row in rows:
                q_id, original_year = row
                cleansed_year = parse_year(original_year)
                
                if cleansed_year is not None:
                    updates.append((cleansed_year, q_id))
                else:
                    print(f"Warning: Could not parse year '{original_year}' for question ID {q_id}")
            
            if updates:
                # Update rows
                cursor.executemany("UPDATE questions SET year = ? WHERE id = ?", updates)
                conn.commit()
                print(f"Successfully updated {len(updates)} records.")
            
            # Verify update
            cursor.execute("SELECT DISTINCT year FROM questions ORDER BY year DESC")
            distinct_years = cursor.fetchall()
            print("\nDistinct years after cleansing:")
            for year in distinct_years:
                print(year[0])

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")

if __name__ == "__main__":
    main()
