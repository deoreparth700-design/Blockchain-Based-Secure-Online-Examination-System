# Blockchain-Based Secure Online Examination System

## Project Overview

This is an online examination system that implements two blockchain integrity layers to secure examination results against tampering. The system allows teachers to create and schedule exams, students to register and take exams, and provides a dual-blockchain verification process.

## Features

- **Teacher Portal**: Create exams with specific time windows, view student submissions, and anchor results to Ethereum.
- **Student Portal**: Register, login (via username or roll number), take active exams, and view verified results.
- **Dual-Blockchain Integrity**:
  1. **Private Blockchain**: A local, Python-based SHA-256 hash-chain storing results in SQLite.
  2. **Public Ethereum Layer**: An external integrity anchor on the Ethereum Sepolia Testnet using a Solidity smart contract.
- **Tamper Detection Demonstration**: Verify the Private Blockchain to catch unauthorized database edits.

## Architecture

```text
                 ONLINE EXAM SYSTEM
                        │
                        ▼
                Student submits exam
                        │
                        ▼
                 Flask calculates score
                        │
                        ▼
                 SQLite stores result
                        │
                        ▼
             Private Python Blockchain
                        │
                        │
                SHA-256 result hash
                        │
                        ▼
          ┌───────────────────────────┐
          │ Ethereum Smart Contract   │
          │           │               │
          │           ▼               │
          │ Result hash stored on     │
          │ Ethereum Sepolia          │
          └───────────────────────────┘
                        ▲
                        │
                   MetaMask
                        ▲
                        │
                 Teacher/Admin
```

**Important distinction**: The Python blockchain is a private hash-chain securing every result automatically. Ethereum is used as a second public integrity layer, initiated manually by the teacher via MetaMask, to store an external, independently verifiable cryptographic hash of the result.

## Technologies Used

### Frontend
- HTML, CSS (Vanilla)
- JavaScript
- Jinja2 (Templating)

### Backend
- Python
- Flask

### Database
- SQLite
- Flask-SQLAlchemy

### Existing Blockchain
- SHA-256 (Python `hashlib`)
- Hash-linked blockchain

### Ethereum Layer
- Solidity
- Ethereum Sepolia Testnet
- MetaMask
- Remix IDE
- ethers.js

### Deployment
- PythonAnywhere (Hosting)
- GitHub

## Project Structure

```text
Blockchain-Based-Secure-Online-Examination-System/
│
├── app.py                 # Flask web application
├── blockchain.py          # Private blockchain logic
├── database.py            # SQLite database interactions
├── models.py              # SQLAlchemy ORM models
├── init_db.py             # Database initialization script
├── migrate_db.py          # Script to update DB schema for Ethereum
├── demo_tamper.py         # Script to demonstrate tampering on the private chain
├── requirements.txt       # Python dependencies
├── README.md              # Project documentation
│
├── contracts/
│   └── ExamResultRegistry.sol  # Solidity smart contract
│
├── static/
│   ├── style.css
│   ├── script.js
│   └── js/
│       ├── ethereum.js         # MetaMask & Ethers.js logic
│       └── ethereum-config.js  # Ethereum contract address & ABI
│
├── templates/             # Jinja2 HTML templates
│   └── ...
│
└── exam_system.db         # SQLite database file
```

## Local Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/deoreparth700-design/Blockchain-Based-Secure-Online-Examination-System.git
   cd Blockchain-Based-Secure-Online-Examination-System
   ```
2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use: venv\Scripts\activate
   ```
3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
4. **Initialize database**:
   ```bash
   python init_db.py
   # Follow the prompt to create the first teacher account
   ```
5. **Run Database Migration (for Ethereum updates)**:
   ```bash
   python migrate_db.py
   ```
6. **Start the application**:
   ```bash
   python app.py
   ```
   Open `http://localhost:5000` in your browser.

## MetaMask & Sepolia Setup

