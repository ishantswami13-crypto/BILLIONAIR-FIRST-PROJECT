import sqlite3

conn = sqlite3.connect('shop.db')
cur = conn.cursor()
cur.execute("SELECT * FROM users")
users = cur.fetchall()
conn.close()
print(users)
