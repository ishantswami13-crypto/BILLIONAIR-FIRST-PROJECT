from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_columns(engine: Engine, table: str, columns: Iterable[str] | dict[str, str]) -> None:
    """
    Safely add missing columns. SQLite cannot ALTER with non-constant defaults
    like CURRENT_TIMESTAMP, so we:
      - add the column without default
      - backfill existing rows
      - create an insert trigger to simulate the default
    """
    insp = inspect(engine)
    if table not in insp.get_table_names():
        return

    if isinstance(columns, dict):
        ddl_iter: Iterable[str] = columns.values()
    elif isinstance(columns, str):
        ddl_iter = [columns]
    else:
        ddl_iter = columns

    ddl_list = [ddl.strip() for ddl in ddl_iter if ddl and ddl.strip()]
    if not ddl_list:
        return

    is_sqlite = engine.url.get_backend_name() == "sqlite"

    with engine.begin() as conn:
        existing = {row[1] for row in conn.execute(text(f"PRAGMA table_info({table})"))}

        for ddl in ddl_list:
            colname = ddl.split()[0]
            if colname in existing:
                continue

            ddl_sql = ddl
            needs_now_trigger = False

            if is_sqlite and "DEFAULT" in ddl.upper():
                up = ddl.upper()
                if "DEFAULT CURRENT_TIMESTAMP" in up or "DEFAULT (CURRENT_TIMESTAMP)" in up:
                    parts = ddl.split()
                    if len(parts) >= 2:
                        ddl_sql = " ".join(parts[:2])
                    needs_now_trigger = True

            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl_sql}"))
            existing.add(colname)

            if needs_now_trigger:
                conn.execute(text(f"UPDATE {table} SET {colname}=datetime('now') WHERE {colname} IS NULL"))
                conn.execute(text(f"""
                CREATE TRIGGER IF NOT EXISTS {table}_{colname}_autofill
                AFTER INSERT ON {table}
                FOR EACH ROW
                WHEN NEW.{colname} IS NULL
                BEGIN
                  UPDATE {table} SET {colname}=datetime('now') WHERE rowid = NEW.rowid;
                END;
                """))
