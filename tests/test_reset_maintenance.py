"""
tests/test_reset_maintenance.py
-------------------------------
Regression tests covering the examination platform reset maintenance workflow:
1. Valid admin username + known password -> successful login
2. Valid student PRN + password -> successful login (for newly registered student)
3. Deleted student account -> cannot log in
4. Admin account remains after student reset
5. Admin role remains 'admin'
6. Wrong admin password -> rejected
7. No student accounts remain after reset
8. No orphaned student attempts/results remain
"""

import os
import sys
import unittest
from datetime import datetime, timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEST_DB_PATH = os.path.join(BASE_DIR, "tests", "test_reset_maintenance.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

sys.path.insert(0, BASE_DIR)

from app import app
from models import db, User, Exam, Question, Attempt, Block
import database
from blockchain import Blockchain
from scripts.reset_student_accounts import reset_student_accounts


class TestResetMaintenance(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.create_all()

            # Seed Admin Account
            cls.admin = database.create_user(
                name="Prof. Amit Kulkarni",
                identifier="admin_demo",
                username="admin_demo",
                email="amit.kulkarni@demo.edu",
                password="OldAdminPassword123!",
                role="admin",
            )

            # Seed Teacher compatibility user
            cls.teacher = database.create_user(
                name="Exam Teacher",
                identifier="teacher_demo",
                username="teacher_demo",
                email="teacher@demo.edu",
                password="TeacherPassword123!",
                role="admin",
            )

            exam = database.create_exam(
                title="Distributed Systems & Blockchain",
                created_by=cls.teacher.id,
                start_time=datetime.now() - timedelta(hours=1),
                end_time=datetime.now() + timedelta(hours=2),
                duration_minutes=60,
                questions=[
                    {
                        "question": "What is the consensus mechanism in Bitcoin?",
                        "options": ["Proof of Work", "Proof of Stake", "Raft", "Paxos"],
                        "correct_index": 0,
                    },
                    {
                        "question": "Which SHA algorithm is standard for blocks?",
                        "options": ["MD5", "SHA-1", "SHA-256", "SHA-512"],
                        "correct_index": 2,
                    },
                ],
                status="published",
            )
            cls.exam_id = exam.id

            # Seed 2 student accounts
            old_student_1 = database.create_user(
                name="Karan Patel",
                identifier="2024-BE-4822",
                email="karan.patel@demo.edu",
                password="OldStudentPass123!",
                role="user",
                username=None,
            )
            cls.student_1_id = old_student_1.id

            old_student_2 = database.create_user(
                name="Sneha Deshmukh",
                identifier="2024-BE-4854",
                email="sneha.deshmukh@demo.edu",
                password="OldStudentPass123!",
                role="user",
                username=None,
            )
            cls.student_2_id = old_student_2.id

            # Seed Attempt and Block for student 1
            chain = Blockchain()
            block_data = {
                "type": "exam_result",
                "student_name": "Karan Patel",
                "roll_no": "2024-BE-4822",
                "score": 2,
                "total": 2,
            }
            sealed_block = chain.add_block(block_data)

            database.create_attempt(
                exam_id=cls.exam_id,
                student_id=cls.student_1_id,
                score=2,
                total=2,
                block_id=sealed_block.index,
                started_at=datetime.now() - timedelta(minutes=40),
                submitted_at=datetime.now() - timedelta(minutes=10),
            )

            # Pre-verification: Ensure student accounts and attempts exist prior to reset
            assert User.query.filter_by(role="user").count() == 2
            assert Attempt.query.count() == 1
            assert Block.query.filter(Block.id != 0).count() == 1

            # Execute transactional reset using the maintenance script logic
            cls.reset_stats = reset_student_accounts(
                admin_password="AdminDemoPass123!",
                print_summary=False,
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

    def test_01_valid_admin_username_known_password_success(self):
        """1. valid admin username + known password -> successful login."""
        c = app.test_client()
        res = self._login(c, "admin_demo", "AdminDemoPass123!", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Admin Dashboard", html)
        with c.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "admin")
            self.assertEqual(sess.get("identifier"), "admin_demo")

    def test_02_wrong_admin_password_rejected(self):
        """6. wrong admin password -> rejected."""
        c = app.test_client()
        res = self._login(c, "admin_demo", "WrongPassword123!", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Invalid PRN, email, or password.", html)
        with c.session_transaction() as sess:
            self.assertIsNone(sess.get("user_id"))

    def test_03_admin_account_remains_and_role_is_admin(self):
        """4 & 5. admin account remains after student reset & admin role remains 'admin'."""
        with app.app_context():
            admin = database.get_user_by_login("admin_demo")
            self.assertIsNotNone(admin)
            self.assertEqual(admin.role, "admin")
            self.assertEqual(admin.username, "admin_demo")
            self.assertTrue(admin.check_password("AdminDemoPass123!"))

            # Teacher compatibility account also preserved
            teacher = database.get_user_by_login("teacher_demo")
            self.assertIsNotNone(teacher)
            self.assertEqual(teacher.role, "admin")

    def test_04_no_student_accounts_remain_after_reset(self):
        """7. no student accounts remain after reset."""
        with app.app_context():
            student_count = User.query.filter_by(role="user").count()
            self.assertEqual(student_count, 0)
            self.assertEqual(self.reset_stats["students_deleted"], 2)

    def test_05_deleted_student_account_cannot_login(self):
        """3. deleted student account -> cannot log in."""
        c = app.test_client()
        res = self._login(c, "2024-BE-4822", "OldStudentPass123!", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Invalid PRN, email, or password.", html)
        with c.session_transaction() as sess:
            self.assertIsNone(sess.get("user_id"))

    def test_06_no_orphaned_student_attempts_remain(self):
        """8. no orphaned student attempts/results remain."""
        with app.app_context():
            attempt_count = Attempt.query.count()
            self.assertEqual(attempt_count, 0)
            self.assertEqual(self.reset_stats["attempts_deleted"], 1)

    def test_07_no_orphaned_integrity_records_remain(self):
        """Genesis block preserved; student result blocks removed; blockchain valid."""
        with app.app_context():
            genesis_block = Block.query.filter_by(id=0).first()
            self.assertIsNotNone(genesis_block)
            non_genesis_blocks = Block.query.filter(Block.id != 0).count()
            self.assertEqual(non_genesis_blocks, 0)

            chain = Blockchain()
            valid, problems = chain.is_chain_valid()
            self.assertTrue(valid)
            self.assertEqual(len(problems), 0)

    def test_08_exams_and_questions_preserved(self):
        """4. Preserve exam definitions and questions."""
        with app.app_context():
            exam = database.get_exam(self.exam_id)
            self.assertIsNotNone(exam)
            self.assertEqual(exam.title, "Distributed Systems & Blockchain")
            self.assertEqual(len(exam.questions), 2)
            self.assertEqual(exam.status, "published")

    def test_09_fresh_student_registration_and_login(self):
        """2. valid student PRN + password -> successful login for newly registered student."""
        c = app.test_client()

        # Fetch register page for CSRF token
        c.get("/register")
        with c.session_transaction() as sess:
            csrf_token = sess.get("csrf_token", "")

        fresh_prn = "2024-BE-9999"
        fresh_pass = "FreshBatchStudent2026!"
        reg_res = c.post(
            "/register",
            data={
                "name": "Fresh Student",
                "prn": fresh_prn,
                "email": "fresh.student@demo.edu",
                "password": fresh_pass,
                "confirm_password": fresh_pass,
                "csrf_token": csrf_token,
            },
            follow_redirects=True,
        )
        self.assertEqual(reg_res.status_code, 200)
        self.assertIn("Account created successfully", reg_res.get_data(as_text=True))

        # Log in with the fresh student account
        login_res = self._login(c, fresh_prn, fresh_pass, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)
        with c.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "user")
            self.assertEqual(sess.get("identifier"), fresh_prn)
            self.assertEqual(sess.get("name"), "Fresh Student")

    def test_10_teacher_compatibility_route_accessible_by_admin(self):
        """Teacher compatibility route /teacher works through admin authorization."""
        c = app.test_client()
        self._login(c, "admin_demo", "AdminDemoPass123!", follow_redirects=True)
        res = c.get("/teacher", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn("Admin Dashboard", res.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
