import os
import sqlite3


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(f"PRAGMA table_info({table})")
    return any(row[1] == column for row in cursor.fetchall())


def add_column(cursor, table: str, column_definition: str) -> None:
    column_name = column_definition.split()[0]
    if not column_exists(cursor, table, column_name):
        cursor.execute(f"ALTER TABLE {table} ADD COLUMN {column_definition}")
        print(f"+ {table}.{column_name}")


def main() -> None:
    db_path = os.getenv("SQLITE_PATH", "instance/dev.sqlite3")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    sale_columns = [
        "subtotal NUMERIC",
        "tax_total NUMERIC",
        "roundoff NUMERIC",
        "cgst NUMERIC",
        "sgst NUMERIC",
        "igst NUMERIC",
        "seller_gstin TEXT",
        "buyer_gstin TEXT",
        "seller_state TEXT",
        "buyer_state TEXT",
        "place_of_supply TEXT",
        "notes TEXT",
    ]
    for definition in sale_columns:
        add_column(cur, "sales", definition)

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sale_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sale_id INTEGER REFERENCES sales(id),
            description TEXT,
            hsn_sac TEXT,
            qty NUMERIC,
            rate NUMERIC,
            gst_rate NUMERIC,
            tax_rate NUMERIC,
            line_total NUMERIC
        )
        """
    )

    sale_item_columns = [
        "hsn_sac TEXT",
        "gst_rate NUMERIC",
        "tax_rate NUMERIC",
        "line_total NUMERIC",
    ]
    for definition in sale_item_columns:
        add_column(cur, "sale_items", definition)

    add_column(cur, "customers", "state TEXT")

    conn.commit()
    conn.close()
    print("✅ SQLite GST columns ready")


if __name__ == "__main__":
    main()
