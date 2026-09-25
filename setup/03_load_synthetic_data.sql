-- ============================================================
-- SentinelReg: Step 3 — Synthetic AML Scenario Data
-- Scenarios: A) Structuring  B) Round-Trip Transfers  C) Velocity Bursts
--            D) Normal/clean activity (noise)  E) Cash-Intensive Business
--            F) Shell Account Fan-Out
-- ============================================================

USE ROLE SENTINEL_REG_ROLE;
USE DATABASE SENTINEL_REG;
USE SCHEMA DATA;
USE WAREHOUSE SENTINEL_REG_WH;

-- ─────────────────────────────────────────────────────────────
-- CUSTOMERS
-- ─────────────────────────────────────────────────────────────
INSERT INTO CUSTOMERS VALUES
-- Clean customers
('CUST-001', 'Rajesh Kumar Sharma',      'INDIVIDUAL', 'LOW',       'India',   '2018-03-10', FALSE, FALSE, 900000,   'Software Engineer',      'Priya Mehta',  '2024-01-15', NULL),
('CUST-002', 'Infoway Technologies Ltd', 'CORPORATE',  'LOW',       'India',   '2016-06-01', FALSE, FALSE, 50000000, 'IT Services',            'Arjun Nair',   '2024-02-01', NULL),
('CUST-003', 'Sneha Pillai',             'INDIVIDUAL', 'LOW',       'India',   '2020-09-22', FALSE, FALSE, 600000,   'Teacher',                'Priya Mehta',  '2024-01-10', NULL),
-- Medium-risk customers
('CUST-004', 'Horizon Exports Pvt Ltd',  'CORPORATE',  'MEDIUM',    'India',   '2019-11-15', FALSE, FALSE, 20000000, 'Export-Import',          'Ravi Gupta',   '2023-12-01', 'Export volume inconsistent with declared turnover'),
('CUST-005', 'Mohammad Farouk Al-Sayed', 'INDIVIDUAL', 'MEDIUM',    'UAE',     '2021-04-08', FALSE, FALSE, 1500000,  'Business Consultant',    'Ravi Gupta',   '2024-03-01', 'Frequent international wire transfers'),
-- High-risk / flagged customers
('CUST-006', 'Greenleaf Trading Co.',    'CORPORATE',  'HIGH',      'India',   '2022-01-20', FALSE, FALSE, 5000000,  'General Trade',          'Kiran Bose',   '2023-06-01', 'Multiple structuring patterns detected'),
('CUST-007', 'Amit Desai',              'INDIVIDUAL', 'HIGH',      'India',   '2020-07-14', FALSE, FALSE, 400000,   'Self-employed',          'Kiran Bose',   '2023-09-01', 'PEP associate, cash-intensive behaviour'),
('CUST-008', 'Nexus Capital Advisory',   'CORPORATE',  'HIGH',      'Mauritius','2021-08-30', TRUE,  FALSE, 80000000, 'Financial Advisory',     'Kiran Bose',   '2023-07-01', 'PEP-linked entity, offshore structure'),
-- Shell / PROHIBITED
('CUST-009', 'Crystal Ventures LLC',     'CORPORATE',  'PROHIBITED','Cayman Is','2023-02-01', FALSE, TRUE,  0,        'Holding Company',        'Kiran Bose',   '2024-01-01', 'Sanctions match — account frozen'),
('CUST-010', 'Pradeep Narayan Joshi',    'INDIVIDUAL', 'MEDIUM',    'India',   '2019-05-03', FALSE, FALSE, 1200000,  'Real Estate Broker',     'Arjun Nair',   '2024-01-20', NULL),
-- Shell fan-out network (Scenario F)
('CUST-011', 'Silverline Holdings FZE',  'CORPORATE',  'HIGH',      'UAE',      '2024-06-01', FALSE, FALSE, 0,        'Trading',                'Kiran Bose',   '2024-06-01', 'Shell company — no verifiable business activity or website'),
('CUST-012', 'Meridian Assets Ltd',      'CORPORATE',  'HIGH',      'British Virgin Islands','2024-06-05', FALSE, FALSE, 0, 'Holding Company', 'Kiran Bose',   '2024-06-05', 'Shell company — fan-out recipient, single-director entity'),
('CUST-013', 'Oceanic Trade Partners',   'CORPORATE',  'HIGH',      'Seychelles','2024-06-10', FALSE, FALSE, 0,        'General Trade',          'Kiran Bose',   '2024-06-10', 'Shell company — fan-out recipient, no import/export licence on file');

