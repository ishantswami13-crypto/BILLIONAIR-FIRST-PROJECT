from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def ensure_columns(engine: Engine, table: str, definitions: dict[str, str]) -> None:
    """Ensure the given columns exist on the table, adding them if missing.

    Only simple `ALTER TABLE ADD COLUMN` statements are supported to keep SQLite compatibility.
    """

    insp = inspect(engine)
    if table not in insp.get_table_names():
        return

    existing = {col["name"] for col in insp.get_columns(table)}
    pending = {name: ddl for name, ddl in definitions.items() if name not in existing}
    if not pending:
        return

    with engine.begin() as conn:
        for column, ddl in pending.items():
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {ddl}"))
