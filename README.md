# MGM University — B.E. Final Year Examination Platform

**Version:** B.E. Final Year Examination Platform (V1)<br>
**Academic Scope:** Department of Computer Science & Engineering · Final Year (2025–2026)<br>
**Security Framework:** Server-Authoritative Evaluation & SHA-256 Tamper-Evident Ledger

[![Live Demo](https://img.shields.io/badge/Live-Demo-success)](https://blockchain-based-secure-online-exam.vercel.app/)
[![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-Web_Framework-black?logo=flask)](https://flask.palletsprojects.com/)
[![Tests](https://img.shields.io/badge/Tests-135%2F135%20Passing-brightgreen)](#testing)

## Overview

The **MGM University B.E. Final Year Examination Platform** is an institutional web-based examination portal designed for conducting scheduled MCQ examinations and maintaining tamper-evident marksheet records. The user interface adheres to the visual identity and institutional design principles of **MGM University** ([mgmu.ac.in](https://mgmu.ac.in/)).

The platform supports two roles:

- **Admin / Faculty** — Author examination papers, configure start/end windows and timers, manage draft/published/closed lifecycle, review class submission metrics, and audit the cryptographic ledger.
- **Student (Candidate)** — Register with official college PRN, access scheduled examinations within designated windows, take distraction-free timed exams, and receive server-evaluated marksheets.

Cryptographic security is provided via a private, hash-linked **SHA-256 integrity ledger**. When an examination attempt is finalized, an immutable cryptographic fingerprint is sealed into the chain. Any post-submission tampering with marks or candidate data immediately breaks hash validation and is flagged upon audit.

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
- Admin-only integrity ledger (students cannot access raw blockchain data)
- Client parameter injection protection (score, percentage, student_id ignored)

### SHA-256 Integrity System

- SHA-256 based result hashing
- Private hash-linked blockchain (each block references previous block's hash)
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
            │   Application  │          │   Blockchain   │
            │      Data      │          │    Ledger      │
            └───────────────┘          └────────────────┘
```

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

- Neon PostgreSQL (production deployment)
- SQLite (local development fallback)

### Integrity

- Python `hashlib`
- SHA-256
- Private hash-linked blockchain ledger

### Deployment

- Vercel
- Neon PostgreSQL
- GitHub

## Project Structure

```text
Blockchain-Based-Secure-Online-Examination-System/
│
├── app.py                          # Flask application and routes
├── blockchain.py                   # SHA-256 blockchain logic and verification
├── database.py                     # Database layer (SQLAlchemy helpers)
├── models.py                       # ORM models (User, Exam, Question, Attempt, Block)
├── validators.py                   # Input validation (registration, login, exam creation)
├── init_db.py                      # First-time database setup and admin creation
├── requirements.txt                # Python dependencies
├── vercel.json                     # Vercel deployment configuration
├── .env.example                    # Environment variable template
│
├── static/
│   ├── style.css                   # Application stylesheet
│   └── script.js                   # Client-side JavaScript
│
├── public/static/                  # Vercel static asset mirror
│
├── templates/
│   ├── base.html                   # Base template with navigation
│   ├── index.html                  # Landing page
│   ├── login.html                  # Login form
│   ├── register.html               # Registration form
│   ├── admin_dashboard.html        # Admin dashboard with stats
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
└── tests/
    ├── test_phase1_roles.py        # Authentication and role tests
    ├── test_phase2_registration.py # Registration and PRN tests
    ├── test_phase3_admin_exam_management.py  # Admin exam lifecycle tests
    ├── test_phase4_exam_engine.py  # Exam timing and submission tests
    ├── test_phase5_results.py      # Evaluation and result tests
    ├── test_phase6_security_integrity.py    # Security and integrity tests
    ├── test_phase8_be_final_v1.py  # B.E. Final Year V1 completion tests
    └── test_phase9_pilot_readiness.py # Pilot readiness and end-to-end tests
```

## Local Setup

### 1. Clone the repository

```bash
git clone https://github.com/deoreparth700-design/Blockchain-Based-Secure-Online-Examination-System.git
cd Blockchain-Based-Secure-Online-Examination-System
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

The project includes 135 automated tests across 8 phase-specific test suites.

Run all tests:

```bash
python -m unittest tests/test_phase1_roles.py tests/test_phase2_registration.py tests/test_phase3_admin_exam_management.py tests/test_phase4_exam_engine.py tests/test_phase5_results.py tests/test_phase6_security_integrity.py tests/test_phase8_be_final_v1.py tests/test_phase9_pilot_readiness.py
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
| Phase 10 & 11 | MGM University visual identity redesign, responsive & accessibility QA, final release |

A formatting check can also be performed with:

```bash
git diff --check
```

## Security

The application includes several security-related controls:

- Password hashing using Werkzeug security utilities
- Server-side and client-side input validation
- CSRF protection on all state-changing POST routes
- HTTP-only session cookies with SameSite=Lax
- Role-based access control (admin/user)
- Server-enforced exam time windows (server clock is authoritative)
- Database-enforced single-attempt constraint per student per exam
- IDOR protection: users cannot view another user's result
- Admin-only blockchain ledger: students cannot access raw chain data
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
Production → Neon PostgreSQL
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

This simulates an attacker modifying blockchain data without recalculating the original block hash. The application can then detect the inconsistency when validating the blockchain.

> This is a demonstration of tamper detection, not a claim that the application itself is an immutable decentralized database.

## Limitations

This project is primarily an academic and demonstration system.

Current limitations include:

- The system is designed for a single BE Final Year class (not multi-class or college-wide)
- The private blockchain is application-controlled rather than decentralized
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

## Why Blockchain Is Used

Traditional database storage can be modified by someone with sufficient database access.

This project adds cryptographic integrity checks:

```text
Result Data
    ↓
SHA-256 Hash
    ↓
Private Hash-Linked Blockchain
    ↓
Tamper Detection via Hash Mismatch
```

The goal is not to store the complete exam on a public blockchain. Instead, blockchain technology is used to create a **verifiable integrity fingerprint** for the result. Any modification to stored data causes the SHA-256 hash to change, which is immediately detectable through chain validation.

## Author

**Parth Deore**

B.Tech Computer Science & Engineering

GitHub: `deoreparth700-design`

## License

This project is intended for educational and academic use.