-- ─────────────────────────────────────────────────────────────
-- ACCOUNTS
-- ─────────────────────────────────────────────────────────────
INSERT INTO ACCOUNTS VALUES
('ACC-0001', 'CUST-001', 'SAVINGS',  'SBIN0001234', 'BR-001', '2018-03-10', 85000,     'ACTIVE',  0.08, 45000,   '2024-09-18'),
('ACC-0002', 'CUST-002', 'CURRENT',  'HDFC0002345', 'BR-002', '2016-06-01', 2300000,   'ACTIVE',  0.12, 800000,  '2024-09-18'),
('ACC-0003', 'CUST-003', 'SAVINGS',  'ICIC0003456', 'BR-001', '2020-09-22', 120000,    'ACTIVE',  0.05, 30000,   '2024-09-17'),
('ACC-0004', 'CUST-004', 'CURRENT',  'AXIS0004567', 'BR-003', '2019-11-15', 4800000,   'ACTIVE',  0.52, 1200000, '2024-09-18'),
('ACC-0005', 'CUST-005', 'NRE',      'HDFC0005678', 'BR-004', '2021-04-08', 9200000,   'ACTIVE',  0.61, 2000000, '2024-09-18'),
('ACC-0006', 'CUST-006', 'CURRENT',  'SBIN0006789', 'BR-005', '2022-01-20', 310000,    'ACTIVE',  0.78, 950000,  '2024-09-18'),
('ACC-0007', 'CUST-006', 'SAVINGS',  'SBIN0006790', 'BR-005', '2022-01-20', 490000,    'ACTIVE',  0.74, 600000,  '2024-09-18'),
('ACC-0008', 'CUST-007', 'SAVINGS',  'KOTAK0007891','BR-006', '2020-07-14', 28000,     'ACTIVE',  0.81, 95000,   '2024-09-18'),
('ACC-0009', 'CUST-008', 'CURRENT',  'HDFC0008901', 'BR-007', '2021-08-30', 28500000,  'ACTIVE',  0.88, 5000000, '2024-09-18'),
('ACC-0010', 'CUST-009', 'CURRENT',  'ICIC0009012', 'BR-008', '2023-02-01', 0,         'FROZEN',  0.99, 0,       '2024-01-15'),
('ACC-0011', 'CUST-010', 'SAVINGS',  'SBIN0010123', 'BR-001', '2019-05-03', 540000,    'ACTIVE',  0.45, 220000,  '2024-09-16'),
-- Counterparty-only accounts referenced in transactions
('ACC-9820', 'CUST-001', 'SAVINGS',  'HDFC0099820', 'BR-010', '2020-01-01', 0,         'ACTIVE',  0.10, 10000,   '2024-09-01'),
('ACC-9821', 'CUST-003', 'SAVINGS',  'KOTAK0099821','BR-010', '2020-01-01', 0,         'ACTIVE',  0.10, 10000,   '2024-09-01'),
('ACC-9822', 'CUST-010', 'SAVINGS',  'ICIC0099822', 'BR-010', '2020-01-01', 0,         'ACTIVE',  0.10, 10000,   '2024-09-01'),
('ACC-9823', 'CUST-007', 'SAVINGS',  'AXIS0099823', 'BR-010', '2020-07-14', 0,         'ACTIVE',  0.85, 80000,   '2024-09-18'),
-- Shell fan-out network accounts (Scenario F)
('ACC-0012', 'CUST-011', 'CURRENT',  'ENBD0000012', 'BR-INT', '2024-06-01', 100000,    'ACTIVE',  0.90, 3000000, '2024-09-21'),
('ACC-0013', 'CUST-012', 'CURRENT',  'CITI0000013', 'BR-INT', '2024-06-05', 100000,    'ACTIVE',  0.83, 1000000, '2024-09-21'),
('ACC-0014', 'CUST-013', 'CURRENT',  'SCBL0000014', 'BR-INT', '2024-06-10', 100000,    'ACTIVE',  0.83, 1000000, '2024-09-21');

