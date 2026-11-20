# Formal QA Defect Reports: Wallet QA Validator

This document catalogs formal, industry-standard defect reports discovered and audited within the **Wallet QA Validator** system. Each report follows enterprise FinTech bug tracking standards (Jira / Linear style) with full SQL query proofs and reproduction commands.

---

## Defect Summary Dashboard

| Bug ID | Title | Severity | Priority | Component | Status |
|---|---|---|---|---|---|
| **BUG-WV-001** | Negative Withdrawal Amount Inverts Sign and Credits User Balance | **Critical (P1)** | Blocker | API / Transaction Engine | Open (Reproduced in Test 4) |
| **BUG-WV-002** | Absence of Reference ID Unique Constraint Permitting Duplicate Wagers | **High (P2)** | High | Database Schema / Idempotency | Open (Audited in Query 2) |
| **BUG-WV-003** | Ledger Drift: Cached User Balance Diverges from Transaction History | **High (P2)** | High | Database / Reconciliation | Open (Audited in Query 1) |

---

## BUG-WV-001: Negative Withdrawal Amount Inverts Sign and Credits User Balance

- **Bug ID:** `BUG-WV-001`
- **Component:** Backend API (`POST /api/transaction`)
- **Severity:** `Critical (Severity 1)`
- **Priority:** `P1 - Blocker`
- **Reporter:** Senior QA Engineer
- **Environment:** Local / Staging (`wallet-qa-validator v1.0.0`, SQLite 3.x, Python Flask)

### Summary
The `POST /api/transaction` endpoint does not enforce a strictly positive constraint (`amount > 0`). When a withdrawal or bet request with a negative numeric value (e.g., `-100.00`) is submitted, it bypasses the insufficient funds check and mathematically credits the user's balance:
$$\text{new\_balance} = \text{current\_balance} - (-100.00) = \text{current\_balance} + 100.00$$

### Steps to Reproduce
1. Query initial balance for `alex_turner` (User ID `1`, initial balance: `$1,420.50`).
2. Send an HTTP POST payload to `http://127.0.0.1:5000/api/transaction`:
   ```bash
   curl -X POST http://127.0.0.1:5000/api/transaction \
     -H "Content-Type: application/json" \
     -d '{
       "user_id": 1,
       "type": "withdraw",
       "amount": -100.00,
       "reference_id": "TXN-EXPLOIT-NEG-SIGN-001"
     }'
   ```
3. Observe HTTP status code and response payload.
4. Query the database table `users` for `id = 1`.

### Expected Result
HTTP `400 Bad Request` with payload:
```json
{
  "error": "Transaction amount must be strictly greater than 0.00"
}
```
User balance must remain unchanged at `$1,420.50`.

### Actual Result
HTTP `201 Created` is returned:
```json
{
  "message": "Transaction processed successfully",
  "new_balance": 1520.5,
  "transaction": {
    "amount": -100.0,
    "id": 18,
    "reference_id": "TXN-EXPLOIT-NEG-SIGN-001",
    "status": "completed",
    "type": "withdraw",
    "user_id": 1,
    "username": "alex_turner"
  }
}
```
The balance increased by $100.00 without any deposit authorization.

### SQL Query Proof
```sql
SELECT id, username, balance FROM users WHERE id = 1;
-- Returns: balance = 1520.50 (Initial was 1420.50)

SELECT * FROM transactions WHERE reference_id = 'TXN-EXPLOIT-NEG-SIGN-001';
-- Returns: type = 'withdraw', amount = -100.00, status = 'completed'
```

### Remediation Recommendation
1. In `backend/app.py`, enforce:
   ```python
   if amount <= 0:
       return jsonify({"error": "Transaction amount must be strictly positive"}), 400
   ```
2. In `database/schema.sql`, add a table-level check constraint:
   ```sql
   CHECK(amount > 0)
   ```

---

## BUG-WV-002: Absence of Reference ID Unique Constraint Permitting Duplicate Transactions

- **Bug ID:** `BUG-WV-002`
- **Component:** Database Schema (`transactions` table) / API Ingestion
- **Severity:** `High (Severity 2)`
- **Priority:** `P2 - High`
- **Reporter:** QA Lead / Ledger Auditor
- **Environment:** Staging / Production Simulation (`seed_data.sql`)

