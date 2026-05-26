from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


TABLE_NAME = "policies_processed"


def project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def find_db_path() -> Path:
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


def load_policy_df() -> pd.DataFrame:
    db_path = find_db_path()
    try:
        with sqlite3.connect(db_path) as conn:
            tables = pd.read_sql(
                "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
                conn,
                params=(TABLE_NAME,),
            )
            if tables.empty:
                raise ValueError(
                    f"SQLite DB exists at {db_path}, but table '{TABLE_NAME}' was not found."
                )
            df = pd.read_sql(f"SELECT * FROM {TABLE_NAME} ORDER BY policy_id", conn)
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to read {TABLE_NAME} from {db_path}: {exc}") from exc

    if df.empty:
        raise ValueError(f"Table '{TABLE_NAME}' in {db_path} has no rows.")
    if "search_text" not in df.columns:
        raise ValueError(f"Table '{TABLE_NAME}' must contain a search_text column.")
    return df

