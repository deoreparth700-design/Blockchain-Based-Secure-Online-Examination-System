"""
migrate_attempts_started_at.py
------------------------------
Safe, non-destructive migration script to add 'started_at' column to 'attempts' table:
- Adds 'started_at' TIMESTAMP/DATETIME NULL
- Backfills existing submitted attempts: started_at = submitted_at
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
    columns = [c["name"] for c in insp.get_columns("attempts")]

    with engine.begin() as conn:
        if "started_at" not in columns:
            print("Adding 'started_at' column to 'attempts' table...")
            col_type = "TIMESTAMP" if "postgres" in db_url else "DATETIME"
            conn.execute(text(f"ALTER TABLE attempts ADD COLUMN started_at {col_type}"))
            print("Column 'started_at' successfully added.")
        else:
            print("Column 'started_at' already exists in 'attempts' table.")

        # Backfill existing submitted attempts so started_at matches submitted_at
        conn.execute(text("UPDATE attempts SET started_at = submitted_at WHERE started_at IS NULL AND submitted_at IS NOT NULL"))
        print("Existing attempts backfilled: started_at = submitted_at.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    migrate_database(target)
