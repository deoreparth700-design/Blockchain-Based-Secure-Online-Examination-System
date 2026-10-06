"""
test_phase4_exam_engine.py
--------------------------
Automated test suite for Phase 4: Exam-Taking Engine & Server-Side Timing.

Tests:
1. Exam Access Rules:
   - User cannot start draft exam
   - User cannot start closed exam
   - User cannot start before start_time
   - User cannot start after end_time
   - User can start published exam inside window
2. Attempt Creation & Session Resumption:
   - Starting creates exactly one attempt
   - started_at is populated by server clock
   - Refreshing does not create another attempt
   - started_at does not reset on refresh
3. Timing & Deadline Calculations:
   - Duration deadline: started_at + duration_minutes
   - Global exam end truncation: min(started_at + duration, exam.end_time)
   - Remaining seconds correctly computed on server
4. Submission Protection:
   - Valid submission succeeds, submitted_at populated
   - Partial / unanswered questions handled safely
   - Double-submission rejected (application level & DB level)
   - Second POST cannot modify original score or create second block
5. Timeout & Late Submission Handling:
   - GET after deadline finalizes expired session
   - POST after deadline (+ grace period) rejected as late
   - Client-side countdown is visual only; server clock is authoritative
6. Security & Isolation:
   - Cannot submit for another user
   - Client form parameters cannot alter deadline
"""

