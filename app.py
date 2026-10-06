"""
app.py
------
Flask application for the Blockchain-Based Secure Online Examination System.

Features:
- Dual-role authentication: Admin and User.
- Strict server-side and client-side form validation.
- Server-enforced exam time windows (start_time to end_time).
- Database-enforced single attempt per student per exam.
- SHA-256 private blockchain for tamper-evident result sealing.
- Ethereum Sepolia smart contract anchoring via MetaMask & ethers.js.
- CSRF protection and secure session management.
- Zero-configuration Vercel deployment compatibility.
- Neon PostgreSQL cloud database with local SQLite fallback.
"""

import os
import secrets
from datetime import datetime, timedelta
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from sqlalchemy.exc import IntegrityError

import database
import validators
from blockchain import Blockchain
from models import format_duration

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)

# Secret key from environment with fallback for local dev
app.secret_key = os.environ.get("SECRET_KEY", "dev-fallback-not-for-production")

# Security headers and cookie configurations
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

database.init_app(app)
blockchain = Blockchain()


# ---------- CSRF Protection ----------
@app.before_request
def handle_csrf():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_hex(16)

    if request.method == "POST":
        # Exempt JSON API endpoints and public verify check
        if request.path.startswith("/api/") or request.path == "/verify":
            return
        token = request.form.get("csrf_token")
        if not token or token != session.get("csrf_token"):
            flash("Session expired or invalid security token. Please try again.", "error")
            return redirect(request.referrer or url_for("index"))


@app.context_processor
def inject_csrf():
    return {"csrf_token": session.get("csrf_token", "")}


# ---------- Auth Helpers ----------
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


