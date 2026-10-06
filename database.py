"""
database.py
------------
The storage layer. This used to read/write two JSON files. It now
sets up a real SQLite database (via SQLAlchemy) and provides small
helper functions so app.py never has to write raw queries inline.

The database file itself is exam_system.db, created automatically
the first time init_db.py is run.
"""

import os
from datetime import datetime

from models import db, User, Exam, Question, Attempt, Block

# Fallback SQLite path for local development when DATABASE_URL is not set.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SQLITE_PATH = os.path.join(BASE_DIR, "exam_system.db")


def init_app(app):
    """Wire SQLAlchemy up to this Flask app. Called once from app.py."""
    database_url = os.environ.get("DATABASE_URL")

    if not database_url:
        # Fall back to local SQLite for development without a .env file
        database_url = f"sqlite:///{SQLITE_PATH}"
    else:
        database_url = database_url.strip().strip("'\"")

    # Some providers give "postgres://" which SQLAlchemy 1.4+ requires
    # as "postgresql://".
    if database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)

    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    # Serverless-friendly connection options for PostgreSQL/Neon
    if not database_url.startswith("sqlite"):
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "pool_pre_ping": True,
            "pool_recycle": 300,
        }
    db.init_app(app)


# ---------- Users ----------
def get_user_by_identifier(identifier):
    if not identifier:
        return None
    return User.query.filter_by(identifier=identifier).first()


def get_user_by_prn(prn):
    """Alias for get_user_by_identifier representing the student PRN."""
    return get_user_by_identifier(prn)


def get_user_by_username(username):
    if not username:
        return None
    return User.query.filter_by(username=username).first()


def get_user_by_email(email):
    if not email:
        return None
    return User.query.filter(User.email.ilike(email.strip())).first()


def get_user_by_login(login_value):
    if not login_value:
        return None
    val = login_value.strip()
    return User.query.filter(
        (User.username == val) |
        (User.identifier == val) |
        (User.email.ilike(val))
    ).first()


def get_user_by_id(user_id):
    return db.session.get(User, user_id)


