import sqlite3

conn = sqlite3.connect('shop.db')
cur = conn.cursor()

# Create items table
cur.execute('''CREATE TABLE IF NOT EXISTS items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE,
    price REAL,
    current_stock INTEGER
)''')

# Create sales table
cur.execute('''CREATE TABLE IF NOT EXISTS sales (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    item TEXT,
    quantity INTEGER,
    total REAL
)''')

# Add sample items
cur.execute("INSERT OR IGNORE INTO items (name, price, current_stock) VALUES ('Tea', 20, 100)")
cur.execute("INSERT OR IGNORE INTO items (name, price, current_stock) VALUES ('Coffee', 50, 50)")
conn.commit()
conn.close()
print("Database initialized!")
