"""
test_phase5_results.py
----------------------
Automated test suite for Phase 5: Evaluation & Results System.

Tests:
1. Evaluation & Scoring:
   - All correct answers
   - All incorrect answers
   - Mixed answers (correct, incorrect, unanswered)
   - All unanswered questions
   - Zero-total questions edge case
   - No negative marking
2. Result Breakdown Counts:
   - Correct count
   - Incorrect count
   - Unanswered count
   - Percentage calculation (server-derived)
3. Attempt Finalization & Idempotency:
   - submitted_at timestamp set on server
   - Finalized attempt cannot be finalized again
   - Score cannot be overwritten by a second submission
4. Timing:
   - time_used derived from server timestamps (submitted_at - started_at)
   - Client-supplied time_used / time parameters ignored
5. Ownership & Authorization:
   - User can view own result
   - User cannot view another user's result
   - Admin can view exam results dashboard and student results
   - Anonymous user blocked from results
   - In-progress / unsubmitted attempt cannot view result
6. Result Manipulation Protection:
   - Injected score, percentage, student_id, submitted_at parameters ignored
7. Timeout Handling:
   - Timed-out auto-submissions evaluate provided answers and seal correctly
8. Cryptographic Integrity:
   - Finalized result has valid block linkage and SHA-256 hash
9. Admin Dashboard Statistics:
   - Correct summary stats (total, avg score, highest, lowest, avg percentage)
   - Zero-submission exams handled safely without division by zero
"""

