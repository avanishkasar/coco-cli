-- ============================================================
-- SentinelReg: Step 4 — Cortex Search Service for Regulatory Docs
-- ============================================================

USE ROLE SENTINEL_REG_ROLE;
USE DATABASE SENTINEL_REG;
USE SCHEMA DATA;
USE WAREHOUSE SENTINEL_REG_WH;

-- Populate regulatory doc chunks inline (representative excerpts)
-- In production: load full PDFs via Snowflake Document AI or chunk externally

INSERT INTO REGULATORY_DOCS_CHUNKS VALUES
-- ── RBI Master Direction on KYC/AML ──
('RBI-KYC-001','RBI Master Direction - Know Your Customer (KYC) Direction, 2016 (Updated 2023)','RBI','Para 4','Customer Due Diligence (CDD)',
'Customer Due Diligence (CDD) is the process of identifying the customer and verifying their identity using reliable, independent source documents, data or information. Banks shall undertake CDD measures at the time of commencement of an account-based relationship. CDD for existing accounts shall be updated periodically, at least once in 2 years for high-risk customers, 8 years for medium-risk customers, and 10 years for low-risk customers.','2023-01-01','INDIA'),

('RBI-KYC-002','RBI Master Direction - Know Your Customer (KYC) Direction, 2016 (Updated 2023)','RBI','Para 12','Cash Transaction Reporting (CTR)',
'Banks are required to file Cash Transaction Reports (CTR) with the Financial Intelligence Unit - India (FIU-IND) for all cash transactions of Rs. 10 lakh and above. Banks shall also file CTR for multiple cash transactions that individually do not exceed Rs. 10 lakh but collectively exceed Rs. 10 lakh in a day and appear to be structured to avoid reporting. The CTR shall be filed on or before the 15th day of the following month.','2023-01-01','INDIA'),

('RBI-KYC-003','RBI Master Direction - Know Your Customer (KYC) Direction, 2016 (Updated 2023)','RBI','Para 15','Suspicious Transaction Reporting (STR)',
'Banks shall file a Suspicious Transaction Report (STR) with FIU-IND whenever there are grounds to suspect that a transaction or an attempted transaction is related to money laundering, terrorist financing, or other illegal activities. The STR shall be filed within 7 days of being satisfied that a transaction is suspicious. The obligation to report shall not be deferred pending the conclusion of an investigation. Banks shall not tip off customers about an STR filing.','2023-01-01','INDIA'),

('RBI-KYC-004','RBI Master Direction - Know Your Customer (KYC) Direction, 2016 (Updated 2023)','RBI','Para 16','Risk Categorisation',
'Banks shall classify customers into Low, Medium, and High risk categories based on the assessment and analysis of the customer''s background, nature and location of activity, country of origin, sources of funds, and his client profile. Customers assessed as high risk shall be subjected to Enhanced Due Diligence (EDD) including more frequent account monitoring and senior management approval. Politically Exposed Persons (PEPs) and their family members shall be treated as high-risk customers.','2023-01-01','INDIA'),

('RBI-KYC-005','RBI Master Direction - Know Your Customer (KYC) Direction, 2016 (Updated 2023)','RBI','Para 18','Structuring',
'Structuring refers to the practice of breaking up large cash transactions into smaller amounts just below the reporting threshold to evade CTR requirements. Banks shall be vigilant for structuring patterns including but not limited to: multiple cash deposits of amounts just below Rs. 10 lakh by the same customer on the same day or over several days; multiple customers making cash deposits below the threshold into the same account; and transactions that do not match the declared business profile.','2023-01-01','INDIA'),

('RBI-KYC-006','RBI Master Direction - Know Your Customer (KYC) Direction, 2016 (Updated 2023)','RBI','Para 22','Transaction Monitoring',
'Banks shall put in place a robust transaction monitoring system capable of identifying, on a risk-based approach, transactions that appear suspicious. The monitoring system shall flag transactions based on velocity, amount, geography, and counterparty risk. Alerts generated shall be reviewed by a qualified compliance officer. Banks shall maintain records of all monitoring alerts and their disposition for a minimum period of 5 years.','2023-01-01','INDIA'),

-- ── FATF 40 Recommendations ──
('FATF-R-001','FATF 40 Recommendations (2023 update)','FATF','Recommendation 10','Customer Due Diligence',
'Financial institutions should be prohibited from keeping anonymous accounts or accounts in obviously fictitious names. Financial institutions should be required to undertake customer due diligence (CDD) measures when establishing business relations; carrying out occasional transactions above the applicable designated threshold (USD/EUR 15,000); there is a suspicion of money laundering or terrorist financing; or when the financial institution has doubts about the veracity or adequacy of previously obtained customer identification data.','2023-06-01','GLOBAL'),

('FATF-R-002','FATF 40 Recommendations (2023 update)','FATF','Recommendation 20','Reporting of Suspicious Transactions',
'If a financial institution suspects or has reasonable grounds to suspect that funds are the proceeds of a criminal activity, or are related to terrorist financing, it should be required, by law, to report promptly its suspicions to the financial intelligence unit (FIU). Financial institutions, their directors, officers and employees should be protected by law from criminal and civil liability for breach of any restriction on disclosure of information imposed by contract or by any legislative, regulatory or administrative provision, if they report their suspicions in good faith to the FIU, even if they did not know precisely what the underlying criminal activity was.','2023-06-01','GLOBAL'),