-- ─────────────────────────────────────────────────────────────
-- TRANSACTIONS — AML Scenario A: Structuring (ACC-0006 / Greenleaf Trading)
-- Multiple cash deposits just below ₹50,000 over 3 days (classic structuring)
-- ─────────────────────────────────────────────────────────────
INSERT INTO TRANSACTIONS (TRANSACTION_ID, ACCOUNT_ID, COUNTERPARTY_ACCOUNT, COUNTERPARTY_BANK, TRANSACTION_DATE, VALUE_DATE, AMOUNT_INR, TRANSACTION_TYPE, CHANNEL, NARRATION, REFERENCE_NUMBER, IS_CASH, CURRENCY, EXCHANGE_RATE, AMOUNT_USD)
VALUES
('TXN-20240901-001','ACC-0006',NULL,NULL,              '2024-09-01 09:15:00','2024-09-01',49000,'CASH_DEPOSIT','BRANCH','Cash deposit - business receipts','REF-001',TRUE,'INR',1.0,NULL),
('TXN-20240901-002','ACC-0006',NULL,NULL,              '2024-09-01 11:30:00','2024-09-01',48500,'CASH_DEPOSIT','BRANCH','Cash deposit - business receipts','REF-002',TRUE,'INR',1.0,NULL),
('TXN-20240901-003','ACC-0006',NULL,NULL,              '2024-09-01 14:45:00','2024-09-01',47900,'CASH_DEPOSIT','BRANCH','Cash deposit - daily sales','REF-003',TRUE,'INR',1.0,NULL),
('TXN-20240902-001','ACC-0006',NULL,NULL,              '2024-09-02 10:00:00','2024-09-02',49500,'CASH_DEPOSIT','BRANCH','Cash deposit - business receipts','REF-004',TRUE,'INR',1.0,NULL),
('TXN-20240902-002','ACC-0006',NULL,NULL,              '2024-09-02 12:20:00','2024-09-02',48000,'CASH_DEPOSIT','BRANCH','Cash deposit - petty cash','REF-005',TRUE,'INR',1.0,NULL),
('TXN-20240903-001','ACC-0006',NULL,NULL,              '2024-09-03 09:45:00','2024-09-03',47500,'CASH_DEPOSIT','BRANCH','Cash deposit - sales','REF-006',TRUE,'INR',1.0,NULL),

-- ─────────────────────────────────────────────────────────────
-- Scenario B: Round-trip transfer (ACC-0009 Nexus Capital ↔ shell)
-- ─────────────────────────────────────────────────────────────
('TXN-20240905-001','ACC-0009','ACC-0010','ICICI Bank',  '2024-09-05 10:00:00','2024-09-05',5000000,'RTGS','NETBANKING','Consultancy fee - Q3 retainer','REF-010',FALSE,'INR',1.0,NULL),
('TXN-20240907-001','ACC-0010','ACC-0009','HDFC Bank',   '2024-09-07 15:30:00','2024-09-07',4900000,'RTGS','NETBANKING','Repayment - advisory services','REF-011',FALSE,'INR',1.0,NULL),
('TXN-20240910-001','ACC-0009','ACC-0006','SBI',         '2024-09-10 11:00:00','2024-09-10',3000000,'NEFT','NETBANKING','Trade finance disbursement','REF-012',FALSE,'INR',1.0,NULL),
('TXN-20240912-001','ACC-0006','ACC-0009','HDFC Bank',   '2024-09-12 16:00:00','2024-09-12',2950000,'NEFT','NETBANKING','Return - trade finance','REF-013',FALSE,'INR',1.0,NULL),

