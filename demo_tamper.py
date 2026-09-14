"""
demo_tamper.py
--------------
This is NOT part of the live web app on purpose. A real system used
by real students should never ship a public button that edits scores
-- so this demonstration lives in a separate script that only YOU run,
directly against the database, when you want to show someone
(a classmate, an examiner) how tamper detection works.

Usage:
    python demo_tamper.py <block_index> <new_score>

Example:
    python demo_tamper.py 3 100

This directly overwrites Block #3's stored score to 100 WITHOUT
recalculating its hash -- exactly like an attacker editing the
database file by hand. Afterwards, open /blockchain in the browser
and click "Verify Blockchain" to watch it get caught.

To undo the demo and restore normal (valid) state, either:
  - re-run this script with the block's original score, or
  - just delete exam_system.db and run init_db.py again to start fresh.
"""

import sys

from app import app
from blockchain import Blockchain

if len(sys.argv) != 3:
    print("Usage: python demo_tamper.py <block_index> <new_score>")
    sys.exit(1)

block_index = int(sys.argv[1])
new_score = int(sys.argv[2])

with app.app_context():
    blockchain = Blockchain()
    block = blockchain.get_block(block_index)

    if not block or "score" not in block.data:
        print(f"Block #{block_index} is not a valid exam-result block.")
        sys.exit(1)

    print(f"Before: Block #{block_index} score = {block.data['score']}")

    tampered_data = dict(block.data)
    tampered_data["score"] = new_score
    blockchain.tamper_block(block_index, tampered_data)

    print(f"After:  Block #{block_index} score = {new_score} (hash NOT recalculated)")
    print("\nNow open /blockchain in the browser and click 'Verify Blockchain' to see it flagged.")
