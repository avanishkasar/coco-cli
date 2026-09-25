---
name: score-fraud-risk
title: Recompute ML fraud risk scores
summary: Retrain or rescore the Snowpark ML fraud classifier and explain which features are driving an account's risk score.
description: >
  Use when the user asks to retrain the model, rescore accounts, or explain
  why the ML risk score changed (e.g. "retrain the fraud model", "why did
  ACC-0009's score jump", "rescore all accounts"). Triggers on keywords:
  retrain, rescore, model, feature importance, ML risk score.
type: community
tools: [snowpark, python]
---

# Recompute ML fraud risk scores

## Workflow

1. Run `python ml_pipeline/fraud_classifier.py --mode train` to refit the
   XGBoost classifier on `ML_RISK_FEATURES` (label column `IS_FRAUD_LABEL`),
   or `--mode score` to score current feature rows and write
   `COMPUTED_RISK_SCORE` back to `ML_RISK_FEATURES`.
2. The five model features are: `CASH_TXN_RATIO_30D`,
   `JUST_BELOW_THRESHOLD_COUNT`, `VELOCITY_SCORE`,
   `UNIQUE_COUNTERPARTIES_30D`, `ROUND_TRIP_DETECTED`. When explaining a
   score, report each feature's value for that account alongside its
   trained importance weight (printed by the script's `--explain
   <ACCOUNT_ID>` flag) rather than guessing at causality.
3. After rescoring, cross-check the new `COMPUTED_RISK_SCORE` against the
   rule-based `ACCOUNTS.RISK_SCORE` — if they diverge by more than 0.2, flag
   it for analyst review instead of silently trusting the ML number.

## Common mistakes

- Don't train on the full `ML_RISK_FEATURES` table without a
  train/holdout split — with this few labeled rows, report accuracy on a
  holdout, not training accuracy.
- Don't present the ML score as ground truth; it's a decision-support
  signal, and the SAR/regulatory narrative must still be evidence-based, not
  "the model said so."
