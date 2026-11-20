"""
Wallet QA Validator - Backend API
A lightweight Flask service simulating a FinTech / iGaming transactional ledger.
Includes REST endpoints, static file serving, and intentional QA test targets.
"""

import os
import sqlite3
from typing import Any, Dict, List, Optional
from flask import Flask, jsonify, request, send_from_directory

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DB_PATH = os.path.join(BASE_DIR, "database", "wallet.db")
SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")
SEED_PATH = os.path.join(BASE_DIR, "database", "seed_data.sql")
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")


def get_db_connection() -> sqlite3.Connection:
    """Creates a database connection with dict-like row access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(force: bool = False) -> None:
    """Initializes schema and seeds data if DB doesn't exist or force=True."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if force or not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) == 0:
        print(f"[*] Initializing database at {DB_PATH}...")
        conn = sqlite3.connect(DB_PATH)
        with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        with open(SEED_PATH, "r", encoding="utf-8") as f:
            conn.executescript(f.read())
        conn.commit()
        conn.close()
        print("[+] Database initialized and seeded successfully.")


# -----------------------------------------------------------------------------
# Frontend Routes
# -----------------------------------------------------------------------------
@app.route("/")
def serve_index():
    return send_from_directory(FRONTEND_DIR, "index.html")


@app.route("/<path:filename>")
def serve_static(filename: str):
    return send_from_directory(FRONTEND_DIR, filename)


# -----------------------------------------------------------------------------
# REST API Endpoints
# -----------------------------------------------------------------------------
@app.route("/api/users", methods=["GET"])
def get_users():
    """Retrieve all users with their current cached balances."""
    conn = get_db_connection()
    users = conn.execute(
        "SELECT id, username, balance, created_at FROM users ORDER BY id ASC"
    ).fetchall()
    conn.close()
    return jsonify([dict(u) for u in users])


@app.route("/api/users/<int:user_id>", methods=["GET"])
def get_user(user_id: int):
    """Retrieve a single user by ID."""
    conn = get_db_connection()
    user = conn.execute(
        "SELECT id, username, balance, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    conn.close()
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(dict(user))


@app.route("/api/transactions", methods=["GET"])
def get_transactions():
    """
    Retrieve transaction history with optional filtering by user_id and type.
    Query params:
      - user_id (optional): integer
      - type (optional): 'deposit' | 'withdraw' | 'bet' | 'win'
    """
    user_id = request.args.get("user_id", type=int)
    txn_type = request.args.get("type", type=str)

    query = """
        SELECT t.id, t.user_id, u.username, t.type, t.amount, t.status, t.reference_id, t.created_at
        FROM transactions t
        JOIN users u ON t.user_id = u.id
        WHERE 1=1
    """
    params: List[Any] = []

    if user_id:
        query += " AND t.user_id = ?"
        params.append(user_id)

    if txn_type and txn_type.lower() != "all":
        query += " AND t.type = ?"
        params.append(txn_type.lower())

    query += " ORDER BY t.id DESC"

    conn = get_db_connection()
    txns = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(t) for t in txns])


@app.route("/api/transaction", methods=["POST"])
def create_transaction():
    """
    Executes a new financial transaction and updates the user's cached balance.
    Expected JSON:
      - user_id: int
      - type: 'deposit' | 'withdraw' | 'bet' | 'win'
      - amount: float
      - reference_id: str
    """
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    user_id = data.get("user_id")
    txn_type = data.get("type")
    raw_amount = data.get("amount")
    reference_id = data.get("reference_id")

    # Basic presence validations
    if user_id is None or not txn_type or raw_amount is None or not reference_id:
        return jsonify({"error": "Missing required fields: user_id, type, amount, reference_id"}), 400

    try:
        amount = float(raw_amount)
    except (ValueError, TypeError):
        return jsonify({"error": "Field 'amount' must be a numeric value"}), 400

    if txn_type not in ("deposit", "withdraw", "bet", "win"):
        return jsonify({"error": f"Invalid transaction type: '{txn_type}'"}), 400

    # -------------------------------------------------------------------------
    # QA TARGET / INTENTIONAL PLANT BUG:
    # Notice: The backend intentionally omits:
    #   if amount <= 0: return jsonify({"error": "Amount must be strictly positive"}), 400
    #
    # This allows negative withdrawal amounts (e.g. amount = -100) which causes:
    #   new_balance = balance - (-100) = balance + 100 !
    # Furthermore, no idempotency check prevents duplicate reference_id submission.
    # Automated QA Test 4 specifically targets this vulnerability.
    # -------------------------------------------------------------------------

    conn = get_db_connection()
    user = conn.execute("SELECT id, username, balance FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"error": f"User ID {user_id} not found"}), 404

    current_balance = user["balance"]

    # Business rule: Insufficient funds validation (only triggers if amount > 0)
    if txn_type in ("withdraw", "bet") and amount > 0:
        if current_balance < amount:
            conn.close()
            return jsonify({
                "error": f"Insufficient funds: Requested {txn_type} ({amount:.2f}) exceeds current balance ({current_balance:.2f})"
            }), 400

    # Calculate balance adjustment
    if txn_type in ("deposit", "win"):
        new_balance = round(current_balance + amount, 2)
    else:  # withdraw, bet
        new_balance = round(current_balance - amount, 2)

    try:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE users SET balance = ? WHERE id = ?",
            (new_balance, user_id),
        )
        cursor.execute(
            """
            INSERT INTO transactions (user_id, type, amount, status, reference_id)
            VALUES (?, ?, ?, 'completed', ?)
            """,
            (user_id, txn_type, amount, reference_id),
        )
        new_txn_id = cursor.lastrowid
        conn.commit()

        # Fetch updated user and transaction row
        updated_txn = conn.execute(
            """
            SELECT t.id, t.user_id, u.username, t.type, t.amount, t.status, t.reference_id, t.created_at
            FROM transactions t
            JOIN users u ON t.user_id = u.id
            WHERE t.id = ?
            """,
            (new_txn_id,),
        ).fetchone()

        conn.close()
        return jsonify({
            "message": "Transaction processed successfully",
            "transaction": dict(updated_txn),
            "new_balance": new_balance,
        }), 201

    except Exception as e:
        conn.rollback()
        conn.close()
        return jsonify({"error": f"Database transaction error: {str(e)}"}), 500