-- ─────────────────────────────────────────────────────────────
-- Scenario C: Velocity burst (ACC-9823 / Amit Desai)
-- 5 rapid transfers to different accounts in under 2 hours
-- ─────────────────────────────────────────────────────────────
('TXN-20240915-001','ACC-9823','ACC-9820','SBI',         '2024-09-15 09:00:00','2024-09-15',45000,'IMPS','MOBILE','Personal transfer','REF-020',FALSE,'INR',1.0,NULL),
('TXN-20240915-002','ACC-9823','ACC-9821','Kotak Bank',  '2024-09-15 09:22:00','2024-09-15',46000,'IMPS','MOBILE','Personal transfer','REF-021',FALSE,'INR',1.0,NULL),
('TXN-20240915-003','ACC-9823','ACC-9822','ICICI Bank',  '2024-09-15 09:45:00','2024-09-15',44500,'IMPS','MOBILE','Personal transfer','REF-022',FALSE,'INR',1.0,NULL),
('TXN-20240915-004','ACC-9823','ACC-0011','SBI',         '2024-09-15 10:10:00','2024-09-15',47000,'IMPS','MOBILE','Personal transfer','REF-023',FALSE,'INR',1.0,NULL),
('TXN-20240915-005','ACC-9823','ACC-0006','SBI',         '2024-09-15 10:55:00','2024-09-15',43000,'IMPS','MOBILE','Personal transfer','REF-024',FALSE,'INR',1.0,NULL),

-- ─────────────────────────────────────────────────────────────
-- Scenario D: Normal transactions (CUST-001, CUST-003) — low noise
-- ─────────────────────────────────────────────────────────────
('TXN-20240916-001','ACC-0001','ACC-0002','HDFC Bank',   '2024-09-16 11:00:00','2024-09-16',35000,'NEFT','NETBANKING','Rent payment - September','REF-030',FALSE,'INR',1.0,NULL),
('TXN-20240917-001','ACC-0003',NULL,NULL,                '2024-09-17 14:00:00','2024-09-17',20000,'CASH_WITHDRAWAL','ATM','ATM withdrawal','REF-031',TRUE,'INR',1.0,NULL),
('TXN-20240918-001','ACC-0001','ACC-0003','ICICI Bank',  '2024-09-18 09:30:00','2024-09-18',12000,'UPI','MOBILE','UPI payment - groceries','REF-032',FALSE,'INR',1.0,NULL),

-- ─────────────────────────────────────────────────────────────
-- Scenario E: Cash-intensive business (ACC-0004 / Horizon Exports)
-- Declared export-import turnover doesn't match heavy cash usage
-- ─────────────────────────────────────────────────────────────
('TXN-20240905-101','ACC-0004',NULL,NULL,                '2024-09-05 10:00:00','2024-09-05',480000,'CASH_DEPOSIT','BRANCH','Cash deposit - export proceeds','REF-040',TRUE,'INR',1.0,NULL),
('TXN-20240910-101','ACC-0004',NULL,NULL,                '2024-09-10 11:15:00','2024-09-10',520000,'CASH_DEPOSIT','BRANCH','Cash deposit - export proceeds','REF-041',TRUE,'INR',1.0,NULL),
('TXN-20240913-101','ACC-0004',NULL,NULL,                '2024-09-13 09:30:00','2024-09-13',610000,'CASH_DEPOSIT','BRANCH','Cash deposit - trading receipts','REF-042',TRUE,'INR',1.0,NULL),
('TXN-20240916-101','ACC-0004',NULL,NULL,                '2024-09-16 12:40:00','2024-09-16',390000,'CASH_DEPOSIT','BRANCH','Cash deposit - trading receipts','REF-043',TRUE,'INR',1.0,NULL),
('TXN-20240918-101','ACC-0004',NULL,NULL,                '2024-09-18 15:00:00','2024-09-18',455000,'CASH_DEPOSIT','BRANCH','Cash deposit - export proceeds','REF-044',TRUE,'INR',1.0,NULL),
('TXN-20240919-101','ACC-0004','ACC-0002','HDFC Bank',   '2024-09-19 10:00:00','2024-09-19',300000,'NEFT','NETBANKING','Supplier payment','REF-045',FALSE,'INR',1.0,NULL),
('TXN-20240920-101','ACC-0004','ACC-0001','SBI',         '2024-09-20 11:00:00','2024-09-20',150000,'NEFT','NETBANKING','Vendor settlement','REF-046',FALSE,'INR',1.0,NULL),