### Summary
The `transactions` table defines `reference_id TEXT NOT NULL` without a `UNIQUE` constraint. When network retries or rapid double-submissions occur, the ledger records multiple completed records for the identical transaction reference.

### Steps to Reproduce
1. Inspect the baseline seed dataset for user `elena_rostova` (User ID `2`).
2. Run duplicate transaction audit query:
   ```sql
   SELECT reference_id, user_id, amount, COUNT(*) 
   FROM transactions 
   WHERE reference_id = 'TXN-ELN-2024-DUP99' 
   GROUP BY reference_id, user_id, amount;
   ```
3. Observe two identical rows with transaction IDs `#7` and `#8`.

### Expected Result
The second insertion with `reference_id = 'TXN-ELN-2024-DUP99'` should fail with an idempotency error (`SQLITE_CONSTRAINT_UNIQUE`) and return HTTP `409 Conflict` or return the cached status of the original transaction.

### Actual Result
Both transactions are accepted and debited twice ($15.00 + $15.00), reducing the player's balance unfairly.

### SQL Query Proof
```sql
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
```

**Query Output:**
```
reference_id        | user_id | username      | type | amount | occurrence_count | duplicate_transaction_ids
--------------------+---------+---------------+------+--------+------------------+--------------------------
TXN-ELN-2024-DUP99  | 2       | elena_rostova | bet  | 15.00  | 2                | 7, 8
```

### Remediation Recommendation
1. Add a unique index to SQLite schema:
   ```sql
   CREATE UNIQUE INDEX uq_transactions_ref_user ON transactions(reference_id, user_id);
   ```
2. Implement distributed idempotency caching (e.g., Redis or in-memory idempotency keys) at the API gateway layer.

---

## BUG-WV-003: Ledger Drift: Cached User Balance Diverges from Transaction History

- **Bug ID:** `BUG-WV-003`
- **Component:** Core Database Integrity (`users.balance` vs `transactions`)
- **Severity:** `High (Severity 2)`
- **Priority:** `P2 - High`
- **Reporter:** Financial Risk & QA Analyst
- **Environment:** Core Ledger Sandbox

### Summary
User `sarah_connor` (User ID `4`) displays a cached `balance` of `$5,190.75` in the `users` table, whereas the mathematical sum of all completed transactions in the `transactions` table totals `$5,700.75`. There is an unaccounted negative drift of `-$510.00`.

### Mathematical Audit Proof
```
Completed Transactions for User 4 (Sarah Connor):
  1. Deposit:   +$4,000.00 (TXN-SCN-2024-001)
  2. Deposit:   +$2,000.00 (TXN-SCN-2024-002)
  3. Bet:         -$500.00 (TXN-SCN-2024-003)
  4. Win:       +$1,200.75 (TXN-SCN-2024-004)
  5. Withdraw:  -$1,000.00 (TXN-SCN-2024-005)
-----------------------------------------------
Expected True Ledger Sum:   $5,700.75
Actual Cached Balance:      $5,190.75
Discrepancy (Uncredited):     -$510.00 (UNDER_CREDITED)
```

### SQL Query Proof
```sql
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
```

**Query Output:**
```
user_id | username     | current_cached_balance | ledger_calculated_balance | discrepancy_amount | anomaly_classification
--------+--------------+------------------------+---------------------------+--------------------+-----------------------
4       | sarah_connor | 5190.75                | 5700.75                   | -510.00            | UNDER_CREDITED
```

### Remediation Recommendation
1. Execute a reconciliation patch:
   ```sql
   UPDATE users
   SET balance = (
       SELECT SUM(
           CASE 
               WHEN type IN ('deposit', 'win') THEN amount
               WHEN type IN ('withdraw', 'bet') THEN -amount
               ELSE 0.0
           END
       )
       FROM transactions
       WHERE user_id = 4 AND status = 'completed'
   )
   WHERE id = 4;
   ```
2. Replace mutable cached balance columns with an event-sourced ledger architecture or write transactional trigger updates.
