import sqlite3

DB = "shop.db"

def column_exists(table, column):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur.fetchall()]
    conn.close()
    return column in cols

def add_column_if_missing(table, column, col_def):
    if not column_exists(table, column):
        conn = sqlite3.connect(DB)
        cur = conn.cursor()
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
        conn.commit()
        conn.close()
        print(f"✅ Added column '{column}' to table '{table}'")
    else:
        print(f"✔ Column '{column}' already exists in '{table}'")

def fix_db():
    # users.role
    add_column_if_missing("users", "role", "TEXT DEFAULT 'admin'")

    # items.barcode
    add_column_if_missing("items", "barcode", "TEXT")

    # items.gst_rate
    add_column_if_missing("items", "gst_rate", "REAL DEFAULT 0")

    print("🎉 Database check complete!")

if __name__ == "__main__":
    fix_db()
