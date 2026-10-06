"""
migrate_roles.py
----------------
Safe, non-destructive migration script to update user role values for V1:
- 'teacher' -> 'admin'
- 'student' -> 'user'

This does NOT drop tables or delete any user, exam, attempt, or block records.
"""

from app import app
from models import db, User

def migrate_roles():
    with app.app_context():
        teachers_updated = User.query.filter_by(role="teacher").update({"role": "admin"})
        students_updated = User.query.filter_by(role="student").update({"role": "user"})
        db.session.commit()
        print(f"Migration completed successfully.")
        print(f"Updated {teachers_updated} teacher account(s) to 'admin'.")
        print(f"Updated {students_updated} student account(s) to 'user'.")

if __name__ == "__main__":
    migrate_roles()
