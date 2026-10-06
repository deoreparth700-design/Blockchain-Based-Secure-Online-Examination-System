"""
migrate_exams_status.py
-----------------------
Safe, non-destructive migration script to add 'status' column to 'exams' table:
- Adds 'status' VARCHAR(20) DEFAULT 'published'
- Backfills existing exams to 'published' so existing exams remain functional and intact
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
    columns = [c["name"] for c in insp.get_columns("exams")]

    with engine.begin() as conn:
        if "status" not in columns:
            print("Adding 'status' column to 'exams' table with default 'published'...")
            conn.execute(text("ALTER TABLE exams ADD COLUMN status VARCHAR(20) DEFAULT 'published'"))
            print("Column 'status' successfully added.")
        else:
            print("Column 'status' already exists in 'exams' table.")

        # Backfill existing exams to 'published' if null or empty
        res = conn.execute(text("UPDATE exams SET status = 'published' WHERE status IS NULL OR status = ''"))
        print("Existing exams successfully assigned 'published' status.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    migrate_database(target)