1. Install the [MetaMask browser extension](https://metamask.io/).
2. Enable "Show test networks" in MetaMask settings.
3. Switch to the **Sepolia** test network.
4. Obtain test ETH from a Sepolia faucet (e.g., [Alchemy Sepolia Faucet](https://sepoliafaucet.com/)). *Never use real ETH for this academic project.*

## Smart Contract Deployment via Remix IDE

1. Open [Remix IDE](https://remix.ethereum.org/).
2. Create a new file named `ExamResultRegistry.sol`.
3. Paste the contents of `contracts/ExamResultRegistry.sol` from this repository.
4. Go to the **Solidity Compiler** tab and compile the contract (ensure compiler version `^0.8.0` is selected).
5. Go to the **Deploy & Run Transactions** tab:
   - Set **Environment** to `Injected Provider - MetaMask`.
   - MetaMask will prompt you to connect. Approve it.
   - Ensure the correct wallet (Teacher/Admin) and network (Sepolia) is selected.
   - Click **Deploy**.
   - Confirm the transaction in MetaMask.
6. Once deployed, expand the contract under **Deployed Contracts**.
7. Click the **Copy** icon next to the contract name to copy its address.

### Configuring the Application

1. Open `static/js/ethereum-config.js`.
2. Replace `YOUR_DEPLOYED_CONTRACT_ADDRESS` with the copied contract address.
3. Replace the `CONTRACT_ABI` if you made any changes to the Solidity code (copy from Remix's Compiler tab).

## Result Anchoring Workflow

1. A student submits an exam. The result is calculated and sealed into the **Private Blockchain**.
2. A teacher logs in and views the result.
3. The teacher clicks **"Anchor on Ethereum"**.
4. MetaMask opens and requests transaction approval on the Sepolia network.
5. Once confirmed, the result hash is permanently recorded on the public blockchain.
6. The application displays a verifiable transaction hash and link to Etherscan.

## Ethereum Verification

Anyone viewing a result anchored on Ethereum can click **"Verify on Ethereum"**. The frontend (`ethers.js`) will query the smart contract on Sepolia to ensure the current result hash matches the immutable hash stored on the blockchain.

## Tamper Demonstration

1. Run the tampering script to simulate a database attack:
   ```bash
   python demo_tamper.py <block_index> <new_score>
   # Example: python demo_tamper.py 1 100
   ```
2. Open the application, log in as a teacher, and go to "View Blockchain".
3. The **Private Blockchain** will instantly flag the tampered block because the stored hash will no longer match the recalculated hash.
4. If the result was anchored to Ethereum, verifying it will also fail because the tampered local hash won't match the one stored securely on Sepolia.

## PythonAnywhere Deployment

1. Push your updated code to GitHub:
   ```bash
   git add .
   git commit -m "Add Ethereum integration"
   git push origin main
   ```
2. In the PythonAnywhere console, pull the latest code:
   ```bash
   cd /home/deore123/Blockchain-Based-Secure-Online-Examination-System
   git pull origin main
   ```
3. Activate the virtual environment:
   ```bash
   workon exam-system-env
   ```
4. Run the database migration (Do NOT delete `exam_system.db`!):
   ```bash
   python migrate_db.py
   ```
5. Reload the PythonAnywhere web app from the Web tab.

## Security Considerations

- **Never** commit a private key, seed phrase, or secret recovery phrase to GitHub.
- The smart contract (`ExamResultRegistry.sol`) uses an `onlyOwner` modifier. Only the wallet address that deployed the contract can anchor results.
- The student's private examination data (answers, personal info) is **not** stored on Ethereum. Only a cryptographic hash (`SHA-256`) of the canonical result data is anchored, preserving privacy.

## Limitations & Future Improvements

- Currently uses Ethereum Sepolia Testnet for academic demonstration. For production, it would be deployed to Mainnet or an L2 (Polygon, Arbitrum).
- Smart contract role management could be expanded to allow multiple authorized teachers.
- The system depends on the teacher manually anchoring results; a backend relayer could automate this process.
