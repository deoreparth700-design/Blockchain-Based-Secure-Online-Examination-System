"""
scripts/reset_student_accounts.py
---------------------------------
Maintenance script to reset the examination platform before a fresh batch
of students.

Transactional workflow:
1. Identify all student users (role == 'user').
2. Identify dependent records (student attempts and result blocks).
3. Delete dependent records in correct foreign-key order:
   - attempts first (removes foreign-key references)
   - result blocks
   - student users
4. Restore/ensure admin account 'admin_demo' with role 'admin' and updated password.
5. Preserve admin/teacher accounts, exams, and questions.
6. Commit transactionally, rolling back on error.
"""

import os
import sys
import argparse
from dotenv import load_dotenv

# Ensure root directory is on sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

load_dotenv(os.path.join(BASE_DIR, ".env"))

from app import app
from models import db, User, Attempt, Block
import database


def reset_student_accounts(admin_password=None, print_summary=True):
    """
    Performs transactional reset of all student accounts and dependent records.
    Returns a dictionary of summary statistics.
    """
    with app.app_context():
        try:
            # 1. Identify all student users
            student_users = User.query.filter(User.role == "user").all()
            student_ids = [u.id for u in student_users]
            students_count = len(student_ids)

            # Preserve admin and teacher compatibility accounts
            admin_users = User.query.filter(User.role.in_(["admin", "teacher"])).all()
            admin_count = len(admin_users)

            # 2. Identify dependent attempts
            if student_ids:
                dependent_attempts = Attempt.query.filter(Attempt.student_id.in_(student_ids)).all()
            else:
                dependent_attempts = []
            attempts_count = len(dependent_attempts)

            # 3. Identify dependent integrity records (Block rows linked to these attempts)
            # Genesis block (id == 0) is strictly excluded and preserved.
            block_ids = {a.block_id for a in dependent_attempts if a.block_id is not None and a.block_id != 0}
            if block_ids:
                dependent_blocks = Block.query.filter(Block.id != 0, Block.id.in_(block_ids)).all()
            else:
                dependent_blocks = []
            integrity_count = len(dependent_blocks)

            # 4. Print summary before committing as required
            if print_summary:
                print(f"Students found: {students_count}")
                print(f"Dependent attempts/results found: {attempts_count}")
                print(f"Dependent integrity records found: {integrity_count}")
                print(f"Admin accounts preserved: {admin_count}")

            # 5. Delete dependent records in correct foreign-key order
            # First: student attempts (clearing references to blocks, exams, and users)
            for attempt in dependent_attempts:
                db.session.delete(attempt)
            db.session.flush()

            # Second: dependent integrity blocks
            for block in dependent_blocks:
                db.session.delete(block)
            db.session.flush()

            # Third: student user accounts
            for student in student_users:
                db.session.delete(student)
            db.session.flush()

            # 6. Restore/ensure admin account
            admin_demo = database.get_user_by_username("admin_demo") or database.get_user_by_identifier("admin_demo")
            if admin_demo:
                if admin_password:
                    admin_demo.set_password(admin_password)
                admin_demo.role = "admin"
                if not admin_demo.username:
                    admin_demo.username = "admin_demo"
            else:
                if admin_password:
                    admin_demo = database.create_user(
                        name="Prof. Amit Kulkarni",
                        identifier="admin_demo",
                        username="admin_demo",
                        email="admin_demo@demo.edu",
                        password=admin_password,
                        role="admin",
                    )

            # 7. Commit transaction
            db.session.commit()

            return {
                "students_deleted": students_count,
                "attempts_deleted": attempts_count,
                "blocks_deleted": integrity_count,
                "admins_preserved": admin_count,
            }

        except Exception as e:
            db.session.rollback()
            if print_summary:
                print(f"Error encountered during reset: {e}", file=sys.stderr)
            raise


def main():
    parser = argparse.ArgumentParser(description="Reset student accounts and dependent records.")
    parser.add_argument(
        "--admin-password",
        dest="admin_password",
        help="Password for admin_demo account. Defaults to ADMIN_PASSWORD env var.",
    )
    args = parser.parse_args()

    admin_password = args.admin_password or os.environ.get("ADMIN_PASSWORD")
    if not admin_password:
        if sys.stdin.isatty():
            import getpass
            admin_password = getpass.getpass("Enter password for admin_demo: ")
        else:
            raise ValueError("Admin password required via --admin-password or ADMIN_PASSWORD env var.")

    print("--- Starting Examination Platform Reset ---")
    active_db = app.config.get("SQLALCHEMY_DATABASE_URI", "unknown")
    # Mask credentials in active_db output if present
    db_display = active_db.split("@")[-1] if "@" in active_db else active_db
    print(f"Active Database Target: ...@{db_display}")

    stats = reset_student_accounts(admin_password=admin_password, print_summary=True)
    print("--- Platform Reset Successfully Completed ---")


if __name__ == "__main__":
    main()
