# Blockchain-Based Secure Online Examination System

A small, real online examination system for classroom use. Teachers create
exams with a start/end time window; students log in, take the exam once, and
get an instant score. Every submitted result is sealed into a hash-linked
blockchain, so results can't be silently altered after the fact without it
being detectable.

This is **not** a toy demo — it uses real login accounts, a real SQLite
database, and enforces its rules (time windows, one attempt per student) on
the server, not just in the browser. It also does **not** use Ethereum,
Solidity, smart contracts, or any external blockchain network — the
blockchain here is a small, from-scratch hash-chain implemented directly in
Python (`blockchain.py`), which keeps it easy to fully understand and audit.

---

## 1. What This System Does

- **Teachers** log in, create MCQ exams with a start and end time, and view
  results once students submit.
- **Students** sign up with their name, roll number, and a password, then log
  in to take any exam that is currently open.
- Every submitted result becomes a **block**: a package of data (student,
  answers, score) plus a SHA-256 hash of that data and the previous block's
  hash. Anyone logged in can open **View Blockchain** and click
  **Verify Blockchain** to confirm nothing has been altered.

## 2. What Changed From the Classroom-Demo Version

| | Demo version | This version |
|---|---|---|
| Storage | Two JSON files | Real SQLite database (`exam_system.db`) via SQLAlchemy |
| Accounts | None — type any name | Real login, password-hashed, two roles |
| Exams | One global exam | Many exams, each with a start/end time window |
| Attempts | Unlimited | One attempt per student per exam (enforced by the database) |
| Time limit | Not enforced | Exam only accessible within its scheduled window (enforced on the server) |
| Tampering demo | A public "Simulate Tampering" button in the app | Moved to a separate script (`demo_tamper.py`) — a real system shouldn't ship a public button that edits scores |

## 3. Blockchain Concepts (recap)

- **Hash**: a SHA-256 fingerprint of a block's data. Same input always gives
  the same hash; changing even one character gives a completely different one.
- **Block**: `index`, `timestamp`, `data`, `previous_hash`, `hash` — now a row
  in the `blocks` table instead of an entry in a JSON list.
- **Previous Hash**: each block includes the hash of the block before it,
  chaining them together.
- **Tamper detection**: `is_chain_valid()` in `blockchain.py` recomputes every
  block's hash from its current data and compares it to the hash stored when
  it was created. A mismatch means the data was changed afterward.

## 4. Technologies Used

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, vanilla JavaScript |
| Backend | Python 3, Flask |
| Database | SQLite, accessed via Flask-SQLAlchemy |
| Blockchain | Pure Python, `hashlib` (SHA-256) — no external library |
| Auth | Flask sessions + `werkzeug.security` password hashing |

## 5. Project Structure

```
project/
├── app.py              Flask routes (auth, teacher, student, blockchain)
├── models.py            Database schema: User, Exam, Question, Attempt, Block
├── database.py          SQLAlchemy setup + small helper functions
├── blockchain.py        Block hashing + chain verification logic
├── init_db.py            Run once: creates tables + your first teacher account
├── demo_tamper.py        Standalone script for the tamper-detection demo
├── requirements.txt
├── README.md
├── templates/            Jinja2 HTML templates
├── static/               style.css + script.js
└── exam_system.db        Created automatically by init_db.py (not in git)
```

## 6. How to Install and Run

```bash
pip install -r requirements.txt
python init_db.py
```

`init_db.py` will ask you to type a name, username, and password for your
first teacher account — nothing is hardcoded in the source code.

Then start the server:

```bash
python app.py
```

Open your browser to:

```
http://127.0.0.1:5000
```

### Running it for an actual class

If students will connect from other devices on the same network (e.g. a
classroom Wi-Fi), find your machine's local IP address (e.g. `192.168.1.42`)
and have students visit `http://192.168.1.42:5000` instead of `127.0.0.1`.
Make sure `app.py`'s `app.run(...)` line includes `host="0.0.0.0"` (it already
does) so the server accepts connections from other devices, not just itself.

**Before a real class uses this**, change the `app.secret_key` value in
`app.py` to something private and random — it's currently a placeholder.

## 7. Demonstrating the Blockchain Integrity (for a viva or class demo)

1. Log in as a student, take an exam, note the block number shown on your
   result page.
2. Go to **View Blockchain**, click **Verify Blockchain** — status shows
   VALID.
3. In a terminal, run:
   ```bash
   python demo_tamper.py <block_index> <new_score>
   ```
   This directly edits that block's stored score without recalculating its
   hash — exactly what a database-level attacker might do.
4. Refresh **View Blockchain** and click **Verify Blockchain** again — the
   status flips to TAMPERING DETECTED, with the exact block flagged.
5. To reset the block back to a valid state, run `demo_tamper.py` again with
   the original score, or delete `exam_system.db` and start over with
   `python init_db.py`.

## 8. Known Limitations (by design, for this scope)

- No anti-cheating measures (tab-switch detection, fullscreen lock, webcam
  proctoring) — this system trusts that a logged-in student's submission is
  their honest attempt.
- No client-side countdown timer that auto-submits — the exam's start/end
  window is enforced, but nothing forces a student to submit before the
  window closes on its own.
- Single-server deployment — for a bigger institution running many
  simultaneous exams, this would need to move from SQLite to PostgreSQL and
  add a production web server (Gunicorn + Nginx). For one class at a time,
  SQLite is genuinely sufficient.
