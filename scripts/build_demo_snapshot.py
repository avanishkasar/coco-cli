"""
One-off generator: parses setup/03_load_synthetic_data.sql and
setup/04_cortex_search.sql with sqlglot and writes app/data/demo_snapshot.json
so the offline demo snapshot is byte-for-byte the same seed data that
gets loaded into Snowflake.
"""
import json
import pathlib
import sys

import sqlglot
from sqlglot import exp

REPO = pathlib.Path(__file__).resolve().parent.parent

COLUMNS = {
    "CUSTOMERS": ["CUSTOMER_ID", "FULL_NAME", "ENTITY_TYPE", "KYC_TIER", "COUNTRY_OF_ORIGIN",
                  "ACCOUNT_OPEN_DATE", "PEP_FLAG", "SANCTIONS_FLAG", "ANNUAL_INCOME_INR",
                  "OCCUPATION", "RELATIONSHIP_MANAGER", "LAST_KYC_REFRESH", "NOTES"],
    "ACCOUNTS": ["ACCOUNT_ID", "CUSTOMER_ID", "ACCOUNT_TYPE", "IFSC_CODE", "BRANCH_CODE",
                 "OPENING_DATE", "CURRENT_BALANCE_INR", "STATUS", "RISK_SCORE",
                 "AVERAGE_MONTHLY_CREDIT", "LAST_TRANSACTION_DATE"],
    "ML_RISK_FEATURES": ["ACCOUNT_ID", "FEATURE_DATE", "TXN_COUNT_7D", "TXN_COUNT_30D",
                         "CASH_TXN_RATIO_30D", "AVG_TXN_AMOUNT_30D", "MAX_TXN_AMOUNT_30D",
                         "JUST_BELOW_THRESHOLD_COUNT", "UNIQUE_COUNTERPARTIES_30D",
                         "ROUND_TRIP_DETECTED", "GEOGRAPHIC_ANOMALY_SCORE", "VELOCITY_SCORE",
                         "COMPUTED_RISK_SCORE", "IS_FRAUD_LABEL"],
    "REGULATORY_DOCS_CHUNKS": ["CHUNK_ID", "DOC_NAME", "DOC_TYPE", "SECTION_NUMBER",
                               "SECTION_TITLE", "CHUNK_TEXT", "EFFECTIVE_DATE", "JURISDICTION"],
}


def value_of(node):
    if isinstance(node, exp.Null):
        return None
    if isinstance(node, exp.Boolean):
        return node.this
    if isinstance(node, exp.Literal):
        if node.is_string:
            return node.this
        text = node.this
        return float(text) if any(c in text for c in ".eE") else int(text)
    if isinstance(node, exp.Neg):
        v = value_of(node.this)
        return -v
    if isinstance(node, exp.Cast):
        return value_of(node.this)
    if isinstance(node, (exp.Array,)):
        return [value_of(e) for e in node.expressions]
    if isinstance(node, exp.Anonymous) and node.name.upper() == "ARRAY_CONSTRUCT":
        return [value_of(e) for e in node.expressions]
    if isinstance(node, exp.Alias):
        return value_of(node.this)
    raise ValueError(f"Unhandled node {type(node).__name__}: {node.sql()}")


def rows_from_insert(stmt: exp.Insert):
    target = stmt.this
    if isinstance(target, exp.Schema):
        table = target.this.name.upper()
        cols = [c.name.upper() for c in target.expressions]
    else:
        table = target.name.upper()
        cols = COLUMNS[table]

    source = stmt.expression
    if isinstance(source, exp.Values):
        tuples = [[value_of(v) for v in t.expressions] for t in source.expressions]
    elif isinstance(source, exp.Select):
        tuples = [[value_of(v) for v in source.expressions]]
    else:
        raise ValueError(f"Unhandled insert source {type(source).__name__}")

    out = []
    for t in tuples:
        if len(t) != len(cols):
            raise ValueError(f"{table}: {len(t)} values vs {len(cols)} columns")
        out.append(dict(zip(cols, t)))
    return table, out


def main():
    snapshot = {k: [] for k in ["CUSTOMERS", "ACCOUNTS", "TRANSACTIONS", "AML_ALERTS",
                                "ML_RISK_FEATURES", "REGULATORY_DOCS_CHUNKS"]}
    for fname in ["03_load_synthetic_data.sql", "04_cortex_search.sql"]:
        sql = (REPO / "setup" / fname).read_text(encoding="utf-8")
        for stmt in sqlglot.parse(sql, read="snowflake"):
            if isinstance(stmt, exp.Insert):
                table, rows = rows_from_insert(stmt)
                snapshot[table].extend(rows)

    counts = {k: len(v) for k, v in snapshot.items()}
    print(counts)
    for k, v in counts.items():
        if v == 0:
            sys.exit(f"empty table in snapshot: {k}")

    out = REPO / "app" / "data" / "demo_snapshot.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(snapshot, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
