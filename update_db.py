import sqlite3

DB = "shop.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute('''CREATE TABLE IF NOT EXISTS credits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_name TEXT,
    item TEXT,
    quantity INTEGER,
    total REAL,
    status TEXT DEFAULT 'unpaid',
    date TEXT
)''')

conn.commit()
conn.close()
print("Credits table created ✅")
