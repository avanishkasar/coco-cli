"""
Shared Snowpark session + query helper used across all three pages.
"""

import os

import pandas as pd
import streamlit as st
from snowflake.snowpark import Session


@st.cache_resource
def get_snowflake_session() -> Session:
    return Session.builder.configs({
        "account":   os.getenv("SNOWFLAKE_ACCOUNT"),
        "user":      os.getenv("SNOWFLAKE_USER"),
        "password":  os.getenv("SNOWFLAKE_PASSWORD"),
        "role":      os.getenv("SNOWFLAKE_ROLE",      "SENTINEL_REG_ROLE"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE",  "SENTINEL_REG_WH"),
        "database":  os.getenv("SNOWFLAKE_DATABASE",   "SENTINEL_REG"),
        "schema":    os.getenv("SNOWFLAKE_SCHEMA",     "DATA"),
    }).create()


def run_query(sql: str) -> pd.DataFrame:
    try:
        return get_snowflake_session().sql(sql).to_pandas()
    except Exception as exc:
        st.error(f"Query error: {exc}")
        return pd.DataFrame()