-- ─────────────────────────────────────────────────────────────
-- Scenario F: Shell account fan-out (ACC-0009 Nexus Capital → 3 shells
-- in one day — classic layering with no plausible business rationale)
-- ─────────────────────────────────────────────────────────────
('TXN-20240921-001','ACC-0009','ACC-0012','Emirates NBD','2024-09-21 09:00:00','2024-09-21',9000000,'RTGS','NETBANKING','Investment advisory fee','REF-050',FALSE,'INR',1.0,107784.0),
('TXN-20240921-002','ACC-0012','ACC-0013','Citibank',    '2024-09-21 10:30:00','2024-09-21',3000000,'RTGS','NETBANKING','Consulting services','REF-051',FALSE,'INR',1.0,35928.0),
('TXN-20240921-003','ACC-0012','ACC-0014','Standard Chartered','2024-09-21 10:45:00','2024-09-21',3000000,'RTGS','NETBANKING','Trade facilitation','REF-052',FALSE,'INR',1.0,35928.0),
('TXN-20240921-004','ACC-0012','ACC-9823','Axis Bank',   '2024-09-21 11:05:00','2024-09-21',2900000,'RTGS','NETBANKING','Referral commission','REF-053',FALSE,'INR',1.0,34730.0);

-- ─────────────────────────────────────────────────────────────
-- AML ALERTS
-- Note: each alert is its own single-row INSERT because Snowflake
-- does not allow ARRAY_CONSTRUCT() inside a multi-row VALUES list.
-- ─────────────────────────────────────────────────────────────
INSERT INTO AML_ALERTS (ALERT_ID, ACCOUNT_ID, CUSTOMER_ID, ALERT_DATE, ALERT_TYPE, ALERT_SEVERITY, ALERT_STATUS, TRIGGER_RULE, TRANSACTION_IDS, TOTAL_AMOUNT_INR, ANALYST_ASSIGNED, INVESTIGATION_NOTES, SAR_FILED, SAR_REFERENCE)
VALUES (
    'ALERT-2024-0041', 'ACC-0006', 'CUST-006',
    '2024-09-03 18:00:00',
    'STRUCTURING',
    'HIGH',
    'UNDER_REVIEW',
    'Rule SR-07: 3+ cash deposits just below ₹50,000 within 72 hours from single account',
    ARRAY_CONSTRUCT('TXN-20240901-001','TXN-20240901-002','TXN-20240901-003','TXN-20240902-001','TXN-20240902-002','TXN-20240903-001'),
    290400,
    'Kiran Bose',
    'Six cash deposits between ₹47,500 and ₹49,500 over 3 days — consistent with structuring to avoid CTR threshold.',
    FALSE,
    NULL
);

INSERT INTO AML_ALERTS (ALERT_ID, ACCOUNT_ID, CUSTOMER_ID, ALERT_DATE, ALERT_TYPE, ALERT_SEVERITY, ALERT_STATUS, TRIGGER_RULE, TRANSACTION_IDS, TOTAL_AMOUNT_INR, ANALYST_ASSIGNED, INVESTIGATION_NOTES, SAR_FILED, SAR_REFERENCE)
VALUES (
    'ALERT-2024-0043', 'ACC-0009', 'CUST-008',
    '2024-09-12 20:00:00',
    'ROUND_TRIP',
    'CRITICAL',
    'ESCALATED',
    'Rule RT-02: Funds transferred out and returned (>80% of amount) within 8 days',
    ARRAY_CONSTRUCT('TXN-20240905-001','TXN-20240907-001','TXN-20240910-001','TXN-20240912-001'),
    15850000,
    'Kiran Bose',
    'PEP-linked entity Nexus Capital transferred ₹5Cr to frozen shell account ACC-0010, received ₹4.9Cr back within 48 hours. Secondary transfer to cash-intensive Greenleaf Trading.',
    FALSE,
    NULL
);

INSERT INTO AML_ALERTS (ALERT_ID, ACCOUNT_ID, CUSTOMER_ID, ALERT_DATE, ALERT_TYPE, ALERT_SEVERITY, ALERT_STATUS, TRIGGER_RULE, TRANSACTION_IDS, TOTAL_AMOUNT_INR, ANALYST_ASSIGNED, INVESTIGATION_NOTES, SAR_FILED, SAR_REFERENCE)
VALUES (
    'ALERT-2024-0047', 'ACC-9823', 'CUST-007',
    '2024-09-15 11:30:00',
    'VELOCITY',
    'HIGH',
    'OPEN',
    'Rule VL-01: 5+ outgoing transfers within 2 hours, each just below ₹50,000',
    ARRAY_CONSTRUCT('TXN-20240915-001','TXN-20240915-002','TXN-20240915-003','TXN-20240915-004','TXN-20240915-005'),
    225500,
    NULL,
    NULL,
    FALSE,
    NULL
);

