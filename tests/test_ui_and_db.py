"""
Wallet QA Validator - Automated E2E & SQL Integrity Test Suite
Covers:
  - Test 1: Positive E2E UI-to-DB Transaction Processing (Deposit)
  - Test 2: Negative UI-to-DB Validation (Insufficient Funds Overdraft Prevention)
  - Test 3: SQL Data Integrity Audit Query Execution & Anomaly Detection
  - Test 4: Planted Bug Reproduction (Negative Amount Sign Inversion & Double Submit)
"""

import os
import re
import socket
import sqlite3
import threading
import time
from typing import Generator
import pytest
from playwright.sync_api import sync_playwright, Page, expect

# Add parent directory to path to import backend
import sys
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from backend.app import app, init_db, DB_PATH, SCHEMA_PATH, SEED_PATH

SERVER_HOST = "127.0.0.1"
SERVER_PORT = 5000
BASE_URL = f"http://{SERVER_HOST}:{SERVER_PORT}"


def is_server_running(host: str, port: int) -> bool:
    """Checks whether the backend server is accepting connections."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


@pytest.fixture(scope="session", autouse=True)
def start_test_server():
    """Starts the Flask server in a background thread if not already running."""
    init_db(force=True)

    if not is_server_running(SERVER_HOST, SERVER_PORT):
        from werkzeug.serving import make_server
        server = make_server(SERVER_HOST, SERVER_PORT, app)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        # Wait for server to bind
        retries = 20
        while retries > 0 and not is_server_running(SERVER_HOST, SERVER_PORT):
            time.sleep(0.2)
            retries -= 1

        if retries == 0:
            raise RuntimeError("Flask server failed to start within timeout.")
        yield
        server.shutdown()
    else:
        yield


@pytest.fixture
def db():
    """Provides a fresh database connection and resets data to seed state."""
    init_db(force=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    yield conn
    conn.close()


@pytest.fixture(scope="function")
def browser_page() -> Generator[Page, None, None]:
    """Launches Playwright headless Chromium for UI testing."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()
        yield page
        browser.close()


# =============================================================================
# TEST 1: Positive E2E UI-to-DB Transaction (Deposit)
# =============================================================================
def test_1_positive_e2e_deposit_ui_to_db(browser_page: Page, db: sqlite3.Connection):
    """
    Scenario: User Alex Turner deposits $250.00 via the web UI.
    Verification:
      1. UI updates: cached balance increases from $1,420.50 to $1,670.50.
      2. UI ledger: table renders newly created deposit transaction row.
      3. SQLite DB direct query: users.balance == 1670.50.
      4. SQLite DB direct query: transactions table holds matching row with 'completed' status.
    """
    page = browser_page
    page.goto(BASE_URL)

    # 1. Assert title and elements loaded
    expect(page.locator("h1.brand-title")).to_contain_text("WALLET LEDGER VALIDATOR")

    # 2. Select Alex Turner (User ID 1)
    account_select = page.locator("#account-select")
    account_select.select_option(value="1")

    # Verify initial balance display ($1,420.50)
    balance_amount = page.locator("#balance-amount")
    expect(balance_amount).to_have_text("1,420.50")

    # 3. Fill transaction form
    page.locator("#txn-type").select_option("deposit")
    page.locator("#txn-amount").fill("250.00")
    test_ref = "TXN-E2E-AUTO-DEP-101"
    page.locator("#txn-reference").fill(test_ref)

    # 4. Submit transaction
    page.locator("#submit-txn-btn").click()

    # 5. Assert UI Inline Success Feedback
    alert_box = page.locator("#form-alert")
    expect(alert_box).to_be_visible()
    expect(alert_box).to_contain_text("processed successfully")
    expect(alert_box).to_contain_text("1,670.50")

    # 6. Assert UI live balance readout updated
    expect(balance_amount).to_have_text("1,670.50")

    # 7. Assert table contains the newly inserted transaction
    table_body = page.locator("#transactions-tbody")
    expect(table_body).to_contain_text(test_ref)
    expect(table_body).to_contain_text("+$250.00")

    # 8. DIRECT DATABASE INTEGRITY ASSERTION (UI-to-DB Verification)
    user_row = db.execute("SELECT balance FROM users WHERE id = 1").fetchone()
    assert user_row is not None
    assert round(user_row["balance"], 2) == 1670.50, f"Expected 1670.50 in DB, found {user_row['balance']}"

    txn_row = db.execute(
        "SELECT user_id, type, amount, status, reference_id FROM transactions WHERE reference_id = ?",
        (test_ref,),
    ).fetchone()
    assert txn_row is not None
    assert txn_row["user_id"] == 1
    assert txn_row["type"] == "deposit"
    assert round(txn_row["amount"], 2) == 250.00
    assert txn_row["status"] == "completed"


