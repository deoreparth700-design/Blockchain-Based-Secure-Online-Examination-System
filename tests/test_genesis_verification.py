"""
tests/test_genesis_verification.py
----------------------------------
Dedicated regression test suite verifying Block #0 Genesis block:
1. Genesis creation consistency: stored hash equals recomputed hash.
2. Genesis invariants: id == 0, previous_hash == "0", expected payload.
3. Individual genesis verification: verify_result_integrity(0) returns valid.
4. Tampering detection: tampering block 0 payload causes verification failure.
5. Full chain verification: global is_chain_valid() passes for untouched genesis block.
6. UI verification endpoints: /verify and /admin/verify_block/0 return valid.
7. Admin blockchain dashboard: page contains no mismatch warnings for genesis block.
"""

import json
import os
import sys
import unittest

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEST_DB_PATH = os.path.join(BASE_DIR, "tests", "test_genesis_verification.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

sys.path.insert(0, BASE_DIR)

from app import app
from models import db, Block as BlockModel
from blockchain import Blockchain
import database


class TestGenesisVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

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
        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.create_all()

            # Create test admin
            self.admin = database.create_user(
                name="Test Admin",
                identifier="test_admin_gen",
                username="test_admin_gen",
                email="admin.gen@test.edu",
                password="AdminPassword123!",
                role="admin",
            )
        self.client = app.test_client()

    def _login_admin(self, client):
        client.get("/login")
        with client.session_transaction() as sess:
            csrf_token = sess.get("csrf_token", "")
        return client.post(
            "/login",
            data={
                "identifier": "test_admin_gen",
                "password": "AdminPassword123!",
                "csrf_token": csrf_token,
            },
            follow_redirects=True,
        )

    def test_01_genesis_creation_consistency(self):
        """Genesis creation uses a single timestamp: block.hash == block.recompute_hash()."""
        with app.app_context():
            chain = Blockchain()
            chain._ensure_genesis()

            block = chain.get_block(0)
            self.assertIsNotNone(block)
            recomputed = block.recompute_hash()
            self.assertEqual(block.hash, recomputed)

    def test_02_genesis_invariants(self):
        """Genesis invariants: id == 0, previous_hash == '0', expected payload."""
        with app.app_context():
            chain = Blockchain()
            chain._ensure_genesis()

            block = chain.get_block(0)
            self.assertEqual(block.index, 0)
            self.assertEqual(block.previous_hash, "0")
            self.assertEqual(block.data, {"info": "Genesis Block - Exam Chain Initialized"})
            self.assertIsInstance(block.timestamp, float)
            self.assertGreater(block.timestamp, 0)

    def test_03_individual_genesis_verification(self):
        """verify_result_integrity(0) returns valid with Genesis Block confirmation."""
        with app.app_context():
            chain = Blockchain()
            chain._ensure_genesis()

            res = chain.verify_result_integrity(0)
            self.assertTrue(res["valid"])
            self.assertEqual(res["block_index"], 0)
            self.assertEqual(res["reason"], "Integrity verified (Genesis Block)")

    def test_04_tampering_detection(self):
        """Tampering genesis payload in database causes individual verification to fail."""
        with app.app_context():
            chain = Blockchain()
            chain._ensure_genesis()

            # Tamper block 0 payload directly
            tampered = chain.tamper_block(0, {"info": "Tampered Genesis Block - Malicious"})
            self.assertTrue(tampered)

            res = chain.verify_result_integrity(0)
            self.assertFalse(res["valid"])
            self.assertEqual(res["block_index"], 0)
            self.assertIn("Block data hash mismatch", res["reason"])

    def test_05_full_chain_verification_with_genesis(self):
        """Global chain validator is_chain_valid() returns valid for pristine genesis block."""
        with app.app_context():
            chain = Blockchain()
            chain._ensure_genesis()

            valid, problems = chain.is_chain_valid()
            self.assertTrue(valid)
            self.assertEqual(len(problems), 0)

    def test_06_ui_verification_endpoints(self):
        """Endpoints /verify and /admin/verify_block/0 return valid for block 0."""
        with app.app_context():
            chain = Blockchain()
            chain._ensure_genesis()

        self._login_admin(self.client)

        # 1. AJAX POST /verify
        res_post = self.client.post("/verify", json={"block_index": 0})
        self.assertEqual(res_post.status_code, 200)
        data_post = res_post.get_json()
        self.assertTrue(data_post["valid"])
        self.assertEqual(data_post["block_index"], 0)

        # 2. Direct GET /admin/verify_block/0
        res_get = self.client.get("/admin/verify_block/0")
        self.assertEqual(res_get.status_code, 200)
        data_get = res_get.get_json()
        self.assertTrue(data_get["valid"])
        self.assertEqual(data_get["block_index"], 0)

    def test_07_blockchain_html_page_no_mismatch_warning(self):
        """Admin /blockchain page renders Block #0 without 'Block data hash mismatch' warning."""
        with app.app_context():
            chain = Blockchain()
            chain._ensure_genesis()

        self._login_admin(self.client)
        res = self.client.get("/blockchain")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("Block #0", html)
        self.assertIn("Genesis Block", html)
        self.assertNotIn("Block data hash mismatch", html)


if __name__ == "__main__":
    unittest.main()
