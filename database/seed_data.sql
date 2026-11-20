-- =============================================================================
-- WALLET QA VALIDATOR: SEED DATA & TEST SCENARIOS
-- Populates 4 realistic test users and 17 transactional ledger entries
-- =============================================================================

-- -----------------------------------------------------------------------------
-- USERS SEED DATA
-- Note: Balances intentionally include realistic decimals and deliberate anomalies
-- -----------------------------------------------------------------------------
INSERT INTO users (id, username, balance, created_at) VALUES
(1, 'alex_turner', 1420.50, '2024-01-10 08:30:00'),
(2, 'elena_rostova', 85.00, '2024-01-12 11:15:00'),
(3, 'marcus_vance', -40.00, '2024-01-14 14:00:00'),
(4, 'sarah_connor', 5190.75, '2024-01-15 09:45:00');

-- -----------------------------------------------------------------------------
-- TRANSACTIONS SEED DATA
-- -----------------------------------------------------------------------------

-- User 1: alex_turner (Normal balanced ledger: Sum = 1000 + 500 - 120 + 340.50 - 300 = 1420.50)
INSERT INTO transactions (id, user_id, type, amount, status, reference_id, created_at) VALUES
(1, 1, 'deposit',  1000.00, 'completed', 'TXN-ALT-2024-001', '2024-01-10 09:00:00'),
(2, 1, 'deposit',   500.00, 'completed', 'TXN-ALT-2024-002', '2024-01-10 10:30:00'),
(3, 1, 'bet',       120.00, 'completed', 'TXN-ALT-2024-003', '2024-01-10 13:15:00'),
(4, 1, 'win',       340.50, 'completed', 'TXN-ALT-2024-004', '2024-01-10 13:45:00'),
(5, 1, 'withdraw',  300.00, 'completed', 'TXN-ALT-2024-005', '2024-01-11 16:20:00');

-- User 2: elena_rostova
-- ANOMALY #2: Duplicate transaction processed twice with identical reference_id, user_id, and amount
INSERT INTO transactions (id, user_id, type, amount, status, reference_id, created_at) VALUES
(6, 2, 'deposit',   100.00, 'completed', 'TXN-ELN-2024-001',   '2024-01-12 12:00:00'),
(7, 2, 'bet',        15.00, 'completed', 'TXN-ELN-2024-DUP99', '2024-01-12 14:10:00'),
(8, 2, 'bet',        15.00, 'completed', 'TXN-ELN-2024-DUP99', '2024-01-12 14:10:02'), -- Duplicate event
(9, 2, 'win',        15.00, 'completed', 'TXN-ELN-2024-003',   '2024-01-12 14:25:00');

-- User 3: marcus_vance
-- ANOMALY #3: Negative balance (-40.00) caused by unconstrained withdrawal exceeding available funds
INSERT INTO transactions (id, user_id, type, amount, status, reference_id, created_at) VALUES
(10, 3, 'deposit',  100.00, 'completed', 'TXN-MVC-2024-001', '2024-01-14 14:30:00'),
(11, 3, 'bet',       80.00, 'completed', 'TXN-MVC-2024-002', '2024-01-14 15:00:00'),
(12, 3, 'withdraw',  60.00, 'completed', 'TXN-MVC-2024-003', '2024-01-14 16:00:00');

-- User 4: sarah_connor
-- ANOMALY #1: Ledger Discrepancy (Drift)
-- Ledger Sum: 4000 + 2000 - 500 + 1200.75 - 1000 = 5700.75
-- Users Table Balance: 5190.75 (Discrepancy: -510.00 unaccounted drift)
INSERT INTO transactions (id, user_id, type, amount, status, reference_id, created_at) VALUES
(13, 4, 'deposit',  4000.00, 'completed', 'TXN-SCN-2024-001', '2024-01-15 10:00:00'),
(14, 4, 'deposit',  2000.00, 'completed', 'TXN-SCN-2024-002', '2024-01-15 11:30:00'),
(15, 4, 'bet',       500.00, 'completed', 'TXN-SCN-2024-003', '2024-01-15 12:45:00'),
(16, 4, 'win',      1200.75, 'completed', 'TXN-SCN-2024-004', '2024-01-15 13:30:00'),
(17, 4, 'withdraw', 1000.00, 'completed', 'TXN-SCN-2024-005', '2024-01-15 15:00:00');
