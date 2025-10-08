import sqlite3

conn = sqlite3.connect('shop.db')  # Connects to your existing database
cur = conn.cursor()

# Create the users table
cur.execute('''CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
)''')

conn.commit()
conn.close()
print("Users table created successfully!")
