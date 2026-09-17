"""
models.py
---------
The database schema, defined using SQLAlchemy (an ORM -- Object
Relational Mapper, meaning we describe tables as Python classes
instead of writing raw SQL).

This is what replaced the old data/exam.json and data/blockchain.json
files. Everything now lives in one SQLite file: exam_system.db.

Five tables:
    User      - a login account, either role="teacher" or role="student"
    Exam      - a teacher-created exam with a start/end time window
    Question  - one MCQ question belonging to an Exam
    Attempt   - one student's finished submission for an Exam
    Block     - the blockchain itself, one row per sealed Attempt
"""

from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    # For a teacher this is a chosen username. For a student this is
    # their roll number. Either way it must be unique so login can
    # find exactly one account.
    username = db.Column(db.String(80), unique=True, nullable=True)
    identifier = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # "teacher" or "student"

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)


class Exam(db.Model):
    __tablename__ = "exams"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, nullable=False, default=30)

    questions = db.relationship("Question", backref="exam", cascade="all, delete-orphan")
    attempts = db.relationship("Attempt", backref="exam", cascade="all, delete-orphan")

    def is_open(self, now=None):
        """
        True if right now falls within this exam's start/end window.
        Deliberately uses naive (timezone-less) datetimes throughout --
        for a single-server classroom deployment where the server and
        every student are in the same timezone, this is simpler and
        avoids an entire class of timezone bugs. If this ever needs to
        serve students across timezones, switch to timezone-aware
        datetimes everywhere at once.
        """
        now = now or datetime.now()
        return self.start_time <= now <= self.end_time


class Question(db.Model):
    __tablename__ = "questions"

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    question_text = db.Column(db.String(500), nullable=False)
    option_a = db.Column(db.String(300), nullable=False)
    option_b = db.Column(db.String(300), nullable=False)
    option_c = db.Column(db.String(300), nullable=False)
    option_d = db.Column(db.String(300), nullable=False)
    correct_index = db.Column(db.Integer, nullable=False)  # 0=A, 1=B, 2=C, 3=D

    @property
    def options(self):
        return [self.option_a, self.option_b, self.option_c, self.option_d]


class Attempt(db.Model):
    __tablename__ = "attempts"

    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey("exams.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    total = db.Column(db.Integer, nullable=False)
    submitted_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    block_id = db.Column(db.Integer, db.ForeignKey("blocks.id"), nullable=True)

    student = db.relationship("User")
    block = db.relationship("Block")

    # One student can only have ONE attempt per exam -- enforced by the
    # database itself, not just by hiding a button in the UI.
    __table_args__ = (db.UniqueConstraint("exam_id", "student_id", name="one_attempt_per_student"),)


class Block(db.Model):
    __tablename__ = "blocks"

    id = db.Column(db.Integer, primary_key=True)  # this IS the block index
    timestamp = db.Column(db.Float, nullable=False)
    data_json = db.Column(db.Text, nullable=False)  # canonical JSON string of the block's data
    previous_hash = db.Column(db.String(64), nullable=False)
    hash = db.Column(db.String(64), nullable=False)
