"""
tests/test_login_regression.py
------------------------------
Regression test suite dedicated to verifying authentication and login flows.

Verifies:
1. Valid admin username + correct password -> successful login
2. Invalid admin username -> login rejected
3. Valid student PRN + correct password -> successful login
4. Invalid student PRN -> login rejected
5. Correct identifier + wrong password -> login rejected
6. Leading/trailing whitespace around admin username does not break login
7. Leading/trailing whitespace around student PRN does not break login
8. Successful admin login creates the expected session and redirect
9. Successful student login creates the expected session and redirect
10. Case-insensitive student PRN login
11. Registered student email login
12. Empty credentials rejection
"""

import os
import sys
import unittest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEST_DB_PATH = os.path.join(BASE_DIR, "tests", "test_login_regression.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

sys.path.insert(0, BASE_DIR)

from app import app
from models import db, User
import database


class TestLoginRegression(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()
        with app.app_context():
            db.create_all()

            # Seed Admin Account (distinct username and identifier)
            cls.admin = database.create_user(
                name="Prof. Admin Examiner",
                identifier="EMP_ADMIN_01",
                username="admin_exam_head",
                email="admin.head@mgmu.ac.in",
                password="AdminSecretPassword123!",
                role="admin",
            )

            # Seed Student Account (PRN stored in identifier, username is None)
            cls.student = database.create_user(
                name="Aditya Kulkarni",
                identifier="BE2026CS777",
                email="aditya.kulkarni@demo.edu",
                password="StudentSecretPassword123!",
                role="user",
                username=None,
            )

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

    def _login(self, client, identifier, password, follow_redirects=True):
        # Fetch login page to ensure CSRF token is populated in the session
        client.get("/login")
        with client.session_transaction() as sess:
            csrf_token = sess.get("csrf_token", "")

        return client.post(
            "/login",
            data={
                "identifier": identifier,
                "password": password,
                "csrf_token": csrf_token,
            },
            follow_redirects=follow_redirects,
        )

    # ---------- 1. Database Safety ----------
    def test_00_database_isolation(self):
        with app.app_context():
            engine_url = str(db.engine.url)
            self.assertIn("sqlite", engine_url)
            self.assertNotIn("neon.tech", engine_url)
            self.assertNotIn("postgresql", engine_url)

    # ---------- 2. Admin Login ----------
    def test_01_valid_admin_username_correct_password_success(self):
        """1. Valid admin username + correct password -> successful login."""
        c = app.test_client()
        res = self._login(c, "admin_exam_head", "AdminSecretPassword123!", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Admin Dashboard", html)
        with c.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "admin")
            self.assertEqual(sess.get("name"), "Prof. Admin Examiner")

    def test_02_invalid_admin_username_rejected(self):
        """2. Invalid admin username -> login rejected."""
        c = app.test_client()
        res = self._login(c, "nonexistent_admin_username", "AdminSecretPassword123!", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Invalid PRN, email, or password.", html)
        with c.session_transaction() as sess:
            self.assertIsNone(sess.get("user_id"))

    # ---------- 3. Student Login ----------
    def test_03_valid_student_prn_correct_password_success(self):
        """3. Valid student PRN + correct password -> successful login."""
        c = app.test_client()
        res = self._login(c, "BE2026CS777", "StudentSecretPassword123!", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Aditya Kulkarni", html)
        self.assertIn("BE2026CS777", html)
        with c.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "user")
            self.assertEqual(sess.get("identifier"), "BE2026CS777")

    def test_04_invalid_student_prn_rejected(self):
        """4. Invalid student PRN -> login rejected."""
        c = app.test_client()
        res = self._login(c, "BE2026CS999", "StudentSecretPassword123!", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Invalid PRN, email, or password.", html)
        with c.session_transaction() as sess:
            self.assertIsNone(sess.get("user_id"))

    # ---------- 4. Wrong Password ----------
    def test_05_correct_identifier_wrong_password_rejected(self):
        """5. Correct identifier + wrong password -> login rejected."""
        c1 = app.test_client()
        res1 = self._login(c1, "admin_exam_head", "IncorrectPassword!", follow_redirects=True)
        self.assertEqual(res1.status_code, 200)
        self.assertIn("Invalid PRN, email, or password.", res1.get_data(as_text=True))
        with c1.session_transaction() as sess:
            self.assertIsNone(sess.get("user_id"))

        c2 = app.test_client()
        res2 = self._login(c2, "BE2026CS777", "IncorrectPassword!", follow_redirects=True)
        self.assertEqual(res2.status_code, 200)
        self.assertIn("Invalid PRN, email, or password.", res2.get_data(as_text=True))
        with c2.session_transaction() as sess:
            self.assertIsNone(sess.get("user_id"))

    # ---------- 5. Whitespace Handling ----------
    def test_06_leading_trailing_whitespace_does_not_break_admin_login(self):
        """6a. Leading/trailing whitespace around admin username does not break login."""
        c = app.test_client()
        res = self._login(c, "   admin_exam_head   ", "AdminSecretPassword123!", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Admin Dashboard", res.get_data(as_text=True))
        with c.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "admin")

    def test_07_leading_trailing_whitespace_does_not_break_student_login(self):
        """6b. Leading/trailing whitespace around student PRN does not break login."""
        c = app.test_client()
        res = self._login(c, "   BE2026CS777   ", "StudentSecretPassword123!", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Aditya Kulkarni", res.get_data(as_text=True))
        with c.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "user")

    # ---------- 6. Session and Redirection Checks ----------
    def test_08_successful_admin_login_creates_expected_session_and_redirect(self):
        """7. Successful admin login creates the expected session/redirect."""
        c = app.test_client()
        res = self._login(c, "admin_exam_head", "AdminSecretPassword123!", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        # Redirects to index, which forwards admin to admin_dashboard
        self.assertEqual(res.headers.get("Location"), "/")
        with c.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "admin")
            self.assertEqual(sess.get("name"), "Prof. Admin Examiner")
            self.assertEqual(sess.get("identifier"), "EMP_ADMIN_01")
            self.assertIsNotNone(sess.get("user_id"))

        # Follow redirect to index
        res_index = c.get("/", follow_redirects=False)
        self.assertEqual(res_index.status_code, 302)
        self.assertIn(res_index.headers.get("Location"), ("/admin", "/admin/exams"))

    def test_09_successful_student_login_creates_expected_session_and_redirect(self):
        """8. Successful student login creates the expected session/redirect."""
        c = app.test_client()
        res = self._login(c, "BE2026CS777", "StudentSecretPassword123!", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        # Redirects to index, which forwards user to student_dashboard
        self.assertEqual(res.headers.get("Location"), "/")
        with c.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "user")
            self.assertEqual(sess.get("name"), "Aditya Kulkarni")
            self.assertEqual(sess.get("identifier"), "BE2026CS777")
            self.assertIsNotNone(sess.get("user_id"))

        # Follow redirect to index
        res_index = c.get("/", follow_redirects=False)
        self.assertEqual(res_index.status_code, 302)
        self.assertEqual(res_index.headers.get("Location"), "/student")

    # ---------- 7. Additional Robustness Checks ----------
    def test_10_student_prn_case_insensitive_login(self):
        """Case-insensitive PRN login works smoothly."""
        c = app.test_client()
        res = self._login(c, "be2026cs777", "StudentSecretPassword123!", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Aditya Kulkarni", res.get_data(as_text=True))
        with c.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "user")

    def test_11_student_email_login_works(self):
        """Student email login continues to work."""
        c = app.test_client()
        res = self._login(c, "aditya.kulkarni@demo.edu", "StudentSecretPassword123!", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Aditya Kulkarni", res.get_data(as_text=True))
        with c.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "user")

    def test_12_empty_credentials_rejected(self):
        """Empty identifier or password fails validation immediately."""
        c = app.test_client()
        res_no_ident = self._login(c, "", "Password123!", follow_redirects=True)
        self.assertEqual(res_no_ident.status_code, 200)
        self.assertIn("Please enter your PRN or email.", res_no_ident.get_data(as_text=True))

        res_no_pwd = self._login(c, "BE2026CS777", "", follow_redirects=True)
        self.assertEqual(res_no_pwd.status_code, 200)
        self.assertIn("Please enter your password.", res_no_pwd.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
