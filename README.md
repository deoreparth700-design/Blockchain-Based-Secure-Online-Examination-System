# Blockchain-Based Secure Online Examination System

A web-based examination platform designed to conduct scheduled MCQ exams and protect result integrity using **SHA-256 hash chaining** and **Ethereum Sepolia** anchoring.

[![Live Demo](https://img.shields.io/badge/Live-Demo-success)](https://blockchain-based-secure-online-exam.vercel.app/)
[![Python](https://img.shields.io/badge/Python-3.x-blue?logo=python)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-Web_Framework-black?logo=flask)](https://flask.palletsprojects.com/)
[![Ethereum](https://img.shields.io/badge/Ethereum-Sepolia-purple?logo=ethereum)](https://ethereum.org/)

## Overview

The **Blockchain-Based Secure Online Examination System** is a Flask-based online examination platform with two roles:

- **Teacher** — create and schedule exams, manage questions, view submissions, and anchor results to Ethereum.
- **Student** — register, log in, take scheduled exams, submit answers, and view results.

After an exam is submitted, the system automatically evaluates the answers and records the result. The result is then sealed into a private SHA-256 hash chain. Teachers can optionally anchor that result hash to an Ethereum smart contract on the **Sepolia testnet** for an additional, publicly verifiable integrity layer.

> The system does not store student answers or personal information on Ethereum. Only the cryptographic result hash is anchored on-chain.

## Live Demo

**Application:** https://blockchain-based-secure-online-exam.vercel.app/

The application is deployed on Vercel and uses Neon PostgreSQL for cloud database storage.

## Key Features

### Examination

- Teacher-created MCQ examinations
- Configurable exam start and end times
- Configurable examination duration
- Server-side exam time enforcement
- Automatic answer evaluation
- One attempt per student per exam
- Student result viewing

### Authentication & Validation

- Separate teacher and student roles
- Student self-registration
- Login using username, roll number, or email
- Password hashing
- Server-side input validation
- CSRF protection
- Secure session configuration

### Blockchain Integrity

- SHA-256 based result hashing
- Private hash-linked blockchain
- Previous-hash chaining between blocks
- Blockchain validation for tamper detection
- Demonstration script for simulating database tampering

### Ethereum Integration

- Solidity smart contract
- Ethereum Sepolia testnet
- MetaMask wallet integration
- Teacher-controlled result anchoring
- On-chain result verification
- Transaction and wallet information stored with anchored results
- Ethers.js integration in the frontend

## How It Works

```text
Student
   │
   ▼
Take Scheduled Exam
   │
   ▼
Submit Answers
   │
   ▼
Flask Evaluates Result
   │
   ▼
Database Stores Attempt
   │
   ▼
SHA-256 Hash Generated
   │
   ▼
Private Blockchain Block Created
   │
   ▼
Teacher Can Anchor Result Hash
   │
   ▼
Ethereum Sepolia Smart Contract
   │
   ▼
Result Hash Can Be Verified
```

### Integrity Layers

**Layer 1 — Application Database**

Exam data, users, questions, attempts, and blockchain records are stored using SQLAlchemy.

**Layer 2 — Private Blockchain**

Each result block contains data, a timestamp, its hash, and the previous block's hash. Modifying stored block data causes the recalculated hash to differ, allowing the system to detect unauthorized changes.

**Layer 3 — Ethereum**

The teacher can submit the result hash to the deployed `ExamResultRegistry` smart contract. The contract records the hash together with the wallet address and timestamp.

During verification, the application compares the current result hash with the hash stored on Ethereum.

## Architecture

```text
                         ┌──────────────────┐
                         │     Student      │
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
            │      Data      │          └───────┬────────┘
            └───────────────┘                  │
                                               │ Result Hash
                                               ▼
                                      ┌────────────────────┐
                                      │ Ethereum Sepolia   │
                                      │ ExamResultRegistry │
                                      └─────────┬──────────┘
                                                │
                                                ▲
                                          MetaMask
                                                │
                                      ┌─────────┴──────────┐
                                      │      Teacher       │
                                      └────────────────────┘
```

## Technology Stack

### Frontend

- HTML5
- CSS3
- Vanilla JavaScript
- Jinja2 templates
- Ethers.js

### Backend

- Python
- Flask
- Flask-SQLAlchemy
- SQLAlchemy

### Database

- Neon PostgreSQL for deployment
- SQLite fallback for local development

### Blockchain

- Python `hashlib`
- SHA-256
- Private hash-linked blockchain
- Solidity
- Ethereum Sepolia Testnet
- MetaMask
- Remix IDE
- Ethers.js

### Deployment

- Vercel
- Neon PostgreSQL
- GitHub

## Project Structure

```text
Blockchain-Based-Secure-Online-Examination-System/
│
├── app.py
├── blockchain.py
├── database.py
├── models.py
├── validators.py
├── init_db.py
├── migrate_db.py
├── demo_tamper.py
├── requirements.txt
├── vercel.json
├── .env.example
│
├── contracts/
│   └── ExamResultRegistry.sol
│
├── static/
│   ├── style.css
│   ├── script.js
│   └── js/
│       ├── ethereum.js
│       └── ethereum-config.js
│
├── public/
│   └── static/
│       ├── style.css
│       ├── script.js
│       └── js/
│
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── login.html
│   ├── register.html
│   ├── create_exam.html
│   ├── exam.html
│   ├── exam_results.html
│   ├── result.html
│   ├── blockchain.html
│   ├── teacher_dashboard.html
│   └── student_dashboard.html
│
└── tests/
    └── test_system.py
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

ETHEREUM_CONTRACT_ADDRESS=your-contract-address
ETHEREUM_CHAIN_ID=11155111
```

For local development, `DATABASE_URL` can be omitted and the application will fall back to SQLite.

### 5. Initialize the database

```bash
python init_db.py
```

The script creates the required tables and prompts you to create the first teacher account.

### 6. Start the application

```bash
python app.py
```

Then open:

```text
http://localhost:5000
```

## Ethereum Setup

The Ethereum integration is designed for the **Sepolia testnet**.

### Requirements

- MetaMask browser extension
- Sepolia network enabled
- Sepolia test ETH
- Deployed `ExamResultRegistry` smart contract

### Smart Contract

The project includes:

```text
contracts/ExamResultRegistry.sol
```

The contract provides two main operations:

```solidity
recordResult(attemptId, resultHash)
```

Stores a result hash on Ethereum.

```solidity
verifyResult(attemptId, resultHash)
```

Checks whether the supplied hash matches the anchored hash.

The contract uses an owner-based permission model, meaning only the contract owner can record a result.

## Result Anchoring Flow

1. Student completes an examination.
2. Flask evaluates the submission.
3. The result is stored in the database.
4. The result is sealed into the private SHA-256 blockchain.
5. A teacher opens the student's result.
6. The teacher selects **Anchor on Ethereum**.
7. MetaMask requests transaction approval.
8. The result hash is written to the Ethereum Sepolia contract.
9. The transaction hash is stored by the application.
10. The result can later be verified against the Ethereum record.

## Tamper Detection Demo

The repository includes a demonstration script:

```bash
python demo_tamper.py <block_index> <new_score>
```

Example:

```bash
python demo_tamper.py 1 100
```

This simulates an attacker modifying blockchain data without recalculating the original block hash.

The application can then detect the inconsistency when validating the private blockchain.

If the original result was also anchored to Ethereum, the changed local hash will no longer match the hash stored on-chain.

> This is a demonstration of tamper detection, not a claim that the application itself is an immutable decentralized database.

## Security

The application includes several security-related controls:

- Password hashing using Werkzeug security utilities
- Server-side validation
- Client-side validation
- CSRF protection
- HTTP-only session cookies
- SameSite session configuration
- Role-based access control
- Server-enforced exam time windows
- Single-attempt enforcement
- Ethereum owner authorization
- Cryptographic hash verification

### Important

Never commit sensitive credentials to GitHub.

Do not commit:

```text
.env
```

Never expose:

- Database passwords
- Flask secret keys
- Wallet private keys
- Seed phrases
- Secret recovery phrases

## Testing

The project includes an automated system test suite.

Run:

```bash
python -m unittest tests/test_system.py
```

The current test suite contains **13 tests**, covering core examination-system functionality.

A formatting check can also be performed with:

```bash
git diff --check
```

## Deployment

### Vercel

The application is configured for Vercel using:

```text
vercel.json
```

The deployed Flask application uses Neon PostgreSQL through the `DATABASE_URL` environment variable.

Required Vercel environment variables include:

```text
DATABASE_URL
SECRET_KEY
ETHEREUM_CONTRACT_ADDRESS
ETHEREUM_CHAIN_ID
```

### Database

The application supports:

```text
Production → Neon PostgreSQL
Local Development → SQLite fallback
```

This allows the same application to run locally without requiring a cloud database while still supporting persistent PostgreSQL storage in deployment.

## Limitations

This project is primarily an academic and demonstration system.

Current limitations include:

- Ethereum integration uses the Sepolia testnet.
- Result anchoring is initiated manually by the teacher.
- The private blockchain is application-controlled rather than decentralized.
- Ethereum stores the result hash, not the complete examination record.
- The smart contract currently uses a single owner for anchoring authorization.
- Production deployment would require stronger operational controls, monitoring, backup strategy, and scalability considerations.

## Future Improvements

Possible future enhancements include:

- Multiple authorized teachers on the smart contract
- Automated Ethereum anchoring through a backend relayer
- Better audit logging
- Production-grade database migrations
- Advanced examination analytics
- Question banks and randomized questions
- Role and permission management
- Email notifications
- Scalable blockchain/L2 deployment
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
Optional Ethereum Anchor
```

The goal is not to store the complete exam on a public blockchain.

Instead, blockchain technology is used to create a **verifiable integrity fingerprint** for the result.

## Author

**Parth Deore**

B.Tech Computer Science & Engineering

GitHub: `deoreparth700-design`

## License

This project is intended for educational and academic use.
