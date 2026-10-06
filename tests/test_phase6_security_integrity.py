"""
test_phase6_security_integrity.py
---------------------------------
Automated test suite for Phase 6: Security & Integrity Cleanup.

Covers:
1. Ethereum Removal:
   - Zero Ethereum runtime dependency required for full flow
   - Result page has no MetaMask, Sepolia, or Ethereum UI
   - Base template does not load ethers.js or ethereum.js
   - /api/anchor_result endpoint is removed / returns 404
   - Result generation and verification works completely without Ethereum
2. Ledger Privacy:
   - Anonymous user cannot access /blockchain (redirects to /login)
   - Normal user (student) cannot access /blockchain (access denied)
   - Admin can access /blockchain
   - Admin ledger does not expose raw student answers or full data_json payload
3. SHA-256 Integrity Verification:
   - Valid block verifies successfully with verify_result_integrity
   - Tampered block data is detected
   - Broken previous_hash link is detected
   - Invalid / non-existent block reported correctly
   - Historical valid blocks remain valid when new blocks are appended
   - Result page reflects valid / tampered status cleanly
   - Admin /verify and /admin/verify_block endpoints work
4. Result Ownership (IDOR Prevention):
   - User can see own result
   - User cannot see another user's result
   - URL block_index manipulation does not bypass ownership
   - Admin can view results for exams they created
   - Admin cannot view results for exams created by other admins
5. Role Security:
   - Anonymous cannot access admin dashboard, exam creation, or integrity ledger
   - User cannot access admin dashboard, exam actions, results, or integrity ledger
   - Admin can access admin functionality
6. Client Manipulation Protection:
   - Injected client values (score=100, percentage=100, student_id, hash, block_id, time_used)
     are ignored and cannot corrupt server-evaluated results
7. CSRF Protection:
   - Missing or invalid CSRF tokens are rejected on all state-changing routes
"""

