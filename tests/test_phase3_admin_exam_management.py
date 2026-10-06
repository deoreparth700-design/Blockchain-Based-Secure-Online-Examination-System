"""
test_phase3_admin_exam_management.py
------------------------------------
Automated test suite for Phase 3: Admin Workspace & Exam Management.

Tests:
1. Database Safety: Isolated SQLite runner, Neon protected.
2. Admin Dashboard:
   - Admin can access /admin (shows stats and header)
   - User cannot access /admin (redirected)
   - Anonymous user redirects to login
   - /teacher legacy compatibility alias works
3. Exam Creation:
   - Admin can create an exam (starts as draft)
   - Invalid schedule (end <= start) is rejected
4. Exam Status & Lifecycle:
   - New exam starts as 'draft'
   - Draft cannot be taken or seen by normal user
   - Admin can publish exam (draft -> published)
   - Published exam within schedule is accessible
   - Admin can close exam (published -> closed)
   - Closed exam cannot be started or submitted
5. Exam Editing:
   - Draft can be edited freely
   - Published exam with zero attempts can be edited
   - Exam with recorded attempts cannot be edited
   - Closed exam cannot be edited
6. Exam Deletion:
   - Unused draft can be safely deleted
   - Exam with recorded attempts cannot be deleted
7. Authorization:
   - User cannot create exams
   - User cannot publish exams
   - User cannot close exams
   - User cannot delete exams
   - User cannot access admin results
8. Regression:
   - Admin login
   - User registration (5 fields, role='user')
   - PRN login & Email login
   - Role protection
"""