@app.route("/api/audit", methods=["GET"])
def run_audit():
    """
    Executes the 3 SQL Data Integrity audit queries and returns anomalies found.
    Used by the QA Audit Inspector in the UI.
    """
    conn = get_db_connection()

    # Query 1: Ledger Mismatches
    q1 = """
        SELECT 
            u.id AS user_id,
            u.username,
            ROUND(u.balance, 2) AS current_cached_balance,
            ROUND(COALESCE(ledger.calculated_balance, 0.0), 2) AS ledger_calculated_balance,
            ROUND(u.balance - COALESCE(ledger.calculated_balance, 0.0), 2) AS discrepancy_amount,
            CASE 
                WHEN u.balance > COALESCE(ledger.calculated_balance, 0.0) THEN 'OVER_CREDITED'
                ELSE 'UNDER_CREDITED'
            END AS anomaly_classification
        FROM users u
        LEFT JOIN (
            SELECT 
                user_id,
                SUM(
                    CASE 
                        WHEN type IN ('deposit', 'win') THEN amount
                        WHEN type IN ('withdraw', 'bet') THEN -amount
                        ELSE 0.0
                    END
                ) AS calculated_balance
            FROM transactions
            WHERE status = 'completed'
            GROUP BY user_id
        ) ledger ON u.id = ledger.user_id
        WHERE ABS(u.balance - COALESCE(ledger.calculated_balance, 0.0)) > 0.001;
    """
    ledger_mismatches = [dict(r) for r in conn.execute(q1).fetchall()]

    # Query 2: Duplicate Transactions
    q2 = """
        SELECT 
            t.reference_id,
            t.user_id,
            u.username,
            t.type,
            t.amount,
            COUNT(*) AS occurrence_count,
            GROUP_CONCAT(t.id, ', ') AS duplicate_transaction_ids,
            MIN(t.created_at) AS first_seen_at,
            MAX(t.created_at) AS last_seen_at
        FROM transactions t
        JOIN users u ON t.user_id = u.id
        GROUP BY t.reference_id, t.user_id, t.amount, t.type
        HAVING COUNT(*) > 1;
    """
    duplicates = [dict(r) for r in conn.execute(q2).fetchall()]

    # Query 3: Negative Balances
    q3 = """
        SELECT 
            u.id AS user_id,
            u.username,
            ROUND(u.balance, 2) AS negative_balance,
            u.created_at AS account_created_at
        FROM users u
        WHERE u.balance < 0.00;
    """
    negative_balances = [dict(r) for r in conn.execute(q3).fetchall()]

    conn.close()
    return jsonify({
        "status": "completed",
        "total_anomalies": len(ledger_mismatches) + len(duplicates) + len(negative_balances),
        "anomalies": {
            "ledger_mismatches": ledger_mismatches,
            "duplicate_transactions": duplicates,
            "negative_balances": negative_balances,
        }
    })


@app.route("/api/reset", methods=["POST"])
def reset_db():
    """Resets the database back to clean schema and seed data."""
    init_db(force=True)
    return jsonify({"message": "Database reset to initial seed state successfully"}), 200


if __name__ == "__main__":
    init_db()
    # Default port 5000
    app.run(host="127.0.0.1", port=5000, debug=False)
