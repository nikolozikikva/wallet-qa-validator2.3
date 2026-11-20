-- =============================================================================
-- WALLET QA VALIDATOR: DATA INTEGRITY AUDIT SUITE
-- Automated SQL queries for detecting financial ledger anomalies
-- =============================================================================

-- =============================================================================
-- AUDIT QUERY 1: Ledger Reconciliation Mismatch
-- -----------------------------------------------------------------------------
-- Objective: Detect users whose cached summary balance in the `users` table
--            does not match the mathematical sum of their completed ledger events.
-- Financial Impact: Unaccounted balance drift, phantom funds, or uncredited deposits.
-- Method: Aggregate transactions by user with credit/debit sign evaluation and
--         compare against users.balance with floating-point tolerance check.
-- =============================================================================

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


-- =============================================================================
-- AUDIT QUERY 2: Duplicate Transaction Detection (Idempotency Violation)
-- -----------------------------------------------------------------------------
-- Objective: Identify transactions sharing the same `reference_id`, `user_id`,
--            and `amount`, indicating a duplicate processing bug or double-click.
-- Financial Impact: Double debits or double payouts, customer dispute risk.
-- Method: GROUP BY reference_id, user_id, amount, and type with HAVING COUNT(*) > 1,
--         and return all associated transaction IDs.
-- =============================================================================

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


-- =============================================================================
-- AUDIT QUERY 3: Negative Balance Detection (Overdraft Rule Violation)
-- -----------------------------------------------------------------------------
-- Objective: Identify user accounts with balance < 0.00. In strict prepaid /
--            non-credit iGaming platforms, accounts must never go negative.
-- Financial Impact: Operator loss / uncollectible debt due to missing balance guard.
-- Method: Direct filter on users.balance < 0.00.
-- =============================================================================

SELECT 
    u.id AS user_id,
    u.username,
    ROUND(u.balance, 2) AS negative_balance,
    u.created_at AS account_created_at,
    (
        SELECT COUNT(*) 
        FROM transactions t 
        WHERE t.user_id = u.id
    ) AS total_transactions_count
FROM users u
WHERE u.balance < 0.00;
