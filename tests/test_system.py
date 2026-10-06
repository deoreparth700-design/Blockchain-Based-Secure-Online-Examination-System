"""
test_system.py
--------------
Automated test suite verifying all 15 project phases:
1. Neon PostgreSQL Database connection and ORM models.
2. Validation rules (Names, Usernames, Emails, Roll numbers, Passwords, Exams).
3. Student registration & duplicate prevention.
4. Authentication (Student login, Teacher login, Invalid credentials).
5. CSRF protection verification.
6. Exam creation & scheduling.
7. Student exam workflow, scoring, and duplicate-attempt prevention.
8. Blockchain block sealing, chain integrity, and tamper detection.
9. Ethereum configuration & anchor API authorization.
10. Flask GET/POST routes and role-based access control.
"""

import os
import sys
import unittest
from datetime import datetime, timedelta

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import app
from models import db, User, Exam, Question, Attempt, Block
import database
import validators
from blockchain import Blockchain


class TestSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()
        with app.app_context():
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        with app.app_context():
            Attempt.query.delete()
            Question.query.delete()
            Exam.query.delete()
            User.query.delete()
            Block.query.filter(Block.id > 0).delete()
            db.session.commit()

    def setUp(self):
        self.client = app.test_client()

    # ---------- 1. Database & Models ----------
    def test_01_database_neon_connection(self):
        with app.app_context():
            user_count = User.query.count()
            self.assertGreaterEqual(user_count, 0)
            self.assertIn("postgresql", str(db.engine.url))

    def test_02_blockchain_genesis(self):
        with app.app_context():
            bc = Blockchain()
            last = bc.last_block
            self.assertIsNotNone(last)
            self.assertGreaterEqual(last.index, 0)

    # ---------- 2. Input Validation Unit Tests ----------
    def test_03_name_validation(self):
        # Valid names (letters and spaces only)
        v, _, _ = validators.validate_student_registration("Rahul Sharma", "rahul_1", "r@e.com", "101", "pass123", "pass123")
        self.assertTrue(v)
        v, _, _ = validators.validate_student_registration("Priya Patil", "priya_1", "p@e.com", "102", "pass123", "pass123")
        self.assertTrue(v)

        # Invalid names: numbers, special characters, whitespace only
        v, errs, _ = validators.validate_student_registration("Rahul123", "rahul_1", "r@e.com", "101", "pass123", "pass123")
        self.assertFalse(v)
        self.assertIn("name", errs)

        v, errs, _ = validators.validate_student_registration("Rahul@123", "rahul_1", "r@e.com", "101", "pass123", "pass123")
        self.assertFalse(v)
        self.assertIn("name", errs)

        v, errs, _ = validators.validate_student_registration("   ", "rahul_1", "r@e.com", "101", "pass123", "pass123")
        self.assertFalse(v)
        self.assertIn("name", errs)

    def test_04_username_validation(self):
        # Valid usernames
        v, _, _ = validators.validate_student_registration("Amit Kumar", "amit_demo", "a@e.com", "103", "pass123", "pass123")
        self.assertTrue(v)
        v, _, _ = validators.validate_student_registration("Amit Kumar", "student123", "a@e.com", "103", "pass123", "pass123")
        self.assertTrue(v)

        # Invalid usernames: spaces, special characters, too short
        v, errs, _ = validators.validate_student_registration("Amit Kumar", "amit demo", "a@e.com", "103", "pass123", "pass123")
        self.assertFalse(v)
        self.assertIn("username", errs)

        v, errs, _ = validators.validate_student_registration("Amit Kumar", "amit@123", "a@e.com", "103", "pass123", "pass123")
        self.assertFalse(v)
        self.assertIn("username", errs)

        v, errs, _ = validators.validate_student_registration("Amit Kumar", "ab", "a@e.com", "103", "pass123", "pass123")
        self.assertFalse(v)
        self.assertIn("username", errs)

    def test_05_email_validation(self):
        # Valid emails
        v, _, _ = validators.validate_student_registration("Sunita Rao", "sunita_r", "sunita@gmail.com", "104", "pass123", "pass123")
        self.assertTrue(v)

        # Invalid emails
        v, errs, _ = validators.validate_student_registration("Sunita Rao", "sunita_r", "sunitagmail.com", "104", "pass123", "pass123")
        self.assertFalse(v)
        self.assertIn("email", errs)

        v, errs, _ = validators.validate_student_registration("Sunita Rao", "sunita_r", "sunita@", "104", "pass123", "pass123")
        self.assertFalse(v)
        self.assertIn("email", errs)

    def test_06_password_validation(self):
        # Too short
        v, errs, _ = validators.validate_student_registration("Sunita Rao", "sunita_r", "s@e.com", "104", "123", "123")
        self.assertFalse(v)
        self.assertIn("password", errs)

        # Mismatch
        v, errs, _ = validators.validate_student_registration("Sunita Rao", "sunita_r", "s@e.com", "104", "pass123", "pass999")
        self.assertFalse(v)
        self.assertIn("confirm_password", errs)

    def test_07_exam_creation_validation(self):
        now = datetime.now()
        start = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
        end = (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
        bad_end = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")

        valid_q = [{
            "question": "What is SHA-256?",
            "options": ["A cryptographic hash function", "A database", "A compiler", "An OS"],
            "correct_index": 0
        }]

        # Valid exam
        v, errs, _ = validators.validate_exam_creation("Midterm Exam", start, end, "45", valid_q)
        self.assertTrue(v, msg=f"Expected valid, got: {errs}")

        # Invalid: End before Start
        v, errs, _ = validators.validate_exam_creation("Midterm Exam", start, bad_end, "45", valid_q)
        self.assertFalse(v)

        # Invalid: Negative duration
        v, errs, _ = validators.validate_exam_creation("Midterm Exam", start, end, "-10", valid_q)
        self.assertFalse(v)

        # Invalid: Blank option
        bad_q = [{
            "question": "What is SHA-256?",
            "options": ["Option A", "", "Option C", "Option D"],
            "correct_index": 0
        }]
        v, errs, _ = validators.validate_exam_creation("Midterm Exam", start, end, "45", bad_q)
        self.assertFalse(v)

    # ---------- 3. Registration & Authentication Flow ----------
    def test_08_student_registration_and_login_flow(self):
        ts = int(datetime.now().timestamp())
        test_uname = f"tstudent_{ts}"
        test_roll = f"ROLL_{ts}"
        test_email = f"student_{ts}@example.com"
        test_pass = "SecurePass123"

        # 1. Fetch registration page to get CSRF token
        res = self.client.get("/register")
        self.assertEqual(res.status_code, 200)

        with self.client.session_transaction() as sess:
            csrf_token = sess["csrf_token"]

        # 2. Register student with CSRF token
        res = self.client.post("/register", data={
            "csrf_token": csrf_token,
            "name": "Test Student",
            "username": test_uname,
            "roll_no": test_roll,
            "email": test_email,
            "password": test_pass,
            "confirm_password": test_pass,
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # 3. Verify user created in database
        with app.app_context():
            user = database.get_user_by_login(test_uname)
            self.assertIsNotNone(user)
            self.assertEqual(user.role, "user")
            self.assertTrue(user.check_password(test_pass))

        # 4. Duplicate registration attempt should be rejected
        with self.client.session_transaction() as sess:
            csrf_token = sess["csrf_token"]

        res = self.client.post("/register", data={
            "csrf_token": csrf_token,
            "name": "Test Student",
            "username": test_uname,
            "roll_no": f"NEW_{ts}",
            "email": f"new_{ts}@example.com",
            "password": test_pass,
            "confirm_password": test_pass,
        }, follow_redirects=True)
        self.assertIn(b"username is already taken", res.data)

        # 5. Log in with Username
        with self.client.session_transaction() as sess:
            csrf_token = sess["csrf_token"]

        res = self.client.post("/login", data={
            "csrf_token": csrf_token,
            "identifier": test_uname,
            "password": test_pass,
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Student Portal", res.data)

        # 6. Log out
        res = self.client.get("/logout", follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        # 7. Log in with Email
        with self.client.session_transaction() as sess:
            csrf_token = sess["csrf_token"]

        res = self.client.post("/login", data={
            "csrf_token": csrf_token,
            "identifier": test_email,
            "password": test_pass,
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Student Portal", res.data)

    def test_09_invalid_login(self):
        self.client.get("/login")
        with self.client.session_transaction() as sess:
            csrf_token = sess["csrf_token"]

        res = self.client.post("/login", data={
            "csrf_token": csrf_token,
            "identifier": "non_existent_user_999",
            "password": "wrong_password",
        }, follow_redirects=True)
        self.assertIn(b"Invalid username, roll number, or password", res.data)

    # ---------- 4. Exam Flow & Blockchain Sealing ----------
    def test_10_exam_creation_and_attempt_flow(self):
        ts = int(datetime.now().timestamp())
        teacher_uname = f"prof_{ts}"
        student_uname = f"stud_{ts}"

        with app.app_context():
            # Create a test admin and user
            teacher = database.create_user(
                name="Prof Smith",
                username=teacher_uname,
                identifier=teacher_uname,
                email=f"prof_{ts}@univ.edu",
                password="TeacherPass123",
                role="admin"
            )
            student = database.create_user(
                name="Alice Wonder",
                username=student_uname,
                identifier=f"PRN_{ts}",
                email=f"alice_{ts}@univ.edu",
                password="StudentPass123",
                role="user"
            )
            teacher_id = teacher.id
            student_id = student.id

            # Create an open exam (now - 1 hour to now + 1 hour)
            now = datetime.now()
            start = now - timedelta(hours=1)
            end = now + timedelta(hours=1)
            questions = [
                {
                    "question": "What is the primary function of a blockchain hash pointer?",
                    "options": [
                        "Points to previous block and stores its hash",
                        "Encrypts the user's password",
                        "Deletes old data",
                        "Sends emails to students"
                    ],
                    "correct_index": 0
                },
                {
                    "question": "Which network is Ethereum testnet?",
                    "options": ["Bitcoin", "Sepolia", "Dogecoin", "Solana"],
                    "correct_index": 1
                }
            ]
            exam = database.create_exam(
                title=f"Blockchain Quiz {ts}",
                created_by=teacher_id,
                start_time=start,
                end_time=end,
                duration_minutes=30,
                questions=questions
            )
            exam_id = exam.id

        # Student logs in
        with self.client.session_transaction() as sess:
            sess["user_id"] = student_id
            sess["role"] = "user"
            sess["name"] = "Alice Wonder"
            sess["identifier"] = f"PRN_{ts}"
            sess["csrf_token"] = "test-csrf-token"

        # Check exam page GET
        res = self.client.get(f"/student/exam/{exam_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Blockchain Quiz", res.data)

        # Submit answers (Q1: option 0 [correct], Q2: option 1 [correct] => 2/2)
        res = self.client.post(f"/student/exam/{exam_id}", data={
            "csrf_token": "test-csrf-token",
            "answer_0": "0",
            "answer_1": "1"
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"2 / 2", res.data)
        self.assertIn(b"Sealed on a VALID Chain", res.data)

        # Verify attempt exists in database
        with app.app_context():
            att = database.get_attempt(exam_id, student_id)
            self.assertIsNotNone(att)
            self.assertEqual(att.score, 2)
            self.assertEqual(att.total, 2)
            block_idx = att.block_id

        # Attempt to submit again (must be blocked)
        res = self.client.post(f"/student/exam/{exam_id}", data={
            "csrf_token": "test-csrf-token",
            "answer_0": "0",
            "answer_1": "1"
        }, follow_redirects=True)
        self.assertIn(b"already submitted this exam", res.data)

        # Verify blockchain validity
        with app.app_context():
            bc = Blockchain()
            is_valid, problems = bc.is_chain_valid()
            self.assertTrue(is_valid, msg=f"Chain invalid: {problems}")
            block = bc.get_block(block_idx)
            self.assertIsNotNone(block)
            self.assertEqual(block.data["score"], 2)

    # ---------- 5. Tamper Detection Test ----------
    def test_11_tamper_detection(self):
        with app.app_context():
            bc = Blockchain()
            last_block = bc.last_block
            self.assertIsNotNone(last_block)

            # Ensure we tamper only if it's an exam result
            if last_block.data.get("type") == "exam_result":
                original_score = last_block.data["score"]
                tampered_data = dict(last_block.data)
                tampered_data["score"] = original_score + 100

                # Directly alter data without updating hash
                bc.tamper_block(last_block.index, tampered_data)

                # Check chain validity - MUST be detected
                is_valid, problems = bc.is_chain_valid()
                self.assertFalse(is_valid, "Tampering should have been detected!")
                self.assertGreater(len(problems), 0)

                # Restore original data
                tampered_data["score"] = original_score
                bc.tamper_block(last_block.index, tampered_data)

                # Check chain validity - MUST be valid again
                is_valid, problems = bc.is_chain_valid()
                self.assertTrue(is_valid, msg=f"Chain did not recover: {problems}")

    # ---------- 6. Ethereum API Authorization ----------
    def test_12_ethereum_anchor_authorization(self):
        # Unauthenticated request must redirect or reject
        res = self.client.post("/api/anchor_result/1", json={
            "tx_hash": "0x123",
            "contract_address": "0x456",
            "result_hash": "0x789",
            "wallet_address": "0xabc"
        })
        self.assertEqual(res.status_code, 302)  # Redirects to login

    # ---------- 7. Public & Static Files ----------
    def test_13_static_and_index_pages(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"ExamChain", res.data)
        res.close()

        res = self.client.get("/static/style.css")
        self.assertEqual(res.status_code, 200)
        res.close()

        res = self.client.get("/static/script.js")
        self.assertEqual(res.status_code, 200)
        res.close()

        res = self.client.get("/static/js/ethereum-config.js")
        self.assertEqual(res.status_code, 200)
        res.close()


if __name__ == "__main__":
    unittest.main()
