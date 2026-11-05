"""
test_login_throttling.py
------------------------
Automated test suite for Phase 4B: Database-backed Login Throttling.

Covers:
1. 4 failures still allowed
2. 5th failure blocks further attempts
3. Correct password while blocked is still refused
4. Success before the limit resets the count
5. Block expires after 15 minutes (simulated time)
6. Different identifiers do not affect each other
7. Unknown user is throttled identically without account enumeration
8. Failures across PRN, email, and username of the same student share one counter
9. Automatic pruning of failure records older than 24h
"""

import os
import sys
import unittest
from datetime import datetime, timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEST_DB_PATH = os.path.join(BASE_DIR, "tests", "test_throttling.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

sys.path.insert(0, BASE_DIR)

from app import app  # noqa: E402  # required after environment/path setup
from models import db, LoginAttempt  # noqa: E402  # required after environment/path setup
import database  # noqa: E402  # required after environment/path setup
import throttling  # noqa: E402  # required after environment/path setup


class TestLoginThrottling(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except OSError:
                pass

    def setUp(self):
        with app.app_context():
            db.drop_all()
            db.create_all()

            # Seed Student 1 with PRN, email, and username
            self.student1 = database.create_user(
                name="Rahul Sharma",
                identifier="PRN2026101",
                username="rahul_sharma",
                password="StudentPassword123",
                role="user",
                email="rahul@college.edu",
            )

            # Seed Student 2
            self.student2 = database.create_user(
                name="Sneha Patil",
                identifier="PRN2026102",
                username="sneha_patil",
                password="StudentPassword123",
                role="user",
                email="sneha@college.edu",
            )

        self.client = app.test_client()

    def tearDown(self):
        with app.app_context():
            db.session.remove()

    def _login(self, client, identifier, password, follow_redirects=True):
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

    # 1. 4 failures still allowed
    def test_01_four_failures_still_allowed(self):
        """4 consecutive login failures are allowed and do not block the account."""
        c = app.test_client()
        for i in range(4):
            res = self._login(c, "PRN2026101", "WrongPassword!", follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            html = res.get_data(as_text=True)
            self.assertIn("Invalid PRN, email, or password.", html)
            self.assertNotIn("Too many failed attempts", html)

        with app.app_context():
            status = throttling.is_blocked("PRN2026101")
            self.assertFalse(status.blocked)
            self.assertEqual(status.minutes, 0)

    # 2. 5th failure blocks
    def test_02_fifth_failure_blocks_further_attempts(self):
        """5 failed logins in the last 15 minutes block further login attempts."""
        c = app.test_client()
        for i in range(5):
            res = self._login(c, "PRN2026101", "WrongPassword!", follow_redirects=True)
            self.assertEqual(res.status_code, 200)

        with app.app_context():
            status = throttling.is_blocked("PRN2026101")
            self.assertTrue(status.blocked)
            self.assertGreaterEqual(status.minutes, 1)

        # 6th attempt is blocked
        res_blocked = self._login(c, "PRN2026101", "WrongPassword!", follow_redirects=True)
        self.assertEqual(res_blocked.status_code, 200)
        html = res_blocked.get_data(as_text=True)
        self.assertIn("Too many failed attempts. Try again in", html)
        self.assertNotIn("Invalid PRN, email, or password.", html)

    # 3. Correct password while blocked is still refused
    def test_03_correct_password_while_blocked_is_still_refused(self):
        """Submitting the correct password while an identifier is blocked is still refused."""
        c = app.test_client()
        for i in range(5):
            self._login(c, "PRN2026101", "WrongPassword!", follow_redirects=True)

        # Try with correct password
        res = self._login(c, "PRN2026101", "StudentPassword123", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Too many failed attempts. Try again in", html)

        # Confirm user is not logged in
        with c.session_transaction() as sess:
            self.assertIsNone(sess.get("user_id"))

    # 4. Success before the limit resets the count
    def test_04_success_before_limit_resets_count(self):
        """A successful login before hitting the limit clears failure history."""
        c = app.test_client()
        # 3 failures
        for i in range(3):
            self._login(c, "PRN2026101", "WrongPassword!", follow_redirects=True)

        with app.app_context():
            count = LoginAttempt.query.filter_by(identifier="prn2026101").count()
            self.assertEqual(count, 3)

        # Successful login
        res_ok = self._login(c, "PRN2026101", "StudentPassword123", follow_redirects=True)
        self.assertEqual(res_ok.status_code, 200)
        self.assertIn("Rahul Sharma", res_ok.get_data(as_text=True))

        with app.app_context():
            count_after = LoginAttempt.query.filter_by(identifier="prn2026101").count()
            self.assertEqual(count_after, 0)

        # Log out
        c.get("/logout")

        # Now 4 failures are allowed again without triggering a block
        for i in range(4):
            res = self._login(c, "PRN2026101", "WrongPassword!", follow_redirects=True)
            self.assertNotIn("Too many failed attempts", res.get_data(as_text=True))

    # 5. Block expires after 15 minutes (simulate time, do not sleep)
    def test_05_block_expires_after_15_minutes(self):
        """Block expires once the oldest of the 5 failures is older than 15 minutes."""
        c = app.test_client()
        for i in range(5):
            self._login(c, "PRN2026101", "WrongPassword!", follow_redirects=True)

        with app.app_context():
            self.assertTrue(throttling.is_blocked("PRN2026101").blocked)

            # Age all failures by 16 minutes to simulate passage of time
            past_time = datetime.now() - timedelta(minutes=16)
            LoginAttempt.query.filter_by(identifier="prn2026101").update({"created_at": past_time})
            db.session.commit()

            # Now is_blocked should return False
            self.assertFalse(throttling.is_blocked("PRN2026101").blocked)

        # Login attempt now succeeds with valid credentials
        res = self._login(c, "PRN2026101", "StudentPassword123", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Rahul Sharma", res.get_data(as_text=True))

    # 6. Different identifiers do not affect each other
    def test_06_different_identifiers_do_not_affect_each_other(self):
        """Throttling one identifier does not affect other student or admin accounts."""
        c = app.test_client()
        # Block Student 1
        for i in range(5):
            self._login(c, "PRN2026101", "WrongPassword!", follow_redirects=True)

        with app.app_context():
            self.assertTrue(throttling.is_blocked("PRN2026101").blocked)
            self.assertFalse(throttling.is_blocked("PRN2026102").blocked)

        # Student 2 logs in successfully
        res = self._login(c, "PRN2026102", "StudentPassword123", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Sneha Patil", res.get_data(as_text=True))

    # 7. Same message for unknown user (no account enumeration)
    def test_07_same_message_for_unknown_user(self):
        """Unknown accounts receive the exact same error and are throttled identically."""
        c = app.test_client()
        unknown_id = "UNKNOWN_NONEXISTENT_PRN"

        # 4 attempts -> generic error
        for i in range(4):
            res = self._login(c, unknown_id, "SomePassword!", follow_redirects=True)
            self.assertEqual(res.status_code, 200)
            self.assertIn("Invalid PRN, email, or password.", res.get_data(as_text=True))
            self.assertNotIn("Too many failed attempts", res.get_data(as_text=True))

        # 5th attempt
        self._login(c, unknown_id, "SomePassword!", follow_redirects=True)

        with app.app_context():
            self.assertTrue(throttling.is_blocked(unknown_id).blocked)

        # 6th attempt -> throttled
        res_blocked = self._login(c, unknown_id, "SomePassword!", follow_redirects=True)
        self.assertEqual(res_blocked.status_code, 200)
        html = res_blocked.get_data(as_text=True)
        self.assertIn("Too many failed attempts. Try again in", html)
        self.assertNotIn("Invalid PRN, email, or password.", html)

    # 8. Failures across PRN, email, and username of the same student share one counter
    def test_08_shared_counter_across_prn_email_and_username(self):
        """
        Failures made via PRN, email, and username of the SAME student share one counter.
        2 via PRN + 2 via email + 1 via username = 5 failures => next attempt by any of the three is blocked.
        """
        c = app.test_client()

        # 2 failures via PRN
        self._login(c, "PRN2026101", "WrongPassword1!", follow_redirects=True)
        self._login(c, "PRN2026101", "WrongPassword2!", follow_redirects=True)

        # 2 failures via Email
        self._login(c, "rahul@college.edu", "WrongPassword3!", follow_redirects=True)
        self._login(c, "rahul@college.edu", "WrongPassword4!", follow_redirects=True)

        # 1 failure via Username (total = 5)
        self._login(c, "rahul_sharma", "WrongPassword5!", follow_redirects=True)

        with app.app_context():
            # Account is throttled under canonical identifier
            self.assertTrue(throttling.is_blocked("PRN2026101").blocked)

        # Any subsequent attempt via PRN is blocked
        res_prn = self._login(c, "PRN2026101", "StudentPassword123", follow_redirects=True)
        self.assertIn("Too many failed attempts. Try again in", res_prn.get_data(as_text=True))

        # Any subsequent attempt via Email is blocked
        res_email = self._login(c, "rahul@college.edu", "StudentPassword123", follow_redirects=True)
        self.assertIn("Too many failed attempts. Try again in", res_email.get_data(as_text=True))

        # Any subsequent attempt via Username is blocked
        res_user = self._login(c, "rahul_sharma", "StudentPassword123", follow_redirects=True)
        self.assertIn("Too many failed attempts. Try again in", res_user.get_data(as_text=True))

    # 9. Automatic pruning of rows older than 24h
    def test_09_old_records_pruned_after_24h(self):
        """Failed attempts older than 24h are deleted upon recording new failures."""
        with app.app_context():
            old_time = datetime.now() - timedelta(hours=25)
            old_attempt = LoginAttempt(
                identifier="prn2026101",
                ip_address="127.0.0.1",
                created_at=old_time,
            )
            db.session.add(old_attempt)
            db.session.commit()

            self.assertEqual(LoginAttempt.query.filter_by(identifier="prn2026101").count(), 1)

            # Record a new failure which triggers pruning
            throttling.record_failure("PRN2026101", ip_address="127.0.0.1")

            # Only the new record should exist; old one pruned
            records = LoginAttempt.query.filter_by(identifier="prn2026101").all()
            self.assertEqual(len(records), 1)
            self.assertGreater(records[0].created_at, datetime.now() - timedelta(minutes=1))