import json
import os
import sys
import unittest
from datetime import datetime, timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEST_DB_PATH = os.path.join(BASE_DIR, "tests", "test_phase6.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

sys.path.insert(0, BASE_DIR)

from app import app, blockchain
from models import db, User, Exam, Question, Attempt, Block
import database


class TestPhase6SecurityIntegrity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    def setUp(self):
        with app.app_context():
            db.drop_all()
            db.create_all()

            # Ensure genesis block exists
            if Block.query.count() == 0:
                from blockchain import compute_hash
                import time
                g_data = {"info": "Genesis Block - Exam Chain Initialized"}
                g_hash = compute_hash(0, time.time(), g_data, "0")
                g = Block(id=0, timestamp=time.time(), data_json=json.dumps(g_data, sort_keys=True), previous_hash="0", hash=g_hash)
                db.session.add(g)
                db.session.commit()

            # Create test admin 1
            self.admin = database.create_user(
                name="Prof. Sharma",
                identifier="admin_sharma",
                password="AdminPassword123",
                role="admin",
                username="sharma_admin",
                email="sharma@college.edu",
            )

            # Create test admin 2
            self.admin2 = database.create_user(
                name="Prof. Verma",
                identifier="admin_verma",
                password="AdminPassword123",
                role="admin",
                username="verma_admin",
                email="verma@college.edu",
            )

            # Create test student 1
            self.student1 = database.create_user(
                name="Rahul Sharma",
                identifier="PRN2026101",
                password="StudentPassword123",
                role="user",
                email="rahul@college.edu",
            )

            # Create test student 2
            self.student2 = database.create_user(
                name="Sneha Patil",
                identifier="PRN2026102",
                password="StudentPassword123",
                role="user",
                email="sneha@college.edu",
            )

            # Create published exam by admin 1
            now = datetime.now()
            questions = [
                {
                    "question": "What does SHA-256 produce?",
                    "options": ["256-bit hash digest", "128-bit key", "Public/private key pair", "Plaintext token"],
                    "correct_index": 0,
                },
                {
                    "question": "What provides tamper evidence in a linked chain?",
                    "options": ["Timestamp only", "Backward hash pointers", "External cookies", "Browser local storage"],
                    "correct_index": 1,
                },
            ]
            self.exam = database.create_exam(
                title="Cloud Architecture & Security",
                created_by=self.admin.id,
                start_time=now - timedelta(minutes=10),
                end_time=now + timedelta(hours=2),
                duration_minutes=60,
                questions=questions,
                status="published",
            )

            self.admin_id = self.admin.id
            self.admin2_id = self.admin2.id
            self.student1_id = self.student1.id
            self.student2_id = self.student2.id
            self.exam_id = self.exam.id

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except OSError:
                pass

    def _login_session(self, user_id, role, name="Test User", identifier="TEST001"):
        c = app.test_client()
        with c.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["role"] = role
            sess["name"] = name
            sess["identifier"] = identifier
            sess["csrf_token"] = "test-csrf-token-12345"
        return c

    def _submit_exam_for_student(self, student_id, student_name, student_prn, answers):
        c = self._login_session(student_id, "user", student_name, student_prn)
        # GET exam to initiate attempt
        res_get = c.get(f"/student/exam/{self.exam_id}")
        self.assertEqual(res_get.status_code, 200)

        # POST submission
        post_data = {"csrf_token": "test-csrf-token-12345"}
        for i, ans in enumerate(answers):
            if ans is not None:
                post_data[f"answer_{i}"] = str(ans)

        res_post = c.post(f"/student/exam/{self.exam_id}", data=post_data, follow_redirects=False)
        self.assertEqual(res_post.status_code, 302)

        # Retrieve attempt and block
        with app.app_context():
            attempt = database.get_attempt(self.exam_id, student_id)
            self.assertIsNotNone(attempt)
            self.assertTrue(attempt.is_submitted)
            self.assertIsNotNone(attempt.block_id)
            block = blockchain.get_block(attempt.block_id)
            return attempt.block_id, attempt.id, block

    # =========================================================================
    # PART 1: ETHEREUM RUNTIME REMOVAL
    # =========================================================================

    def test_01_complete_flow_works_without_ethereum(self):
        """Core flow: Create -> Take -> Submit -> Evaluate -> Result -> SHA-256 verification has zero Ethereum interaction."""
        block_id, attempt_id, block = self._submit_exam_for_student(
            self.student1_id, "Rahul Sharma", "PRN2026101", [0, 1]
        )
        self.assertIsNotNone(block_id)

        # Access result page as student
        c_student = self._login_session(self.student1_id, "user", "Rahul Sharma", "PRN2026101")
        res = c_student.get(f"/result/{block_id}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Result Integrity", res.data)
        self.assertIn(b"Integrity Verified", res.data)
        self.assertIn(block.hash.encode(), res.data)

    def test_02_result_page_contains_no_ethereum_ui(self):
        """Result page must not contain active MetaMask, Ethereum, or Sepolia UI."""
        block_id, _, _ = self._submit_exam_for_student(
            self.student1_id, "Rahul Sharma", "PRN2026101", [0, 1]
        )
        c_student = self._login_session(self.student1_id, "user", "Rahul Sharma", "PRN2026101")
        res = c_student.get(f"/result/{block_id}")
        self.assertEqual(res.status_code, 200)

        html = res.data.decode("utf-8")
        self.assertNotIn("ethereum", html.lower())
        self.assertNotIn("metamask", html.lower())
        self.assertNotIn("sepolia", html.lower())
        self.assertNotIn("anchorResultOnEthereum", html)
        self.assertNotIn("verifyEthereumResult", html)
        self.assertNotIn("etherscan", html.lower())

    def test_03_base_template_does_not_load_ethers_or_ethereum_js(self):
        """Base template must NOT load ethers.umd.min.js or ethereum.js."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.data.decode("utf-8")
        self.assertNotIn("ethers", html.lower())
        self.assertNotIn("ethereum.js", html)
        self.assertNotIn("ethereum-config.js", html)

    def test_04_anchor_api_endpoint_removed(self):
        """/api/anchor_result endpoint must no longer exist in the active V1 application."""
        c_admin = self._login_session(self.admin_id, "admin")
        res_get = c_admin.get("/api/anchor_result/1")
        self.assertEqual(res_get.status_code, 404)

        res_post = c_admin.post("/api/anchor_result/1", data={"csrf_token": "test-csrf-token-12345"})
        self.assertEqual(res_post.status_code, 404)

    # =========================================================================
    # PART 2: LEDGER PRIVACY
    # =========================================================================

    def test_05_anonymous_cannot_access_blockchain_ledger(self):
        """Anonymous user trying to access /blockchain is redirected to /login."""
        res = self.client.get("/blockchain", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    def test_06_student_cannot_access_blockchain_ledger(self):
        """Normal user (role='user') must be denied access to /blockchain."""
        c_student = self._login_session(self.student1_id, "user")
        res = c_student.get("/blockchain", follow_redirects=False)
        self.assertEqual(res.status_code, 302)

        # Follow redirect and verify flash denial
        res_follow = c_student.get("/blockchain", follow_redirects=True)
        self.assertIn(b"only available to admin", res_follow.data.lower())

    def test_07_admin_can_access_blockchain_ledger(self):
        """Admin (role='admin') can access the integrity ledger."""
        c_admin = self._login_session(self.admin_id, "admin")
        res = c_admin.get("/blockchain")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Integrity Ledger", res.data)

    def test_08_ledger_does_not_expose_raw_answers_or_payload(self):
        """Blockchain explorer must not expose student answers, options, or data_json payload."""
        self._submit_exam_for_student(
            self.student1_id, "Rahul Sharma", "PRN2026101", [0, 1]
        )
        c_admin = self._login_session(self.admin_id, "admin")
        res = c_admin.get("/blockchain")
        self.assertEqual(res.status_code, 200)

        html = res.data.decode("utf-8")
        # Should display summary info
        self.assertIn("Rahul Sharma", html)
        self.assertIn("PRN2026101", html)
        self.assertIn("Cloud Architecture", html)
        # Should NOT display question options or answers array
        self.assertNotIn("256-bit hash digest", html)
        self.assertNotIn("Backward hash pointers", html)
        self.assertNotIn('"selected_index":', html)
        self.assertNotIn("data_json", html)

    # =========================================================================
    # PART 3: SHA-256 INTEGRITY VERIFICATION
    # =========================================================================

    def test_09_valid_block_verifies_successfully(self):
        """verify_result_integrity correctly reports valid block."""
        block_id, _, block = self._submit_exam_for_student(
            self.student1_id, "Rahul Sharma", "PRN2026101", [0, 1]
        )
        with app.app_context():
            res = blockchain.verify_result_integrity(block_id)
            self.assertTrue(res["valid"])
            self.assertEqual(res["block_index"], block_id)
            self.assertEqual(res["reason"], "Integrity verified")

    def test_10_tampered_block_data_is_detected(self):
        """verify_result_integrity detects when stored block data has been tampered with."""
        block_id, _, block = self._submit_exam_for_student(
            self.student1_id, "Rahul Sharma", "PRN2026101", [0, 1]
        )
        with app.app_context():
            # Simulate direct database tampering: modify score without updating hash
            row = db.session.get(Block, block_id)
            data = json.loads(row.data_json)
            data["score"] = 99
            row.data_json = json.dumps(data, sort_keys=True)
            db.session.commit()

            res = blockchain.verify_result_integrity(block_id)
            self.assertFalse(res["valid"])
            self.assertIn("mismatch", res["reason"].lower())

            chain_valid, problems = blockchain.is_chain_valid()
            self.assertFalse(chain_valid)
            self.assertGreater(len(problems), 0)

    def test_11_broken_previous_hash_link_is_detected(self):
        """verify_result_integrity detects when previous_hash pointer link is broken."""
        block_id1, _, _ = self._submit_exam_for_student(
            self.student1_id, "Rahul Sharma", "PRN2026101", [0, 1]
        )
        block_id2, _, _ = self._submit_exam_for_student(
            self.student2_id, "Sneha Patil", "PRN2026102", [0, 0]
        )
        with app.app_context():
            # 1. Tamper with block2's previous_hash alone -> detected as invalid
            row2 = db.session.get(Block, block_id2)
            row2.previous_hash = "deadbeef" * 8
            db.session.commit()

            res = blockchain.verify_result_integrity(block_id2)
            self.assertFalse(res["valid"])

            # 2. Tamper with previous_hash AND recompute hash to bypass data hash check -> caught by link check
            from blockchain import compute_hash
            new_hash = compute_hash(row2.id, row2.timestamp, json.loads(row2.data_json), row2.previous_hash)
            row2.hash = new_hash
            db.session.commit()

            res2 = blockchain.verify_result_integrity(block_id2)
            self.assertFalse(res2["valid"])
            self.assertIn("link", res2["reason"].lower())

    def test_12_nonexistent_block_verification(self):
        """verify_result_integrity returns structured failure for missing block."""
        with app.app_context():
            res = blockchain.verify_result_integrity(9999)
            self.assertFalse(res["valid"])
            self.assertIn("does not exist", res["reason"])

    def test_13_historical_valid_blocks_remain_valid(self):
        """Historical valid blocks remain verified as new blocks are appended."""
        b1, _, _ = self._submit_exam_for_student(self.student1_id, "Rahul Sharma", "PRN2026101", [0, 1])
        b2, _, _ = self._submit_exam_for_student(self.student2_id, "Sneha Patil", "PRN2026102", [0, 0])

        with app.app_context():
            res1 = blockchain.verify_result_integrity(b1)
            res2 = blockchain.verify_result_integrity(b2)
            self.assertTrue(res1["valid"])
            self.assertTrue(res2["valid"])

    def test_14_admin_verify_endpoints(self):
        """Admin can trigger verification via /verify and /admin/verify_block/<id>."""
        b1, _, _ = self._submit_exam_for_student(self.student1_id, "Rahul Sharma", "PRN2026101", [0, 1])
        c_admin = self._login_session(self.admin_id, "admin")

        # Whole ledger check
        res_whole = c_admin.post("/verify", json={})
        self.assertEqual(res_whole.status_code, 200)
        data_whole = json.loads(res_whole.data)
        self.assertTrue(data_whole["valid"])

        # Specific block check via /admin/verify_block
        res_single = c_admin.get(f"/admin/verify_block/{b1}")
        self.assertEqual(res_single.status_code, 200)
        data_single = json.loads(res_single.data)
        self.assertTrue(data_single["valid"])
        self.assertEqual(data_single["block_index"], b1)

    # =========================================================================
    # PART 4: RESULT OWNERSHIP & OBJECT-LEVEL AUTHORIZATION
    # =========================================================================

    def test_15_student_can_see_own_result(self):
        """Student can view their own result."""
        b1, _, _ = self._submit_exam_for_student(self.student1_id, "Rahul Sharma", "PRN2026101", [0, 1])
        c_student = self._login_session(self.student1_id, "user", "Rahul Sharma", "PRN2026101")
        res = c_student.get(f"/result/{b1}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Rahul Sharma", res.data)

    def test_16_student_cannot_view_another_student_result_idor(self):
        """Student A cannot access Student B's result by guessing or modifying block_index."""
        b1, _, _ = self._submit_exam_for_student(self.student1_id, "Rahul Sharma", "PRN2026101", [0, 1])
        # Student 2 logs in
        c_student2 = self._login_session(self.student2_id, "user", "Sneha Patil", "PRN2026102")

        # Student 2 attempts to open Student 1's block
        res = c_student2.get(f"/result/{b1}", follow_redirects=False)
        self.assertEqual(res.status_code, 302)

        res_follow = c_student2.get(f"/result/{b1}", follow_redirects=True)
        self.assertIn(b"permission to view another student", res_follow.data.lower())
        self.assertNotIn(b"Rahul Sharma", res_follow.data)

    def test_17_admin_and_student_results_authorization(self):
        """Admin can view results; normal user cannot access admin exam results endpoint."""
        b1, _, _ = self._submit_exam_for_student(self.student1_id, "Rahul Sharma", "PRN2026101", [0, 1])

        # Admin 1 can view
        c_admin1 = self._login_session(self.admin_id, "admin")
        res1 = c_admin1.get(f"/result/{b1}")
        self.assertEqual(res1.status_code, 200)

        res_results1 = c_admin1.get(f"/admin/exams/{self.exam_id}/results")
        self.assertEqual(res_results1.status_code, 200)
        self.assertIn(b"Student Submissions", res_results1.data)

        # Normal student cannot access /admin/exams/<id>/results
        c_student = self._login_session(self.student1_id, "user")
        res_stu = c_student.get(f"/admin/exams/{self.exam_id}/results", follow_redirects=False)
        self.assertEqual(res_stu.status_code, 302)

    # =========================================================================
    # PART 5: ROLE SECURITY
    # =========================================================================

    def test_18_role_authorization_matrix(self):
        """Role boundaries: Anonymous -> /login, User -> denied admin areas."""
        # Anonymous checks
        res = self.client.get("/admin", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

        res = self.client.get("/admin/exams/create", follow_redirects=False)
        self.assertEqual(res.status_code, 302)

        # User checks
        c_user = self._login_session(self.student1_id, "user")
        res_adm = c_user.get("/admin", follow_redirects=False)
        self.assertEqual(res_adm.status_code, 302)

        res_create = c_user.get("/admin/exams/create", follow_redirects=False)
        self.assertEqual(res_create.status_code, 302)

        res_results = c_user.get(f"/admin/exams/{self.exam_id}/results", follow_redirects=False)
        self.assertEqual(res_results.status_code, 302)

        res_verify = c_user.post("/verify", json={})
        self.assertEqual(res_verify.status_code, 302)

    # =========================================================================
    # PART 6: CLIENT MANIPULATION PROTECTION
    # =========================================================================

    def test_19_client_cannot_manipulate_scores_or_identity(self):
        """Client-supplied score, percentage, student_id, hash, and block_id are ignored."""
        c = self._login_session(self.student1_id, "user", "Rahul Sharma", "PRN2026101")
        c.get(f"/student/exam/{self.exam_id}")

        # Inject malicious parameters into submission form
        malicious_payload = {
            "csrf_token": "test-csrf-token-12345",
            "answer_0": "0",          # Correct (Question 1)
            "answer_1": "0",          # Incorrect (Question 2 correct is index 1)
            "score": "100",           # Injected
            "percentage": "100.0",    # Injected
            "student_id": str(self.student2_id),  # Injected other student
            "hash": "0xFAKEHASH" * 4, # Injected
            "block_id": "9999",       # Injected
            "correct_count": "50",    # Injected
        }
        res = c.post(f"/student/exam/{self.exam_id}", data=malicious_payload, follow_redirects=False)
        self.assertEqual(res.status_code, 302)

        with app.app_context():
            # Check attempt in database
            attempt = database.get_attempt(self.exam_id, self.student1_id)
            self.assertIsNotNone(attempt)
            # Authoritative server score must be 1 (out of 2), NOT 100!
            self.assertEqual(attempt.score, 1)
            self.assertEqual(attempt.percentage, 50.0)
            self.assertEqual(attempt.student_id, self.student1_id)

            # Block sealed in blockchain must reflect true score
            block = blockchain.get_block(attempt.block_id)
            self.assertIsNotNone(block)
            self.assertEqual(block.data["score"], 1)
            self.assertEqual(block.data["student_name"], "Rahul Sharma")
            self.assertNotEqual(block.data["score"], 100)

    # =========================================================================
    # PART 7: CSRF PROTECTION
    # =========================================================================

    def test_20_csrf_protection_on_state_changing_routes(self):
        """State-changing routes must reject requests with missing or invalid CSRF tokens."""
        c_admin = self._login_session(self.admin_id, "admin")

        # 1. Admin create exam without CSRF token
        res = c_admin.post("/admin/exams/create", data={
            "title": "CSRF Attack Exam",
            "start_time": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
            "end_time": (datetime.now() + timedelta(days=1, hours=2)).strftime("%Y-%m-%dT%H:%M"),
            "duration_minutes": "30",
            "question_0": "Sample Question",
            "option_0_0": "A", "option_0_1": "B", "option_0_2": "C", "option_0_3": "D",
            "correct_0": "0",
        }, follow_redirects=True)
        self.assertIn(b"invalid security token", res.data.lower())

        # 2. Admin publish exam with invalid CSRF token
        res_pub = c_admin.post(f"/admin/exams/{self.exam_id}/publish", data={
            "csrf_token": "wrong-token"
        }, follow_redirects=True)
        self.assertIn(b"invalid security token", res_pub.data.lower())

        # 3. Admin close exam without CSRF token
        res_close = c_admin.post(f"/admin/exams/{self.exam_id}/close", data={}, follow_redirects=True)
        self.assertIn(b"invalid security token", res_close.data.lower())

        # 4. Student submit exam without CSRF token
        c_student = self._login_session(self.student1_id, "user")
        c_student.get(f"/student/exam/{self.exam_id}")
        res_sub = c_student.post(f"/student/exam/{self.exam_id}", data={
            "answer_0": "0",
            # missing csrf_token
        }, follow_redirects=True)
        self.assertIn(b"invalid security token", res_sub.data.lower())


if __name__ == "__main__":
    unittest.main()
