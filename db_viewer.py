import sqlite3
from tabulate import tabulate  # Pretty table output

DB = "shop.db"

def show_table(name, headers):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(f"SELECT * FROM {name}")
    rows = cur.fetchall()
    conn.close()

    if rows:
        print(f"\n📌 {name.upper()} TABLE")
        print(tabulate(rows, headers=headers, tablefmt="pretty"))
    else:
        print(f"\n📌 {name.upper()} TABLE is empty")

if __name__ == "__main__":
    show_table("users", ["ID", "Username", "Password"])
    show_table("items", ["ID", "Name", "Price", "Stock"])
    show_table("sales", ["ID", "Date", "Item", "Quantity", "Total"])
