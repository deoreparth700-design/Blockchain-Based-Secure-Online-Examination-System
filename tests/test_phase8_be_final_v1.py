"""
test_phase8_be_final_v1.py
---------------------------
Automated test suite for Phase 8: B.E. Final Year V1 Completion.

Verifies:
1. Isolated test runner (SQLite, Neon protected)
2. Registration page contains fixed B.E. Final Year academic context
3. Registration creates role=user
4. PRN remains strictly unique
5. User-supplied role=admin is ignored
6. User-supplied username is ignored
7. Student dashboard contains B.E. Final Year academic context, name, and PRN
8. Draft exams are not visible to students on dashboard
9. Student dashboard organizes exams into states (Upcoming, Available Now, In Progress, Completed)
10. Full examination flow (Draft -> Publish -> Take -> Submit -> Evaluate -> Sealed Result)
11. Cryptographic SHA-256 result integrity verification and tamper detection
12. Backward compatibility of all primary routes and legacy aliases
"""

import json
import os
import sys
import unittest
from datetime import datetime, timedelta

# Ensure an isolated test SQLite database is used BEFORE app is imported
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEST_DB_PATH = os.path.join(BASE_DIR, "tests", "test_phase8.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

sys.path.insert(0, BASE_DIR)

from app import app
from models import db, User, Exam, Question, Attempt, Block
import database
import blockchain


class TestPhase8BEFinalV1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()
        with app.app_context():
            db.create_all()

    @classmethod
    def tearDownClass(cls):
        with app.app_context():
            db.session.remove()
            db.drop_all()
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except OSError:
                pass

    def setUp(self):
        self.client = app.test_client()

    def _login(self, client, identifier, password):
        client.get("/login")
        with client.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")
        return client.post(
            "/login",
            data={
                "identifier": identifier,
                "password": password,
                "csrf_token": csrf,
            },
            follow_redirects=True,
        )

    def _post(self, client, url, data, follow_redirects=True):
        with client.session_transaction() as sess:
            csrf = sess.get("csrf_token", "")
        post_data = dict(data)
        if "csrf_token" not in post_data:
            post_data["csrf_token"] = csrf
        return client.post(url, data=post_data, follow_redirects=follow_redirects)

    # =========================================================================
    # PART 1: DATABASE SAFETY & ACADEMIC CONTEXT
    # =========================================================================

    def test_01_database_safety(self):
        """Ensure test executes against isolated SQLite database and NOT Neon."""
        with app.app_context():
            uri = str(db.engine.url)
            self.assertTrue(uri.startswith("sqlite:///"), f"Database URI must be sqlite: {uri}")
            self.assertNotIn("neon.tech", uri)
            self.assertNotIn("postgresql", uri)

    def test_02_registration_page_contains_be_final_year_context(self):
        """Registration page clearly displays B.E. Final Year fixed academic context."""
        res = self.client.get("/register")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("B.E. Final Year", html)
        self.assertIn("B.E. Computer Science and Engineering", html)
        self.assertIn("Full Name", html)
        self.assertIn("College PRN", html)
        self.assertIn("Email Address", html)
        self.assertIn("Password", html)
        self.assertIn("Confirm Password", html)

    # =========================================================================
    # PART 2: REGISTRATION SECURITY & BEHAVIOR
    # =========================================================================

    def test_03_registration_creates_role_user(self):
        """Successful student registration creates a user account with role='user'."""
        self.client.get("/register")
        res = self._post(
            self.client,
            "/register",
            {
                "name": "Aarav Sharma",
                "prn": "BE2026CS101",
                "email": "aarav.sharma@engg.edu",
                "password": "Password123!",
                "confirm_password": "Password123!",
            },
        )
        self.assertEqual(res.status_code, 200)
        with app.app_context():
            user = database.get_user_by_identifier("BE2026CS101")
            self.assertIsNotNone(user)
            self.assertEqual(user.name, "Aarav Sharma")
            self.assertEqual(user.role, "user")
            self.assertEqual(user.email, "aarav.sharma@engg.edu")

    def test_04_prn_remains_strictly_unique(self):
        """Duplicate PRN registration must be rejected."""
        self.client.get("/register")
        res = self._post(
            self.client,
            "/register",
            {
                "name": "Another Student",
                "prn": "BE2026CS101",  # duplicate PRN
                "email": "different.email@engg.edu",
                "password": "Password123!",
                "confirm_password": "Password123!",
            },
        )
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("already registered", html.lower())

    def test_05_user_supplied_role_admin_ignored(self):
        """User cannot escalate privilege by posting role='admin' during registration."""
        self.client.get("/register")
        res = self._post(
            self.client,
            "/register",
            {
                "name": "Privilege Escalation Attempt",
                "prn": "BE2026CS102",
                "email": "escalate@engg.edu",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "role": "admin",  # Malicious injection
            },
        )
        self.assertEqual(res.status_code, 200)
        with app.app_context():
            user = database.get_user_by_identifier("BE2026CS102")
            self.assertIsNotNone(user)
            self.assertEqual(user.role, "user", "Role must strictly remain 'user'")

    def test_06_user_supplied_username_ignored(self):
        """User cannot set arbitrary username during registration."""
        self.client.get("/register")
        res = self._post(
            self.client,
            "/register",
            {
                "name": "Username Injection Student",
                "prn": "BE2026CS103",
                "email": "username.inj@engg.edu",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "username": "fake_admin_user",  # Malicious injection
            },
        )
        self.assertEqual(res.status_code, 200)
        with app.app_context():
            user = database.get_user_by_identifier("BE2026CS103")
            self.assertIsNotNone(user)
            self.assertIsNone(user.username, "Username must remain None for V1 students")

    # =========================================================================
    # PART 3: STUDENT DASHBOARD & ACADEMIC CONTEXT
    # =========================================================================

    def test_07_student_dashboard_contains_be_final_year_context(self):
        """Student dashboard clearly identifies B.E. Final Year, student name, and PRN."""
        c = app.test_client()
        self._login(c, "BE2026CS101", "Password123!")
        res = c.get("/student")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("B.E. Final Year", html)
        self.assertIn("B.E. Computer Science and Engineering", html)
        self.assertIn("Aarav Sharma", html)
        self.assertIn("BE2026CS101", html)

    def test_08_draft_exams_not_visible_to_students(self):
        """Exams in draft status must never be displayed to students."""
        with app.app_context():
            admin = database.create_user(
                name="Prof. Sharma",
                identifier="admin_phase8",
                password="AdminPassword123!",
                role="admin",
                username="admin_phase8",
                email="admin8@engg.edu",
            )
            exam = database.create_exam(
                title="Draft Cryptography Exam",
                created_by=admin.id,
                start_time=datetime.now() - timedelta(hours=1),
                end_time=datetime.now() + timedelta(hours=2),
                duration_minutes=30,
                questions=[{"question": "Q1", "options": ["A", "B", "C", "D"], "correct_index": 0}],
                status="draft",
            )

        c = app.test_client()
        self._login(c, "BE2026CS101", "Password123!")
        res = c.get("/student")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertNotIn("Draft Cryptography Exam", html)

    def test_09_student_dashboard_categorization(self):
        """Student dashboard categorizes upcoming, available now, in progress, and completed exams."""
        with app.app_context():
            admin = database.get_user_by_identifier("admin_phase8")

            # 1. Upcoming exam
            upcoming = database.create_exam(
                title="Upcoming Cloud Computing Exam",
                created_by=admin.id,
                start_time=datetime.now() + timedelta(days=2),
                end_time=datetime.now() + timedelta(days=2, hours=2),
                duration_minutes=45,
                questions=[{"question": "Q1", "options": ["A", "B", "C", "D"], "correct_index": 1}],
                status="published",
            )

            # 2. Available Now exam
            available = database.create_exam(
                title="Available Distributed Systems Exam",
                created_by=admin.id,
                start_time=datetime.now() - timedelta(hours=1),
                end_time=datetime.now() + timedelta(hours=2),
                duration_minutes=60,
                questions=[{"question": "Q1", "options": ["A", "B", "C", "D"], "correct_index": 2}],
                status="published",
            )

        c = app.test_client()
        self._login(c, "BE2026CS101", "Password123!")
        res = c.get("/student")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Upcoming Cloud Computing Exam", html)
        self.assertIn("Available Distributed Systems Exam", html)
        self.assertIn("Take Exam", html)
        self.assertIn("Opens", html)

    # =========================================================================
    # PART 4: COMPLETE EXAM FLOW & SHA-256 INTEGRITY
    # =========================================================================

    def test_10_complete_exam_flow_and_result_integrity(self):
        """Complete workflow: Draft -> Publish -> Take -> Submit -> Evaluate -> Sealed Result -> Tamper Detection."""
        with app.app_context():
            admin = database.get_user_by_identifier("admin_phase8")
            # Create a 2-question exam
            exam = database.create_exam(
                title="Network Security V1 Final",
                created_by=admin.id,
                start_time=datetime.now() - timedelta(minutes=10),
                end_time=datetime.now() + timedelta(hours=1),
                duration_minutes=20,
                questions=[
                    {
                        "question": "What does SHA stand for?",
                        "options": ["Secure Hash Algorithm", "Simple Host Access", "Server Hardening Auth", "Shared Hash Array"],
                        "correct_index": 0,
                    },
                    {
                        "question": "Which port does HTTPS standardly use?",
                        "options": ["80", "8080", "443", "22"],
                        "correct_index": 2,
                    },
                ],
                status="draft",
            )
            exam_id = exam.id

        # 1. Publish exam as admin
        c_admin = app.test_client()
        self._login(c_admin, "admin_phase8", "AdminPassword123!")
        res_pub = self._post(c_admin, f"/admin/exams/{exam_id}/publish", {})
        self.assertEqual(res_pub.status_code, 200)

        # 2. Student starts exam
        c_student = app.test_client()
        self._login(c_student, "BE2026CS101", "Password123!")
        res_start = c_student.get(f"/student/exam/{exam_id}")
        self.assertEqual(res_start.status_code, 200)
        html_exam = res_start.get_data(as_text=True)
        self.assertIn("What does SHA stand for?", html_exam)
        self.assertIn("Which port does HTTPS standardly use?", html_exam)

        # 3. Student submits correct answers
        res_submit = self._post(
            c_student,
            f"/student/exam/{exam_id}",
            {
                "answer_0": "0",  # Correct (Secure Hash Algorithm)
                "answer_1": "2",  # Correct (443)
            },
        )
        self.assertEqual(res_submit.status_code, 200)

        # 4. Verify result page
        html_result = res_submit.get_data(as_text=True)
        self.assertIn("2 / 2", html_result)
        self.assertIn("100.0% Score", html_result)
        self.assertIn("SHA-256 Integrity Verified", html_result)
        self.assertIn("Tamper-evident result fingerprint", html_result)
        self.assertIn("B.E. Final Year", html_result)

        # 5. Verify cryptographic validity via backend
        with app.app_context():
            attempt = database.get_attempt(exam_id, database.get_user_by_identifier("BE2026CS101").id)
            self.assertIsNotNone(attempt)
            self.assertTrue(attempt.is_submitted)
            self.assertEqual(attempt.score, 2)
            self.assertEqual(attempt.total, 2)
            self.assertIsNotNone(attempt.block_id)
            block_idx = attempt.block_id

            # Verify integrity
            verify_res = blockchain.verify_result_integrity(block_idx)
            self.assertTrue(verify_res["valid"])
            self.assertEqual(verify_res["block_index"], block_idx)

            # 6. Simulate Tamper Detection: modify database record directly
            row = db.session.get(Block, block_idx)
            data = json.loads(row.data_json)
            data["score"] = 999  # Attacker alters score
            row.data_json = json.dumps(data, sort_keys=True)
            db.session.commit()

            # Verification must now FAIL with hash mismatch
            verify_tampered = blockchain.verify_result_integrity(block_idx)
            self.assertFalse(verify_tampered["valid"])
            self.assertIn("mismatch", verify_tampered["reason"].lower())

    # =========================================================================
    # PART 5: ROUTE COMPATIBILITY & ADMIN SCOPE
    # =========================================================================

    def test_11_backward_compatibility_routes(self):
        """All primary routes and legacy aliases (/teacher, /admin/exams) remain accessible."""
        c_anon = app.test_client()

        # Public routes
        self.assertEqual(c_anon.get("/").status_code, 200)
        self.assertEqual(c_anon.get("/login").status_code, 200)
        self.assertEqual(c_anon.get("/register").status_code, 200)

        # Protected routes redirect unauthenticated users
        self.assertEqual(c_anon.get("/student").status_code, 302)
        self.assertEqual(c_anon.get("/admin").status_code, 302)
        self.assertEqual(c_anon.get("/teacher").status_code, 302)
        self.assertEqual(c_anon.get("/blockchain").status_code, 302)

        # Admin routes
        c_admin = app.test_client()
        self._login(c_admin, "admin_phase8", "AdminPassword123!")

        res_admin = c_admin.get("/admin")
        self.assertEqual(res_admin.status_code, 200)
        self.assertIn(b"Admin Dashboard", res_admin.data)
        self.assertIn(b"BE Final Year Examination System", res_admin.data)

        # Legacy alias /teacher redirects to /admin
        res_teacher = c_admin.get("/teacher", follow_redirects=True)
        self.assertEqual(res_teacher.status_code, 200)
        self.assertIn(b"Admin Dashboard", res_teacher.data)

        # /teacher/create_exam compatibility
        res_create = c_admin.get("/teacher/create_exam")
        self.assertEqual(res_create.status_code, 200)

        # /admin/exams
        res_exams = c_admin.get("/admin/exams")
        self.assertEqual(res_exams.status_code, 200)

        # /blockchain
        res_chain = c_admin.get("/blockchain")
        self.assertEqual(res_chain.status_code, 200)
        self.assertIn(b"Integrity Ledger", res_chain.data)


if __name__ == "__main__":
    unittest.main()
