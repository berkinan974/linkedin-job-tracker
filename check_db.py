import sqlite3
conn = sqlite3.connect('data/db/jobs.db')
rows = conn.execute(
    "SELECT id, title, company, match_score, status FROM jobs ORDER BY match_score DESC"
).fetchall()
print(f"Toplam ilan: {len(rows)}\n")
for r in rows:
    print(r)
