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

# Use an absolute path for the database file, anchored to this file's
# own folder -- this avoids any ambiguity about "relative to what?"
# that can otherwise depend on the current working directory the app
# happens to be started from.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "exam_system.db")


def init_app(app):
    """Wire SQLAlchemy up to this Flask app. Called once from app.py."""
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    db.init_app(app)


# ---------- Users ----------
def get_user_by_identifier(identifier):
    return User.query.filter_by(identifier=identifier).first()

def get_user_by_login(login_value):
    return User.query.filter(
        (User.username == login_value) |
        (User.identifier == login_value)
    ).first()


def get_user_by_id(user_id):
    return User.query.get(user_id)


def create_user(name, identifier, password, role, username=None):
    user = User(
        name=name,
        username=username,
        identifier=identifier,
        role=role,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


# ---------- Exams ----------
def get_exam(exam_id):
    return Exam.query.get(exam_id)


def get_exams_by_teacher(teacher_id):
    return Exam.query.filter_by(created_by=teacher_id).order_by(Exam.start_time.desc()).all()


def get_all_exams():
    """Used on the student dashboard so they can see upcoming/open/closed exams."""
    return Exam.query.order_by(Exam.start_time.desc()).all()


def create_exam(title, created_by, start_time, end_time, duration_minutes, questions):
    exam = Exam(
        title=title,
        created_by=created_by,
        start_time=start_time,
        end_time=end_time,
        duration_minutes=duration_minutes,
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


# ---------- Attempts ----------
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
