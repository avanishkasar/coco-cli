-- ============================================================
-- SentinelReg: Step 2 — AML Core Tables
-- ============================================================

USE ROLE SENTINEL_REG_ROLE;
USE DATABASE SENTINEL_REG;
USE SCHEMA DATA;
USE WAREHOUSE SENTINEL_REG_WH;

-- ─────────────────────────────────────────────────────────────
-- CUSTOMERS — KYC profile and risk classification
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE CUSTOMERS (
    CUSTOMER_ID         VARCHAR(20)     NOT NULL,
    FULL_NAME           VARCHAR(200)    NOT NULL,
    ENTITY_TYPE         VARCHAR(50),    -- INDIVIDUAL | CORPORATE | TRUST | NGO
    KYC_TIER            VARCHAR(20),    -- LOW | MEDIUM | HIGH | PROHIBITED
    COUNTRY_OF_ORIGIN   VARCHAR(100),
    ACCOUNT_OPEN_DATE   DATE,
    PEP_FLAG            BOOLEAN DEFAULT FALSE,   -- Politically Exposed Person
    SANCTIONS_FLAG      BOOLEAN DEFAULT FALSE,
    ANNUAL_INCOME_INR   BIGINT,
    OCCUPATION          VARCHAR(200),
    RELATIONSHIP_MANAGER VARCHAR(200),
    LAST_KYC_REFRESH    DATE,
    NOTES               TEXT,
    PRIMARY KEY (CUSTOMER_ID)
);

-- ─────────────────────────────────────────────────────────────
-- ACCOUNTS — Bank accounts linked to customers
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE ACCOUNTS (
    ACCOUNT_ID          VARCHAR(20)     NOT NULL,
    CUSTOMER_ID         VARCHAR(20)     NOT NULL,
    ACCOUNT_TYPE        VARCHAR(50),    -- SAVINGS | CURRENT | OD | NRE | NRO
    IFSC_CODE           VARCHAR(20),
    BRANCH_CODE         VARCHAR(20),
    OPENING_DATE        DATE,
    CURRENT_BALANCE_INR BIGINT,
    STATUS              VARCHAR(20),    -- ACTIVE | DORMANT | FROZEN | CLOSED
    RISK_SCORE          FLOAT,          -- 0.0 - 1.0
    AVERAGE_MONTHLY_CREDIT BIGINT,
    LAST_TRANSACTION_DATE DATE,
    PRIMARY KEY (ACCOUNT_ID),
    FOREIGN KEY (CUSTOMER_ID) REFERENCES CUSTOMERS(CUSTOMER_ID)
);

-- ─────────────────────────────────────────────────────────────
-- TRANSACTIONS — All debit/credit movements
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE TRANSACTIONS (
    TRANSACTION_ID      VARCHAR(30)     NOT NULL,
    ACCOUNT_ID          VARCHAR(20)     NOT NULL,
    COUNTERPARTY_ACCOUNT VARCHAR(20),
    COUNTERPARTY_BANK   VARCHAR(100),
    TRANSACTION_DATE    TIMESTAMP,
    VALUE_DATE          DATE,
    AMOUNT_INR          BIGINT          NOT NULL,
    TRANSACTION_TYPE    VARCHAR(50),    -- CASH_DEPOSIT | CASH_WITHDRAWAL | NEFT | RTGS | IMPS | UPI | CHEQUE
    CHANNEL             VARCHAR(50),    -- BRANCH | ATM | NETBANKING | MOBILE | UPI
    NARRATION           TEXT,
    REFERENCE_NUMBER    VARCHAR(50),
    IS_CASH             BOOLEAN DEFAULT FALSE,
    CURRENCY            VARCHAR(5) DEFAULT 'INR',
    EXCHANGE_RATE       FLOAT DEFAULT 1.0,
    AMOUNT_USD          FLOAT,
    PRIMARY KEY (TRANSACTION_ID),
    FOREIGN KEY (ACCOUNT_ID) REFERENCES ACCOUNTS(ACCOUNT_ID)
);
ALTER TABLE TRANSACTIONS SET CHANGE_TRACKING = TRUE;

