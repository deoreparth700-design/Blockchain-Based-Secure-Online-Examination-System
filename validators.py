"""
validators.py
-------------
Strict frontend- and backend-aligned validation rules for:
- Student Registration (Name, Username, Email, Roll No, Password, Confirm Password)
- Login (Identifier, Password)
- Exam Creation (Title, Time Window, Duration, Questions, Options, Correct Answer)
"""

import re
from datetime import datetime

# Regex patterns
RE_NAME = re.compile(r"^[A-Za-z]+(?: [A-Za-z]+)*$")
RE_USERNAME = re.compile(r"^[a-zA-Z0-9_]{3,30}$")
RE_EMAIL = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")
RE_ROLL_NO = re.compile(r"^[A-Za-z0-9/_-]{2,40}$")


def validate_student_registration(name, username, email, roll_no, password, confirm_password):
    """
    Validates all student registration fields.
    Returns: (is_valid, errors_dict, cleaned_data)
    """
    errors = {}
    cleaned = {}

    # 1. Name validation: letters and spaces only, no numbers, no special characters
    name_clean = (name or "").strip()
    if not name_clean:
        errors["name"] = "Full name is required."
    elif len(name_clean) < 2 or len(name_clean) > 100:
        errors["name"] = "Name must be between 2 and 100 characters."
    elif not RE_NAME.match(name_clean):
        if any(char.isdigit() for char in name_clean):
            errors["name"] = "Name must contain letters and spaces only (no numbers allowed)."
        else:
            errors["name"] = "Name must contain letters and spaces only (no special characters)."
    else:
        cleaned["name"] = name_clean

    # 2. Username validation: letters, numbers, underscore, 3-30 chars, no spaces
    user_clean = (username or "").strip()
    if not user_clean:
        errors["username"] = "Username is required."
    elif " " in user_clean:
        errors["username"] = "Username cannot contain spaces."
    elif len(user_clean) < 3 or len(user_clean) > 30:
        errors["username"] = "Username must be between 3 and 30 characters."
    elif not RE_USERNAME.match(user_clean):
        errors["username"] = "Username can only contain letters, numbers, and underscores."
    else:
        cleaned["username"] = user_clean

    # 3. Email validation
    email_clean = (email or "").strip().lower()
    if not email_clean:
        errors["email"] = "Email address is required."
    elif len(email_clean) > 120:
        errors["email"] = "Email address cannot exceed 120 characters."
    elif not RE_EMAIL.match(email_clean):
        errors["email"] = "Please enter a valid email address (e.g. student@example.com)."
    else:
        cleaned["email"] = email_clean

    # 4. Roll No / Identifier validation
    roll_clean = (roll_no or "").strip()
    if not roll_clean:
        errors["roll_no"] = "Roll number / PRN is required."
    elif len(roll_clean) < 2 or len(roll_clean) > 40:
        errors["roll_no"] = "Roll number must be between 2 and 40 characters."
    elif not RE_ROLL_NO.match(roll_clean):
        errors["roll_no"] = "Roll number can only contain letters, numbers, hyphens, and slashes."
    else:
        cleaned["roll_no"] = roll_clean

    # 5. Password validation
    if not password:
        errors["password"] = "Password is required."
    elif len(password) < 6:
        errors["password"] = "Password must be at least 6 characters long."
    elif len(password) > 128:
        errors["password"] = "Password cannot exceed 128 characters."

    # 6. Confirm Password validation
    if not confirm_password:
        errors["confirm_password"] = "Please confirm your password."
    elif password != confirm_password:
        errors["confirm_password"] = "Passwords do not match."

    is_valid = len(errors) == 0
    return is_valid, errors, cleaned


def validate_login_input(identifier, password):
    """
    Validates login input parameters.
    Returns: (is_valid, error_message, cleaned_identifier)
    """
    ident_clean = (identifier or "").strip()
    if not ident_clean:
        return False, "Please enter your username, roll number, or email.", ""
    if not password:
        return False, "Please enter your password.", ident_clean
    return True, None, ident_clean


def validate_exam_creation(title, start_raw, end_raw, duration_raw, questions_raw):
    """
    Validates exam creation input.
    Returns: (is_valid, errors_list, cleaned_data)
    """
    errors = []
    cleaned = {}

    # Title
    title_clean = (title or "").strip()
    if not title_clean:
        errors.append("Exam title is required.")
    elif len(title_clean) < 3 or len(title_clean) > 200:
        errors.append("Exam title must be between 3 and 200 characters.")
    else:
        cleaned["title"] = title_clean

    # Start and End Times
    try:
        start_time = datetime.strptime(start_raw, "%Y-%m-%dT%H:%M")
        cleaned["start_time"] = start_time
    except (ValueError, TypeError):
        errors.append("Please provide a valid start date and time.")

    try:
        end_time = datetime.strptime(end_raw, "%Y-%m-%dT%H:%M")
        cleaned["end_time"] = end_time
    except (ValueError, TypeError):
        errors.append("Please provide a valid end date and time.")

    if "start_time" in cleaned and "end_time" in cleaned:
        if cleaned["end_time"] <= cleaned["start_time"]:
            errors.append("End time must be strictly after start time.")

    # Duration
    try:
        duration = int(duration_raw)
        if duration <= 0:
            errors.append("Exam duration must be greater than 0 minutes.")
        elif duration > 1440:
            errors.append("Exam duration cannot exceed 24 hours (1440 minutes).")
        else:
            cleaned["duration"] = duration
    except (ValueError, TypeError):
        errors.append("Exam duration must be a valid positive integer.")

    # Questions
    if not questions_raw or len(questions_raw) == 0:
        errors.append("The exam must contain at least one question.")
    else:
        cleaned_questions = []
        for idx, q in enumerate(questions_raw):
            q_num = idx + 1
            q_text = (q.get("question") or "").strip()
            if not q_text:
                errors.append(f"Question #{q_num} text cannot be empty.")
                continue
            if len(q_text) > 500:
                errors.append(f"Question #{q_num} text is too long (max 500 characters).")
                continue

            raw_options = q.get("options") or []
            if len(raw_options) != 4:
                errors.append(f"Question #{q_num} must have exactly 4 options.")
                continue

            cleaned_opts = []
            has_blank_opt = False
            for opt_idx, opt in enumerate(raw_options):
                opt_str = (opt or "").strip()
                if not opt_str:
                    has_blank_opt = True
                    break
                if len(opt_str) > 300:
                    errors.append(f"Question #{q_num}, Option {chr(65 + opt_idx)} cannot exceed 300 characters.")
                    break
                cleaned_opts.append(opt_str)

            if has_blank_opt:
                errors.append(f"Question #{q_num} has empty option fields. All 4 options are required.")
                continue

            correct_idx = q.get("correct_index")
            try:
                correct_idx = int(correct_idx)
                if correct_idx not in (0, 1, 2, 3):
                    errors.append(f"Question #{q_num} has an invalid correct option selected.")
                    continue
            except (ValueError, TypeError):
                errors.append(f"Question #{q_num} has an invalid correct option value.")
                continue

            cleaned_questions.append({
                "question": q_text,
                "options": cleaned_opts,
                "correct_index": correct_idx,
            })

        if not errors and not cleaned_questions:
            errors.append("At least one valid question is required.")
        else:
            cleaned["questions"] = cleaned_questions

    is_valid = len(errors) == 0
    return is_valid, errors, cleaned
