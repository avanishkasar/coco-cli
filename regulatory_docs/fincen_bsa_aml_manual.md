# FinCEN BSA/AML Examination Manual (2023)

> Source excerpts used to populate `REGULATORY_DOCS_CHUNKS` via
> `setup/04_cortex_search.sql`. Kept in sync manually with the SQL inserts —
> the source of truth for every FinCEN citation the Cortex Agent can surface.

## Chapter 4 — Suspicious Activity Reporting

A suspicious activity report (SAR) must be filed within **30 days** of the
date of initial detection of the suspicious activity. If no suspect is
identified, the period extends to **60 days** from initial detection. A SAR
must be filed for any transaction involving at least $5,000 where the bank
knows, suspects, or has reason to suspect that: the transaction involves
funds from illegal activity; the transaction is designed to evade reporting
requirements; or the transaction lacks a lawful purpose.

## Chapter 5 — Layering and Integration

Layering is the stage of money laundering in which the launderer separates
the proceeds of criminal activity from their source through a series of
complex financial transactions. Common layering techniques include:
transferring funds electronically between accounts in different countries;
purchasing high-value assets and converting them to cash; shell company
transactions; and converting cash into monetary instruments. Banks should be
alert to transactions involving multiple jurisdictions, frequent wire
transfers with no apparent business purpose, and accounts that receive and
immediately transfer funds without holding them — including same-day
fan-out of a single large inbound wire to multiple newly opened,
shell-profile accounts with no shared business rationale.

---

## FATF Recommendation 20 (cross-reference)

If a financial institution suspects funds are the proceeds of criminal
activity, it should be required by law to report its suspicions promptly to
the financial intelligence unit, and should be protected from liability for
good-faith reporting — the same principle underlying FinCEN's SAR
confidentiality provisions (tipping-off is prohibited).