import os
import sys
import unittest
from datetime import datetime, timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEST_DB_PATH = os.path.join(BASE_DIR, "tests", "test_phase4.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

sys.path.insert(0, BASE_DIR)

from app import app
from models import db, User, Exam, Question, Attempt
import database


class TestPhase4ExamEngine(unittest.TestCase):
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
        with app.app_context():
            # Clean attempts, questions, exams, users
            Attempt.query.delete()
            Question.query.delete()
            Exam.query.delete()
            User.query.delete()
            db.session.commit()

            # Create test admin
            self.admin = User(
                prn="ADMIN2026",
                email="admin@college.edu",
                role="admin",
                name="Test Admin",
            )
            self.admin.set_password("AdminPass123!")

            # Create test student 1
            self.student1 = User(
                prn="PRN2026001",
                email="student1@college.edu",
                role="user",
                name="Student One",
            )
            self.student1.set_password("StudentPass123!")

            # Create test student 2
            self.student2 = User(
                prn="PRN2026002",
                email="student2@college.edu",
                role="user",
                name="Student Two",
            )
            self.student2.set_password("StudentPass123!")

            db.session.add_all([self.admin, self.student1, self.student2])
            db.session.commit()
            self.admin_id = self.admin.id
            self.student1_id = self.student1.id
            self.student2_id = self.student2.id

    def _login(self, client, identifier, password):
        client.get("/login")
        with client.session_transaction() as sess:
            csrf_token = sess.get("csrf_token", "")
        return client.post("/login", data={
            "identifier": identifier,
            "password": password,
            "csrf_token": csrf_token,
        }, follow_redirects=True)

    def _post(self, client, url, data=None, follow_redirects=True):
        post_data = dict(data or {})
        with client.session_transaction() as sess:
            if "csrf_token" not in post_data:
                post_data["csrf_token"] = sess.get("csrf_token", "")
        return client.post(url, data=post_data, follow_redirects=follow_redirects)

    def _create_exam(self, title="Test Exam", status="published", start_delta_min=-10, end_delta_min=60, duration_min=30):
        with app.app_context():
            now = datetime.now()
            start_time = now + timedelta(minutes=start_delta_min)
            end_time = now + timedelta(minutes=end_delta_min)
            exam = Exam(
                title=title,
                created_by=self.admin_id,
                duration_minutes=duration_min,
                start_time=start_time,
                end_time=end_time,
                status=status,
            )
            db.session.add(exam)
            db.session.flush()

            # Add 2 questions
            q1 = Question(
                exam_id=exam.id,
                question_text="What is 2+2?",
                option_a="2",
                option_b="3",
                option_c="4",
                option_d="5",
                correct_index=2,
            )
            q2 = Question(
                exam_id=exam.id,
                question_text="Capital of France?",
                option_a="Berlin",
                option_b="Madrid",
                option_c="Paris",
                option_d="Rome",
                correct_index=2,
            )
            db.session.add_all([q1, q2])
            db.session.commit()
            return exam.id

    # ==========================================
    # 1. Exam Access Rules
    # ==========================================
    def test_user_cannot_start_draft_exam(self):
        exam_id = self._create_exam(title="Draft Exam", status="draft")
        self._login(self.client, "PRN2026001", "StudentPass123!")

        resp = self.client.get(f"/student/exam/{exam_id}", follow_redirects=True)
        self.assertIn(b"This exam is not available", resp.data)

        # Ensure no attempt was created
        with app.app_context():
            attempt = Attempt.query.filter_by(exam_id=exam_id).first()
            self.assertIsNone(attempt)

    def test_user_cannot_start_closed_exam(self):
        exam_id = self._create_exam(title="Closed Exam", status="closed")
        self._login(self.client, "PRN2026001", "StudentPass123!")

        resp = self.client.get(f"/student/exam/{exam_id}", follow_redirects=True)
        self.assertIn(b"This exam has been closed", resp.data)

        with app.app_context():
            attempt = Attempt.query.filter_by(exam_id=exam_id).first()
            self.assertIsNone(attempt)

    def test_user_cannot_start_before_start_time(self):
        # Exam starts 1 hour in the future
        exam_id = self._create_exam(title="Future Exam", status="published", start_delta_min=60, end_delta_min=120)
        self._login(self.client, "PRN2026001", "StudentPass123!")

        resp = self.client.get(f"/student/exam/{exam_id}", follow_redirects=True)
        self.assertIn(b"This exam is not open yet", resp.data)

        with app.app_context():
            attempt = Attempt.query.filter_by(exam_id=exam_id).first()
            self.assertIsNone(attempt)

    def test_user_cannot_start_after_end_time(self):
        # Exam ended 10 minutes ago
        exam_id = self._create_exam(title="Past Exam", status="published", start_delta_min=-60, end_delta_min=-10)
        self._login(self.client, "PRN2026001", "StudentPass123!")

        resp = self.client.get(f"/student/exam/{exam_id}", follow_redirects=True)
        self.assertIn(b"The exam window has closed", resp.data)

        with app.app_context():
            attempt = Attempt.query.filter_by(exam_id=exam_id).first()
            self.assertIsNone(attempt)

    def test_user_can_start_published_exam_inside_window(self):
        exam_id = self._create_exam(title="Active Exam", status="published", start_delta_min=-10, end_delta_min=50)
        self._login(self.client, "PRN2026001", "StudentPass123!")

        resp = self.client.get(f"/student/exam/{exam_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Active Exam", resp.data)
        self.assertIn(b"Time Remaining", resp.data)
        self.assertIn(b"exam-timer-container", resp.data)

    # ==========================================
    # 2. Attempt Creation & Session Resumption
    # ==========================================
    def test_starting_creates_exactly_one_attempt_with_started_at(self):
        exam_id = self._create_exam(title="Attempt Check", status="published")
        self._login(self.client, "PRN2026001", "StudentPass123!")

        self.client.get(f"/student/exam/{exam_id}")

        with app.app_context():
            attempts = Attempt.query.filter_by(exam_id=exam_id).all()
            self.assertEqual(len(attempts), 1)
            attempt = attempts[0]
            self.assertIsNotNone(attempt.started_at)
            self.assertIsNone(attempt.submitted_at)
            self.assertTrue(attempt.is_active)
            self.assertFalse(attempt.is_submitted)

    def test_refreshing_does_not_create_another_attempt_or_reset_started_at(self):
        exam_id = self._create_exam(title="Refresh Check", status="published")
        self._login(self.client, "PRN2026001", "StudentPass123!")

        # 1st GET (Start attempt)
        self.client.get(f"/student/exam/{exam_id}")
        with app.app_context():
            first_attempt = Attempt.query.filter_by(exam_id=exam_id).first()
            original_started_at = first_attempt.started_at

        # 2nd GET (Simulate browser refresh)
        self.client.get(f"/student/exam/{exam_id}")
        with app.app_context():
            attempts = Attempt.query.filter_by(exam_id=exam_id).all()
            self.assertEqual(len(attempts), 1)
            second_attempt = attempts[0]
            self.assertEqual(second_attempt.id, first_attempt.id)
            self.assertEqual(second_attempt.started_at, original_started_at)

    def test_dashboard_displays_in_progress_for_active_attempt(self):
        exam_id = self._create_exam(title="Dashboard In Progress", status="published")
        self._login(self.client, "PRN2026001", "StudentPass123!")

        # Start exam
        self.client.get(f"/student/exam/{exam_id}")

        # Navigate back to dashboard
        resp = self.client.get("/student")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"In Progress", resp.data)
        self.assertIn(b"Resume Exam", resp.data)

    # ==========================================
    # 3. Timing & Effective Deadline Logic
    # ==========================================
    def test_duration_deadline_within_exam_window(self):
        # Exam window: 10 min ago to 60 min from now (70 min window)
        # Duration: 30 min
        # Effective deadline should be started_at + 30 min (since that is well before end_time)
        exam_id = self._create_exam(title="Duration Normal", duration_min=30, start_delta_min=-10, end_delta_min=60)
        self._login(self.client, "PRN2026001", "StudentPass123!")

        self.client.get(f"/student/exam/{exam_id}")

        with app.app_context():
            exam = database.get_exam(exam_id)
            attempt = database.get_attempt(exam_id, self.student1_id)
            deadline = database.get_effective_deadline(exam, attempt)

            expected_deadline = attempt.started_at + timedelta(minutes=30)
            self.assertEqual(deadline, expected_deadline)
            self.assertTrue(deadline < exam.end_time)

    def test_global_exam_end_truncates_duration(self):
        # Exam window: 50 min ago to 10 min from now (window ends in 10 min)
        # Duration: 30 min
        # Student starts now, but exam window ends in 10 min.
        # Effective deadline MUST be exam.end_time, NOT started_at + 30 min!
        exam_id = self._create_exam(title="Truncate Window", duration_min=30, start_delta_min=-50, end_delta_min=10)
        self._login(self.client, "PRN2026001", "StudentPass123!")

        self.client.get(f"/student/exam/{exam_id}")

        with app.app_context():
            exam = database.get_exam(exam_id)
            attempt = database.get_attempt(exam_id, self.student1_id)
            deadline = database.get_effective_deadline(exam, attempt)

            # Deadline must strictly equal exam.end_time
            self.assertEqual(deadline, exam.end_time)
            self.assertTrue(deadline < (attempt.started_at + timedelta(minutes=30)))

    def test_server_calculates_correct_remaining_seconds(self):
        exam_id = self._create_exam(title="Remaining Sec", duration_min=20)
        self._login(self.client, "PRN2026001", "StudentPass123!")

        self.client.get(f"/student/exam/{exam_id}")

        with app.app_context():
            exam = database.get_exam(exam_id)
            attempt = database.get_attempt(exam_id, self.student1_id)
            remaining = database.get_remaining_seconds(exam, attempt)

            # Should be approximately 20 min * 60 = 1200 seconds (allow 5 sec test delta)
            self.assertGreaterEqual(remaining, 1195)
            self.assertLessEqual(remaining, 1205)

    # ==========================================
    # 4. Submission & Scoring Protection
    # ==========================================
    def test_valid_submission_succeeds_and_evaluates(self):
        exam_id = self._create_exam(title="Submission Test", status="published")
        self._login(self.client, "PRN2026001", "StudentPass123!")

        # Start attempt
        self.client.get(f"/student/exam/{exam_id}")

        # Post answers: Q0 correct=2 ("4"), Q1 correct=2 ("Paris")
        resp = self._post(self.client, f"/student/exam/{exam_id}", data={
            "answer_0": "2",  # Correct (score +1)
            "answer_1": "0",  # Incorrect Berlin (score +0)
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        self.assertIn(b"Exam submitted and sealed successfully!", resp.data)

        with app.app_context():
            attempt = database.get_attempt(exam_id, self.student1_id)
            self.assertIsNotNone(attempt.submitted_at)
            self.assertTrue(attempt.is_submitted)
            self.assertFalse(attempt.is_active)
            self.assertEqual(attempt.score, 1)
            self.assertEqual(attempt.total, 2)
            self.assertIsNotNone(attempt.block_id)

    def test_partial_submission_handles_unanswered_questions(self):
        exam_id = self._create_exam(title="Partial Submission", status="published")
        self._login(self.client, "PRN2026001", "StudentPass123!")

        # Start attempt
        self.client.get(f"/student/exam/{exam_id}")

        # Only answer Q0, leave Q1 blank (as happens on timeout auto-submit)
        resp = self._post(self.client, f"/student/exam/{exam_id}", data={
            "answer_0": "2",  # Correct
            "auto_submit": "true",
        }, follow_redirects=True)

        self.assertEqual(resp.status_code, 200)
        with app.app_context():
            attempt = database.get_attempt(exam_id, self.student1_id)
            self.assertEqual(attempt.score, 1)
            self.assertEqual(attempt.total, 2)
            self.assertTrue(attempt.is_submitted)

    def test_second_submission_rejected_application_level(self):
        exam_id = self._create_exam(title="Double Submit Check", status="published")
        self._login(self.client, "PRN2026001", "StudentPass123!")

        # Start and submit first time
        self.client.get(f"/student/exam/{exam_id}")
        self._post(self.client, f"/student/exam/{exam_id}", data={
            "answer_0": "2",
            "answer_1": "2",
        })

        with app.app_context():
            attempt = database.get_attempt(exam_id, self.student1_id)
            first_score = attempt.score
            first_submitted_at = attempt.submitted_at
            first_block_id = attempt.block_id

        # Try to submit a second time
        resp = self._post(self.client, f"/student/exam/{exam_id}", data={
            "answer_0": "0",
            "answer_1": "0",
        }, follow_redirects=True)

        self.assertIn(b"You have already submitted this exam", resp.data)

        # Verify database record was NOT mutated
        with app.app_context():
            attempt_after = database.get_attempt(exam_id, self.student1_id)
            self.assertEqual(attempt_after.score, first_score)
            self.assertEqual(attempt_after.submitted_at, first_submitted_at)
            self.assertEqual(attempt_after.block_id, first_block_id)

    def test_cannot_access_exam_after_submission(self):
        exam_id = self._create_exam(title="Submitted Reopen Check", status="published")
        self._login(self.client, "PRN2026001", "StudentPass123!")

        self.client.get(f"/student/exam/{exam_id}")
        self._post(self.client, f"/student/exam/{exam_id}", data={"answer_0": "2"})

        # Try GET again
        resp = self.client.get(f"/student/exam/{exam_id}", follow_redirects=True)
        self.assertIn(b"You have already submitted this exam", resp.data)

    # ==========================================
    # 5. Timeout & Late Submission Handling
    # ==========================================
    def test_expired_session_on_get_is_finalized(self):
        exam_id = self._create_exam(title="Timeout GET Check", duration_min=10)
        self._login(self.client, "PRN2026001", "StudentPass123!")

        # Start attempt
        self.client.get(f"/student/exam/{exam_id}")

        # Simulate time passing beyond deadline by shifting started_at in the past
        with app.app_context():
            attempt = database.get_attempt(exam_id, self.student1_id)
            attempt.started_at = datetime.now() - timedelta(minutes=15)
            db.session.commit()

        # Re-open page after expiration
        resp = self.client.get(f"/student/exam/{exam_id}", follow_redirects=True)
        self.assertIn(b"The exam time limit has expired", resp.data)

        # Check DB state
        with app.app_context():
            finalized_attempt = database.get_attempt(exam_id, self.student1_id)
            self.assertTrue(finalized_attempt.is_submitted)
            self.assertEqual(finalized_attempt.score, 0)

    def test_late_post_submission_rejected(self):
        exam_id = self._create_exam(title="Late POST Check", duration_min=10)
        self._login(self.client, "PRN2026001", "StudentPass123!")

        self.client.get(f"/student/exam/{exam_id}")

        # Manipulate attempt started_at to simulate late submission past 10 min + 5s grace period
        with app.app_context():
            attempt = database.get_attempt(exam_id, self.student1_id)
            attempt.started_at = datetime.now() - timedelta(minutes=12)
            db.session.commit()

        resp = self._post(self.client, f"/student/exam/{exam_id}", data={
            "answer_0": "2",
            "answer_1": "2",
        }, follow_redirects=True)

        self.assertIn(b"The exam time limit has expired. Your submission was not accepted", resp.data)

        with app.app_context():
            attempt = database.get_attempt(exam_id, self.student1_id)
            self.assertTrue(attempt.is_submitted)
            self.assertEqual(attempt.score, 0)
            self.assertIsNone(attempt.block_id)

    # ==========================================
    # 6. Security & Manipulation
    # ==========================================
    def test_fake_client_timestamps_ignored_by_server(self):
        # Client sends fake hidden fields attempting to manipulate timing
        exam_id = self._create_exam(title="Tamper Timing Check", duration_min=10)
        self._login(self.client, "PRN2026001", "StudentPass123!")

        self.client.get(f"/student/exam/{exam_id}")

        # Send POST with spoofed countdown / timestamp parameters
        resp = self._post(self.client, f"/student/exam/{exam_id}", data={
            "answer_0": "2",
            "remaining_seconds": "99999",
            "deadline": "2099-01-01 00:00:00",
            "started_at": "2099-01-01 00:00:00",
        }, follow_redirects=True)

        self.assertIn(b"Exam submitted and sealed successfully!", resp.data)

        # Verify server used real server started_at and submitted_at
        with app.app_context():
            attempt = database.get_attempt(exam_id, self.student1_id)
            now = datetime.now()
            self.assertTrue(abs((attempt.submitted_at - now).total_seconds()) < 5)

    def test_student_cannot_submit_for_another_student(self):
        exam_id = self._create_exam(title="User Isolation Check", status="published")
        # Student 1 in client 1
        client1 = app.test_client()
        self._login(client1, "PRN2026001", "StudentPass123!")
        client1.get(f"/student/exam/{exam_id}")

        # Student 2 in client 2
        client2 = app.test_client()
        self._login(client2, "PRN2026002", "StudentPass123!")

        # Student 2 tries to post to Student 1's attempt or submit their own
        self._post(client2, f"/student/exam/{exam_id}", data={
            "answer_0": "2",
            "student_id": str(self.student1_id),  # Spoof student_id in POST body
        })

        # Verify Student 1's attempt is still in progress (not submitted)
        with app.app_context():
            att1 = database.get_attempt(exam_id, self.student1_id)
            self.assertTrue(att1.is_active)
            self.assertFalse(att1.is_submitted)

            # And Student 2's own attempt was created and finalized under Student 2's user_id
            att2 = database.get_attempt(exam_id, self.student2_id)
            self.assertIsNotNone(att2)
            self.assertTrue(att2.is_submitted)

    def test_database_unique_constraint_enforces_one_attempt_per_user_exam(self):
        exam_id = self._create_exam(title="DB Unique Constraint Check", status="published")

        with app.app_context():
            # First attempt
            att1 = Attempt(exam_id=exam_id, student_id=self.student1_id, started_at=datetime.now())
            db.session.add(att1)
            db.session.commit()

            # Attempt to create duplicate record directly in database
            att2 = Attempt(exam_id=exam_id, student_id=self.student1_id, started_at=datetime.now())
            db.session.add(att2)
            from sqlalchemy.exc import IntegrityError
            with self.assertRaises(IntegrityError):
                db.session.commit()
            db.session.rollback()


if __name__ == "__main__":
    unittest.main()
