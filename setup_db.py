import sqlite3

conn = sqlite3.connect('shop.db')
cur = conn.cursor()

# Users table
cur.execute('''
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT
)
''')

# Items table
cur.execute('''
CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    price REAL,
    current_stock INTEGER
)
''')

# Sales table
cur.execute('''
CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    item TEXT,
    quantity INTEGER,
    total REAL
)
''')

# Add a test user and some items
cur.execute("INSERT OR IGNORE INTO users (username, password) VALUES (?, ?)", ("admin", "1234"))
cur.execute("INSERT OR IGNORE INTO items (name, price, current_stock) VALUES (?, ?, ?)", ("Pen", 10, 100))
cur.execute("INSERT OR IGNORE INTO items (name, price, current_stock) VALUES (?, ?, ?)", ("Notebook", 50, 50))

conn.commit()
conn.close()