INSERT INTO AML_ALERTS (ALERT_ID, ACCOUNT_ID, CUSTOMER_ID, ALERT_DATE, ALERT_TYPE, ALERT_SEVERITY, ALERT_STATUS, TRIGGER_RULE, TRANSACTION_IDS, TOTAL_AMOUNT_INR, ANALYST_ASSIGNED, INVESTIGATION_NOTES, SAR_FILED, SAR_REFERENCE)
VALUES (
    'ALERT-2024-0050', 'ACC-0004', 'CUST-004',
    '2024-09-19 08:00:00',
    'CASH_INTENSIVE',
    'MEDIUM',
    'OPEN',
    'Rule CI-03: cash-to-total transaction ratio >70% inconsistent with declared export-import business profile',
    ARRAY_CONSTRUCT('TXN-20240905-101','TXN-20240910-101','TXN-20240913-101','TXN-20240916-101','TXN-20240918-101'),
    2455000,
    NULL,
    'Five large cash deposits (₹3.9L–₹6.1L) over two weeks against a declared export business — cash usage inconsistent with cross-border trade profile.',
    FALSE,
    NULL
);

INSERT INTO AML_ALERTS (ALERT_ID, ACCOUNT_ID, CUSTOMER_ID, ALERT_DATE, ALERT_TYPE, ALERT_SEVERITY, ALERT_STATUS, TRIGGER_RULE, TRANSACTION_IDS, TOTAL_AMOUNT_INR, ANALYST_ASSIGNED, INVESTIGATION_NOTES, SAR_FILED, SAR_REFERENCE)
VALUES (
    'ALERT-2024-0052', 'ACC-0009', 'CUST-008',
    '2024-09-21 12:00:00',
    'SHELL_FANOUT',
    'CRITICAL',
    'ESCALATED',
    'Rule SF-01: inbound wire >₹50L fanned out same-day to 3+ newly opened shell-profile accounts with no shared business rationale',
    ARRAY_CONSTRUCT('TXN-20240921-001','TXN-20240921-002','TXN-20240921-003','TXN-20240921-004'),
    17900000,
    'Kiran Bose',
    'PEP-linked Nexus Capital received ₹90L from an unrelated advisory client and fanned it out within 2 hours to three offshore shell entities (Silverline, Meridian, Oceanic) plus already-flagged ACC-9823 — classic layering signature.',
    FALSE,
    NULL
);

-- ─────────────────────────────────────────────────────────────
-- ML RISK FEATURES (pre-computed snapshot for demonstration)
-- ─────────────────────────────────────────────────────────────
INSERT INTO ML_RISK_FEATURES VALUES
('ACC-0001','2024-09-18',2,8,  0.00,22000,35000,0,3,FALSE,0.05,0.10,0.08, FALSE),
('ACC-0003','2024-09-18',1,4,  0.25,16000,20000,0,2,FALSE,0.03,0.05,0.05, FALSE),
('ACC-0006','2024-09-18',6,22, 0.90,47600,49500,6,4,FALSE,0.20,0.88,0.82, TRUE),
('ACC-0007','2024-09-18',3,12, 0.50,38000,48000,3,5,FALSE,0.15,0.65,0.74, TRUE),
('ACC-9823','2024-09-18',5,18, 0.00,45100,47000,5,5,TRUE, 0.10,0.92,0.85, TRUE),
('ACC-0009','2024-09-18',4,16, 0.00,4000000,5000000,0,3,FALSE,0.70,0.75,0.88,TRUE),
('ACC-0004','2024-09-20',7,19, 0.71,406400,610000,0,2,FALSE,0.35,0.20,0.58, FALSE),
('ACC-0012','2024-09-21',4,4,  0.00,4475000,9000000,0,3,FALSE,0.55,0.95,0.91, TRUE);

SELECT 'Step 3 complete: Synthetic AML scenario data loaded.' AS STATUS;
