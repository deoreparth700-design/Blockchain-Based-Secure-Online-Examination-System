"""
test_phase1_roles.py
--------------------
Focused test suite for Phase 1: Authentication and Role Foundation (ADMIN and USER).

Verifies:
1. Admin access: Admin can access protected admin routes (/teacher, /teacher/create_exam).
2. User access: User can access protected user routes (/student).
3. User cannot access admin functionality: Logged-in user is denied access to admin routes.
4. Anonymous user: Unauthenticated user is redirected to /login on protected routes.
5. Registration: Newly registered accounts always receive role="user".
6. Admin cannot be created via registration: Tampered POST payload cannot create an admin.
7. Redirect logic:
   - Admin -> Admin Dashboard (/teacher)
   - User -> User Dashboard (/student)
8. Legacy role normalization on login: 'teacher' -> 'admin', 'student' -> 'user'.

DATABASE SAFETY:
Forces an isolated, temporary SQLite database to completely protect the production Neon database.
"""

import os
import sys
import unittest

# Ensure an isolated test SQLite database is used BEFORE app is imported
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEST_DB_PATH = os.path.join(BASE_DIR, "tests", "test_phase1.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

sys.path.insert(0, BASE_DIR)

from app import app
from models import db, User
import database


class TestPhase1Roles(unittest.TestCase):
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

    # ---------- 1. Database Safety Verification ----------
    def test_01_safe_isolated_database_used(self):
        with app.app_context():
            engine_url = str(db.engine.url)
            self.assertIn("sqlite", engine_url)
            self.assertNotIn("neon.tech", engine_url)
            self.assertNotIn("postgresql", engine_url)

    # ---------- 2. User Self-Registration & Role Enforcement ----------
    def test_02_new_registration_always_has_user_role(self):
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf-test-token"

        res = self.client.post("/register", data={
            "csrf_token": "csrf-test-token",
            "name": "Aarav Sharma",
            "username": "aarav_user",
            "roll_no": "2024-BE-101",
            "email": "aarav@example.com",
            "password": "Password123",
            "confirm_password": "Password123",
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        with app.app_context():
            user = database.get_user_by_username("aarav_user")
            self.assertIsNotNone(user)
            self.assertEqual(user.role, "user")
            self.assertNotEqual(user.role, "admin")

    def test_03_registration_cannot_create_admin(self):
        """Attacker attempts to inject role='admin' in form POST data."""
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf-test-token"

        res = self.client.post("/register", data={
            "csrf_token": "csrf-test-token",
            "name": "Evil Attacker",
            "username": "evil_hacker",
            "roll_no": "2024-BE-999",
            "email": "evil@example.com",
            "password": "Password123",
            "confirm_password": "Password123",
            "role": "admin",  # Tampered field
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        with app.app_context():
            user = database.get_user_by_username("evil_hacker")
            self.assertIsNotNone(user)
            # Backend MUST ignore user-supplied role and enforce 'user'
            self.assertEqual(user.role, "user")
            self.assertNotEqual(user.role, "admin")

    # ---------- 3. Anonymous Access Protection ----------
    def test_04_anonymous_user_blocked_from_protected_routes(self):
        # Admin dashboard
        res = self.client.get("/teacher", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

        # Admin create exam
        res = self.client.get("/teacher/create_exam", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

        # User dashboard
        res = self.client.get("/student", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    # ---------- 4. User Role Access & Privilege Escalation Prevention ----------
    def test_05_user_can_access_user_dashboard(self):
        with app.app_context():
            student = database.create_user(
                name="Rohan Verma",
                username="rohan_v",
                identifier="2024-BE-102",
                email="rohan@example.com",
                password="Password123",
                role="user"
            )
            student_id = student.id

        with self.client.session_transaction() as sess:
            sess["user_id"] = student_id
            sess["role"] = "user"
            sess["name"] = "Rohan Verma"
            sess["identifier"] = "2024-BE-102"

        res = self.client.get("/student")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Rohan Verma", res.data)

    def test_06_user_cannot_access_admin_dashboard(self):
        with app.app_context():
            student = database.get_user_by_username("rohan_v")
            student_id = student.id

        with self.client.session_transaction() as sess:
            sess["user_id"] = student_id
            sess["role"] = "user"
            sess["name"] = "Rohan Verma"

        # User attempts to visit Admin Dashboard
        res = self.client.get("/teacher", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        # Should be redirected away and flash error message
        self.assertIn(b"This page is only available to admins.", res.data)

    def test_07_user_cannot_access_admin_create_exam(self):
        with app.app_context():
            student = database.get_user_by_username("rohan_v")
            student_id = student.id

        with self.client.session_transaction() as sess:
            sess["user_id"] = student_id
            sess["role"] = "user"
            sess["name"] = "Rohan Verma"

        res = self.client.get("/teacher/create_exam", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"This page is only available to admins.", res.data)

    # ---------- 5. Admin Role Access ----------
    def test_08_admin_can_access_admin_dashboard(self):
        with app.app_context():
            admin = database.create_user(
                name="System Administrator",
                username="admin_user",
                identifier="admin_user",
                email="admin@example.com",
                password="AdminPassword123",
                role="admin"
            )
            admin_id = admin.id

        with self.client.session_transaction() as sess:
            sess["user_id"] = admin_id
            sess["role"] = "admin"
            sess["name"] = "System Administrator"

        res = self.client.get("/teacher")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Admin Dashboard", res.data)
        self.assertIn(b"System Administrator", res.data)

    def test_09_admin_can_access_create_exam(self):
        with app.app_context():
            admin = database.get_user_by_username("admin_user")
            admin_id = admin.id

        with self.client.session_transaction() as sess:
            sess["user_id"] = admin_id
            sess["role"] = "admin"
            sess["name"] = "System Administrator"

        res = self.client.get("/teacher/create_exam")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Create New Examination", res.data)

    # ---------- 6. Login & Role-Based Redirection ----------
    def test_10_admin_login_redirects_to_admin_dashboard(self):
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf-test-token"

        res = self.client.post("/login", data={
            "csrf_token": "csrf-test-token",
            "identifier": "admin_user",
            "password": "AdminPassword123",
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Admin Dashboard", res.data)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "admin")

    def test_11_user_login_redirects_to_user_dashboard(self):
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf-test-token"

        res = self.client.post("/login", data={
            "csrf_token": "csrf-test-token",
            "identifier": "rohan_v",
            "password": "Password123",
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "user")

    # ---------- 7. Legacy Role Auto-Normalization ----------
    def test_12_legacy_roles_normalized_on_login(self):
        with app.app_context():
            legacy_teacher = database.create_user(
                name="Legacy Teacher",
                username="legacy_teacher",
                identifier="legacy_teacher",
                email="teacher@legacy.edu",
                password="Password123",
                role="teacher"
            )
            legacy_student = database.create_user(
                name="Legacy Student",
                username="legacy_student",
                identifier="legacy_student",
                email="student@legacy.edu",
                password="Password123",
                role="student"
            )

        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf-test-token"

        # Log in legacy teacher
        self.client.post("/login", data={
            "csrf_token": "csrf-test-token",
            "identifier": "legacy_teacher",
            "password": "Password123",
        }, follow_redirects=True)

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "admin")

        with app.app_context():
            u = database.get_user_by_username("legacy_teacher")
            self.assertEqual(u.role, "admin")

        # Log out legacy teacher before logging in legacy student
        self.client.get("/logout")

        # Log in legacy student
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf-test-token"

        self.client.post("/login", data={
            "csrf_token": "csrf-test-token",
            "identifier": "legacy_student",
            "password": "Password123",
        }, follow_redirects=True)

        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "user")

        with app.app_context():
            u = database.get_user_by_username("legacy_student")
            self.assertEqual(u.role, "user")


if __name__ == "__main__":
    unittest.main()
