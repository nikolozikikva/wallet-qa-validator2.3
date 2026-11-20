# Wallet QA Validator: Full-Stack & Ledger Integrity Testing Suite

[![Python](https://img.shields.io/badge/Python-3.13%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Framework-Flask_3.1-black.svg)](https://palletsprojects.com/p/flask/)
[![Pytest](https://img.shields.io/badge/Testing-Pytest_8.3-green.svg)](https://docs.pytest.org/)
[![Playwright](https://img.shields.io/badge/E2E-Playwright_Chromium-orange.svg)](https://playwright.dev/)
[![SQLite](https://img.shields.io/badge/Database-SQLite3_Forensics-003B57.svg)](https://www.sqlite.org/)
[![UI](https://img.shields.io/badge/UI-Dark_Dashboard-262626.svg)]()

> A QA Engineering & Full-Stack verification platform demonstrating End-to-End (UI-to-DB) browser automation, forensic SQL data integrity auditing, and formal defect reporting on an iGaming / FinTech transactional wallet ledger.

---

## Architecture Overview

```
+-----------------------------------------------------------------------------------+
|                           WALLET QA VALIDATOR ARCHITECTURE                        |
+-----------------------------------------------------------------------------------+
|                                                                                   |
|  [ FRONTEND LAYER ]  (Responsive Ledger Dashboard UI)                             |
|   ├── Account Selector & Live Monospace Balance Card                              |
|   ├── Transaction Execution Form (REST POST with Inline Validation)               |
|   ├── Filterable Ledger History Table (Deposit, Withdraw, Bet, Win)              |
|   └── Live SQL Data Integrity Inspector Modal                                     |
|                                                                                   |
|                                     │  ▲                                          |
|                  REST HTTP / JSON   │  │  Responses & State                       |
|                                     ▼  │                                          |
|                                                                                   |
|  [ BACKEND LAYER ]   (Python 3 Flask API)                                         |
|   ├── GET  /api/users        -> List all accounts & cached balances               |
|   ├── GET  /api/transactions -> Filter transactions by user_id & type             |
|   ├── POST /api/transaction  -> Atomic balance calculation & row creation         |
|   ├── GET  /api/audit        -> Forensic query execution against SQLite           |
|   └── POST /api/reset        -> Re-seed database to pristine baseline             |
|                                                                                   |
|                                     │  ▲                                          |
|                     Direct PRAGMA   │  │  Row Factory Cursors                     |
|                                     ▼  │                                          |
|                                                                                   |
|  [ DATABASE LAYER ]  (SQLite3: wallet.db)                                         |
|   ├── users        (id, username, balance, created_at)                            |
|   └── transactions (id, user_id, type, amount, status, reference_id, created_at)  |
|                                                                                   |
+-----------------------------------------------------------------------------------+
                                      ▲
                                      │ Automated Assertions
+-----------------------------------------------------------------------------------+
|  [ QA AUTOMATION SUITE ]  (tests/test_ui_and_db.py)                              |
|   ├── Test 1: Positive E2E UI-to-DB Verification (Deposit -> Balance -> Table)   |
|   ├── Test 2: Negative UI-to-DB Validation (Overdraft / Insufficient Funds)       |
|   ├── Test 3: SQL Integrity Forensic Auditing (Drift, Duplicates, Negative)       |
|   └── Test 4: Defect Reproduction (Negative Amount Sign Inversion Exploit)        |
+-----------------------------------------------------------------------------------+
```

---

## Directory Structure

```
wallet-qa-validator/
├── frontend/
│   ├── index.html            # Ledger dashboard UI
│   ├── style.css             # Dark-mode dashboard styles
│   └── app.js                # State management, API sync & SQL audit modal
├── backend/
│   └── app.py                # Flask REST service & auto-initialization
├── database/
│   ├── schema.sql            # SQLite DDL tables, foreign keys & indexes
│   ├── seed_data.sql         # 4 test users & 17 realistic transactions (3 anomalies)
│   └── qa_audit_queries.sql  # Well-commented SQL queries detecting anomalies
├── tests/
│   └── test_ui_and_db.py     # Pytest + Playwright sync API + direct SQLite suite
├── docs/
│   ├── TEST_PLAN.md          # Comprehensive IEEE 829-aligned QA Test Plan
│   └── BUG_REPORTS.md        # 3 formal bug reports with SQL proofs
├── requirements.txt          # Python dependencies (flask, pytest, playwright)
└── README.md                 # Project documentation & run guides
```

---

## Forensic SQL Integrity Audit

The seed dataset incorporates **3 realistic FinTech ledger anomalies** designed to simulate production data corruption, idempotency failures, and balance drift:

| Anomaly # | Description | Target Entity | Detection SQL Technique |
|---|---|---|---|
| **Anomaly 1** | **Ledger Reconciliation Drift:** User balance does not equal transaction sum (`-$510.00` discrepancy). | `sarah_connor` (ID 4) | `LEFT JOIN` on aggregated transaction `SUM(CASE ...)`, filtered by `ABS(u.balance - calculated_balance) > 0.001` |
| **Anomaly 2** | **Duplicate Transaction:** Identical reference ID processed twice (`TXN-ELN-2024-DUP99`). | `elena_rostova` (ID 2) | `GROUP BY reference_id, user_id, amount, type` with `HAVING COUNT(*) > 1` |
| **Anomaly 3** | **Negative Balance Record:** Account permitted to overdraft to `-$40.00`. | `marcus_vance` (ID 3) | `SELECT ... WHERE balance < 0.00` |

---

## Quickstart & Installation

### 1. Prerequisites
- Python 3.10+ (tested on Python 3.13)
- Chrome / Chromium (Playwright will manage this automatically)

### 2. Install Dependencies
```bash
cd wallet-qa-validator
pip install -r requirements.txt
playwright install chromium
```

### 3. Start the Web Application
```bash
python backend/app.py
```
Open your browser to: **`http://127.0.0.1:5000`**

### 4. Run the Automated QA Test Suite
The automated suite automatically spins up the server in-process, resets the database to the baseline state, and runs both headless browser and database assertions:

```bash
pytest tests/test_ui_and_db.py -v
```

---

## Test Execution Summary

The test suite validates the system across multiple architectural layers:

1. **`test_1_positive_e2e_deposit_ui_to_db`**:
   - Executes a `$250.00` deposit via browser interaction.
   - Verifies the live balance increments from `$1,420.50` to `$1,670.50`.
   - Confirms the transaction row is injected into the ledger table.
   - Asserts against `wallet.db` SQLite cursors directly.

2. **`test_2_negative_insufficient_funds_validation`**:
   - Submits an overdraft withdrawal of `$500.00` for an account with only `$85.00`.
   - Verifies the inline UI error banner appears without browser alerts.
   - Asserts that no database transaction row is written and balance remains `$85.00`.

3. **`test_3_sql_integrity_audit_queries`**:
   - Runs `database/qa_audit_queries.sql` against the database.
   - Proves all 3 planted seed anomalies (reconciliation drift, idempotency duplication, negative balance) are detected.

4. **`test_4_bug_reproduction_negative_amount_exploit`**:
   - Automated reproduction of **BUG-WV-001**: Submitting a negative withdrawal amount (`-100.00`) bypasses balance checks and corrupts the ledger by crediting instead of debiting.

---

## UI Layout & Design Specifications

- **Layout Architecture:** Asymmetric two-column grid featuring account selection, live balance metrics, and transaction submission in the left panel (340px), with the filterable transaction ledger in the main panel.
- **Color Palette & Contrast:** High-contrast dark theme utilizing `#0D0D0D` background surfaces, `#161616` container panels, and semantic status indicators (`#16A34A` for credit, `#DC2626` for debit).
- **Typography:** `Plus Jakarta Sans` for UI labels and navigational controls; `JetBrains Mono` (`font-variant-numeric: tabular-nums`) for currency figures, reference IDs, and timestamps.
