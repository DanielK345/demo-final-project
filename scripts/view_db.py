import sqlite3
import os

db_path = "data/app.db"
print("=== DATABASE INFO ===")
print("File location:", os.path.abspath(db_path))

if not os.path.exists(db_path):
    print("Database file not found yet!")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall() if not row[0].startswith("sqlite_")]
    print("\nDanh sach cac bang trong CSDL:")
    for t in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {t}")
        cnt = cursor.fetchone()[0]
        print(f"- Bang {t}: {cnt} ban ghi")

    print("\nChi tiet schema cac bang:")
    for t in tables:
        cursor.execute(f"PRAGMA table_info({t});")
        cols = [col[1] for col in cursor.fetchall()]
        print(f"  + {t}: [{', '.join(cols)}]")
