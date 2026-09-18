import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "exam_system.db")

def migrate():
    if not os.path.exists(DB_PATH):
        print("Database not found. Please run init_db.py first.")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if column exists
    cursor.execute("PRAGMA table_info(attempts)")
    columns = [info[1] for info in cursor.fetchall()]

    if 'ethereum_tx_hash' not in columns:
        print("Adding Ethereum fields to attempts table...")
        cursor.execute("ALTER TABLE attempts ADD COLUMN ethereum_tx_hash VARCHAR(66)")
        cursor.execute("ALTER TABLE attempts ADD COLUMN ethereum_contract_address VARCHAR(42)")
        cursor.execute("ALTER TABLE attempts ADD COLUMN ethereum_result_hash VARCHAR(66)")
        cursor.execute("ALTER TABLE attempts ADD COLUMN ethereum_wallet_address VARCHAR(42)")
        cursor.execute("ALTER TABLE attempts ADD COLUMN ethereum_anchored_at DATETIME")
        
        conn.commit()
        print("Database migrated successfully.")
    else:
        print("Database is already up to date. No migration needed.")
        
    conn.close()

if __name__ == '__main__':
    migrate()
