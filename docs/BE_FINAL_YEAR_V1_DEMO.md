# B.E. Final Year Examination Platform (V1) — Teacher Pilot Demo Guide

**Target Scope:** B.E. Computer Science and Engineering (Final Year)  
**System Architecture:** Flask + SQLAlchemy + SQLite (Local) / Neon PostgreSQL (Cloud)  
**Integrity Layer:** Private Hash-Linked SHA-256 Blockchain  
**Status:** V1 Pilot Ready  

---

## 1. Prerequisites

1. **Environment Setup**:
   - Python 3.10+ installed.
   - Dependencies installed via `pip install -r requirements.txt`.
   - Local database seeded via `python seed_demo_pilot.py` (or live Vercel cloud deployment).
2. **Access Points**:
   - **Local URL**: `http://localhost:5000`
   - **Cloud Deployment**: `https://blockchain-based-secure-online-exam.vercel.app/`
3. **Demo Accounts (Placeholders)**:
   - **Teacher / Administrator**:
     - Identifier: `admin_demo` (or custom created via `python init_db.py`)
     - Role: `admin`
     - Permissions: Exam scheduling, drafting, publishing, reviewing submissions, ledger auditing.
   - **Student (Completed Attempt)**:
     - PRN: `BE2026CS001` (Rahul Sharma)
     - Role: `user`
     - Status: Already completed *Distributed Systems & Consensus V1* (Score: 3/3, sealed into Block).
   - **Student (Fresh / Ready to Attempt)**:
     - PRN: `BE2026CS002` (Priya Patil)
     - Role: `user`
     - Status: Ready to take published examinations live during demonstration.

---

## 2. Part 1 — Teacher / Administrator Workflow

### Step 1: Administrator Sign In
1. Navigate to `/login`.
2. Enter the administrator credentials (`admin_demo` / `AdminDemoPass123!`).
3. Click **Sign In**.
4. **Expected Outcome**:
   - Redirects to `/admin` (Admin Dashboard).
   - Navbar displays `Admin Dashboard`, `+ Create Exam`, `Integrity Ledger`, and `Logout (Admin)`.
   - Header shows: `Admin Dashboard &middot; BE Final Year Examination System &middot; B.E. Computer Science and Engineering`.
   - Metric cards display real-time counters:
     - `TOTAL EXAMS`
     - `DRAFT EXAMS`
     - `PUBLISHED EXAMS`
     - `CLOSED EXAMS`
     - `REGISTERED USERS` (B.E. Final Year Students)
     - `TOTAL SUBMISSIONS`

### Step 2: Create a Scheduled Examination
1. Click **+ Create New Exam** (or navigate to `/admin/exams/create`).
2. Fill in the exam metadata:
   - **Exam Title**: `Network Security & Cryptography Unit Test`
   - **Start Time**: Set to current time minus 5 minutes (or scheduled opening).
   - **End Time**: Set to current time plus 2 hours.
   - **Duration**: `15` minutes.
3. Add Multiple Choice Questions:
   - **Question 1**:
     - Prompt: `What does the SHA in SHA-256 stand for?`
     - Options: `A) Secure Hash Algorithm`, `B) Simple Host Access`, `C) Server Hardening Auth`, `D) Shared Hash Array`
     - Correct Option: `Option A`
   - **Question 2**:
     - Prompt: `Which standard TCP port is utilized by HTTPS?`
     - Options: `A) 80`, `B) 22`, `C) 443`, `D) 8080`
     - Correct Option: `Option C`
4. Click **Save as Draft**.
5. **Expected Outcome**:
   - Redirects to `/admin`.
   - Flash banner: `Exam created successfully as draft.`
   - Exam appears in the table with a yellow `[Draft]` status badge.
   - Action buttons available: `Edit`, `Publish`, `Delete`.

### Step 3: Publish the Examination
1. On the newly created draft exam, click **Publish**.
2. **Expected Outcome**:
   - Status badge transitions from `Draft` to `Published (Open Now)`.
   - The exam is now live and accessible to registered students.
   - Action buttons update to: `Results`, `Close`.

---

## 3. Part 2 — Student Examination Workflow

### Step 1: Student Sign In
1. Click **Logout** from the Admin session.
2. Navigate to `/login`.
3. Sign in as student `Priya Patil` (PRN: `BE2026CS002`, Password: `StudentPass123!`).
4. **Expected Outcome**:
   - Redirects to `/student` (Student Portal).
   - Header displays: `Student Portal`, `B.E. Final Year &middot; B.E. Computer Science and Engineering`, Logged in as `Priya Patil &middot; College PRN: BE2026CS002`.

### Step 2: Dashboard State Organization
1. Observe the organized exam categories:
   - **Available Now**: Lists `Network Security & Cryptography Unit Test` with duration `15 min` and active deadline.
   - **Upcoming**: Shows future scheduled exams with open date/time.
   - **Completed**: (Empty for Priya; shows completed submission with score for Rahul Sharma).
2. Note that draft exams created by the teacher are completely invisible to students.