('FATF-R-003','FATF 40 Recommendations (2023 update)','FATF','Recommendation 26','Regulation and Supervision of Financial Institutions',
'Financial institutions should be subject to adequate regulation and supervision to ensure that they effectively implement the FATF Recommendations. Supervisors should have adequate powers to supervise or monitor and ensure compliance by financial institutions with requirements to combat money laundering and terrorist financing. Supervisors should be authorised to conduct inspections and require the production of any information from financial institutions that is relevant to monitoring compliance.','2023-06-01','GLOBAL'),

-- ── Basel AML/CFT Guidelines ──
('BASEL-AML-001','Basel Committee on Banking Supervision - Sound Management of Risks related to Money Laundering and Financing of Terrorism (2020)','BASEL','Section 3','Customer Risk Assessment',
'Banks should have a sound understanding of the risk profiles of their customers. The customer risk assessment should be based on factors including: the nature of the customer and their business; the geographic area where the customer is located or does business; the type of products and services used; and the channels through which the customer accesses the bank''s services. High-risk customers such as PEPs, non-resident customers, legal persons or arrangements with nominee shareholders or bearer shares, and cash-intensive businesses should be subject to enhanced due diligence.','2020-07-01','GLOBAL'),

('BASEL-AML-002','Basel Committee on Banking Supervision - Sound Management of Risks related to Money Laundering and Financing of Terrorism (2020)','BASEL','Section 5','Transaction Monitoring',
'Banks should monitor customer transactions on an ongoing basis. Transaction monitoring should be carried out on a risk-sensitive basis. Monitoring systems should be capable of detecting unusual patterns of activity including: transactions that are inconsistent with the customer''s business profile; large cash transactions; transactions from high-risk jurisdictions; rapid movement of funds through accounts with no plausible business reason; and transactions that have no apparent economic rationale. Banks should ensure that the outputs of their transaction monitoring systems are reviewed by qualified staff and that appropriate action is taken on a timely basis.','2020-07-01','GLOBAL'),

-- ── FinCEN BSA/AML Manual ──
('FINCEN-001','FinCEN BSA/AML Examination Manual (2023)','FINCEN','Chapter 4','Suspicious Activity Reporting',
'A suspicious activity report (SAR) must be filed within 30 days of the date of the initial detection of the suspicious activity. If no suspect is identified, the time period is extended to 60 days from the initial detection of the suspicious activity. A SAR must be filed for any transaction involving at least $5,000 where the bank knows, suspects, or has reason to suspect that: the transaction involves funds from illegal activity; the transaction is designed to evade reporting requirements; or the transaction lacks a lawful purpose.','2023-01-01','US'),

('FINCEN-002','FinCEN BSA/AML Examination Manual (2023)','FINCEN','Chapter 5','Layering and Integration',
'Layering is the stage of money laundering in which the launderer separates the proceeds of criminal activity from their source through a series of complex financial transactions. Common layering techniques include: transferring funds electronically between accounts in different countries; purchasing high-value assets and converting them to cash; shell company transactions; and converting cash into monetary instruments. Banks should be alert to transactions involving multiple jurisdictions, frequent wire transfers with no apparent business purpose, and accounts that receive and immediately transfer funds without holding them.','2023-01-01','US');

-- ─────────────────────────────────────────────────────────────
-- Cortex Search requires EMBED_TEXT_768, which is not available
-- on trial accounts. Regulatory chunks are queried via Cortex
-- Analyst (SQL/ILIKE over REGULATORY_DOCS_CHUNKS) instead — see
-- the REGULATORY_DOCS_CHUNKS table in semantic_model/aml_risk_model.yaml.
-- If you're on a paid account with Cortex Search available, you can
-- swap back to semantic search by uncommenting the block below and
-- restoring the CORTEX SEARCH SERVICE tool in setup/05_create_agent.sql.
-- ─────────────────────────────────────────────────────────────
-- CREATE OR REPLACE CORTEX SEARCH SERVICE AML_REGULATORY_SEARCH
--   ON CHUNK_TEXT
--   ATTRIBUTES DOC_NAME, DOC_TYPE, SECTION_NUMBER, SECTION_TITLE, JURISDICTION, EFFECTIVE_DATE
--   WAREHOUSE = SENTINEL_REG_WH
--   TARGET_LAG = '24 hours'
--   AS (
--     SELECT CHUNK_ID, CHUNK_TEXT, DOC_NAME, DOC_TYPE, SECTION_NUMBER, SECTION_TITLE, JURISDICTION, EFFECTIVE_DATE
--     FROM REGULATORY_DOCS_CHUNKS
--   );
-- GRANT USAGE ON CORTEX SEARCH SERVICE AML_REGULATORY_SEARCH TO ROLE SENTINEL_REG_ROLE;

SELECT 'Step 4 complete: regulatory doc chunks loaded (queried via Cortex Analyst).' AS STATUS;
