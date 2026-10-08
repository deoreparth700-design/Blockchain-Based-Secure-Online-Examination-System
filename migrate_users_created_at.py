"""
migrate_users_created_at.py
---------------------------
Safe, non-destructive migration script to add 'created_at' column to 'users' table:
- Adds 'created_at' DATETIME / TIMESTAMP NULL
- Backfills existing users: created_at = CURRENT_TIMESTAMP
- Safe to run multiple times (idempotent)
- Does NOT drop any tables or delete any users, exams, attempts, or blockchain blocks
"""

import os
import sys
from dotenv import load_dotenv
from sqlalchemy import create_engine, inspect, text

load_dotenv()


def migrate_database(db_url=None):
    if not db_url:
        db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        sqlite_path = os.path.join(base_dir, "exam_system.db")
        db_url = f"sqlite:///{sqlite_path}"
    elif db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)

    masked_url = db_url.split("@")[-1] if "@" in db_url else db_url
    print(f"Connecting to database: {masked_url}")

    engine = create_engine(db_url)
    insp = inspect(engine)
    if "users" not in insp.get_table_names():
        print("'users' table does not exist. Skipping.")
        return

    columns = [c["name"] for c in insp.get_columns("users")]

    with engine.begin() as conn:
        if "created_at" not in columns:
            print("Adding 'created_at' column to 'users' table...")
            col_type = "TIMESTAMP" if "postgres" in db_url else "DATETIME"
            conn.execute(text(f"ALTER TABLE users ADD COLUMN created_at {col_type}"))
            print("Column 'created_at' successfully added.")
        else:
            print("Column 'created_at' already exists in 'users' table.")

        conn.execute(text("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
        print("Existing users backfilled with registration timestamps.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    migrate_database(target)
