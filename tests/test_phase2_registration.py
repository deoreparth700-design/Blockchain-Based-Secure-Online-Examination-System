"""
test_phase2_registration.py
---------------------------
Automated test suite for Phase 2: Simplified BE Final Year Registration & PRN Authentication.

Tests:
1. Database safety (Isolated SQLite test runner)
2. Target registration: name, prn, email, password, confirm_password creates role='user'
3. Duplicate PRN rejection
4. Duplicate Email rejection
5. Password mismatch rejection
6. Invalid PRN rejection
7. Admin injection protection (role='admin' in POST is ignored)
8. Username injection ignored (username is not required, stays None)
9. Login with PRN + password
10. Login with Email + password
11. Wrong password login rejection
12. Existing Admin login compatibility
13. Regression: Role-based authorization for Admin and User
"""

import os
import sys
import unittest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEST_DB_PATH = os.path.join(BASE_DIR, "tests", "test_phase2.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

sys.path.insert(0, BASE_DIR)

from app import app
from models import db, User
import database
import validators


class TestPhase2Registration(unittest.TestCase):
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

    # ---------- 1. Database Safety ----------
    def test_01_safe_isolated_database_used(self):
        with app.app_context():
            engine_url = str(db.engine.url)
            self.assertIn("sqlite", engine_url)
            self.assertNotIn("neon.tech", engine_url)
            self.assertNotIn("postgresql", engine_url)

    # ---------- 2. Target 5-Field Registration ----------
    def test_02_new_registration_success(self):
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf-token-123"

        res = self.client.post("/register", data={
            "csrf_token": "csrf-token-123",
            "name": "Siddharth Shinde",
            "prn": "2024-BE-001",
            "email": "siddharth@college.edu",
            "password": "SecurePassword123",
            "confirm_password": "SecurePassword123",
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Account created successfully", res.data)

        with app.app_context():
            user = database.get_user_by_identifier("2024-BE-001")
            self.assertIsNotNone(user)
            self.assertEqual(user.name, "Siddharth Shinde")
            self.assertEqual(user.identifier, "2024-BE-001")
            self.assertEqual(user.prn, "2024-BE-001")
            self.assertEqual(user.email, "siddharth@college.edu")
            self.assertEqual(user.role, "user")
            self.assertIsNone(user.username)  # Username is not set
            self.assertTrue(user.check_password("SecurePassword123"))

    # ---------- 3. Duplicate Prevention ----------
    def test_03_duplicate_prn_fails(self):
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf-token-123"

        res = self.client.post("/register", data={
            "csrf_token": "csrf-token-123",
            "name": "Different Name",
            "prn": "2024-BE-001",  # Same PRN
            "email": "different@college.edu",
            "password": "SecurePassword123",
            "confirm_password": "SecurePassword123",
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b"That PRN is already registered", res.data)

    def test_04_duplicate_email_fails(self):
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf-token-123"

        res = self.client.post("/register", data={
            "csrf_token": "csrf-token-123",
            "name": "Another Student",
            "prn": "2024-BE-002",
            "email": "siddharth@college.edu",  # Same Email
            "password": "SecurePassword123",
            "confirm_password": "SecurePassword123",
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b"account with that email address already exists", res.data)

    # ---------- 4. Validation Rules ----------
    def test_05_password_mismatch_fails(self):
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf-token-123"

        res = self.client.post("/register", data={
            "csrf_token": "csrf-token-123",
            "name": "Ananya Kulkarni",
            "prn": "2024-BE-003",
            "email": "ananya@college.edu",
            "password": "SecurePassword123",
            "confirm_password": "MismatchedPassword999",
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Passwords do not match", res.data)

    def test_06_invalid_prn_fails(self):
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf-token-123"

        # PRN with illegal characters
        res = self.client.post("/register", data={
            "csrf_token": "csrf-token-123",
            "name": "Ananya Kulkarni",
            "prn": "PRN@!#$%",
            "email": "ananya@college.edu",
            "password": "SecurePassword123",
            "confirm_password": "SecurePassword123",
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b"PRN can only contain letters, numbers, hyphens, and slashes", res.data)

    # ---------- 5. Security & Privilege Escalation Checks ----------
    def test_07_admin_injection_prevented(self):
        """Attacker includes role=admin in registration POST body."""
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf-token-123"

        res = self.client.post("/register", data={
            "csrf_token": "csrf-token-123",
            "name": "Malicious User",
            "prn": "2024-BE-999",
            "email": "attacker@college.edu",
            "password": "SecurePassword123",
            "confirm_password": "SecurePassword123",
            "role": "admin",
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        with app.app_context():
            user = database.get_user_by_identifier("2024-BE-999")
            self.assertIsNotNone(user)
            self.assertEqual(user.role, "user")
            self.assertNotEqual(user.role, "admin")

    def test_08_username_injection_ignored(self):
        """Attacker includes username=hacker_root in registration POST body."""
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf-token-123"

        res = self.client.post("/register", data={
            "csrf_token": "csrf-token-123",
            "name": "Tester User",
            "prn": "2024-BE-004",
            "email": "tester@college.edu",
            "password": "SecurePassword123",
            "confirm_password": "SecurePassword123",
            "username": "hacker_root",
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        with app.app_context():
            user = database.get_user_by_identifier("2024-BE-004")
            self.assertIsNotNone(user)
            # Username is strictly ignored and remains None
            self.assertIsNone(user.username)
            self.assertEqual(user.role, "user")

    # ---------- 6. Login Functionality (PRN, Email, Wrong Password) ----------
    def test_09_login_with_prn(self):
        self.client.get("/logout")
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf-token-123"

        res = self.client.post("/login", data={
            "csrf_token": "csrf-token-123",
            "identifier": "2024-BE-001",  # Login by PRN
            "password": "SecurePassword123",
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "user")
            self.assertEqual(sess.get("identifier"), "2024-BE-001")
        self.assertIn(b"Student Portal", res.data)

    def test_10_login_with_email(self):
        self.client.get("/logout")
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf-token-123"

        res = self.client.post("/login", data={
            "csrf_token": "csrf-token-123",
            "identifier": "siddharth@college.edu",  # Login by Email
            "password": "SecurePassword123",
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "user")
            self.assertEqual(sess.get("identifier"), "2024-BE-001")

    def test_11_wrong_password_fails(self):
        self.client.get("/logout")
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf-token-123"

        res = self.client.post("/login", data={
            "csrf_token": "csrf-token-123",
            "identifier": "2024-BE-001",
            "password": "WrongPassword999",
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Invalid PRN, email, or password", res.data)

    # ---------- 7. Admin Login Compatibility & Regression Checks ----------
    def test_12_admin_login_still_works(self):
        with app.app_context():
            admin = database.create_user(
                name="Prof Head Admin",
                identifier="admin_coordinator",
                username="admin_coordinator",
                email="coordinator@college.edu",
                password="AdminSecretPass123",
                role="admin"
            )

        self.client.get("/logout")
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf-token-123"

        res = self.client.post("/login", data={
            "csrf_token": "csrf-token-123",
            "identifier": "admin_coordinator",
            "password": "AdminSecretPass123",
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        with self.client.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "admin")
        self.assertIn(b"Admin Dashboard", res.data)

    def test_13_regression_role_access_control(self):
        # Log in as admin
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf-token-123"
        self.client.post("/login", data={
            "csrf_token": "csrf-token-123",
            "identifier": "admin_coordinator",
            "password": "AdminSecretPass123",
        }, follow_redirects=True)

        # Admin can access admin dashboard
        res = self.client.get("/teacher")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Admin Dashboard", res.data)

        # Log in as user
        self.client.get("/logout")
        with self.client.session_transaction() as sess:
            sess["csrf_token"] = "csrf-token-123"

        self.client.post("/login", data={
            "csrf_token": "csrf-token-123",
            "identifier": "2024-BE-001",
            "password": "SecurePassword123",
        }, follow_redirects=True)

        # User is denied admin dashboard
        res = self.client.get("/teacher", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"This page is only available to admins", res.data)

        # User can access student dashboard
        res = self.client.get("/student")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Student Portal", res.data)

        # Anonymous is redirected to login
        self.client.get("/logout")
        res = self.client.get("/student", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))


if __name__ == "__main__":
    unittest.main()
