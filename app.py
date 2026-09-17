"""
app.py
------
Flask routes for the real (small-deployment) version of the system.

New compared to the demo:
    - Login required for everything except the public landing page,
      login, and registration.
    - Two roles: "teacher" (creates exams, views results) and
      "student" (takes exams).
    - Exam time windows are enforced on the SERVER (Exam.is_open()),
      not just hidden in the UI -- a student can't take an exam
      before start_time or after end_time no matter what they do in
      their browser.
    - One attempt per student per exam, enforced by a database
      uniqueness constraint (see Attempt.__table_args__ in models.py),
      not just a disabled button.

Deliberately NOT included (by design, for this scope):
    - No public "tamper" button. See demo_tamper.py for how to run
      that demonstration separately, outside the live app.
    - No anti-cheating (tab-switch detection, fullscreen lock, etc).
"""

from datetime import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, session, flash

import database
from blockchain import Blockchain

app = Flask(__name__)
app.secret_key = "change-this-secret-key-before-real-deployment"
database.init_app(app)

blockchain = Blockchain()


# ---------- auth helpers ----------
def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in first.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper


def role_required(role):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if session.get("role") != role:
                flash(f"This page is only available to {role}s.", "error")
                return redirect(url_for("index"))
            return f(*args, **kwargs)
        return wrapper
    return decorator


def current_user():
    user_id = session.get("user_id")
    return database.get_user_by_id(user_id) if user_id else None


