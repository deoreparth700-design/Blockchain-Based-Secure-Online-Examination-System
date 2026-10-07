"""
blockchain.py
--------------
The blockchain logic itself. This is almost UNCHANGED from the demo
version -- compute_hash() and is_chain_valid() work exactly the same
way. The only real change is WHERE blocks are stored: previously a
list inside a JSON file, now rows in the `blocks` table (see
models.py), read and written through SQLAlchemy.

Concept recap:
    Every block stores a SHA-256 hash of its own data PLUS the
    previous block's hash. Change a block's data later, and its
    hash no longer matches what's recomputed -- breaking the link
    to every block after it. That's how tampering is detected.
"""

import hashlib
import json
import time

from models import db, Block as BlockModel


def compute_hash(index, timestamp, data, previous_hash):
    """
    Deterministically turn a block's contents into one SHA-256 hash.
    sort_keys=True guarantees the same data always produces the same
    string, and therefore the same hash.
    """
    block_string = json.dumps({
        "index": index,
        "timestamp": timestamp,
        "data": data,
        "previous_hash": previous_hash,
    }, sort_keys=True)
    return hashlib.sha256(block_string.encode()).hexdigest()


class BlockView:
    """
    A convenience wrapper around a BlockModel row, so templates and
    app.py can work with plain attributes (.data as a dict, not a
    JSON string) without needing to know about the database layer.
    """
    def __init__(self, row):
        self.index = row.id
        self.timestamp = row.timestamp
        self.data = json.loads(row.data_json)
        self.previous_hash = row.previous_hash
        self.hash = row.hash

    def recompute_hash(self):
        return compute_hash(self.index, self.timestamp, self.data, self.previous_hash)

    def to_dict(self):
        return {
            "index": self.index,
            "timestamp": self.timestamp,
            "data": self.data,
            "previous_hash": self.previous_hash,
            "hash": self.hash,
        }


class Blockchain:
    """
    Talks to the `blocks` table. No in-memory list is kept -- every
    call reads fresh from the database, so this class has no state
    that could go stale, and (just as importantly) SQLite's own
    file-level locking means two simultaneous submissions can't both
    read the same "last block" and corrupt the chain -- one write
    simply waits a few milliseconds for the other to finish.
    """

    def _ensure_genesis(self):
        if BlockModel.query.count() == 0:
            genesis_data = {"info": "Genesis Block - Exam Chain Initialized"}
            now = time.time()
            genesis_hash = compute_hash(0, now, genesis_data, "0")
            genesis = BlockModel(
                id=0,
                timestamp=now,
                data_json=json.dumps(genesis_data, sort_keys=True),
                previous_hash="0",
                hash=genesis_hash,
            )
            db.session.add(genesis)
            db.session.commit()

    @property
    def last_block(self):
        self._ensure_genesis()
        row = BlockModel.query.order_by(BlockModel.id.desc()).first()
        return BlockView(row)

    def add_block(self, data):
        """
        Seal a new piece of data (an exam result) into a new block,
        linked to the current last block's hash.
        """
        self._ensure_genesis()
        previous = self.last_block
        new_index = previous.index + 1
        new_timestamp = time.time()
        new_hash = compute_hash(new_index, new_timestamp, data, previous.hash)

        row = BlockModel(
            id=new_index,
            timestamp=new_timestamp,
            data_json=json.dumps(data, sort_keys=True),
            previous_hash=previous.hash,
            hash=new_hash,
        )
        db.session.add(row)
        db.session.commit()
        return BlockView(row)

    def tamper_block(self, index, new_data):
        """
        DEMO ONLY -- used by demo_tamper.py, never exposed in the web
        app itself. Directly overwrites a block's data WITHOUT
        recalculating its hash, exactly like an attacker editing a
        database row by hand.
        """
        row = db.session.get(BlockModel, index)
        if row is None:
            return False
        row.data_json = json.dumps(new_data, sort_keys=True)
        # row.hash is deliberately left untouched.
        db.session.commit()
        return True

    def get_block(self, index):
        row = db.session.get(BlockModel, index)
        return BlockView(row) if row else None

    def all_blocks(self):
        self._ensure_genesis()
        rows = BlockModel.query.order_by(BlockModel.id.asc()).all()
        return [BlockView(r) for r in rows]

    def verify_result_integrity(self, block_index):
        """
        Dedicated backend integrity verification service for a specific result block.
        Determines:
        1. Block exists.
        2. Block's stored hash matches the block's current data (recomputed hash).
        3. Block's previous_hash matches the preceding block's actual hash.
        4. Relevant chain integrity up to this block is valid.
        5. Result has not been altered.
        """
        if block_index is None:
            return {
                "valid": False,
                "block_index": None,
                "reason": "Block index must be specified",
            }

        target_block = self.get_block(block_index)
        if target_block is None:
            return {
                "valid": False,
                "block_index": block_index,
                "reason": f"Block #{block_index} does not exist",
            }

        # 1. Verify target block's own data hash
        recomputed = target_block.recompute_hash()
        if target_block.hash != recomputed:
            return {
                "valid": False,
                "block_index": block_index,
                "reason": "Block data hash mismatch: stored hash does not match current data",
            }

        # 2. If genesis block (index == 0), hash match is sufficient
        if target_block.index == 0:
            return {
                "valid": True,
                "block_index": 0,
                "reason": "Integrity verified (Genesis Block)",
            }

        # 3. Verify link to preceding block
        prev_row = BlockModel.query.filter(BlockModel.id < target_block.index).order_by(BlockModel.id.desc()).first()
        if not prev_row:
            return {
                "valid": False,
                "block_index": block_index,
                "reason": "Preceding block not found (broken link)",
            }

        if target_block.previous_hash != prev_row.hash:
            return {
                "valid": False,
                "block_index": block_index,
                "reason": f"Broken chain link: previous_hash does not match Block #{prev_row.id}'s hash",
            }

        # 4. Verify historical chain integrity from genesis up to this block
        chain_rows = BlockModel.query.filter(BlockModel.id <= target_block.index).order_by(BlockModel.id.asc()).all()
        for i in range(1, len(chain_rows)):
            curr_v = BlockView(chain_rows[i])
            prev_v = BlockView(chain_rows[i - 1])

            if curr_v.hash != curr_v.recompute_hash():
                return {
                    "valid": False,
                    "block_index": block_index,
                    "reason": f"Chain integrity failure at Block #{curr_v.index}: data was modified",
                }
            if curr_v.previous_hash != prev_v.hash:
                return {
                    "valid": False,
                    "block_index": block_index,
                    "reason": f"Broken chain link between Block #{prev_v.index} and Block #{curr_v.index}",
                }

        return {
            "valid": True,
            "block_index": block_index,
            "reason": "Integrity verified",
        }

    def is_chain_valid(self):
        blocks = self.all_blocks()
        problems = []
        for i in range(1, len(blocks)):
            current = blocks[i]
            previous = blocks[i - 1]

            recomputed = current.recompute_hash()
            if current.hash != recomputed:
                problems.append(
                    f"Block #{current.index}: stored hash does not match recomputed hash "
                    f"(data was changed after this block was created)."
                )

            if current.previous_hash != previous.hash:
                problems.append(
                    f"Block #{current.index}: previous_hash does not match Block #{previous.index}'s "
                    f"actual hash (the link between blocks is broken)."
                )

        return (len(problems) == 0, problems)


def verify_result_integrity(block_index):
    """Module-level helper to verify integrity of a specific block."""
    return Blockchain().verify_result_integrity(block_index)
