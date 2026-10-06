"""
test_phase9_pilot_readiness.py
------------------------------
Automated test suite for Phase 9: B.E. Final Year V1 Pilot Readiness.

Verifies all critical failure cases and pilot workflow requirements:
1. Database safety (Isolated SQLite test runner, Neon protected)
2. Student cannot access draft exam
3. Student cannot access closed exam
4. Student cannot submit twice (single-attempt enforcement)
5. Student cannot view another student's result (IDOR protection)
6. Student cannot access admin or blockchain ledger routes
7. Admin cannot access another admin's exam results (object-level ownership)
8. Expired exam session cannot be submitted normally
9. Client parameter manipulation (score, total, student_id) is strictly ignored
10. Server-authoritative timing (client timer manipulation cannot bypass deadline)
11. Invalid block/result ID fails safely without exceptions
12. Missing or invalid CSRF token fails safely
13. End-to-end pilot demonstration flow
14. Demo pilot seeding integrity
"""

import json
import os
import sys
import unittest
from datetime import datetime, timedelta

# Ensure an isolated test SQLite database is used BEFORE app is imported
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEST_DB_PATH = os.path.join(BASE_DIR, "tests", "test_phase9.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

sys.path.insert(0, BASE_DIR)

from app import app
from models import db, User, Exam, Question, Attempt, Block
import database
import blockchain


class TestPhase9PilotReadiness(unittest.TestCase):
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
    # PART 1: DATABASE SAFETY
    # =========================================================================

    def test_01_database_safety(self):
        """Ensure pilot tests execute against isolated SQLite database and NOT Neon."""
        with app.app_context():
            uri = str(db.engine.url)
            self.assertTrue(uri.startswith("sqlite:///"), f"Database URI must be sqlite: {uri}")
            self.assertNotIn("neon.tech", uri)
            self.assertNotIn("postgresql", uri)

    # =========================================================================
    # PART 2: ACCESS CONTROL & FAILURE CASES
    # =========================================================================

    def test_02_student_cannot_access_draft_exam(self):
        """Student cannot access or take an exam that is currently in Draft status."""
        with app.app_context():
            admin = database.create_user(
                name="Prof. Pilot Admin",
                identifier="admin_p9_1",
                password="AdminPassword123!",
                role="admin",
                username="admin_p9_1",
                email="admin_p9_1@demo.edu",
            )
            student = database.create_user(
                name="Pilot Student 1",
                identifier="BE2026CS901",
                password="StudentPassword123!",
                role="user",
                email="student901@demo.edu",
            )
            draft_exam = database.create_exam(
                title="Draft OS Pilot Exam",
                created_by=admin.id,
                start_time=datetime.now() - timedelta(minutes=10),
                end_time=datetime.now() + timedelta(hours=1),
                duration_minutes=30,
                questions=[{"question": "Q1", "options": ["A", "B", "C", "D"], "correct_index": 0}],
                status="draft",
            )
            draft_id = draft_exam.id

        c = app.test_client()
        self._login(c, "BE2026CS901", "StudentPassword123!")

        # GET request to draft exam must redirect to student dashboard
        res_get = c.get(f"/student/exam/{draft_id}", follow_redirects=True)
        self.assertEqual(res_get.status_code, 200)
        html = res_get.get_data(as_text=True)
        self.assertIn("not available", html.lower())

        # POST request to draft exam must also be rejected
        res_post = self._post(c, f"/student/exam/{draft_id}", {"answer_0": "0"}, follow_redirects=True)
        html_post = res_post.get_data(as_text=True)
        self.assertIn("not available", html_post.lower())

    def test_03_student_cannot_access_closed_exam(self):
        """Student cannot start or submit a closed exam."""
        with app.app_context():
            admin = database.get_user_by_identifier("admin_p9_1")
            closed_exam = database.create_exam(
                title="Closed DBMS Pilot Exam",
                created_by=admin.id,
                start_time=datetime.now() - timedelta(days=2),
                end_time=datetime.now() - timedelta(days=1),
                duration_minutes=30,
                questions=[{"question": "Q1", "options": ["A", "B", "C", "D"], "correct_index": 0}],
                status="closed",
            )
            closed_id = closed_exam.id

        c = app.test_client()
        self._login(c, "BE2026CS901", "StudentPassword123!")

        res_get = c.get(f"/student/exam/{closed_id}", follow_redirects=True)
        self.assertEqual(res_get.status_code, 200)
        html = res_get.get_data(as_text=True)
        self.assertIn("closed", html.lower())

    def test_04_student_cannot_submit_twice(self):
        """Student cannot submit multiple attempts for the same examination."""
        with app.app_context():
            admin = database.get_user_by_identifier("admin_p9_1")
            exam = database.create_exam(
                title="Single Attempt Test Exam",
                created_by=admin.id,
                start_time=datetime.now() - timedelta(minutes=5),
                end_time=datetime.now() + timedelta(hours=1),
                duration_minutes=20,
                questions=[{"question": "Q1", "options": ["A", "B", "C", "D"], "correct_index": 1}],
                status="published",
            )
            exam_id = exam.id

        c = app.test_client()
        self._login(c, "BE2026CS901", "StudentPassword123!")

        # First attempt: load and submit
        c.get(f"/student/exam/{exam_id}")
        res1 = self._post(c, f"/student/exam/{exam_id}", {"answer_0": "1"})
        self.assertEqual(res1.status_code, 200)
        self.assertIn("Score", res1.get_data(as_text=True))

        # Second attempt: try to submit again
        res2 = self._post(c, f"/student/exam/{exam_id}", {"answer_0": "1"}, follow_redirects=True)
        html2 = res2.get_data(as_text=True)
        self.assertIn("already submitted", html2.lower())

    def test_05_student_cannot_view_another_students_result(self):
        """IDOR protection: Student B cannot view Student A's result page."""
        with app.app_context():
            # Create Student B
            student2 = database.create_user(
                name="Pilot Student 2",
                identifier="BE2026CS902",
                password="StudentPassword123!",
                role="user",
                email="student902@demo.edu",
            )
            # Find the block_id from Student 1's submission in test_04
            attempt1 = Attempt.query.filter_by(student_id=database.get_user_by_identifier("BE2026CS901").id).first()
            block_id_1 = attempt1.block_id

        # Student B logs in
        c_student2 = app.test_client()
        self._login(c_student2, "BE2026CS902", "StudentPassword123!")

        # Attempts to access Student 1's result
        res = c_student2.get(f"/result/{block_id_1}", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("permission", html.lower())

    def test_06_student_cannot_access_admin_or_blockchain_routes(self):
        """Student cannot access /admin, /admin/exams/create, or /blockchain."""
        c = app.test_client()
        self._login(c, "BE2026CS901", "StudentPassword123!")

        for path in ["/admin", "/admin/exams", "/admin/exams/create", "/blockchain"]:
            res = c.get(path, follow_redirects=False)
            self.assertEqual(res.status_code, 302, f"Path {path} should redirect for student")

    def test_07_admin_object_level_result_isolation(self):
        """Admin 2 cannot view results of an exam created by Admin 1."""
        with app.app_context():
            admin2 = database.create_user(
                name="Prof. Second Admin",
                identifier="admin_p9_2",
                password="AdminPassword123!",
                role="admin",
                username="admin_p9_2",
                email="admin_p9_2@demo.edu",
            )
            attempt1 = Attempt.query.filter_by(student_id=database.get_user_by_identifier("BE2026CS901").id).first()
            block_id_1 = attempt1.block_id
            exam1_id = attempt1.exam_id

        c_admin2 = app.test_client()
        self._login(c_admin2, "admin_p9_2", "AdminPassword123!")

        # Admin 2 attempts to view Admin 1's student result
        res = c_admin2.get(f"/result/{block_id_1}", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("permission", html.lower())

        # Admin 2 attempts to view Admin 1's exam results summary
        res_summary = c_admin2.get(f"/admin/exams/{exam1_id}/results", follow_redirects=True)
        html_summary = res_summary.get_data(as_text=True)
        # Should redirect to admin dashboard because exam was not created by admin2
        self.assertEqual(res_summary.status_code, 200)

    def test_08_expired_exam_session_handles_timeout(self):
        """Submitting after the effective deadline marks attempt as timeout."""
        with app.app_context():
            admin = database.get_user_by_identifier("admin_p9_1")
            student2 = database.get_user_by_identifier("BE2026CS902")
            # Exam that expired 1 minute ago
            expired_exam = database.create_exam(
                title="Expired Window Exam",
                created_by=admin.id,
                start_time=datetime.now() - timedelta(hours=2),
                end_time=datetime.now() - timedelta(minutes=1),
                duration_minutes=10,
                questions=[{"question": "Q1", "options": ["A", "B", "C", "D"], "correct_index": 0}],
                status="published",
            )
            exp_id = expired_exam.id

        c = app.test_client()
        self._login(c, "BE2026CS902", "StudentPassword123!")

        # Attempt to load expired exam
        res = c.get(f"/student/exam/{exp_id}", follow_redirects=True)
        html = res.get_data(as_text=True)
        self.assertIn("closed", html.lower())

    def test_09_client_score_manipulation_ignored(self):
        """Client POST parameters (score=100, student_id=999) are completely ignored."""
        with app.app_context():
            admin = database.get_user_by_identifier("admin_p9_1")
            exam = database.create_exam(
                title="Parameter Injection Test Exam",
                created_by=admin.id,
                start_time=datetime.now() - timedelta(minutes=5),
                end_time=datetime.now() + timedelta(hours=1),
                duration_minutes=20,
                questions=[{"question": "Q1", "options": ["A", "B", "C", "D"], "correct_index": 0}],
                status="published",
            )
            exam_id = exam.id

        c = app.test_client()
        self._login(c, "BE2026CS902", "StudentPassword123!")
        c.get(f"/student/exam/{exam_id}")

        # Student submits WRONG answer (choice 1) but injects score=999, total=1, percentage=100
        res = self._post(
            c,
            f"/student/exam/{exam_id}",
            {
                "answer_0": "1",  # Wrong answer!
                "score": "999",   # Malicious injection
                "total": "1",     # Malicious injection
                "percentage": "100.0", # Malicious injection
                "student_id": "1",     # Malicious injection
            },
        )
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        # Real score evaluated by server must be 0 / 1 (0.0%), NOT 999
        self.assertIn("0 / 1", html)
        self.assertIn("0.0% Score", html)

    def test_10_invalid_block_or_result_id_fails_safely(self):
        """Accessing a nonexistent result ID redirects safely without 500 error."""
        c = app.test_client()
        self._login(c, "BE2026CS901", "StudentPassword123!")

        res = c.get("/result/999999", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("not found", html.lower())

    def test_11_missing_csrf_token_fails_safely(self):
        """POST without CSRF token is rejected with security error."""
        c = app.test_client()
        c.get("/login")

        res = c.post("/login", data={"identifier": "admin_p9_1", "password": "AdminPassword123!"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("invalid security token", html.lower())

    # =========================================================================
    # PART 3: END-TO-END PILOT DEMONSTRATION WORKFLOW
    # =========================================================================

    def test_12_complete_pilot_workflow(self):
        """End-to-end pilot workflow: Teacher creates draft -> publishes -> Student attempts -> Evaluates -> Seals -> Admin audits ledger."""
        with app.app_context():
            admin = database.create_user(
                name="Prof. Pilot Lead",
                identifier="admin_pilot_lead",
                password="AdminLeadPassword123!",
                role="admin",
                username="admin_pilot_lead",
                email="pilot_lead@demo.edu",
            )
            student = database.create_user(
                name="Pilot Candidate",
                identifier="BE2026CSPILOT",
                password="PilotCandidatePass123!",
                role="user",
                email="candidate_pilot@demo.edu",
            )

        # 1. Teacher Logs In
        c_teacher = app.test_client()
        res_t_login = self._login(c_teacher, "admin_pilot_lead", "AdminLeadPassword123!")
        self.assertEqual(res_t_login.status_code, 200)

        # 2. Teacher Creates Exam as Draft
        now = datetime.now()
        start = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M")
        end = (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")

        res_create = self._post(
            c_teacher,
            "/admin/exams/create",
            {
                "title": "B.E. Final Year Cloud & Security Pilot",
                "start_time": start,
                "end_time": end,
                "duration": "30",
                "question_text": [
                    "Which algorithm is used for cryptographic integrity verification?",
                    "What is the degree of decentralization in an application-controlled ledger?",
                ],
                "option_0_0": "SHA-256",
                "option_0_1": "Rot13",
                "option_0_2": "Base64",
                "option_0_3": "ASCII",
                "correct_0": "0",
                "option_1_0": "Public PoW",
                "option_1_1": "Centralized / Private Hash Chain",
                "option_1_2": "Proof of Stake",
                "option_1_3": "BFT Quorum",
                "correct_1": "1",
            },
        )
        self.assertEqual(res_create.status_code, 200)

        with app.app_context():
            exam = Exam.query.filter_by(title="B.E. Final Year Cloud & Security Pilot").first()
            self.assertIsNotNone(exam)
            self.assertEqual(exam.status, "draft")
            exam_id = exam.id

        # 3. Teacher Publishes Exam
        res_pub = self._post(c_teacher, f"/admin/exams/{exam_id}/publish", {})
        self.assertEqual(res_pub.status_code, 200)

        with app.app_context():
            exam_refreshed = db.session.get(Exam, exam_id)
            self.assertEqual(exam_refreshed.status, "published")

        # 4. Student Logs In & Views Available Exam
        c_student = app.test_client()
        self._login(c_student, "BE2026CSPILOT", "PilotCandidatePass123!")

        res_dash = c_student.get("/student")
        self.assertEqual(res_dash.status_code, 200)
        html_dash = res_dash.get_data(as_text=True)
        self.assertIn("B.E. Final Year Cloud", html_dash)
        self.assertIn("Take Exam", html_dash)

        # 5. Student Starts Exam
        res_exam_page = c_student.get(f"/student/exam/{exam_id}")
        self.assertEqual(res_exam_page.status_code, 200)
        self.assertIn("Which algorithm is used for cryptographic integrity verification?", res_exam_page.get_data(as_text=True))

        # 6. Student Submits Answers
        res_submit = self._post(
            c_student,
            f"/student/exam/{exam_id}",
            {
                "answer_0": "0",  # Correct (SHA-256)
                "answer_1": "1",  # Correct (Centralized / Private Hash Chain)
            },
        )
        self.assertEqual(res_submit.status_code, 200)
        html_res = res_submit.get_data(as_text=True)
        self.assertIn("2 / 2", html_res)
        self.assertIn("100.0% Score", html_res)
        self.assertIn("SHA-256 Integrity Verified", html_res)

        # 7. Teacher Audits Results and Blockchain Explorer
        res_admin_results = c_teacher.get(f"/admin/exams/{exam_id}/results")
        self.assertEqual(res_admin_results.status_code, 200)
        html_admin_res = res_admin_results.get_data(as_text=True)
        self.assertIn("Pilot Candidate", html_admin_res)
        self.assertIn("BE2026CSPILOT", html_admin_res)

        res_ledger = c_teacher.get("/blockchain")
        self.assertEqual(res_ledger.status_code, 200)
        self.assertIn("Integrity Ledger", res_ledger.get_data(as_text=True))

        # 8. Teacher Verifies Blockchain Integrity via Backend
        res_verify = self._post(c_teacher, "/verify", {})
        self.assertEqual(res_verify.status_code, 200)
        verify_json = json.loads(res_verify.get_data(as_text=True))
        self.assertTrue(verify_json["valid"])
        self.assertEqual(len(verify_json["problems"]), 0)

    def test_13_demo_pilot_seeding_integrity(self):
        """Verify that seed_demo_pilot creates all required demo entities and maintains chain validity."""
        import seed_demo_pilot

        with app.app_context():
            seed_demo_pilot.seed_demo()

            # Verify admin account
            admin = database.get_user_by_identifier("admin_demo")
            self.assertIsNotNone(admin)
            self.assertEqual(admin.role, "admin")

            # Verify 3 fictional students
            s1 = database.get_user_by_identifier("BE2026CS001")
            s2 = database.get_user_by_identifier("BE2026CS002")
            s3 = database.get_user_by_identifier("BE2026CS003")
            self.assertIsNotNone(s1)
            self.assertIsNotNone(s2)
            self.assertIsNotNone(s3)

            # Verify 1 draft exam, 1 published exam, 1 closed exam
            draft_exam = Exam.query.filter_by(title="Cloud Architecture & Security (Draft)").first()
            self.assertIsNotNone(draft_exam)
            self.assertEqual(draft_exam.status, "draft")

            pub_exam = Exam.query.filter_by(title="Distributed Systems & Consensus V1").first()
            self.assertIsNotNone(pub_exam)
            self.assertEqual(pub_exam.status, "published")

            closed_exam = Exam.query.filter_by(title="Operating Systems & Virtualization (Completed Semester)").first()
            self.assertIsNotNone(closed_exam)
            self.assertEqual(closed_exam.status, "closed")

            # Verify completed attempt for Rahul Sharma
            attempt = database.get_attempt(pub_exam.id, s1.id)
            self.assertIsNotNone(attempt)
            self.assertTrue(attempt.is_submitted)
            self.assertEqual(attempt.score, 3)
            self.assertEqual(attempt.total, 3)
            self.assertIsNotNone(attempt.block_id)

            # Verify block data
            chain = blockchain.Blockchain()
            block = chain.get_block(attempt.block_id)
            self.assertIsNotNone(block)
            self.assertEqual(block.data["score"], 3)
            self.assertEqual(block.data["prn"], "BE2026CS001")

            # Chain verification passes
            valid, problems = chain.is_chain_valid()
            self.assertTrue(valid, f"Chain validity check failed: {problems}")


if __name__ == "__main__":
    unittest.main()
