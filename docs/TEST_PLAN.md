# Test Plan: Wallet QA Validator & Ledger Integrity

**Project Name:** `wallet-qa-validator`  
**Application Type:** FinTech / iGaming Transactional Ledger & User Balance Subsystem  
**Document Version:** 1.0.0  
**Test Lead:** Senior QA Automation & Data Integrity Engineer  
**Status:** Approved / Active  

---

## 1. Executive Summary & Objective

The **Wallet QA Validator** is a mission-critical financial ledger subsystem responsible for tracking user account balances and recording immutable transaction histories (`deposit`, `withdraw`, `bet`, `win`). In online gaming and financial services, ledger consistency, idempotency, and strict balance boundaries are non-negotiable.

The primary objective of this QA test campaign is to:
1. Validate End-to-End (UI-to-Database) data consistency across all user operations.
2. Verify boundary checking and overdraft protection mechanisms under adverse input conditions.
3. Perform automated SQL-level data integrity auditing to detect ledger drift, duplicate transactions, and unauthorized overdrafts.
4. Reproduce and document edge-case security/financial logic flaws in a controlled staging sandbox.

---

## 2. Scope of Testing

### 2.1 In-Scope
- **Functional Testing:** UI user switching, live balance synchronization, transaction form execution, and ledger table filtering (`all`, `deposit`, `withdraw`, `bet`, `win`).
- **Data Integrity & Reconciliation:** Direct SQLite query auditing against the double-entry style ledger; balance-to-transaction sum reconciliations.
- **Idempotency & Concurrency:** Detection of duplicate transaction references and handling of repeated submissions.
- **Negative & Boundary Testing:** Zero values, decimal precision, insufficient funds rejection, and negative value injection.
- **Automated Regression Suite:** Pytest + Playwright (Headless Chromium) + direct SQLite cursor assertions.

### 2.2 Out-of-Scope
- Multi-region distributed replication testing.
- Third-party fiat payment gateway integrations (e.g., Stripe, Adyen webhooks).
- KYC/AML identity verification flows.

---

## 3. Test Environment & Stack

| Component | Specification |
|---|---|
| **Operating System** | Windows 11 / Linux CI Runner |
| **Backend Framework** | Python 3.13 / Flask 3.1 REST API |
| **Database Engine** | SQLite 3.x (with Foreign Key constraints enabled) |
| **Frontend UI** | Vanilla ES6+ JavaScript, HTML5, Responsive CSS3 Dashboard |
| **Automation Framework** | Pytest 8.x, Playwright 1.65+ (Chromium) |
| **Test Database Baseline** | `database/schema.sql`, `database/seed_data.sql` |
| **Audit Scripts** | `database/qa_audit_queries.sql` |

---

## 4. Test Strategy & Methodologies

```
+-------------------------------------------------------------+
|                     TESTING PYRAMID                         |
|                                                             |
|           [ E2E Browser Tests: Playwright ]                 |
|           - Deposit UI-to-DB confirmation                   |
|           - Insufficient funds inline error banner          |
|                                                             |
|       [ API & Contract Testing: REST Requests ]             |
|       - /api/users, /api/transactions, /api/transaction     |
|       - Exploit & Boundary testing (Negative amounts)       |
|                                                             |
|   [ SQL Data Integrity Audits: Automated Queries ]          |
|   - Ledger sum reconciliation vs cached users.balance       |
|   - Duplicate reference_id detection (Idempotency)          |
|   - Negative balance violation scanning                     |
+-------------------------------------------------------------+
```

1. **Deterministic State Management:**  
   Prior to each automated run, the database is reset via `init_db(force=True)` to ensure reproducible baselines.
2. **Dual-Layer Assertion (UI + DB):**  
   Every UI test verifies not only the DOM visual presentation (balance header, ledger table rows, alert boxes) but also queries the SQLite database directly to confirm persistent storage.
3. **Automated Forensic SQL Audits:**  
   SQL reconciliation queries run automatically to audit the system for ledger drift without relying on UI state.

---

## 5. Entry & Exit Criteria

### 5.1 Entry Criteria
- Flask application starts cleanly and serves static UI on `http://127.0.0.1:5000`.
- Database initializes cleanly with tables `users` and `transactions` and loads the baseline seed records.
- Playwright Chromium headless engine is successfully provisioned.

### 5.2 Exit Criteria
- 100% pass rate on core automated test suite (`tests/test_ui_and_db.py`).
- All 3 intentional database integrity anomalies correctly flagged by `database/qa_audit_queries.sql`.
- Planted API vulnerability reproduced and fully documented in `docs/BUG_REPORTS.md`.
- Zero visual defects or UI degradation in the frontend ledger interface.

---

## 6. Risk Assessment & Mitigation Matrix

| Risk ID | Identified Risk | Severity | Probability | Mitigation Strategy |
|---|---|---|---|---|
| **RSK-01** | Ledger Drift (Cached balance diverging from transaction ledger) | **Critical** | Medium | Continuous automated SQL audit query comparing `users.balance` against `SUM(amount)`. |
| **RSK-02** | Duplicate Transaction Processing (Network retry / double click) | **High** | High | Implement unique constraint on `reference_id` and idempotent API transaction middleware. |
| **RSK-03** | Unauthorized Account Overdraft (Balance dropping below zero) | **High** | Medium | Strict client & server-side validation rejecting withdrawals/bets exceeding balance. |
| **RSK-04** | Negative Amount Sign Inversion Injection | **High** | Low | Enforce strict positive constraint (`amount > 0`) at both schema and API levels. |
| **RSK-05** | Floating-point rounding inaccuracies in balance computations | **Medium** | High | Standardize on 2-decimal rounded storage or integer cents in ledger entries. |
