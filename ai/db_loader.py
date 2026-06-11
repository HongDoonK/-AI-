from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd


TABLE_NAME = "search_documents"
FALLBACK_TABLE_NAME = "policies_processed"


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def find_db_path() -> Path:
    env_path = os.getenv("YOUTH_POLICY_DB_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
        raise FileNotFoundError(f"YOUTH_POLICY_DB_PATH was set, but no file exists at: {path}")

    root = project_root()
    candidates = [
        root / "youth_policy.db",
        root / "data" / "youth_policy.db",
        root / "backend" / "youth_policy.db",
    ]
    for path in candidates:
        if path.exists():
            return path
    checked = "\n".join(f"- {path}" for path in candidates)
    raise FileNotFoundError("youth_policy.db file was not found. Checked:\n" + checked)


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    tables = pd.read_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
        conn,
        params=(table_name,),
    )
    return not tables.empty


def _normalize_search_documents(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized["policy_id"] = normalized.get("doc_id", normalized.index.astype(str))
    normalized["policy_name"] = normalized.get("title", "")
    normalized["description"] = normalized.get("summary", "")
    normalized["support_content"] = normalized.get("summary", "")
    normalized["category_main"] = normalized.get("domain", "")
    normalized["category_sub"] = normalized.get("source_table", "")
    normalized["keyword"] = normalized.get("target", "")
    normalized["apply_period"] = (
        normalized.get("apply_start_date", "").fillna("").astype(str)
        + " ~ "
        + normalized.get("apply_end_date", "").fillna("").astype(str)
    ).str.strip(" ~")
    normalized["application_url"] = normalized.get("url", "")
    normalized["job_cd"] = normalized.get("employment_status", "")
    normalized["school_cd"] = normalized.get("status", "")
    normalized["income_type"] = ""
    normalized["income_etc"] = ""
    normalized["apply_condition"] = normalized.get("target", "")
    return normalized


def load_policy_df() -> pd.DataFrame:
    db_path = find_db_path()
    try:
        with sqlite3.connect(db_path) as conn:
            if _table_exists(conn, TABLE_NAME):
                df = pd.read_sql(f"SELECT * FROM {TABLE_NAME} ORDER BY doc_id", conn)
                if not df.empty:
                    df = _normalize_search_documents(df)
            else:
                df = pd.DataFrame()

            if df.empty:
                if not _table_exists(conn, FALLBACK_TABLE_NAME):
                    raise ValueError(
                        f"SQLite DB exists at {db_path}, but neither '{TABLE_NAME}' nor "
                        f"'{FALLBACK_TABLE_NAME}' was found."
                    )
                df = pd.read_sql(f"SELECT * FROM {FALLBACK_TABLE_NAME} ORDER BY policy_id", conn)

            if df.empty:
                raise ValueError(
                    f"SQLite DB exists at {db_path}, but recommendation source tables are empty."
                )
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to read recommendation data from {db_path}: {exc}") from exc

    if df.empty:
        raise ValueError(f"Recommendation table in {db_path} has no rows.")
    if "search_text" not in df.columns:
        raise ValueError("Recommendation table must contain a search_text column.")
    return df