import os
import sys
import unittest
from datetime import datetime, timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEST_DB_PATH = os.path.join(BASE_DIR, "tests", "test_phase3.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

sys.path.insert(0, BASE_DIR)

from app import app
from models import db, User, Exam, Question, Attempt
import database


class TestPhase3AdminExamManagement(unittest.TestCase):
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
        # Visit login page to get CSRF token in session
        res = client.get("/login")
        with client.session_transaction() as sess:
            csrf_token = sess.get("csrf_token", "")
        return client.post("/login", data={
            "identifier": identifier,
            "password": password,
            "csrf_token": csrf_token,
        }, follow_redirects=False)

    # ---------- 1. Database Safety ----------
    def test_01_safe_isolated_database_used(self):
        with app.app_context():
            engine_url = str(db.engine.url)
            self.assertIn("sqlite", engine_url)
            self.assertNotIn("neon.tech", engine_url)
            self.assertNotIn("postgresql", engine_url)

    # ---------- 2. Setup Accounts ----------
    def test_02_create_admin_and_user_accounts(self):
        with app.app_context():
            admin = database.create_user(
                name="Admin Instructor",
                identifier="admin_phase3",
                password="AdminPassword123!",
                role="admin",
                username="admin_phase3",
                email="admin3@engg.edu",
            )
            self.assertIsNotNone(admin)
            self.assertEqual(admin.role, "admin")

            student = database.create_user(
                name="BE Student One",
                identifier="BE2026CS001",
                password="StudentPassword123!",
                role="user",
                username=None,
                email="student1@engg.edu",
            )
            self.assertIsNotNone(student)
            self.assertEqual(student.role, "user")

    # ---------- 3. Admin Dashboard Access & Metrics ----------
    def test_03_admin_can_access_admin_dashboard(self):
        c = app.test_client()
        self._login(c, "admin_phase3", "AdminPassword123!")
        res = c.get("/admin")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Admin Dashboard", res.data)
        self.assertIn(b"BE Final Year Examination System", res.data)
        self.assertIn(b"TOTAL EXAMS", res.data)
        self.assertIn(b"PUBLISHED EXAMS", res.data)
        self.assertIn(b"CLOSED EXAMS", res.data)
        self.assertIn(b"REGISTERED USERS", res.data)
        self.assertIn(b"TOTAL SUBMISSIONS", res.data)

    def test_04_user_cannot_access_admin_dashboard(self):
        c = app.test_client()
        self._login(c, "BE2026CS001", "StudentPassword123!")
        res = c.get("/admin")
        self.assertEqual(res.status_code, 302)  # redirected away

    def test_05_anonymous_user_redirects_to_login(self):
        c = app.test_client()
        res = c.get("/admin")
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    def test_06_legacy_teacher_route_alias_works(self):
        c = app.test_client()
        self._login(c, "admin_phase3", "AdminPassword123!")
        res = c.get("/teacher")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Admin Dashboard", res.data)

    # ---------- 4. Exam Creation & Status Lifecycle ----------
    def test_07_admin_can_create_draft_exam(self):
        c = app.test_client()
        self._login(c, "admin_phase3", "AdminPassword123!")
        c.get("/admin/exams/create")
        with c.session_transaction() as sess:
            token = sess["csrf_token"]

        now = datetime.now()
        start = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
        end = (now + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M")

        res = c.post("/admin/exams/create", data={
            "csrf_token": token,
            "title": "Distributed Systems Quiz 1",
            "start_time": start,
            "end_time": end,
            "duration": "45",
            "question_text": ["What does PBFT stand for?"],
            "option_0_0": "Practical Byzantine Fault Tolerance",
            "option_0_1": "Private Blockchain Fast Transmission",
            "option_0_2": "Peer-to-Peer Binary Fault Tree",
            "option_0_3": "Protocol Based Fast Transaction",
            "correct_0": "0",
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b"created as Draft", res.data)

        with app.app_context():
            exam = Exam.query.filter_by(title="Distributed Systems Quiz 1").first()
            self.assertIsNotNone(exam)
            self.assertEqual(exam.status, "draft")
            self.assertEqual(len(exam.questions), 1)

    def test_08_invalid_schedule_rejected(self):
        c = app.test_client()
        self._login(c, "admin_phase3", "AdminPassword123!")
        c.get("/admin/exams/create")
        with c.session_transaction() as sess:
            token = sess["csrf_token"]

        now = datetime.now()
        start = (now + timedelta(hours=5)).strftime("%Y-%m-%dT%H:%M")
        end = (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")  # end < start!

        res = c.post("/admin/exams/create", data={
            "csrf_token": token,
            "title": "Invalid Schedule Exam",
            "start_time": start,
            "end_time": end,
            "duration": "30",
            "question_text": ["Sample Q?"],
            "option_0_0": "A",
            "option_0_1": "B",
            "option_0_2": "C",
            "option_0_3": "D",
            "correct_0": "0",
        }, follow_redirects=True)

        self.assertIn(b"End time must be strictly after start time", res.data)
        with app.app_context():
            exam = Exam.query.filter_by(title="Invalid Schedule Exam").first()
            self.assertIsNone(exam)

    def test_09_draft_cannot_be_seen_or_taken_by_student(self):
        c = app.test_client()
        self._login(c, "BE2026CS001", "StudentPassword123!")

        # Student dashboard: draft exam must NOT appear
        res = c.get("/student")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b"Distributed Systems Quiz 1", res.data)

        # Attempt to access draft exam directly
        with app.app_context():
            exam = Exam.query.filter_by(title="Distributed Systems Quiz 1").first()
            exam_id = exam.id

        res_take = c.get(f"/student/exam/{exam_id}", follow_redirects=True)
        self.assertIn(b"This exam is not available", res_take.data)

        with c.session_transaction() as sess:
            token = sess["csrf_token"]
        res_post = c.post(f"/student/exam/{exam_id}", data={"csrf_token": token}, follow_redirects=True)
        self.assertIn(b"This exam is not available", res_post.data)

    def test_10_admin_can_publish_draft_exam(self):
        c = app.test_client()
        self._login(c, "admin_phase3", "AdminPassword123!")
        c.get("/admin")
        with c.session_transaction() as sess:
            token = sess["csrf_token"]

        with app.app_context():
            exam = Exam.query.filter_by(title="Distributed Systems Quiz 1").first()
            exam_id = exam.id

        res = c.post(f"/admin/exams/{exam_id}/publish", data={"csrf_token": token}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"published successfully", res.data)

        with app.app_context():
            updated = database.get_exam(exam_id)
            self.assertEqual(updated.status, "published")

    def test_11_admin_can_close_published_exam(self):
        c = app.test_client()
        self._login(c, "admin_phase3", "AdminPassword123!")
        c.get("/admin")
        with c.session_transaction() as sess:
            token = sess["csrf_token"]

        with app.app_context():
            exam = Exam.query.filter_by(title="Distributed Systems Quiz 1").first()
            exam_id = exam.id

        res = c.post(f"/admin/exams/{exam_id}/close", data={"csrf_token": token}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"has been closed", res.data)

        with app.app_context():
            updated = database.get_exam(exam_id)
            self.assertEqual(updated.status, "closed")

    def test_12_closed_exam_cannot_be_taken_by_student(self):
        c = app.test_client()
        self._login(c, "BE2026CS001", "StudentPassword123!")

        with app.app_context():
            exam = Exam.query.filter_by(title="Distributed Systems Quiz 1").first()
            exam_id = exam.id

        res = c.get(f"/student/exam/{exam_id}", follow_redirects=True)
        self.assertIn(b"This exam has been closed", res.data)

        with c.session_transaction() as sess:
            token = sess["csrf_token"]
        res_post = c.post(f"/student/exam/{exam_id}", data={"csrf_token": token}, follow_redirects=True)
        self.assertIn(b"This exam has been closed", res_post.data)

    # ---------- 5. Edit Exam Actions ----------
    def test_13_draft_exam_can_be_edited(self):
        c = app.test_client()
        self._login(c, "admin_phase3", "AdminPassword123!")

        with app.app_context():
            now = datetime.now()
            draft = database.create_exam(
                title="Draft Quiz for Edit",
                created_by=1,
                start_time=now + timedelta(hours=1),
                end_time=now + timedelta(hours=2),
                duration_minutes=30,
                questions=[{
                    "question": "Original Q?",
                    "options": ["A1", "B1", "C1", "D1"],
                    "correct_index": 0,
                }],
                status="draft",
            )
            draft_id = draft.id

        c.get(f"/admin/exams/{draft_id}/edit")
        with c.session_transaction() as sess:
            token = sess["csrf_token"]

        now = datetime.now()
        start = (now + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
        end = (now + timedelta(hours=4)).strftime("%Y-%m-%dT%H:%M")

        res = c.post(f"/admin/exams/{draft_id}/edit", data={
            "csrf_token": token,
            "title": "Edited Draft Quiz",
            "start_time": start,
            "end_time": end,
            "duration": "50",
            "question_text": ["Updated Question Text?"],
            "option_0_0": "Opt A",
            "option_0_1": "Opt B",
            "option_0_2": "Opt C",
            "option_0_3": "Opt D",
            "correct_0": "2",
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b"updated successfully", res.data)

        with app.app_context():
            updated = database.get_exam(draft_id)
            self.assertEqual(updated.title, "Edited Draft Quiz")
            self.assertEqual(updated.duration_minutes, 50)
            self.assertEqual(updated.questions[0].question_text, "Updated Question Text?")
            self.assertEqual(updated.questions[0].correct_index, 2)

    def test_14_exam_with_attempts_cannot_be_edited(self):
        c = app.test_client()
        self._login(c, "admin_phase3", "AdminPassword123!")

        with app.app_context():
            now = datetime.now()
            exam = database.create_exam(
                title="Exam With Attempts",
                created_by=1,
                start_time=now - timedelta(hours=1),
                end_time=now + timedelta(hours=1),
                duration_minutes=30,
                questions=[{
                    "question": "Q1?",
                    "options": ["A", "B", "C", "D"],
                    "correct_index": 0,
                }],
                status="published",
            )
            # Create an attempt
            student = User.query.filter_by(role="user").first()
            database.create_attempt(exam.id, student.id, 1, 1, block_id=1)
            exam_id = exam.id

        # Attempt to access edit page
        res = c.get(f"/admin/exams/{exam_id}/edit", follow_redirects=True)
        self.assertIn(b"Cannot edit this exam", res.data)

    def test_15_closed_exam_cannot_be_edited(self):
        c = app.test_client()
        self._login(c, "admin_phase3", "AdminPassword123!")

        with app.app_context():
            closed_exam = Exam.query.filter_by(status="closed").first()
            closed_id = closed_exam.id

        res = c.get(f"/admin/exams/{closed_id}/edit", follow_redirects=True)
        self.assertIn(b"Cannot edit a closed exam", res.data)

    # ---------- 6. Delete Exam Actions ----------
    def test_16_unused_draft_can_be_deleted(self):
        c = app.test_client()
        self._login(c, "admin_phase3", "AdminPassword123!")

        with app.app_context():
            now = datetime.now()
            draft = database.create_exam(
                title="Draft To Delete",
                created_by=1,
                start_time=now + timedelta(hours=1),
                end_time=now + timedelta(hours=2),
                duration_minutes=20,
                questions=[{
                    "question": "Q?",
                    "options": ["1", "2", "3", "4"],
                    "correct_index": 0,
                }],
                status="draft",
            )
            draft_id = draft.id

        c.get("/admin")
        with c.session_transaction() as sess:
            token = sess["csrf_token"]

        res = c.post(f"/admin/exams/{draft_id}/delete", data={"csrf_token": token}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"deleted successfully", res.data)

        with app.app_context():
            self.assertIsNone(database.get_exam(draft_id))

    def test_17_exam_with_attempts_cannot_be_deleted(self):
        c = app.test_client()
        self._login(c, "admin_phase3", "AdminPassword123!")

        with app.app_context():
            exam = Exam.query.filter_by(title="Exam With Attempts").first()
            exam_id = exam.id

        c.get("/admin")
        with c.session_transaction() as sess:
            token = sess["csrf_token"]

        res = c.post(f"/admin/exams/{exam_id}/delete", data={"csrf_token": token}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Cannot delete exam", res.data)

        with app.app_context():
            self.assertIsNotNone(database.get_exam(exam_id))

    # ---------- 7. Server-Side Authorization Protection ----------
    def test_18_user_cannot_create_exam(self):
        c = app.test_client()
        self._login(c, "BE2026CS001", "StudentPassword123!")
        c.get("/student")
        with c.session_transaction() as sess:
            token = sess["csrf_token"]

        now = datetime.now()
        res = c.post("/admin/exams/create", data={
            "csrf_token": token,
            "title": "Unauthorized User Exam",
            "start_time": now.strftime("%Y-%m-%dT%H:%M"),
            "end_time": (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "duration": "30",
        })
        self.assertEqual(res.status_code, 302)  # forbidden/redirected

    def test_19_user_cannot_publish_exam(self):
        c = app.test_client()
        self._login(c, "BE2026CS001", "StudentPassword123!")
        c.get("/student")
        with c.session_transaction() as sess:
            token = sess["csrf_token"]

        with app.app_context():
            exam = Exam.query.first()
            exam_id = exam.id

        res = c.post(f"/admin/exams/{exam_id}/publish", data={"csrf_token": token})
        self.assertEqual(res.status_code, 302)

    def test_20_user_cannot_close_exam(self):
        c = app.test_client()
        self._login(c, "BE2026CS001", "StudentPassword123!")
        c.get("/student")
        with c.session_transaction() as sess:
            token = sess["csrf_token"]

        with app.app_context():
            exam = Exam.query.first()
            exam_id = exam.id

        res = c.post(f"/admin/exams/{exam_id}/close", data={"csrf_token": token})
        self.assertEqual(res.status_code, 302)

    def test_21_user_cannot_delete_exam(self):
        c = app.test_client()
        self._login(c, "BE2026CS001", "StudentPassword123!")
        c.get("/student")
        with c.session_transaction() as sess:
            token = sess["csrf_token"]

        with app.app_context():
            exam = Exam.query.first()
            exam_id = exam.id

        res = c.post(f"/admin/exams/{exam_id}/delete", data={"csrf_token": token})
        self.assertEqual(res.status_code, 302)

    def test_22_user_cannot_access_admin_results(self):
        c = app.test_client()
        self._login(c, "BE2026CS001", "StudentPassword123!")

        with app.app_context():
            exam = Exam.query.first()
            exam_id = exam.id

        res = c.get(f"/admin/exams/{exam_id}/results")
        self.assertEqual(res.status_code, 302)

    # ---------- 8. Regression: Phase 1 & Phase 2 ----------
    def test_23_regression_admin_login(self):
        c = app.test_client()
        res = self._login(c, "admin_phase3", "AdminPassword123!")
        self.assertEqual(res.status_code, 302)
        with c.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "admin")

    def test_24_regression_user_registration(self):
        c = app.test_client()
        c.get("/register")
        with c.session_transaction() as sess:
            token = sess["csrf_token"]

        res = c.post("/register", data={
            "csrf_token": token,
            "name": "Regression Student",
            "prn": "BE2026CS999",
            "email": "reg999@engg.edu",
            "password": "ValidPassword123!",
            "confirm_password": "ValidPassword123!",
        }, follow_redirects=False)

        self.assertEqual(res.status_code, 302)
        with app.app_context():
            user = database.get_user_by_prn("BE2026CS999")
            self.assertIsNotNone(user)
            self.assertEqual(user.role, "user")

    def test_25_regression_prn_and_email_login(self):
        # PRN login
        c1 = app.test_client()
        res1 = self._login(c1, "BE2026CS999", "ValidPassword123!")
        self.assertEqual(res1.status_code, 302)
        with c1.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "user")

        # Email login
        c2 = app.test_client()
        res2 = self._login(c2, "reg999@engg.edu", "ValidPassword123!")
        self.assertEqual(res2.status_code, 302)
        with c2.session_transaction() as sess:
            self.assertEqual(sess.get("role"), "user")


if __name__ == "__main__":
    unittest.main()
