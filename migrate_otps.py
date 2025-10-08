import sqlite3

DB = "shop.db"

conn = sqlite3.connect(DB)
cur = conn.cursor()

# add columns to users if missing
def column_exists(table, column):
    cur.execute(f"PRAGMA table_info({table})")
    return any(r[1] == column for r in cur.fetchall())

if not column_exists("users", "email"):
    cur.execute("ALTER TABLE users ADD COLUMN email TEXT")
if not column_exists("users", "phone"):
    cur.execute("ALTER TABLE users ADD COLUMN phone TEXT")
if not column_exists("users", "email_verified"):
    cur.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER DEFAULT 0")

# create otps table to store temporary OTPs
cur.execute("""
CREATE TABLE IF NOT EXISTS otps(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT,
    email TEXT,
    otp TEXT,
    created_at TEXT,
    expires_at TEXT
)
""")

conn.commit()
conn.close()
print("Migration complete.")
