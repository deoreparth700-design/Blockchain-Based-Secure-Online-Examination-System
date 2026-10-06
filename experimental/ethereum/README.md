# Experimental Ethereum & MetaMask Integration (Decoupled from V1)

> **Notice:** The contents of this directory are historical, experimental artifacts and are **completely isolated** from the active V1 Examination System runtime.

## Rationale
In Phase 6 (Security & Integrity Cleanup), Ethereum Sepolia and MetaMask dependencies were permanently decoupled from the core examination system.

The V1 examination system relies strictly on an authoritative, private SHA-256 linked hash ledger for tamper detection and cryptographic result verification.

## Isolated Artifacts
- `contracts/ExamResultRegistry.sol`: Solidity smart contract for anchoring hashes on Sepolia.
- `static/js/ethereum.js`: Browser wallet and ethers.js interaction script.
- `static/js/ethereum-config.js`: Contract ABI and network configuration.
- `migrate_db.py`: One-off SQLite migration script for adding legacy columns.

None of these files are loaded, served, or imported by the V1 Flask application.