def create_user(name, identifier, password, role, username=None, email=None):
    user = User(
        name=name,
        username=username,
        identifier=identifier,
        email=email.strip().lower() if email else None,
        role=role,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


# ---------- Exams ----------
def get_exam(exam_id):
    return db.session.get(Exam, exam_id)


def get_admin_dashboard_stats():
    """Summary metrics for the V1 Admin Dashboard."""
    total_exams = Exam.query.count()
    published_exams = Exam.query.filter_by(status="published").count()
    closed_exams = Exam.query.filter_by(status="closed").count()
    draft_exams = Exam.query.filter_by(status="draft").count()
    total_users = User.query.filter_by(role="user").count()
    total_submissions = Attempt.query.count()
    return {
        "total_exams": total_exams,
        "published_exams": published_exams,
        "closed_exams": closed_exams,
        "draft_exams": draft_exams,
        "total_users": total_users,
        "total_submissions": total_submissions,
    }


def get_admin_exams():
    """All exams managed by Admin in the V1 single-class system."""
    return Exam.query.order_by(Exam.start_time.desc()).all()


def get_exams_by_teacher(teacher_id):
    """Compatibility alias for get_admin_exams."""
    return Exam.query.order_by(Exam.start_time.desc()).all()


def get_all_exams(include_drafts=False):
    """Used on the student dashboard so they can see upcoming/open/closed exams (drafts excluded)."""
    query = Exam.query
    if not include_drafts:
        query = query.filter(Exam.status != "draft")
    return query.order_by(Exam.start_time.desc()).all()


def create_exam(title, created_by, start_time, end_time, duration_minutes, questions, status="draft"):
    exam = Exam(
        title=title,
        created_by=created_by,
        start_time=start_time,
        end_time=end_time,
        duration_minutes=duration_minutes,
        status=status,
    )
    db.session.add(exam)
    db.session.flush()  # so exam.id is available before commit

    for q in questions:
        db.session.add(Question(
            exam_id=exam.id,
            question_text=q["question"],
            option_a=q["options"][0],
            option_b=q["options"][1],
            option_c=q["options"][2],
            option_d=q["options"][3],
            correct_index=q["correct_index"],
        ))
    db.session.commit()
    return exam


def update_exam(exam_id, title, start_time, end_time, duration_minutes, questions):
    """
    Safely update an exam and its questions.
    Only permitted if zero attempts exist and exam is not closed.
    """
    exam = db.session.get(Exam, exam_id)
    if not exam:
        return None, "Exam not found."
    if exam.status == "closed":
        return None, "Cannot edit a closed exam."
    if len(exam.attempts) > 0:
        return None, "Cannot edit this exam: student submissions have already been recorded."

    exam.title = title
    exam.start_time = start_time
    exam.end_time = end_time
    exam.duration_minutes = duration_minutes

    # Replace questions cleanly
    for q in list(exam.questions):
        db.session.delete(q)
    db.session.flush()

    for q in questions:
        db.session.add(Question(
            exam_id=exam.id,
            question_text=q["question"],
            option_a=q["options"][0],
            option_b=q["options"][1],
            option_c=q["options"][2],
            option_d=q["options"][3],
            correct_index=q["correct_index"],
        ))
    db.session.commit()
    return exam, None


def publish_exam(exam_id):
    """
    Publish a draft exam: draft -> published.
    Validates title, start/end time, schedule ordering, and valid questions.
    """
    exam = db.session.get(Exam, exam_id)
    if not exam:
        return False, "Exam not found."
    if exam.status == "closed":
        return False, "Cannot publish a closed exam."
    if exam.status == "published":
        return True, "Exam is already published."

    if not exam.title or not exam.title.strip():
        return False, "Exam title is required to publish."
    if not exam.start_time or not exam.end_time:
        return False, "Exam start and end times are required to publish."
    if exam.end_time <= exam.start_time:
        return False, "Exam end time must be after start time."
    if not exam.questions or len(exam.questions) == 0:
        return False, "Exam must contain at least one question before publishing."

    for q in exam.questions:
        if not q.question_text or not q.question_text.strip():
            return False, "All questions must contain question text."
        if not q.option_a or not q.option_b or not q.option_c or not q.option_d:
            return False, "All four options are required for every question."
        if q.correct_index not in (0, 1, 2, 3):
            return False, "Each question must have a valid correct option marked."

    exam.status = "published"
    db.session.commit()
    return True, f"Exam '{exam.title}' published successfully."


def close_exam(exam_id):
    """
    Close a published exam manually: published -> closed.
    Students cannot start or submit closed exams. Attempts/results are preserved.
    """
    exam = db.session.get(Exam, exam_id)
    if not exam:
        return False, "Exam not found."
    if exam.status == "closed":
        return True, f"Exam '{exam.title}' is already closed."
    if exam.status == "draft":
        return False, "Draft exams cannot be closed directly. Publish or delete the draft instead."

    exam.status = "closed"
    db.session.commit()
    return True, f"Exam '{exam.title}' has been closed."


def delete_exam(exam_id):
    """
    Delete an exam only if zero attempts exist.
    Prevents deleting any exam whose results are sealed in the blockchain.
    """
    exam = db.session.get(Exam, exam_id)
    if not exam:
        return False, "Exam not found."
    if len(exam.attempts) > 0:
        return False, "Cannot delete exam: student results have already been recorded and cryptographically sealed into the blockchain ledger."

    db.session.delete(exam)
    db.session.commit()
    return True, f"Exam '{exam.title}' was deleted successfully."


# ---------- Attempts ----------
def get_attempt_by_id(attempt_id):
    return db.session.get(Attempt, attempt_id)


def get_attempt_by_block_id(block_id):
    return Attempt.query.filter_by(block_id=block_id).first()


def get_attempt(exam_id, student_id):
    return Attempt.query.filter_by(exam_id=exam_id, student_id=student_id).first()


def get_attempts_for_exam(exam_id):
    return Attempt.query.filter_by(exam_id=exam_id).order_by(Attempt.submitted_at.asc()).all()


def create_attempt(exam_id, student_id, score, total, block_id):
    attempt = Attempt(
        exam_id=exam_id,
        student_id=student_id,
        score=score,
        total=total,
        block_id=block_id,
        submitted_at=datetime.now(),
    )
    db.session.add(attempt)
    db.session.commit()
    return attempt