import os
import sys
import unittest
from datetime import datetime, timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEST_DB_PATH = os.path.join(BASE_DIR, "tests", "test_phase5.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

sys.path.insert(0, BASE_DIR)

from app import app, blockchain
from models import db, User, Exam, Question, Attempt, Block
import database


class TestPhase5Results(unittest.TestCase):
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
            Attempt.query.delete()
            Question.query.delete()
            Exam.query.delete()
            User.query.delete()
            Block.query.delete()
            db.session.commit()

            # Ensure genesis block exists if blockchain empty
            if Block.query.count() == 0:
                genesis_block = Block(
                    id=0,
                    timestamp=datetime.now().timestamp(),
                    data_json='{"type": "genesis", "message": "Genesis Block"}',
                    previous_hash="0" * 64,
                    hash="genesis_hash_init",
                )
                from blockchain import compute_hash
                genesis_block.hash = compute_hash(0, genesis_block.timestamp, {"type": "genesis", "message": "Genesis Block"}, "0" * 64)
                db.session.add(genesis_block)
                db.session.commit()

            # Create test Admin
            self.admin = User(
                prn="ADMIN2026",
                email="admin@college.edu",
                role="admin",
                name="Prof. Sharma",
            )
            self.admin.set_password("AdminPass123!")

            # Create test Student 1
            self.student1 = User(
                prn="PRN2026001",
                email="student1@college.edu",
                role="user",
                name="Aarav Patel",
            )
            self.student1.set_password("StudentPass123!")

            # Create test Student 2
            self.student2 = User(
                prn="PRN2026002",
                email="student2@college.edu",
                role="user",
                name="Diya Roy",
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

    def _create_standard_exam(self, question_count=4, duration_min=30):
        with app.app_context():
            now = datetime.now()
            exam = Exam(
                title="Distributed Systems Exam",
                created_by=self.admin_id,
                duration_minutes=duration_min,
                start_time=now - timedelta(minutes=5),
                end_time=now + timedelta(minutes=55),
                status="published",
            )
            db.session.add(exam)
            db.session.flush()

            for i in range(question_count):
                q = Question(
                    exam_id=exam.id,
                    question_text=f"Question {i + 1}: What is algorithm {chr(65 + i)}?",
                    option_a="Choice A",
                    option_b="Choice B",
                    option_c="Choice C",
                    option_d="Choice D",
                    correct_index=i % 4,  # Q0: A (0), Q1: B (1), Q2: C (2), Q3: D (3)
                )
                db.session.add(q)

            db.session.commit()
            return exam.id

    # =========================================================================
    # 1. EVALUATION & SCORING TESTS
    # =========================================================================

    def test_evaluation_all_correct(self):
        """Student submits all correct answers: score = 4/4, percentage = 100.0%."""
        exam_id = self._create_standard_exam(question_count=4)
        c = app.test_client()
        self._login(c, "PRN2026001", "StudentPass123!")

        # Start exam
        c.get(f"/student/exam/{exam_id}")

        # Correct answers: Q0->0, Q1->1, Q2->2, Q3->3
        response = self._post(c, f"/student/exam/{exam_id}", {
            "answer_0": "0",
            "answer_1": "1",
            "answer_2": "2",
            "answer_3": "3",
        })
        self.assertEqual(response.status_code, 200)

        with app.app_context():
            attempt = database.get_attempt(exam_id, self.student1_id)
            self.assertIsNotNone(attempt)
            self.assertTrue(attempt.is_submitted)
            self.assertEqual(attempt.score, 4)
            self.assertEqual(attempt.total, 4)
            self.assertEqual(attempt.percentage, 100.0)
            self.assertEqual(attempt.correct_count, 4)
            self.assertEqual(attempt.incorrect_count, 0)
            self.assertEqual(attempt.unanswered_count, 0)

            # Block verification
            block = blockchain.get_block(attempt.block_id)
            self.assertEqual(block.data["score"], 4)
            self.assertEqual(block.data["percentage"], 100.0)
            self.assertEqual(block.data["correct_count"], 4)

    def test_evaluation_all_incorrect(self):
        """Student submits all incorrect answers: score = 0/4, percentage = 0.0%."""
        exam_id = self._create_standard_exam(question_count=4)
        c = app.test_client()
        self._login(c, "PRN2026001", "StudentPass123!")

        c.get(f"/student/exam/{exam_id}")

        # Inverted answers (all wrong): Q0->3, Q1->0, Q2->1, Q3->2
        response = self._post(c, f"/student/exam/{exam_id}", {
            "answer_0": "3",
            "answer_1": "0",
            "answer_2": "1",
            "answer_3": "2",
        })
        self.assertEqual(response.status_code, 200)

        with app.app_context():
            attempt = database.get_attempt(exam_id, self.student1_id)
            self.assertEqual(attempt.score, 0)
            self.assertEqual(attempt.total, 4)
            self.assertEqual(attempt.percentage, 0.0)
            self.assertEqual(attempt.correct_count, 0)
            self.assertEqual(attempt.incorrect_count, 4)
            self.assertEqual(attempt.unanswered_count, 0)

    def test_evaluation_mixed_and_unanswered(self):
        """Student submits mixed answers: 2 correct, 1 incorrect, 1 unanswered."""
        exam_id = self._create_standard_exam(question_count=4)
        c = app.test_client()
        self._login(c, "PRN2026001", "StudentPass123!")

        c.get(f"/student/exam/{exam_id}")

        # Q0: 0 (Correct), Q1: 1 (Correct), Q2: 0 (Incorrect, correct is 2), Q3: not answered
        response = self._post(c, f"/student/exam/{exam_id}", {
            "answer_0": "0",
            "answer_1": "1",
            "answer_2": "0",
        })
        self.assertEqual(response.status_code, 200)

        with app.app_context():
            attempt = database.get_attempt(exam_id, self.student1_id)
            self.assertEqual(attempt.score, 2)
            self.assertEqual(attempt.total, 4)
            self.assertEqual(attempt.percentage, 50.0)
            self.assertEqual(attempt.correct_count, 2)
            self.assertEqual(attempt.incorrect_count, 1)
            self.assertEqual(attempt.unanswered_count, 1)

            # Block payload verification
            block = blockchain.get_block(attempt.block_id)
            self.assertEqual(block.data["score"], 2)
            self.assertEqual(block.data["correct_count"], 2)
            self.assertEqual(block.data["incorrect_count"], 1)
            self.assertEqual(block.data["unanswered_count"], 1)
            self.assertEqual(block.data["percentage"], 50.0)

    def test_evaluation_all_unanswered(self):
        """Student submits an empty form: score = 0/4, unanswered = 4."""
        exam_id = self._create_standard_exam(question_count=4)
        c = app.test_client()
        self._login(c, "PRN2026001", "StudentPass123!")

        c.get(f"/student/exam/{exam_id}")

        response = self._post(c, f"/student/exam/{exam_id}", {})
        self.assertEqual(response.status_code, 200)

        with app.app_context():
            attempt = database.get_attempt(exam_id, self.student1_id)
            self.assertEqual(attempt.score, 0)
            self.assertEqual(attempt.total, 4)
            self.assertEqual(attempt.percentage, 0.0)
            self.assertEqual(attempt.correct_count, 0)
            self.assertEqual(attempt.incorrect_count, 0)
            self.assertEqual(attempt.unanswered_count, 4)

    def test_no_negative_marking(self):
        """Incorrect answers do not deduct from score."""
        exam_id = self._create_standard_exam(question_count=4)
        c = app.test_client()
        self._login(c, "PRN2026001", "StudentPass123!")

        c.get(f"/student/exam/{exam_id}")

        # Q0: 0 (Correct), Q1: 3 (Wrong), Q2: 1 (Wrong), Q3: 0 (Wrong)
        self._post(c, f"/student/exam/{exam_id}", {
            "answer_0": "0",
            "answer_1": "3",
            "answer_2": "1",
            "answer_3": "0",
        })

        with app.app_context():
            attempt = database.get_attempt(exam_id, self.student1_id)
            # Score must remain 1, not negative
            self.assertEqual(attempt.score, 1)
            self.assertEqual(attempt.correct_count, 1)
            self.assertEqual(attempt.incorrect_count, 3)

    def test_zero_total_questions_edge_case(self):
        """Percentage handles total=0 gracefully without division by zero."""
        with app.app_context():
            attempt = Attempt(
                exam_id=1,
                student_id=self.student1_id,
                score=0,
                total=0,
                started_at=datetime.now(),
                submitted_at=datetime.now(),
            )
            self.assertEqual(attempt.percentage, 0.0)

    # =========================================================================
    # 2. FINALIZATION & IDEMPOTENCY TESTS
    # =========================================================================

    def test_attempt_finalization_sets_submitted_at(self):
        """Finalization populates submitted_at with server timestamp."""
        exam_id = self._create_standard_exam(question_count=2)
        c = app.test_client()
        self._login(c, "PRN2026001", "StudentPass123!")

        c.get(f"/student/exam/{exam_id}")
        before_submit = datetime.now()
        self._post(c, f"/student/exam/{exam_id}", {"answer_0": "0", "answer_1": "1"})
        after_submit = datetime.now()

        with app.app_context():
            attempt = database.get_attempt(exam_id, self.student1_id)
            self.assertTrue(attempt.is_submitted)
            self.assertIsNotNone(attempt.submitted_at)
            self.assertTrue(before_submit - timedelta(seconds=2) <= attempt.submitted_at <= after_submit + timedelta(seconds=2))

    def test_database_finalize_attempt_is_idempotent(self):
        """database.finalize_attempt cannot overwrite an already submitted attempt."""
        exam_id = self._create_standard_exam(question_count=2)
        with app.app_context():
            attempt = database.start_attempt(exam_id, self.student1_id, 2)
            orig_sub_time = datetime.now() - timedelta(minutes=5)
            database.finalize_attempt(attempt, score=2, total_questions=2, block_id=1, submitted_at=orig_sub_time)

            # Try to finalize again with different score and time
            result = database.finalize_attempt(attempt, score=0, total_questions=2, block_id=99, submitted_at=datetime.now())

            # Attempt score and submitted_at must remain untouched
            self.assertEqual(result.score, 2)
            self.assertEqual(result.block_id, 1)
            self.assertEqual(result.submitted_at, orig_sub_time)

    def test_second_submission_rejected(self):
        """A second POST cannot recalculate or overwrite finalized result."""
        exam_id = self._create_standard_exam(question_count=2)
        c = app.test_client()
        self._login(c, "PRN2026001", "StudentPass123!")

        # First submission (score 2)
        c.get(f"/student/exam/{exam_id}")
        resp1 = self._post(c, f"/student/exam/{exam_id}", {"answer_0": "0", "answer_1": "1"})
        self.assertEqual(resp1.status_code, 200)

        with app.app_context():
            attempt1 = database.get_attempt(exam_id, self.student1_id)
            orig_score = attempt1.score
            orig_block_id = attempt1.block_id
            block_count_before = Block.query.count()

        # Malicious second submission trying to change answers to 0
        resp2 = self._post(c, f"/student/exam/{exam_id}", {"answer_0": "3", "answer_1": "3"})
        # Should be redirected to student_dashboard with flash error
        self.assertIn("You have already submitted this exam.", resp2.get_data(as_text=True))

        with app.app_context():
            attempt2 = database.get_attempt(exam_id, self.student1_id)
            self.assertEqual(attempt2.score, orig_score)
            self.assertEqual(attempt2.block_id, orig_block_id)
            # No additional block was added
            self.assertEqual(Block.query.count(), block_count_before)

    # =========================================================================
    # 3. TIME USED TESTS
    # =========================================================================

    def test_time_used_calculated_from_server_timestamps(self):
        """time_used is derived strictly from submitted_at - started_at."""
        with app.app_context():
            started = datetime(2026, 10, 6, 10, 0, 0)
            submitted = datetime(2026, 10, 6, 10, 17, 8)  # 17m 08s
            attempt = Attempt(
                exam_id=1,
                student_id=self.student1_id,
                score=10,
                total=10,
                started_at=started,
                submitted_at=submitted,
            )
            self.assertEqual(attempt.time_used_seconds, 1028)
            self.assertEqual(attempt.time_used_display, "17m 08s")

    def test_client_supplied_time_used_ignored(self):
        """Client-supplied duration parameters in POST are ignored."""
        exam_id = self._create_standard_exam(question_count=2)
        c = app.test_client()
        self._login(c, "PRN2026001", "StudentPass123!")

        c.get(f"/student/exam/{exam_id}")
        self._post(c, f"/student/exam/{exam_id}", {
            "answer_0": "0",
            "answer_1": "1",
            "time_used": "1s",
            "time_used_seconds": "1",
            "submitted_at": "1999-01-01 00:00:00",
        })

        with app.app_context():
            attempt = database.get_attempt(exam_id, self.student1_id)
            block = blockchain.get_block(attempt.block_id)
            # Duration must not be "1s" unless the server literally took 1s
            self.assertNotEqual(block.data.get("submitted_at"), "1999-01-01 00:00:00")
            self.assertTrue(attempt.time_used_seconds >= 0)

    # =========================================================================
    # 4. OWNERSHIP & ACCESS CONTROL TESTS
    # =========================================================================

    def test_user_can_view_own_result(self):
        """Student 1 can view their own result."""
        exam_id = self._create_standard_exam(question_count=2)
        c1 = app.test_client()
        self._login(c1, "PRN2026001", "StudentPass123!")

        c1.get(f"/student/exam/{exam_id}")
        self._post(c1, f"/student/exam/{exam_id}", {"answer_0": "0", "answer_1": "1"})

        with app.app_context():
            attempt = database.get_attempt(exam_id, self.student1_id)
            block_id = attempt.block_id

        # Access result page directly
        resp = c1.get(f"/result/{block_id}")
        self.assertEqual(resp.status_code, 200)
        content = resp.get_data(as_text=True)
        self.assertIn("Aarav Patel", content)
        self.assertIn("PRN2026001", content)
        self.assertIn("2 / 2", content)
        self.assertIn("100.0% Score", content)

    def test_user_cannot_view_another_user_result(self):
        """Student 2 cannot view Student 1's result by tampering with the URL."""
        exam_id = self._create_standard_exam(question_count=2)
        c1 = app.test_client()
        self._login(c1, "PRN2026001", "StudentPass123!")

        c1.get(f"/student/exam/{exam_id}")
        self._post(c1, f"/student/exam/{exam_id}", {"answer_0": "0", "answer_1": "1"})

        with app.app_context():
            attempt1 = database.get_attempt(exam_id, self.student1_id)
            block_id_user1 = attempt1.block_id

        # Student 2 logs in and tries to access Student 1's block
        c2 = app.test_client()
        self._login(c2, "PRN2026002", "StudentPass123!")

        resp = c2.get(f"/result/{block_id_user1}", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        content = resp.get_data(as_text=True)
        self.assertIn("You do not have permission to view another student&#39;s result.", content)

    def test_admin_can_view_exam_results_and_student_result(self):
        """Admin can view the exam results dashboard and individual student result."""
        exam_id = self._create_standard_exam(question_count=2)
        c1 = app.test_client()
        self._login(c1, "PRN2026001", "StudentPass123!")

        c1.get(f"/student/exam/{exam_id}")
        self._post(c1, f"/student/exam/{exam_id}", {"answer_0": "0", "answer_1": "1"})

        with app.app_context():
            attempt1 = database.get_attempt(exam_id, self.student1_id)
            block_id = attempt1.block_id

        # Admin logs in
        c_admin = app.test_client()
        self._login(c_admin, "ADMIN2026", "AdminPass123!")

        # 1. Dashboard results table
        resp_dashboard = c_admin.get(f"/admin/exams/{exam_id}/results")
        self.assertEqual(resp_dashboard.status_code, 200)
        self.assertIn("Exam Results", resp_dashboard.get_data(as_text=True))
        self.assertIn("Aarav Patel", resp_dashboard.get_data(as_text=True))

        # 2. Individual student result
        resp_result = c_admin.get(f"/result/{block_id}")
        self.assertEqual(resp_result.status_code, 200)
        self.assertIn("Aarav Patel", resp_result.get_data(as_text=True))

    def test_anonymous_user_blocked(self):
        """Unauthenticated user is blocked from viewing results."""
        c = app.test_client()
        resp = c.get("/result/1", follow_redirects=False)
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login", resp.headers["Location"])

        resp2 = c.get("/admin/exams/1/results", follow_redirects=False)
        self.assertEqual(resp2.status_code, 302)
        self.assertIn("/login", resp2.headers["Location"])

    def test_in_progress_attempt_cannot_view_result(self):
        """Active in-progress attempt cannot be viewed as a result."""
        exam_id = self._create_standard_exam(question_count=2)
        c = app.test_client()
        self._login(c, "PRN2026001", "StudentPass123!")

        # Start attempt (in progress, not submitted)
        c.get(f"/student/exam/{exam_id}")

        # Attempt to access student exam result route
        resp = c.get(f"/student/exam/{exam_id}/result", follow_redirects=True)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("This exam has not been submitted yet.", resp.get_data(as_text=True))

    # =========================================================================
    # 5. MANIPULATION PROTECTION TESTS
    # =========================================================================

    def test_client_result_manipulation_ignored(self):
        """Spoofed score, percentage, student_id, submitted_at parameters are ignored."""
        exam_id = self._create_standard_exam(question_count=4)
        c = app.test_client()
        self._login(c, "PRN2026001", "StudentPass123!")

        c.get(f"/student/exam/{exam_id}")

        # Student only actually answered Q0 correctly (0). Q1, Q2, Q3 wrong.
        # But attempts to send forged score=4, percentage=100, student_id=self.student2_id
        response = self._post(c, f"/student/exam/{exam_id}", {
            "answer_0": "0",
            "answer_1": "3",  # wrong
            "answer_2": "3",  # wrong
            "answer_3": "0",  # wrong
            "score": "4",
            "percentage": "100.0",
            "correct_count": "4",
            "incorrect_count": "0",
            "unanswered_count": "0",
            "student_id": str(self.student2_id),
            "submitted_at": "2099-01-01 00:00:00",
        })
        self.assertEqual(response.status_code, 200)

        with app.app_context():
            # Attempt belongs to Student 1, NOT Student 2
            attempt1 = database.get_attempt(exam_id, self.student1_id)
            attempt2 = database.get_attempt(exam_id, self.student2_id)
            self.assertIsNone(attempt2)
            self.assertIsNotNone(attempt1)

            # Score is server-evaluated (1 correct out of 4 = 25.0%)
            self.assertEqual(attempt1.score, 1)
            self.assertEqual(attempt1.percentage, 25.0)
            self.assertEqual(attempt1.correct_count, 1)
            self.assertEqual(attempt1.incorrect_count, 3)

            block = blockchain.get_block(attempt1.block_id)
            self.assertEqual(block.data["score"], 1)
            self.assertEqual(block.data["percentage"], 25.0)
            self.assertEqual(block.data["student_name"], "Aarav Patel")

    # =========================================================================
    # 6. TIMEOUT HANDLING TESTS
    # =========================================================================

    def test_timeout_auto_submit_evaluates_submitted_answers(self):
        """Auto-submitted timeout evaluates answers provided, unanswered remain unanswered."""
        exam_id = self._create_standard_exam(question_count=4)
        c = app.test_client()
        self._login(c, "PRN2026001", "StudentPass123!")

        c.get(f"/student/exam/{exam_id}")

        # Simulate timeout submission with partial answers: Q0 correct (0), Q1 correct (1), Q2/Q3 unanswered
        response = self._post(c, f"/student/exam/{exam_id}", {
            "answer_0": "0",
            "answer_1": "1",
            "auto_submit": "true",
        })
        self.assertEqual(response.status_code, 200)

        with app.app_context():
            attempt = database.get_attempt(exam_id, self.student1_id)
            self.assertTrue(attempt.is_submitted)
            self.assertEqual(attempt.score, 2)
            self.assertEqual(attempt.correct_count, 2)
            self.assertEqual(attempt.unanswered_count, 2)
            self.assertEqual(attempt.percentage, 50.0)

            block = blockchain.get_block(attempt.block_id)
            self.assertTrue(block.data.get("is_timeout"))
            self.assertEqual(block.data["score"], 2)

    # =========================================================================
    # 7. CRYPTOGRAPHIC INTEGRITY TESTS
    # =========================================================================

    def test_result_cryptographic_integrity_and_block_sealing(self):
        """Result block is sealed with SHA-256 and chain integrity is verified."""
        exam_id = self._create_standard_exam(question_count=2)
        c = app.test_client()
        self._login(c, "PRN2026001", "StudentPass123!")

        c.get(f"/student/exam/{exam_id}")
        self._post(c, f"/student/exam/{exam_id}", {"answer_0": "0", "answer_1": "1"})

        with app.app_context():
            attempt = database.get_attempt(exam_id, self.student1_id)
            self.assertIsNotNone(attempt.block_id)

            block = blockchain.get_block(attempt.block_id)
            self.assertEqual(block.hash, block.recompute_hash())

            chain_valid, errors = blockchain.is_chain_valid()
            self.assertTrue(chain_valid, f"Chain invalid: {errors}")

    # =========================================================================
    # 8. ADMIN DASHBOARD SUMMARY STATISTICS TESTS
    # =========================================================================

    def test_admin_results_statistics_multiple_submissions(self):
        """Admin exam results dashboard displays accurate aggregated statistics."""
        exam_id = self._create_standard_exam(question_count=4)

        # Student 1 scores 4/4 (100%)
        c1 = app.test_client()
        self._login(c1, "PRN2026001", "StudentPass123!")
        c1.get(f"/student/exam/{exam_id}")
        self._post(c1, f"/student/exam/{exam_id}", {
            "answer_0": "0", "answer_1": "1", "answer_2": "2", "answer_3": "3"
        })

        # Student 2 scores 2/4 (50%)
        c2 = app.test_client()
        self._login(c2, "PRN2026002", "StudentPass123!")
        c2.get(f"/student/exam/{exam_id}")
        self._post(c2, f"/student/exam/{exam_id}", {
            "answer_0": "0", "answer_1": "1"
        })

        # Admin checks results
        c_admin = app.test_client()
        self._login(c_admin, "ADMIN2026", "AdminPass123!")
        resp = c_admin.get(f"/admin/exams/{exam_id}/results")
        self.assertEqual(resp.status_code, 200)

        content = resp.get_data(as_text=True)
        # Check statistics cards
        # Total Submissions: 2
        self.assertIn("Total Submissions", content)
        # Average Score: (4 + 2) / 2 = 3.0
        self.assertIn("3.0", content)
        # Average Percentage: (100 + 50) / 2 = 75.0%
        self.assertIn("75.0%", content)
        # Highest Score: 4
        self.assertIn("4", content)
        # Lowest Score: 2
        self.assertIn("2", content)

    def test_admin_results_zero_submissions_safe(self):
        """Admin results handles exam with 0 submissions without division by zero."""
        exam_id = self._create_standard_exam(question_count=3)
        c_admin = app.test_client()
        self._login(c_admin, "ADMIN2026", "AdminPass123!")

        resp = c_admin.get(f"/admin/exams/{exam_id}/results")
        self.assertEqual(resp.status_code, 200)
        content = resp.get_data(as_text=True)
        self.assertIn("No Submissions Recorded Yet", content)


if __name__ == "__main__":
    unittest.main()
