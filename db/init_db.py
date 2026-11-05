"""ExportSight — database initialization script.

Creates the SQLite database (all tables + indexes) and optionally seeds it
with clearly-labeled fictional demo data for a textile exporter.

Usage:
    python -m db.init_db                 # create schema only
    python -m db.init_db --seed          # create schema + load demo data
    python -m db.init_db --seed --db /path/to/exportsight.db
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.database import DEFAULT_DB_PATH, get_connection, init_database  # noqa: E402
from db.seed import seed_demo_data  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the ExportSight database.")
    parser.add_argument("--seed", action="store_true",
                        help="Load fictional textile-exporter demo data.")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH),
                        help="Path to the SQLite database file.")
    args = parser.parse_args()

    db_path = Path(args.db)
    print(f"Initializing database at {db_path} ...")
    init_database(db_path)
    print("Schema created.")

    if args.seed:
        conn = get_connection(db_path)
        try:
            counts = seed_demo_data(conn)
        finally:
            conn.close()
        print("Fictional demo data loaded (clearly labeled as demo in the app):")
        for table, n in counts.items():
            print(f"  {table:12s}: {n} rows")


if __name__ == "__main__":
    main()