# =============================================================================
# TEST 2: Negative Validation (Overdraft / Insufficient Funds)
# =============================================================================
def test_2_negative_insufficient_funds_validation(browser_page: Page, db: sqlite3.Connection):
    """
    Scenario: User Elena Rostova (Balance: $85.00) attempts to withdraw $500.00.
    Verification:
      1. UI displays inline error notification: 'Insufficient funds'.
      2. UI balance does not change (remains $85.00).
      3. SQLite DB direct query: balance remains strictly unchanged.
      4. SQLite DB direct query: no unauthorized transaction record created.
    """
    page = browser_page
    page.goto(BASE_URL)

    # 1. Select Elena Rostova (User ID 2)
    account_select = page.locator("#account-select")
    account_select.select_option(value="2")

    balance_amount = page.locator("#balance-amount")
    expect(balance_amount).to_have_text("85.00")

    # 2. Attempt unauthorized overdraft withdrawal
    page.locator("#txn-type").select_option("withdraw")
    page.locator("#txn-amount").fill("500.00")
    test_ref = "TXN-E2E-OVERDRAFT-REJECT"
    page.locator("#txn-reference").fill(test_ref)

    page.locator("#submit-txn-btn").click()

    # 3. Assert Inline Error Banner
    alert_box = page.locator("#form-alert")
    expect(alert_box).to_be_visible()
    expect(alert_box).to_have_class(re.compile(r"alert-error"))
    expect(alert_box).to_contain_text("Insufficient funds")
    expect(alert_box).to_contain_text("Requested withdraw (500.00) exceeds current balance (85.00)")

    # 4. Assert UI balance remains unmodified
    expect(balance_amount).to_have_text("85.00")

    # 5. DIRECT DATABASE ASSERTION: Zero state change
    user_row = db.execute("SELECT balance FROM users WHERE id = 2").fetchone()
    assert round(user_row["balance"], 2) == 85.00

    txn_row = db.execute(
        "SELECT id FROM transactions WHERE reference_id = ?",
        (test_ref,),
    ).fetchone()
    assert txn_row is None, "Transaction record should NOT exist in database after rejected withdrawal"