-- ─────────────────────────────────────────────────────────────
-- AML_ALERTS — System-generated fraud/AML signals
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE AML_ALERTS (
    ALERT_ID            VARCHAR(30)     NOT NULL,
    ACCOUNT_ID          VARCHAR(20)     NOT NULL,
    CUSTOMER_ID         VARCHAR(20)     NOT NULL,
    ALERT_DATE          TIMESTAMP,
    ALERT_TYPE          VARCHAR(100),   -- STRUCTURING | VELOCITY | ROUND_TRIP | CASH_INTENSIVE | UNUSUAL_GEOGRAPHY
    ALERT_SEVERITY      VARCHAR(20),    -- LOW | MEDIUM | HIGH | CRITICAL
    ALERT_STATUS        VARCHAR(30),    -- OPEN | UNDER_REVIEW | ESCALATED | CLOSED_FALSE_POSITIVE | CLOSED_SAR_FILED
    TRIGGER_RULE        VARCHAR(200),
    TRANSACTION_IDS     ARRAY,          -- list of related transaction IDs
    TOTAL_AMOUNT_INR    BIGINT,
    ANALYST_ASSIGNED    VARCHAR(200),
    INVESTIGATION_NOTES TEXT,
    SAR_FILED           BOOLEAN DEFAULT FALSE,
    SAR_REFERENCE       VARCHAR(50),
    CREATED_AT          TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    UPDATED_AT          TIMESTAMP DEFAULT CURRENT_TIMESTAMP(),
    PRIMARY KEY (ALERT_ID)
);

-- ─────────────────────────────────────────────────────────────
-- REGULATORY_DOCS_CHUNKS — Chunked regulatory text for Cortex Search
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE REGULATORY_DOCS_CHUNKS (
    CHUNK_ID        VARCHAR(50)     NOT NULL,
    DOC_NAME        VARCHAR(500),
    DOC_TYPE        VARCHAR(100),   -- RBI | FATF | BASEL | FINCEN | INTERNAL_POLICY
    SECTION_NUMBER  VARCHAR(50),
    SECTION_TITLE   VARCHAR(500),
    CHUNK_TEXT      TEXT,
    EFFECTIVE_DATE  DATE,
    JURISDICTION    VARCHAR(100),   -- INDIA | US | GLOBAL
    PRIMARY KEY (CHUNK_ID)
);
ALTER TABLE REGULATORY_DOCS_CHUNKS SET CHANGE_TRACKING = TRUE;

-- ─────────────────────────────────────────────────────────────
-- ML_RISK_FEATURES — Precomputed features for ML scorer
-- ─────────────────────────────────────────────────────────────
CREATE OR REPLACE TABLE ML_RISK_FEATURES (
    ACCOUNT_ID                  VARCHAR(20)     NOT NULL,
    FEATURE_DATE                DATE,
    TXN_COUNT_7D                INT,            -- transactions in last 7 days
    TXN_COUNT_30D               INT,
    CASH_TXN_RATIO_30D          FLOAT,          -- % of transactions that are cash
    AVG_TXN_AMOUNT_30D          BIGINT,
    MAX_TXN_AMOUNT_30D          BIGINT,
    JUST_BELOW_THRESHOLD_COUNT  INT,            -- txns just below ₹50,000 (structuring proxy)
    UNIQUE_COUNTERPARTIES_30D   INT,
    ROUND_TRIP_DETECTED         BOOLEAN DEFAULT FALSE,
    GEOGRAPHIC_ANOMALY_SCORE    FLOAT,          -- 0.0-1.0
    VELOCITY_SCORE              FLOAT,          -- 0.0-1.0
    COMPUTED_RISK_SCORE         FLOAT,          -- ML output: 0.0-1.0
    IS_FRAUD_LABEL              BOOLEAN,        -- ground truth for training
    PRIMARY KEY (ACCOUNT_ID, FEATURE_DATE)
);

-- Grants
GRANT SELECT ON ALL TABLES IN SCHEMA SENTINEL_REG.DATA TO ROLE SENTINEL_REG_ROLE;
GRANT SELECT ON FUTURE TABLES IN SCHEMA SENTINEL_REG.DATA TO ROLE SENTINEL_REG_ROLE;

SELECT 'Step 2 complete: Core AML tables created.' AS STATUS;
