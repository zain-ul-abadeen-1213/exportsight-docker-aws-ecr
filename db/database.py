"""ExportSight — database connection and safe query helpers.

All SQL in the application goes through these helpers so that:
  * every query uses parameterized statements (no string interpolation),
  * foreign-key enforcement is always on,
  * writes are transactional (commit on success, rollback on error).
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

from .schema import SCHEMA_SQL

DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "exportsight.db"


def get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Open a SQLite connection with FK enforcement and Row access.

    ``check_same_thread=False`` is required because Streamlit reuses script
    threads across sessions while ``st.cache_resource`` shares one
    connection. The app is single-user; writes are transactional.
    """
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_database(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Create all tables/indexes if they do not exist."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()


def fetch_df(conn: sqlite3.Connection, sql: str, params: Sequence = ()) -> pd.DataFrame:
    """Run a parameterized SELECT and return a DataFrame."""
    return pd.read_sql_query(sql, conn, params=list(params))


def fetch_one(conn: sqlite3.Connection, sql: str, params: Sequence = ()):
    """Return a single row (sqlite3.Row) or None."""
    cur = conn.execute(sql, list(params))
    return cur.fetchone()


def execute(conn: sqlite3.Connection, sql: str, params: Sequence = ()) -> int:
    """Run a parameterized INSERT/UPDATE/DELETE inside a transaction.

    Returns the number of affected rows. Rolls back on any error.
    """
    try:
        cur = conn.execute(sql, list(params))
        conn.commit()
        return cur.rowcount
    except Exception:
        conn.rollback()
        raise


def execute_many(conn: sqlite3.Connection, sql: str, seq_of_params: Iterable[Sequence]) -> int:
    """Run a parameterized executemany inside one transaction."""
    try:
        cur = conn.executemany(sql, [list(p) for p in seq_of_params])
        conn.commit()
        return cur.rowcount
    except Exception:
        conn.rollback()
        raise


@contextmanager
def transaction(conn: sqlite3.Connection):
    """Context manager for multi-statement transactions."""
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


# ---------------------------------------------------------------------------
# Settings helpers (exchange rates, base currency, revenue recognition rule)
# ---------------------------------------------------------------------------

def get_setting(conn: sqlite3.Connection, key: str, default: str | None = None) -> str | None:
    row = fetch_one(conn, "SELECT value FROM settings WHERE key = ?", (key,))
    return row["value"] if row else default


def set_setting(conn: sqlite3.Connection, key: str, value: str, updated_at: str) -> None:
    execute(
        conn,
        """INSERT INTO settings (key, value, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                          updated_at = excluded.updated_at""",
        (key, value, updated_at),
    )