# ---------- public ----------
@app.route("/")
def index():
    if session.get("role") == "teacher":
        return redirect(url_for("teacher_dashboard"))
    if session.get("role") == "student":
        return redirect(url_for("student_dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Student self-registration."""
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        username = request.form.get("username", "").strip()
        roll_no = request.form.get("roll_no", "").strip()
        password = request.form.get("password", "")

        if not name or not username or not roll_no or not password:
            flash("Please fill in all fields.", "error")
            return redirect(url_for("register"))

        if database.get_user_by_login(username):
            flash("That username is already taken. Please choose another.", "error")
            return redirect(url_for("register"))

        if database.get_user_by_identifier(roll_no):
            flash("That roll number is already registered.", "error")
            return redirect(url_for("register"))

        database.create_user(
            name=name,
            username=username,
            identifier=roll_no,
            password=password,
            role="student",
        )

        flash("Account created. You can now log in with your username or roll number.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        password = request.form.get("password", "")

        user = database.get_user_by_login(identifier)
        if not user or not user.check_password(password):
            flash("Invalid username/roll number or password.", "error")
            return redirect(url_for("login"))

        session["user_id"] = user.id
        session["role"] = user.role
        session["name"] = user.name
        return redirect(url_for("index"))

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))


# ---------- teacher ----------
@app.route("/teacher")
@login_required
@role_required("teacher")
def teacher_dashboard():
    exams = database.get_exams_by_teacher(session["user_id"])
    now = datetime.now()
    return render_template("teacher_dashboard.html", exams=exams, now=now)


@app.route("/teacher/create_exam", methods=["GET", "POST"])
@login_required
@role_required("teacher")
def create_exam():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        start_raw = request.form.get("start_time", "")
        end_raw = request.form.get("end_time", "")
        duration = int(request.form.get("duration", "30") or 30)

        try:
            start_time = datetime.strptime(start_raw, "%Y-%m-%dT%H:%M")
            end_time = datetime.strptime(end_raw, "%Y-%m-%dT%H:%M")
        except ValueError:
            flash("Please provide valid start and end times.", "error")
            return redirect(url_for("create_exam"))

        if end_time <= start_time:
            flash("End time must be after start time.", "error")
            return redirect(url_for("create_exam"))

        q_texts = request.form.getlist("question_text")
        questions = []
        for i, qtext in enumerate(q_texts):
            if not qtext.strip():
                continue
            options = [
                request.form.get(f"option_{i}_0", ""),
                request.form.get(f"option_{i}_1", ""),
                request.form.get(f"option_{i}_2", ""),
                request.form.get(f"option_{i}_3", ""),
            ]
            correct_index = int(request.form.get(f"correct_{i}", 0))
            questions.append({"question": qtext.strip(), "options": options, "correct_index": correct_index})

        if not title or not questions:
            flash("Please provide a title and at least one complete question.", "error")
            return redirect(url_for("create_exam"))

        database.create_exam(
            title=title,
            created_by=session["user_id"],
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration,
            questions=questions,
        )
        flash(f"Exam '{title}' created with {len(questions)} question(s).", "success")
        return redirect(url_for("teacher_dashboard"))

    return render_template("create_exam.html")


@app.route("/teacher/exam/<int:exam_id>/results")
@login_required
@role_required("teacher")
def exam_results(exam_id):
    exam = database.get_exam(exam_id)
    if not exam or exam.created_by != session["user_id"]:
        flash("Exam not found.", "error")
        return redirect(url_for("teacher_dashboard"))

    attempts = database.get_attempts_for_exam(exam_id)
    return render_template("exam_results.html", exam=exam, attempts=attempts)


# ---------- student ----------
@app.route("/student")
@login_required
@role_required("student")
def student_dashboard():
    exams = database.get_all_exams()
    now = datetime.now()
    student_id = session["user_id"]

    exam_rows = []
    for exam in exams:
        attempt = database.get_attempt(exam.id, student_id)
        if attempt:
            status = "attempted"
        elif now < exam.start_time:
            status = "upcoming"
        elif now > exam.end_time:
            status = "closed"
        else:
            status = "open"
        exam_rows.append({"exam": exam, "status": status, "attempt": attempt})

    return render_template("student_dashboard.html", exam_rows=exam_rows)


@app.route("/student/exam/<int:exam_id>", methods=["GET", "POST"])
@login_required
@role_required("student")
def take_exam(exam_id):
    exam = database.get_exam(exam_id)
    if not exam:
        flash("Exam not found.", "error")
        return redirect(url_for("student_dashboard"))

    student_id = session["user_id"]

    # Server-side enforcement -- checked again on POST, never trusting
    # that the student only reached this page through the "proper" flow.
    existing = database.get_attempt(exam_id, student_id)
    if existing:
        flash("You have already attempted this exam.", "error")
        return redirect(url_for("student_dashboard"))

    if not exam.is_open():
        flash("This exam is not currently open.", "error")
        return redirect(url_for("student_dashboard"))

    if request.method == "POST":
        # Re-check both conditions again at submit time, in case the
        # window closed or a second tab already submitted while this
        # student was answering.
        if database.get_attempt(exam_id, student_id):
            flash("You have already submitted this exam.", "error")
            return redirect(url_for("student_dashboard"))
        if not exam.is_open():
            flash("The exam window has closed.", "error")
            return redirect(url_for("student_dashboard"))

        student = current_user()
        answers = []
        score = 0
        for i, q in enumerate(exam.questions):
            selected = request.form.get(f"answer_{i}")
            selected_index = int(selected) if selected is not None else -1
            is_correct = selected_index == q.correct_index
            if is_correct:
                score += 1
            answers.append({
                "question": q.question_text,
                "selected_index": selected_index,
                "correct_index": q.correct_index,
                "is_correct": is_correct,
            })

        result_data = {
            "type": "exam_result",
            "student_name": student.name,
            "roll_no": student.identifier,
            "exam_title": exam.title,
            "answers": answers,
            "score": score,
            "total": len(exam.questions),
            "submitted_at": datetime.now().strftime("%d %b %Y, %I:%M:%S %p"),
        }
        new_block = blockchain.add_block(result_data)
        database.create_attempt(exam_id, student_id, score, len(exam.questions), new_block.index)

        return redirect(url_for("show_result", block_index=new_block.index))

    return render_template("exam.html", exam=exam)


@app.route("/result/<int:block_index>")
@login_required
def show_result(block_index):
    block = blockchain.get_block(block_index)
    if not block or "score" not in block.data:
        flash("Result not found.", "error")
        return redirect(url_for("index"))
    chain_valid, _ = blockchain.is_chain_valid()
    return render_template("result.html", block=block, chain_valid=chain_valid)


# ---------- blockchain (any logged-in user) ----------
@app.route("/blockchain")
@login_required
def view_blockchain():
    chain_valid, problems = blockchain.is_chain_valid()
    blocks = []
    for b in blockchain.all_blocks():
        blocks.append({
            "index": b.index,
            "time_str": datetime.fromtimestamp(b.timestamp).strftime("%d %b %Y, %I:%M:%S %p"),
            "data": b.data,
            "previous_hash": b.previous_hash,
            "hash": b.hash,
            "recomputed_hash": b.recompute_hash(),
            "mismatch": b.hash != b.recompute_hash(),
        })
    return render_template("blockchain.html", blocks=blocks, chain_valid=chain_valid, problems=problems)


@app.route("/verify", methods=["POST"])
@login_required
def verify():
    valid, problems = blockchain.is_chain_valid()
    return {"valid": valid, "problems": problems}


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
