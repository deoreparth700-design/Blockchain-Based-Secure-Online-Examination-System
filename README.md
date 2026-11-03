# Hash-Chained Online Examination System

**Version:** B.E. Final Year Examination Platform (V1)<br>
**Academic Scope:** Department of Computer Science & Engineering · Final Year (2025–2026)<br>
**Security Framework:** Server-Authoritative Evaluation & SHA-256 Hash Chain

[![Live Demo](https://img.shields.io/badge/Live-Demo-success)](https://blockchain-based-secure-online-exam.vercel.app/)
[![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-Web_Framework-black?logo=flask)](https://flask.palletsprojects.com/)
[![Tests](https://github.com/deoreparth700-design/hash-chained-exam-system/actions/workflows/tests.yml/badge.svg)](https://github.com/deoreparth700-design/hash-chained-exam-system/actions/workflows/tests.yml)

## Overview

An online examination system with a tamper-evident hash chain running on a single server (each sealed result block stores the hash of the previous block). The user interface adheres to the visual identity and institutional design principles of **MGM University** ([mgmu.ac.in](https://mgmu.ac.in/)).

The platform supports two roles:

- **Admin / Faculty** — Author examination papers, configure start/end windows and timers, manage draft/published/closed lifecycle, review class submission metrics, and audit the cryptographic ledger.
- **Student (Candidate)** — Register with official college PRN, access scheduled examinations within designated windows, take distraction-free timed exams, and receive server-evaluated marksheets.

Any post-submission tampering with marks or candidate data immediately breaks hash validation and is flagged upon audit.

## What This Is and Is Not

- **Single-server hash chain, not a distributed blockchain.** There is no consensus, no multiple nodes and no cryptocurrency.
- **Detects tampering after the fact.** It flags changes to stored results, but it cannot stop someone with database admin access from rewriting the whole chain.
- **A student learning project.** Built for learning, with a demo dataset and only the security controls listed in the Security section.

## Live Application

**Production URL:** https://blockchain-based-secure-online-exam.vercel.app/

Deployed on Vercel with Neon PostgreSQL cloud database and local SQLite development fallback.

## Key Features

### Examination

- Admin-created MCQ examinations with draft → published → closed lifecycle
- Configurable exam start and end times
- Configurable examination duration per exam
- Server-side exam time enforcement (server clock is authoritative)
- Automatic answer evaluation and scoring
- One attempt per student per exam (database-enforced)
- Detailed result breakdown (correct, incorrect, unanswered)

### Authentication & Security

- Two roles: `admin` and `user`
- Student self-registration with PRN and email
- Login using PRN or email
- Password hashing (Werkzeug)
- Server-side input validation
- CSRF protection on all state-changing routes
- HTTP-only, SameSite session cookies
- Role-based access control
- IDOR protection on results (users cannot view other users' results)
- Admin-only integrity ledger (students cannot access raw ledger data)
- Client parameter injection protection (score, percentage, student_id ignored)

### SHA-256 Integrity System

- SHA-256 based result hashing
- Private hash-linked chain (each block references previous block's hash)
- Automatic block sealing on exam submission
- Per-block integrity verification (`verify_result_integrity`)
- Full chain validation (Genesis to latest block)
- Tamper detection with clear status on result page
- Admin integrity ledger with summary metadata (raw answers suppressed)

## How It Works

```text
Student Registers (PRN + Email)
   │
   ▼
Login → Student Dashboard
   │
   ▼
Take Published Exam (Timed)
   │
   ▼
Submit Answers
   │
   ▼
Flask Evaluates Result (Server-Side)
   │
   ▼
Result Sealed into SHA-256 Block
   │
   ▼
View Result + Integrity Verification
```

### Exam Lifecycle

```text
Admin creates exam → Draft
   │
   ▼
Admin publishes → Published (visible to students)
   │
   ▼
Students take exam within time window
   │
   ▼
Admin closes → Closed (no new attempts)
```

## Architecture

```text
                         ┌──────────────────┐
                         │   Student/Admin   │
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │      Vercel      │
                         │   Flask App      │
                         └────────┬─────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    ▼                           ▼
            ┌───────────────┐          ┌────────────────┐
            │ Neon PostgreSQL│          │ Private SHA-256│
            │   Application  │          │   Hash Chain   │
            │      Data      │          │    Ledger      │
            └───────────────┘          └────────────────┘
```

The ledger is not a separate database: its blocks are stored in the `blocks` table of the same database (Neon PostgreSQL in production, SQLite locally). The hash links between blocks are what make tampering detectable.

## Technology Stack

### Frontend

- HTML5
- CSS3
- Vanilla JavaScript
- Jinja2 templates

### Backend

- Python
- Flask
- Flask-SQLAlchemy
- SQLAlchemy
- Werkzeug (password hashing)

### Database

- Neon PostgreSQL (production deployment, via `psycopg` 3)
- SQLite (local development fallback)

### Integrity

- Python `hashlib`
- SHA-256
- Single-server hash-linked ledger

### Deployment

- Vercel
- Neon PostgreSQL
- GitHub

## Project Structure

```text
hash-chained-exam-system/
│
├── app.py                          # Flask application and routes
├── blockchain.py                   # SHA-256 blockchain logic and verification
├── database.py                     # Database layer (SQLAlchemy helpers)
├── models.py                       # ORM models (User, Exam, Question, Attempt, Block)
├── validators.py                   # Input validation (registration, login, exam creation)
├── throttling.py                   # Database-backed login attempt throttling
├── init_db.py                      # First-time database setup and admin creation
├── seed_demo_pilot.py              # Seeds a fictional demo dataset (local SQLite only)
├── demo_tamper.py                  # Tamper-detection demonstration script
├── migrate_roles.py                # One-off migration: old role names -> admin/user
├── migrate_exams_status.py         # One-off migration: adds exams.status
├── migrate_attempts_started_at.py  # One-off migration: adds attempts.started_at
├── migrate_users_created_at.py     # One-off migration: adds users.created_at
├── requirements.txt                # Python dependencies
├── vercel.json                     # Vercel deployment configuration
├── .env.example                    # Environment variable template
│
├── scripts/
│   └── reset_student_accounts.py   # Maintenance: wipe students and results before a new batch
│
├── docs/
│   └── BE_FINAL_YEAR_V1_DEMO.md    # Step-by-step teacher/student demo guide
│
├── static/
│   ├── style.css                   # Application stylesheet
│   ├── script.js                   # Client-side JavaScript
│   └── images/                     # Logos and favicons
│
├── public/static/                  # Vercel static asset mirror (keep in sync with static/)
│
├── templates/
│   ├── base.html                   # Base template with navigation
│   ├── index.html                  # Landing page
│   ├── login.html                  # Login form
│   ├── register.html               # Registration form
│   ├── admin_dashboard.html        # Admin dashboard with stats
│   ├── admin_students.html         # Admin list of registered students
│   ├── admin_student_detail.html   # Admin view of one student's exam history
│   ├── teacher_dashboard.html      # Legacy teacher dashboard template
│   ├── create_exam.html            # Exam creation form
│   ├── edit_exam.html              # Exam editing form
│   ├── exam.html                   # Exam-taking interface with countdown
│   ├── exam_results.html           # Admin results view
│   ├── result.html                 # Student result with integrity badge
│   ├── blockchain.html             # Admin integrity ledger view
│   └── student_dashboard.html      # Student dashboard
│
├── experimental/
│   └── ethereum/                   # Archived Ethereum/MetaMask integration (not used in V1)
│
└── tests/                          # 14 test files, 202 test cases (see Testing)
    ├── test_database_url.py        # Database URL normalization and psycopg v3 driver tests
    ├── test_login_throttling.py    # Database-backed login throttling tests
    ├── test_phase1_roles.py        # Authentication and role tests
    ├── test_phase2_registration.py # Registration and PRN tests
    ├── test_phase3_admin_exam_management.py  # Admin exam lifecycle tests
    ├── test_phase4_exam_engine.py  # Exam timing and submission tests
    ├── test_phase5_results.py      # Evaluation and result tests
    ├── test_phase6_security_integrity.py    # Security and integrity tests
    ├── test_phase8_be_final_v1.py  # B.E. Final Year V1 completion tests
    ├── test_phase9_pilot_readiness.py # Pilot readiness and end-to-end tests
    ├── test_admin_students.py      # Admin student list and detail pages
    ├── test_genesis_verification.py # Genesis block (Block #0) integrity
    ├── test_login_regression.py    # Login regression cases
    └── test_reset_maintenance.py   # Student reset maintenance workflow
```

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/deoreparth700-design/hash-chained-exam-system.git
cd hash-chained-exam-system
```

### 2. Create a virtual environment

#### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

#### macOS / Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file based on `.env.example`.

```env
DATABASE_URL=postgresql://user:password@host/neondb?sslmode=require
SECRET_KEY=your-random-secret-key
FLASK_DEBUG=False
```

The database connection string accepts `postgres://`, `postgresql://`, or `postgresql+psycopg://` schemes and automatically normalizes to use the `psycopg` (v3) driver.

For local development, `DATABASE_URL` can be omitted and the application will fall back to SQLite.

### 5. Initialize the database

```bash
python init_db.py
```

The script creates the required tables and prompts you to create the first admin account.

### 6. Start the application

```bash
python app.py
```

Then open:

```text
http://localhost:5000
```

## Testing

The project includes 202 automated test cases across 14 test files.

Each test file sets up its own SQLite database when it is imported, so **run each file in its own process**. Running several files in a single `unittest` command shares one app instance between them and causes spurious errors.

Run one test file:

```bash
python -m unittest tests/test_phase1_roles.py
```

Run every test file, one process per file:

```bash
# macOS / Linux / Git Bash
for f in tests/test_*.py; do python -m unittest "$f"; done
```

```powershell
# Windows PowerShell
Get-ChildItem tests\test_*.py | ForEach-Object { python -m unittest $_.FullName }
```

All test suites use isolated SQLite databases and do not touch the production Neon PostgreSQL database.

| Suite | Coverage |
|-------|----------|
| Phase 1 | Authentication, roles, login redirect, role normalization |
| Phase 2 | PRN registration, duplicate prevention, admin injection |
| Phase 3 | Exam creation, lifecycle (draft/publish/close), editing, deletion |
| Phase 4 | Exam timing, server-authoritative deadlines, submission protection |
| Phase 5 | Scoring, result breakdown, ownership, admin statistics |
| Phase 6 | Ethereum removal, ledger privacy, integrity verification, CSRF, IDOR |
| Phase 8 | B.E. Final Year academic scope, registration, state organization, tamper detection |
| Phase 9 | Pilot readiness audit, access control failure cases, client injection immunity, seed integrity, E2E demo workflow |
| Admin students | Admin registered-students list and student detail pages, search, empty states, password hashes never rendered |
| Genesis verification | Block #0 invariants, tamper detection on the genesis block, chain validation and the `/verify` endpoints |
| Login regression | Login by admin username, PRN or email, whitespace and case handling, wrong credentials and empty input |
| Reset maintenance | Student reset workflow: student accounts and their attempts removed, admin account kept and still able to log in |
| Login throttling | Database-backed throttling (5 failures / 15 min), lockout release, credential reset, 24h cleanup |
| Database URL | URL normalization (postgres://, postgresql://, postgresql+psycopg://, sqlite:///), whitespace/quote stripping, and psycopg v3 lazy engine initialization |

The visual redesign and responsive/accessibility work (Phases 10 and 11) has no dedicated automated test file.

A formatting check can also be performed with:

```bash
git diff --check
```

## Security

The application includes several security-related controls:

- Password hashing using Werkzeug security utilities
- Database-backed login attempt throttling: failures are counted per account (5 failed attempts within 15 minutes blocks further login attempts for that account until the 5th most recent failure is 15 minutes old). Known trade-off: anyone who knows a PRN can temporarily lock that account for 15 minutes; there is no per-IP limiting.
- Server-side and client-side input validation
- CSRF protection on all state-changing POST routes
- HTTP-only session cookies with SameSite=Lax
- Role-based access control (admin/user)
- Server-enforced exam time windows (server clock is authoritative)
- Database-enforced single-attempt constraint per student per exam
- IDOR protection: users cannot view another user's result
- Admin-only hash chain ledger: students cannot access raw chain data
- Client parameter injection protection: score, percentage, student_id, hash, block_id, time_used are server-derived and cannot be overridden by POST data
- Custom error handlers: no Python tracebacks or SQL details exposed to users
- Cryptographic SHA-256 hash verification with per-block and full-chain validation

### Important

Never commit sensitive credentials to GitHub.

Do not commit:

```text
.env
```

Never expose:

- Database passwords
- Flask secret keys

## Deployment

### Vercel

The application is configured for Vercel using:

```text
vercel.json
```

The deployed Flask application uses Neon PostgreSQL through the `DATABASE_URL` environment variable.

Required Vercel environment variables:

```text
DATABASE_URL
SECRET_KEY
```

### Database

The application supports:

```text
Production → Neon PostgreSQL (psycopg v3 driver; accepts postgres://, postgresql://, or postgresql+psycopg://)
Local Development → SQLite fallback
```

This allows the same application to run locally without requiring a cloud database while still supporting persistent PostgreSQL storage in deployment.

## Ethereum Integration (Experimental / Archived)

An experimental Ethereum Sepolia and MetaMask integration was developed as a research component and has been **archived** under `experimental/ethereum/`. It is **not required** by V1 and is completely decoupled from the active application runtime.

The V1 examination system relies entirely on the private SHA-256 hash-linked ledger for tamper detection and result verification. No Ethereum wallet, MetaMask extension, or Sepolia testnet connection is needed to operate the current system.

The archived experimental files are preserved for academic documentation only.

## Teacher Pilot Demonstration

A complete step-by-step teacher and student demonstration guide is available in:
[`docs/BE_FINAL_YEAR_V1_DEMO.md`](docs/BE_FINAL_YEAR_V1_DEMO.md)

To seed a realistic, fictional pilot dataset in the local development SQLite database:

```bash
python seed_demo_pilot.py
```

This seeds:
- 1 Administrator account (`admin_demo`)
- 3 Fictional B.E. Final Year student accounts (`BE2026CS001`, `BE2026CS002`, `BE2026CS003`)
- 1 Draft examination
- 1 Published examination
- 1 Completed submission sealed into SHA-256 Block #1
- 1 Closed examination

## Tamper Detection Demo

The repository includes a demonstration script:

```bash
python demo_tamper.py <block_index> <new_score>
```

Example:

```bash
python demo_tamper.py 1 100
```

This simulates an attacker modifying block data without recalculating the original block hash. The application can then detect the inconsistency when validating the chain: log in as an admin, open `/blockchain` and click **Verify Blockchain**.

Run `python seed_demo_pilot.py` first so that Block #1 exists. The script edits the database your `DATABASE_URL` points to (local SQLite when it is unset), so never run it against a database you care about.

## Maintenance Scripts

- `scripts/reset_student_accounts.py` deletes **all student accounts and their attempts and result blocks**, keeps the genesis block, exams and questions, and resets the `admin_demo` admin account. Usage: `python scripts/reset_student_accounts.py --admin-password <password>` (or set `ADMIN_PASSWORD`). It loads your `.env`, so check that `DATABASE_URL` points to the database you intend to reset before running it.
- `migrate_roles.py`, `migrate_exams_status.py`, `migrate_attempts_started_at.py` and `migrate_users_created_at.py` are one-off, non-destructive migrations for databases created before those columns or role names existed. A fresh database created with `init_db.py` does not need them.

> This is a demonstration of tamper detection, not a claim that the application itself is an immutable decentralized database.

## Limitations

This project is primarily an academic and demonstration system.

Current limitations include:

- The system is designed for a single BE Final Year class (not multi-class or college-wide)
- The hash chain is application-controlled on a single server rather than a decentralized network
- Production deployment would require stronger operational controls, monitoring, backup strategy, and scalability considerations
- Future multi-class/college-wide expansion is planned but not implemented

## Future Improvements

Possible future enhancements include:

- Multi-class and department support
- Role expansion (T&P coordinator, department admin)
- Production-grade database migrations
- Advanced examination analytics and export
- Question banks and randomized questions
- Email notifications
- Audit logging
- Improved administration dashboard

## Why a Hash Chain Is Used

Traditional database storage can be modified by someone with sufficient database access.

This project adds cryptographic integrity checks:

```text
Result Data
    ↓
SHA-256 Hash
    ↓
Private Hash-Linked Chain
    ↓
Tamper Detection via Hash Mismatch
```

The goal is not to store the complete exam on a distributed blockchain. Instead, a sequential SHA-256 hash chain creates a **verifiable integrity fingerprint** for each result. Any modification to stored data causes the SHA-256 hash to change, which is immediately detectable through chain validation.

## Author

**Parth Deore**

B.Tech Computer Science & Engineering

GitHub: `deoreparth700-design`

## License

This project is intended for educational and academic use.