### Step 3: Take Examination
1. Click **Take Exam &rarr;** on `Network Security & Cryptography Unit Test`.
2. **Expected Outcome**:
   - Loads the clean MCQ exam interface at `/student/exam/<id>`.
   - Prominently displays the live countdown timer (`exam-timer-container`), synchronized with the server's deadline.
   - Server initializes an active `Attempt` record in the database.

### Step 4: Submit Answers
1. Select answers:
   - Q1: Select `Secure Hash Algorithm`
   - Q2: Select `443`
2. Click **Submit Exam**.
3. **Expected Outcome**:
   - Submission evaluation executes exclusively on the server.
   - Server calculates score (`2 / 2`), percentage (`100.0%`), and records duration used.
   - Automatically invokes the blockchain ledger to seal a new block containing candidate PRN, timestamp, score, and previous block hash.
   - Redirects to `/result/<block_index>`.

---

## 4. Part 3 — Result Verification & Cryptographic Fingerprint

### Step 1: Student Result Review
1. On `/result/<block_index>`, inspect the evaluated summary:
   - **Candidate Details**: `Priya Patil &middot; PRN: BE2026CS002 &middot; Class: B.E. Final Year (B.E. Computer Science and Engineering)`.
   - **Score**: `2 / 2` (Large display).
   - **Percentage**: `100.0% Score`.
   - **Stats Grid**:
     - `Correct: 2` (Green)
     - `Incorrect: 0` (Red)
     - `Unanswered: 0` (Amber)
     - `Time Used: <duration>` (Blue)
   - **Timing Info**: Start time, submission timestamp, duration used.

### Step 2: Cryptographic SHA-256 Integrity Verification
1. Inspect the **Result Integrity** container on the result page:
   - Status Badge: `✓ SHA-256 Integrity Verified` (Green).
   - Verification Explanation: `The stored result data matches its authoritative cryptographic fingerprint and backward ledger link.`
   - Fingerprint Box: Displays the 64-character SHA-256 hash sealed into the ledger.
2. **Key Academic Point for Teachers**:
   - Traditional databases allow silent SQL modifications.
   - In this platform, any post-submission alteration to scores, candidate PRNs, or timestamps recalculates to a completely different SHA-256 hash, causing the integrity check to fail instantly.

---

## 5. Part 4 — Teacher Examination Audit & Ledger Explorer

### Step 1: Review Exam Results
1. Log out of student session and log back in as `admin_demo`.
2. On `/admin`, locate the published exam and click **Results** (or `/admin/exams/<id>/results`).
3. **Expected Outcome**:
   - Shows total submissions count, class average score, highest score, lowest score, and average percentage.
   - Submissions table lists student name, PRN, score, percentage, submission time, and a **View Result** button linking to the sealed result block.

### Step 2: Audit Integrity Ledger (Blockchain Explorer)
1. Click **Integrity Ledger** in the navigation bar (or navigate to `/blockchain`).
2. **Expected Outcome**:
   - Displays the cryptographic chain of blocks from Genesis (`Block #0`) to the latest result blocks.
   - Each block card displays:
     - Block index & timestamp
     - Associated exam title, student name, and masked PRN
     - Score & total marks
     - SHA-256 Block Hash
     - Previous Block Hash pointer
3. Click **Verify Blockchain Integrity**:
   - The server iterates sequentially through the hash chain.
   - Validates that `hash == compute_hash(...)` for every block and `previous_hash == previous.hash`.
   - Displays modal/banner: `Integrity verified: all blocks in the ledger are cryptographically valid.`

---

## 6. Part 5 — Security & Failure Cases Demonstrated

| Scenario | Tested Behavior | Security Outcome |
|---|---|---|
| **Draft Access by Student** | Student attempts direct GET to `/student/exam/<draft_id>` | Blocked; redirects to `/student` with error flash |
| **Closed Exam Access** | Student attempts GET to `/student/exam/<closed_id>` | Blocked; redirects with `This exam has been closed.` |
| **Double Submission** | Student submits answers twice or resends POST | Blocked; single attempt rule strictly enforced |
| **Result IDOR** | Student visits `/result/<other_student_block_id>` | Blocked; user can only view their own result |
| **Admin Route Isolation** | Student visits `/admin` or `/blockchain` | Blocked; HTTP 302 redirect to home or login |
| **Client Parameter Injection** | Student POSTs malicious `score=100` or `student_id=99` | Ignored; evaluation and identity are server-authoritative |
| **Direct DB Tampering** | Attacker modifies row data in database without re-hashing | Flagged; verification fails with `Hash mismatch` |

---

## 7. Known Scope & Limitations

1. **Academic Scope**:
   - Strictly designed for a **single B.E. Final Year class** (Computer Science and Engineering).
   - Multi-department, multi-year, and university-wide hierarchies are out of scope for V1.
2. **Ledger Architecture**:
   - The blockchain ledger is an application-level, hash-linked cryptographic chain providing **tamper-evident verification**.
   - It is not a distributed proof-of-work/proof-of-stake network.
3. **Question Types**:
   - Supports single-correct Multiple Choice Questions (MCQ) with 4 choices. Advanced essay questions and randomized question banks are planned for future versions.
