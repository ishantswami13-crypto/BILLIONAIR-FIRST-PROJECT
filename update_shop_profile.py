import sqlite3

DB = "shop.db"
conn = sqlite3.connect(DB)
cur = conn.cursor()

cur.execute('''CREATE TABLE IF NOT EXISTS shop_profile (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    address TEXT,
    phone TEXT,
    gst TEXT
)''')

# Insert a default shop profile if none exists
cur.execute("SELECT COUNT(*) FROM shop_profile")
if cur.fetchone()[0] == 0:
    cur.execute("INSERT INTO shop_profile (name, address, phone, gst) VALUES (?, ?, ?, ?)",
                ("My Shop", "123 Market Road, City", "9876543210", "GST1234567"))

conn.commit()
conn.close()
print("Shop profile table created ✅")