# ---------- Public Routes ----------
@app.route("/")
def index():
    if session.get("role") == "admin":
        return redirect(url_for("admin_dashboard"))
    if session.get("role") == "user":
        return redirect(url_for("student_dashboard"))
    return render_template("index.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """BE Final Year student self-registration with PRN and email."""
    if session.get("user_id"):
        return redirect(url_for("index"))

    form_data = {}
    field_errors = {}

    if request.method == "POST":
        name = request.form.get("name", "")
        prn = request.form.get("prn", "") or request.form.get("roll_no", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")

        form_data = {
            "name": name,
            "prn": prn,
            "email": email,
        }

        is_valid, errors, cleaned = validators.validate_user_registration(
            name=name,
            prn=prn,
            email=email,
            password=password,
            confirm_password=confirm_password,
        )

        if not is_valid:
            for field, err in errors.items():
                flash(err, "error")
            return render_template("register.html", form_data=form_data, field_errors=errors)

        # Database uniqueness checks (PRN and Email only)
        if database.get_user_by_identifier(cleaned["prn"]):
            flash("That PRN is already registered.", "error")
            field_errors["prn"] = "PRN is already registered."
            return render_template("register.html", form_data=form_data, field_errors=field_errors)

        if database.get_user_by_email(cleaned["email"]):
            flash("An account with that email address already exists.", "error")
            field_errors["email"] = "Email address is already registered."
            return render_template("register.html", form_data=form_data, field_errors=field_errors)

        # Create user: explicitly role='user', username=None.
        # User-supplied 'role' or 'username' in POST data are strictly ignored.
        database.create_user(
            name=cleaned["name"],
            identifier=cleaned["prn"],
            email=cleaned["email"],
            password=password,
            role="user",
            username=None,
        )

        flash("Account created successfully! You can now log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", form_data=form_data, field_errors=field_errors)


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("index"))

    form_data = {}
    if request.method == "POST":
        identifier = request.form.get("identifier", "")
        password = request.form.get("password", "")
        form_data["identifier"] = identifier

        is_valid, err_msg, clean_ident = validators.validate_login_input(identifier, password)
        if not is_valid:
            flash(err_msg, "error")
            return render_template("login.html", form_data=form_data)

        user = database.get_user_by_login(clean_ident)
        if not user or not user.check_password(password):
            # Generic error to prevent account enumeration
            flash("Invalid PRN, email, or password.", "error")
            return render_template("login.html", form_data=form_data)

        # Normalize role value: ensure it's either "admin" or "user"
        effective_role = "admin" if user.role in ("admin", "teacher") else "user"
        if user.role != effective_role:
            user.role = effective_role
            database.db.session.commit()

        # Regenerate session to protect against session fixation
        session.clear()
        session["user_id"] = user.id
        session["role"] = effective_role
        session["name"] = user.name
        session["identifier"] = user.identifier
        session["csrf_token"] = secrets.token_hex(16)
        return redirect(url_for("index"))

    return render_template("login.html", form_data=form_data)


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


# ---------- Admin Routes ----------
@app.route("/admin")
@app.route("/admin/exams")
@login_required
@role_required("admin")
def admin_dashboard():
    exams = database.get_admin_exams()
    stats = database.get_admin_dashboard_stats()
    now = datetime.now()
    return render_template("admin_dashboard.html", exams=exams, stats=stats, now=now)


@app.route("/teacher")
@login_required
@role_required("admin")
def teacher_dashboard():
    """Compatibility alias for the canonical V1 Admin dashboard."""
    return admin_dashboard()


@app.route("/admin/exams/create", methods=["GET", "POST"])
@app.route("/teacher/create_exam", methods=["GET", "POST"])
@login_required
@role_required("admin")
def create_exam():
    if request.method == "POST":
        title = request.form.get("title", "")
        start_raw = request.form.get("start_time", "")
        end_raw = request.form.get("end_time", "")
        duration_raw = request.form.get("duration", "30")

        q_texts = request.form.getlist("question_text")
        questions_raw = []
        for i, qtext in enumerate(q_texts):
            options = [
                request.form.get(f"option_{i}_0", ""),
                request.form.get(f"option_{i}_1", ""),
                request.form.get(f"option_{i}_2", ""),
                request.form.get(f"option_{i}_3", ""),
            ]
            correct_idx = request.form.get(f"correct_{i}", "0")
            questions_raw.append({
                "question": qtext,
                "options": options,
                "correct_index": correct_idx,
            })

        is_valid, errors, cleaned = validators.validate_exam_creation(
            title=title,
            start_raw=start_raw,
            end_raw=end_raw,
            duration_raw=duration_raw,
            questions_raw=questions_raw,
        )

        if not is_valid:
            for err in errors:
                flash(err, "error")
            return render_template("create_exam.html")

        # Newly created exams start as DRAFT
        exam = database.create_exam(
            title=cleaned["title"],
            created_by=session["user_id"],
            start_time=cleaned["start_time"],
            end_time=cleaned["end_time"],
            duration_minutes=cleaned["duration"],
            questions=cleaned["questions"],
            status="draft",
        )
        flash(f"Exam '{cleaned['title']}' created as Draft. Review and publish when ready.", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("create_exam.html")


@app.route("/admin/exams/<int:exam_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("admin")
def edit_exam(exam_id):
    exam = database.get_exam(exam_id)
    if not exam:
        flash("Exam not found.", "error")
        return redirect(url_for("admin_dashboard"))

    if exam.status == "closed":
        flash("Cannot edit a closed exam.", "error")
        return redirect(url_for("admin_dashboard"))

    if len(exam.attempts) > 0:
        flash("Cannot edit this exam: student submissions have already been recorded.", "error")
        return redirect(url_for("admin_dashboard"))

    if request.method == "POST":
        title = request.form.get("title", "")
        start_raw = request.form.get("start_time", "")
        end_raw = request.form.get("end_time", "")
        duration_raw = request.form.get("duration", "30")

        q_texts = request.form.getlist("question_text")
        questions_raw = []
        for i, qtext in enumerate(q_texts):
            options = [
                request.form.get(f"option_{i}_0", ""),
                request.form.get(f"option_{i}_1", ""),
                request.form.get(f"option_{i}_2", ""),
                request.form.get(f"option_{i}_3", ""),
            ]
            correct_idx = request.form.get(f"correct_{i}", "0")
            questions_raw.append({
                "question": qtext,
                "options": options,
                "correct_index": correct_idx,
            })

        is_valid, errors, cleaned = validators.validate_exam_creation(
            title=title,
            start_raw=start_raw,
            end_raw=end_raw,
            duration_raw=duration_raw,
            questions_raw=questions_raw,
        )

        if not is_valid:
            for err in errors:
                flash(err, "error")
            return render_template("edit_exam.html", exam=exam)

        updated_exam, err = database.update_exam(
            exam_id=exam.id,
            title=cleaned["title"],
            start_time=cleaned["start_time"],
            end_time=cleaned["end_time"],
            duration_minutes=cleaned["duration"],
            questions=cleaned["questions"],
        )
        if err:
            flash(err, "error")
            return render_template("edit_exam.html", exam=exam)

        flash(f"Exam '{updated_exam.title}' updated successfully.", "success")
        return redirect(url_for("admin_dashboard"))

    return render_template("edit_exam.html", exam=exam)


@app.route("/admin/exams/<int:exam_id>/publish", methods=["POST"])
@login_required
@role_required("admin")
def publish_exam(exam_id):
    exam = database.get_exam(exam_id)
    if not exam:
        flash("Exam not found.", "error")
        return redirect(url_for("admin_dashboard"))

    success, message = database.publish_exam(exam_id)
    if success:
        flash(message, "success")
    else:
        flash(message, "error")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/exams/<int:exam_id>/close", methods=["POST"])
@login_required
@role_required("admin")
def close_exam(exam_id):
    exam = database.get_exam(exam_id)
    if not exam:
        flash("Exam not found.", "error")
        return redirect(url_for("admin_dashboard"))

    success, message = database.close_exam(exam_id)
    if success:
        flash(message, "success")
    else:
        flash(message, "error")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/exams/<int:exam_id>/delete", methods=["POST"])
@login_required
@role_required("admin")
def delete_exam(exam_id):
    exam = database.get_exam(exam_id)
    if not exam:
        flash("Exam not found.", "error")
        return redirect(url_for("admin_dashboard"))

    success, message = database.delete_exam(exam_id)
    if success:
        flash(message, "success")
    else:
        flash(message, "error")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/exams/<int:exam_id>/results")
@app.route("/teacher/exam/<int:exam_id>/results")
@login_required
@role_required("admin")
def exam_results(exam_id):
    exam = database.get_exam(exam_id)
    if not exam:
        flash("Exam not found.", "error")
        return redirect(url_for("admin_dashboard"))

    attempts = database.get_attempts_for_exam(exam_id)

    total_submissions = len(attempts)
    if total_submissions > 0:
        scores = [a.score for a in attempts]
        percentages = [a.percentage for a in attempts]
        avg_score = round(sum(scores) / total_submissions, 1)
        highest_score = max(scores)
        lowest_score = min(scores)
        avg_percentage = round(sum(percentages) / total_submissions, 1)
    else:
        avg_score = 0.0
        highest_score = 0
        lowest_score = 0
        avg_percentage = 0.0

    stats = {
        "total_submissions": total_submissions,
        "avg_score": avg_score,
        "highest_score": highest_score,
        "lowest_score": lowest_score,
        "avg_percentage": avg_percentage,
    }

    return render_template("exam_results.html", exam=exam, attempts=attempts, stats=stats)


# ---------- User Routes ----------
@app.route("/student")
@login_required
@role_required("user")
def student_dashboard():
    exams = database.get_all_exams()
    now = datetime.now()
    student_id = session["user_id"]

    exam_rows = []
    for exam in exams:
        attempt = database.get_attempt(exam.id, student_id)
        if attempt and attempt.is_submitted:
            status = "attempted"
        elif attempt and attempt.is_active:
            deadline = database.get_effective_deadline(exam, attempt)
            if now > deadline:
                status = "closed"
            else:
                status = "in_progress"
        elif exam.status == "closed":
            status = "closed"
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
@role_required("user")
def take_exam(exam_id):
    exam = database.get_exam(exam_id)
    if not exam:
        flash("Exam not found.", "error")
        return redirect(url_for("student_dashboard"))

    student_id = session["user_id"]
    now = datetime.now()

    # Draft and closed exams cannot be attempted or submitted
    if exam.status == "draft":
        flash("This exam is not available.", "error")
        return redirect(url_for("student_dashboard"))

    if exam.status == "closed":
        flash("This exam has been closed.", "error")
        return redirect(url_for("student_dashboard"))

    if exam.status != "published":
        flash("This exam is not available.", "error")
        return redirect(url_for("student_dashboard"))

    # Server-side schedule window checks
    if now < exam.start_time:
        flash(f"This exam is not open yet. It will open on {exam.start_time.strftime('%d %b %Y, %I:%M %p')}.", "error")
        return redirect(url_for("student_dashboard"))

    # Look up existing attempt for this student & exam
    attempt = database.get_attempt(exam_id, student_id)

    # 1. If already submitted, prevent any further action (GET or POST)
    if attempt and attempt.is_submitted:
        flash("You have already submitted this exam.", "error")
        return redirect(url_for("student_dashboard"))

    # 2. If no attempt exists yet: verify window has not closed before creating
    if not attempt:
        if now > exam.end_time:
            flash("The exam window has closed.", "error")
            return redirect(url_for("student_dashboard"))

        attempt = database.start_attempt(exam_id, student_id, len(exam.questions))

    # Calculate authoritative server deadline and remaining seconds
    effective_deadline = database.get_effective_deadline(exam, attempt)
    remaining_seconds = database.get_remaining_seconds(exam, attempt, now)

    # Grace period in seconds to account for network transit latency on auto-submission
    GRACE_PERIOD_SECONDS = 5

    # 3. Handle POST (Submission)
    if request.method == "POST":
        is_auto_submit = (request.form.get("auto_submit") == "true")

        # Check if deadline has strictly passed (beyond grace period)
        if now > effective_deadline + timedelta(seconds=GRACE_PERIOD_SECONDS):
            if not is_auto_submit:
                # Late manual submission rejected
                database.finalize_attempt(
                    attempt,
                    score=0,
                    total_questions=len(exam.questions),
                    block_id=None,
                    submitted_at=now,
                )
                flash("The exam time limit has expired. Your submission was not accepted.", "error")
                return redirect(url_for("student_dashboard"))

        student = current_user()
        total = len(exam.questions)
        correct_count = 0
        incorrect_count = 0
        unanswered_count = 0
        answers = []

        for i, q in enumerate(exam.questions):
            selected = request.form.get(f"answer_{i}")
            try:
                selected_index = int(selected) if selected is not None else -1
            except (ValueError, TypeError):
                selected_index = -1

            if selected_index == -1:
                status = "unanswered"
                is_correct = False
                unanswered_count += 1
            elif selected_index == q.correct_index:
                status = "correct"
                is_correct = True
                correct_count += 1
            else:
                status = "incorrect"
                is_correct = False
                incorrect_count += 1

            answers.append({
                "question": q.question_text,
                "options": q.options,
                "selected_index": selected_index,
                "correct_index": q.correct_index,
                "is_correct": is_correct,
                "status": status,
            })

        score = correct_count
        percentage = round((score / total) * 100, 1) if total > 0 else 0.0
        submission_time = now if now <= effective_deadline else effective_deadline
        time_used_seconds = int((submission_time - attempt.started_at).total_seconds()) if attempt.started_at else 0
        time_used_display = format_duration(time_used_seconds)
        is_timeout = is_auto_submit or (now > effective_deadline)

        result_data = {
            "type": "exam_result",
            "student_name": student.name,
            "roll_no": student.identifier,
            "prn": student.identifier,
            "exam_id": exam.id,
            "exam_title": exam.title,
            "answers": answers,
            "score": score,
            "total": total,
            "percentage": percentage,
            "correct_count": correct_count,
            "incorrect_count": incorrect_count,
            "unanswered_count": unanswered_count,
            "started_at": attempt.started_at.strftime("%d %b %Y, %I:%M:%S %p") if attempt.started_at else None,
            "submitted_at": submission_time.strftime("%d %b %Y, %I:%M:%S %p"),
            "time_used_seconds": time_used_seconds,
            "time_used_display": time_used_display,
            "is_timeout": is_timeout,
        }

        try:
            new_block = blockchain.add_block(result_data)
            database.finalize_attempt(
                attempt,
                score=score,
                total_questions=total,
                block_id=new_block.index,
                submitted_at=submission_time,
            )
        except IntegrityError:
            database.db.session.rollback()
            flash("You have already submitted this exam.", "error")
            return redirect(url_for("student_dashboard"))

        flash("Exam submitted and sealed successfully!", "success")
        return redirect(url_for("show_result", block_index=new_block.index))

    # 4. Handle GET (Viewing / Resuming the exam)
    if remaining_seconds <= 0:
        database.finalize_attempt(
            attempt,
            score=0,
            total_questions=len(exam.questions),
            block_id=None,
            submitted_at=now,
        )
        flash("The exam time limit has expired.", "error")
        return redirect(url_for("student_dashboard"))

    return render_template(
        "exam.html",
        exam=exam,
        attempt=attempt,
        remaining_seconds=remaining_seconds,
        effective_deadline=effective_deadline.strftime("%Y-%m-%dT%H:%M:%S"),
    )


@app.route("/student/exam/<int:exam_id>/result")
@login_required
@role_required("user")
def student_exam_result(exam_id):
    student_id = session.get("user_id")
    attempt = database.get_attempt(exam_id, student_id)
    if not attempt or not attempt.is_submitted:
        flash("This exam has not been submitted yet.", "error")
        return redirect(url_for("student_dashboard"))

    if attempt.block_id is not None:
        return redirect(url_for("show_result", block_index=attempt.block_id))

    flash("No sealed result found for this exam attempt.", "error")
    return redirect(url_for("student_dashboard"))


@app.route("/result/<int:block_index>")
@login_required
def show_result(block_index):
    block = blockchain.get_block(block_index)
    if not block or "score" not in block.data:
        flash("Result not found.", "error")
        return redirect(url_for("index"))

    attempt = database.get_attempt_by_block_id(block_index)
    if not attempt:
        flash("Attempt record not found.", "error")
        return redirect(url_for("index"))

    if not attempt.is_submitted:
        flash("This exam has not been submitted yet.", "error")
        return redirect(url_for("student_dashboard") if session.get("role") == "user" else url_for("admin_dashboard"))

    # Role-based authorization:
    # Users can only view their own result.
    # Admins can only view results for exams they created.
    if session.get("role") == "user":
        if attempt.student_id != session.get("user_id"):
            flash("You do not have permission to view another student's result.", "error")
            return redirect(url_for("student_dashboard"))
    elif session.get("role") == "admin":
        exam = database.get_exam(attempt.exam_id)
        if not exam:
            flash("You do not have permission to view results for this exam.", "error")
            return redirect(url_for("admin_dashboard"))

    chain_valid, _ = blockchain.is_chain_valid()
    is_block_tampered = (block.hash != block.recompute_hash())

    # Build structured result summary with fallbacks for older blocks
    answers = block.data.get("answers", [])
    total = block.data.get("total", attempt.total)
    score = block.data.get("score", attempt.score)
    percentage = block.data.get("percentage")
    if percentage is None:
        percentage = round((score / total) * 100, 1) if total > 0 else 0.0

    correct_count = block.data.get("correct_count")
    if correct_count is None:
        correct_count = sum(1 for a in answers if a.get("is_correct"))

    unanswered_count = block.data.get("unanswered_count")
    if unanswered_count is None:
        unanswered_count = sum(1 for a in answers if a.get("selected_index", -1) == -1)

    incorrect_count = block.data.get("incorrect_count")
    if incorrect_count is None:
        incorrect_count = max(0, total - correct_count - unanswered_count)

    time_used = block.data.get("time_used_display")
    if not time_used and attempt:
        time_used = attempt.time_used_display

    result_summary = {
        "exam_title": block.data.get("exam_title", ""),
        "student_name": block.data.get("student_name", attempt.student.name if attempt and attempt.student else ""),
        "prn": block.data.get("prn", block.data.get("roll_no", attempt.student.identifier if attempt and attempt.student else "")),
        "score": score,
        "total": total,
        "percentage": percentage,
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "unanswered_count": unanswered_count,
        "started_at": block.data.get("started_at") or (attempt.started_at.strftime("%d %b %Y, %I:%M:%S %p") if attempt.started_at else "N/A"),
        "submitted_at": block.data.get("submitted_at") or (attempt.submitted_at.strftime("%d %b %Y, %I:%M:%S %p") if attempt.submitted_at else "N/A"),
        "time_used": time_used or "N/A",
        "is_timeout": block.data.get("is_timeout", False),
    }

    return render_template(
        "result.html",
        block=block,
        chain_valid=chain_valid,
        is_block_tampered=is_block_tampered,
        attempt=attempt,
        result_summary=result_summary,
    )


# ---------- Blockchain (Any Logged-in User) ----------
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
    return jsonify({"valid": valid, "problems": problems})


# ---------- Ethereum Smart Contract Anchoring ----------
@app.route("/api/anchor_result/<int:attempt_id>", methods=["POST"])
@login_required
@role_required("admin")
def anchor_result(attempt_id):
    attempt = database.get_attempt_by_id(attempt_id)
    if not attempt:
        return jsonify({"error": "Attempt not found"}), 404

    exam = database.get_exam(attempt.exam_id)
    if not exam or exam.created_by != session["user_id"]:
        return jsonify({"error": "Unauthorized: You can only anchor results for exams you created."}), 403

    data = request.get_json(silent=True) or {}
    tx_hash = data.get("tx_hash")
    contract_address = data.get("contract_address")
    result_hash = data.get("result_hash")
    wallet_address = data.get("wallet_address")

    if not tx_hash or not contract_address or not result_hash or not wallet_address:
        return jsonify({"error": "Missing required Ethereum transaction details."}), 400

    attempt.ethereum_tx_hash = tx_hash
    attempt.ethereum_contract_address = contract_address
    attempt.ethereum_result_hash = result_hash
    attempt.ethereum_wallet_address = wallet_address
    attempt.ethereum_anchored_at = datetime.now()

    database.db.session.commit()
    return jsonify({"status": "success"})


if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() in ("true", "1", "yes")
    app.run(debug=debug_mode, host="0.0.0.0", port=5000)