# =============================================================================
# TEST 3: SQL Integrity Audit Queries (Detecting Seed Anomalies)
# =============================================================================
def test_3_sql_integrity_audit_queries(db: sqlite3.Connection):
    """
    Executes the queries from database/qa_audit_queries.sql directly against wallet.db.
    Assures that all 3 intentional seed data anomalies are accurately caught:
      - Anomaly 1: Sarah Connor's balance mismatch (5190.75 vs 5700.75 ledger sum).
      - Anomaly 2: Duplicate transaction (TXN-ELN-2024-DUP99 processed twice).
      - Anomaly 3: Negative balance (Marcus Vance has -$40.00).
    """
    audit_sql_path = os.path.join(BASE_DIR, "database", "qa_audit_queries.sql")
    with open(audit_sql_path, "r", encoding="utf-8") as f:
        sql_content = f.read()

    # -------------------------------------------------------------------------
    # Anomaly 1: Ledger Reconciliation Mismatch Query
    # -------------------------------------------------------------------------
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
    mismatches = db.execute(q1).fetchall()
    assert len(mismatches) == 1, f"Expected exactly 1 ledger mismatch, found {len(mismatches)}"
    mismatch = mismatches[0]
    assert mismatch["username"] == "sarah_connor"
    assert round(mismatch["current_cached_balance"], 2) == 5190.75
    assert round(mismatch["ledger_calculated_balance"], 2) == 5700.75
    assert round(mismatch["discrepancy_amount"], 2) == -510.00
    assert mismatch["anomaly_classification"] == "UNDER_CREDITED"

    # -------------------------------------------------------------------------
    # Anomaly 2: Duplicate Transaction Detection Query
    # -------------------------------------------------------------------------
    q2 = """
        SELECT 
            t.reference_id,
            t.user_id,
            u.username,
            t.type,
            t.amount,
            COUNT(*) AS occurrence_count,
            GROUP_CONCAT(t.id, ', ') AS duplicate_transaction_ids
        FROM transactions t
        JOIN users u ON t.user_id = u.id
        GROUP BY t.reference_id, t.user_id, t.amount, t.type
        HAVING COUNT(*) > 1;
    """
    duplicates = db.execute(q2).fetchall()
    assert len(duplicates) == 1, f"Expected 1 duplicate transaction group, found {len(duplicates)}"
    dup = duplicates[0]
    assert dup["reference_id"] == "TXN-ELN-2024-DUP99"
    assert dup["username"] == "elena_rostova"
    assert dup["occurrence_count"] == 2
    assert round(dup["amount"], 2) == 15.00
    assert dup["type"] == "bet"

    # -------------------------------------------------------------------------
    # Anomaly 3: Negative Balance Query
    # -------------------------------------------------------------------------
    q3 = """
        SELECT 
            u.id AS user_id,
            u.username,
            ROUND(u.balance, 2) AS negative_balance
        FROM users u
        WHERE u.balance < 0.00;
    """
    negative_accounts = db.execute(q3).fetchall()
    assert len(negative_accounts) == 1, f"Expected 1 negative balance account, found {len(negative_accounts)}"
    neg = negative_accounts[0]
    assert neg["username"] == "marcus_vance"
    assert round(neg["negative_balance"], 2) == -40.00


# =============================================================================
# TEST 4: Planted Bug Reproduction (Negative Amount Sign Inversion)
# =============================================================================
def test_4_bug_reproduction_negative_amount_exploit(db: sqlite3.Connection):
    """
    QA BUG REPRODUCTION:
    Bug ID: BUG-WV-001 / Severity: High / Vulnerability: Sign Inversion via Negative Amount.
    
    Description:
      The backend POST /api/transaction endpoint validates the presence of 'amount',
      but fails to enforce 'amount > 0'. When an adversary submits a withdrawal with
      a negative amount (e.g. -100.00), the insufficient funds validation is bypassed
      and the ledger balance computation executes:
          new_balance = balance - (-100.00) = balance + 100.00
      This results in an unauthorized balance increase (illicit credit) instead of a debit.
    """
    import urllib.request
    import json

    user_id = 1  # Alex Turner, initial balance 1420.50
    initial_user = db.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
    initial_balance = initial_user["balance"]

    exploit_payload = {
        "user_id": user_id,
        "type": "withdraw",
        "amount": -100.00,
        "reference_id": "TXN-EXPLOIT-NEG-SIGN-001",
    }

    req = urllib.request.Request(
        f"{BASE_URL}/api/transaction",
        data=json.dumps(exploit_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    # The API bug allows this request to succeed (HTTP 201) instead of rejecting with HTTP 400
    with urllib.request.urlopen(req) as response:
        status_code = response.getcode()
        body = json.loads(response.read().decode("utf-8"))

    # Assert bug manifestation: HTTP 201 Created was returned instead of 400 Bad Request
    assert status_code == 201, f"Expected bug reproduction with 201 Created, got {status_code}"
    assert "new_balance" in body

    # Verify that the balance increased instead of decreasing
    updated_user = db.execute("SELECT balance FROM users WHERE id = ?", (user_id,)).fetchone()
    expected_corrupted_balance = initial_balance - (-100.00)  # 1420.50 + 100.00 = 1520.50
    assert round(updated_user["balance"], 2) == round(expected_corrupted_balance, 2)
    assert updated_user["balance"] > initial_balance, "CRITICAL: Balance increased on withdrawal request!"
