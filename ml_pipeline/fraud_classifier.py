"""
Fraud Classifier — Snowpark ML training & scoring pipeline for SentinelReg.

Trains a gradient-boosted classifier on ML_RISK_FEATURES to predict
IS_FRAUD_LABEL, then writes COMPUTED_RISK_SCORE back to Snowflake so the
Cortex Agent and Streamlit dashboard can surface it.

Usage:
    python ml_pipeline/fraud_classifier.py --mode train
    python ml_pipeline/fraud_classifier.py --mode score
    python ml_pipeline/fraud_classifier.py --mode explain --account ACC-0009
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv
from snowflake.snowpark import Session

load_dotenv()

FEATURE_COLUMNS = [
    "CASH_TXN_RATIO_30D",
    "JUST_BELOW_THRESHOLD_COUNT",
    "UNIQUE_COUNTERPARTIES_30D",
    "ROUND_TRIP_DETECTED",
    "VELOCITY_SCORE",
    "GEOGRAPHIC_ANOMALY_SCORE",
]
LABEL_COLUMN = "IS_FRAUD_LABEL"
MODEL_STAGE = "@sentinel_reg.data.models"
MODEL_FILE = "fraud_classifier.joblib"


def get_session() -> Session:
    return Session.builder.configs(
        {
            "account": os.getenv("SNOWFLAKE_ACCOUNT"),
            "user": os.getenv("SNOWFLAKE_USER"),
            "password": os.getenv("SNOWFLAKE_PASSWORD"),
            "role": os.getenv("SNOWFLAKE_ROLE", "SENTINEL_REG_ROLE"),
            "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "SENTINEL_REG_WH"),
            "database": os.getenv("SNOWFLAKE_DATABASE", "SENTINEL_REG"),
            "schema": os.getenv("SNOWFLAKE_SCHEMA", "DATA"),
        }
    ).create()


def _load_features(session: Session):
    df = session.table("ML_RISK_FEATURES").to_pandas()
    if df.empty:
        raise RuntimeError(
            "ML_RISK_FEATURES is empty — run setup/03_load_synthetic_data.sql first."
        )
    df["ROUND_TRIP_DETECTED"] = df["ROUND_TRIP_DETECTED"].astype(int)
    return df


def train(session: Session) -> None:
    """Fit an XGBoost classifier and persist it to the internal stage."""
    from sklearn.ensemble import GradientBoostingClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import roc_auc_score, classification_report
    import joblib
    import tempfile

    df = _load_features(session)
    X, y = df[FEATURE_COLUMNS], df[LABEL_COLUMN].astype(int)

    if y.nunique() < 2 or len(df) < 8:
        print(
            f"[warn] Only {len(df)} labeled rows with classes {sorted(y.unique())} — "
            "training on the full set without a holdout split (demo-scale data)."
        )
        model = GradientBoostingClassifier(
            n_estimators=150, max_depth=3, learning_rate=0.08, random_state=42
        ).fit(X, y)
        print(classification_report(y, model.predict(X), zero_division=0))
    else:
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.25, random_state=42, stratify=y
        )
        model = GradientBoostingClassifier(
            n_estimators=150, max_depth=3, learning_rate=0.08, random_state=42
        ).fit(X_train, y_train)
        preds = model.predict(X_test)
        probs = model.predict_proba(X_test)[:, 1]
        print(classification_report(y_test, preds, zero_division=0))
        if y_test.nunique() > 1:
            print(f"Holdout ROC-AUC: {roc_auc_score(y_test, probs):.3f}")

    importances = dict(zip(FEATURE_COLUMNS, model.feature_importances_))
    print("\nFeature importances:")
    for feat, imp in sorted(importances.items(), key=lambda kv: -kv[1]):
        print(f"  {feat:<28} {imp:.3f}")

    with tempfile.NamedTemporaryFile(suffix=".joblib", delete=False) as tmp:
        joblib.dump(model, tmp.name)
        session.file.put(
            tmp.name, MODEL_STAGE, auto_compress=False, overwrite=True
        )
    print(f"\nModel persisted to {MODEL_STAGE}/{MODEL_FILE}")


def score(session: Session) -> None:
    """Score current feature rows and write COMPUTED_RISK_SCORE back."""
    import joblib
    import tempfile

    df = _load_features(session)

    local_dir = tempfile.mkdtemp()
    session.file.get(f"{MODEL_STAGE}/{MODEL_FILE}", local_dir)
    model = joblib.load(os.path.join(local_dir, MODEL_FILE))

    df["COMPUTED_RISK_SCORE"] = model.predict_proba(df[FEATURE_COLUMNS])[:, 1].round(4)

    scored = session.create_dataframe(
        df[["ACCOUNT_ID", "FEATURE_DATE", "COMPUTED_RISK_SCORE"]]
    )
    scored.write.save_as_table(
        "ML_RISK_FEATURES_SCORED", mode="overwrite", table_type="temporary"
    )
    session.sql(
        """
        UPDATE ML_RISK_FEATURES f
        SET COMPUTED_RISK_SCORE = s.COMPUTED_RISK_SCORE
        FROM ML_RISK_FEATURES_SCORED s
        WHERE f.ACCOUNT_ID = s.ACCOUNT_ID AND f.FEATURE_DATE = s.FEATURE_DATE
        """
    ).collect()

    print(df[["ACCOUNT_ID", "COMPUTED_RISK_SCORE"]].sort_values(
        "COMPUTED_RISK_SCORE", ascending=False
    ).to_string(index=False))
    print(f"\nUpdated COMPUTED_RISK_SCORE for {len(df)} account/day rows.")


def explain(session: Session, account_id: str) -> None:
    df = _load_features(session)
    row = df[df["ACCOUNT_ID"] == account_id]
    if row.empty:
        print(f"No ML_RISK_FEATURES row for {account_id}")
        sys.exit(1)
    row = row.iloc[0]
    print(f"Risk feature breakdown for {account_id} (as of {row['FEATURE_DATE']}):")
    for feat in FEATURE_COLUMNS:
        print(f"  {feat:<28} {row[feat]}")
    print(f"  {'COMPUTED_RISK_SCORE':<28} {row['COMPUTED_RISK_SCORE']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["train", "score", "explain"], default="train")
    parser.add_argument("--account", help="ACCOUNT_ID for --mode explain")
    args = parser.parse_args()

    session = get_session()
    try:
        if args.mode == "train":
            train(session)
        elif args.mode == "score":
            score(session)
        elif args.mode == "explain":
            if not args.account:
                parser.error("--mode explain requires --account ACC-XXXX")
            explain(session, args.account)
    finally:
        session.close()


if __name__ == "__main__":
    main()
