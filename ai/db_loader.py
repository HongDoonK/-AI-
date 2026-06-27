from __future__ import annotations

import os
import sqlite3
from pathlib import Path

import pandas as pd


TABLE_NAME = "search_documents"
FALLBACK_TABLE_NAME = "policies_processed"

# 충북 전용(lgcv) 데이터가 별도 SQLite 파일이 아니라 기존 youth_policy.db 안에
# 들어있는 경우를 대비해, 추천 표준 테이블 이름 후보를 둔다.
LGCV_TABLE_NAMES = ("lgcv", "lgcv_search_documents")
WELFARE_CHUNGBUK_LOCAL_TABLE_NAME = "welfare_chungbuk_local"


class LgcvDataUnavailable(RuntimeError):
    """충북 전용(lgcv) 데이터를 찾지 못했을 때 발생. recommender가 기존 DB로 fallback한다."""


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
    built_period = (
        normalized.get("apply_start_date", pd.Series([""] * len(normalized))).fillna("").astype(str)
        + " ~ "
        + normalized.get("apply_end_date", pd.Series([""] * len(normalized))).fillna("").astype(str)
    ).str.strip(" ~")
    normalized["apply_period"] = built_period
    normalized["application_url"] = normalized.get("url", "")
    normalized["job_cd"] = normalized.get("employment_status", "")
    normalized["school_cd"] = normalized.get("status", "")
    normalized["income_type"] = ""
    normalized["income_etc"] = ""
    normalized["apply_condition"] = normalized.get("target", "")
    return normalized


def _clean(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def _join_nonempty(*parts) -> str:
    return " ".join(part for part in (_clean(part) for part in parts) if part)


def _normalize_chungbuk_sido(value) -> str:
    text = _clean(value)
    if "충청북도" in text or "충북" in text:
        return "충북"
    return text or "충북"


def _normalize_welfare_chungbuk_local(df: pd.DataFrame) -> pd.DataFrame:
    """Convert the Git DB's welfare_chungbuk_local source into lgcv search docs."""
    rows = []
    for item in df.to_dict("records"):
        source_id = _clean(item.get("service_id") or item.get("source_id") or item.get("id"))
        if not source_id:
            continue

        region_sido = _normalize_chungbuk_sido(
            item.get("region_sido") or item.get("sido") or item.get("region")
        )
        region_sigungu = _clean(
            item.get("region_sigungu") or item.get("sigungu") or item.get("sgg_nm")
        )
        region_name = _join_nonempty(region_sido, region_sigungu) or "충북"
        title = _clean(item.get("service_name") or item.get("title") or item.get("name"))
        summary = _join_nonempty(
            item.get("summary"),
            item.get("detail_summary"),
            item.get("support_content"),
            item.get("description"),
        )
        target = _join_nonempty(
            item.get("life_cycle"),
            item.get("target_group"),
            item.get("target_detail"),
            item.get("support_target"),
            item.get("target"),
            item.get("selection_criteria"),
        )
        agency = _join_nonempty(
            item.get("department"),
            item.get("responsible_agency"),
            item.get("ministry"),
            item.get("organization"),
        )
        search_text = _clean(item.get("search_text")) or _join_nonempty(
            title,
            item.get("interest_theme"),
            summary,
            target,
            item.get("application_method"),
            agency,
            region_name,
        )

        rows.append(
            {
                "doc_id": f"lgcv:{source_id}",
                "source_table": "lgcv",
                "source_id": source_id,
                "domain": "welfare",
                "title": title,
                "summary": summary,
                "region_name": region_name,
                "region_sido": region_sido,
                "region_sigungu": region_sigungu,
                "target": target,
                "min_age": None,
                "max_age": None,
                "employment_status": "",
                "status": _clean(item.get("life_cycle")),
                "apply_start_date": _clean(item.get("enforcement_start_date")),
                "apply_end_date": _clean(item.get("enforcement_end_date")),
                "url": _clean(item.get("service_url") or item.get("homepage") or item.get("url")),
                "search_text": search_text,
                "raw_ref": source_id,
                "collected_at": _clean(item.get("imported_at") or item.get("last_modified_date")),
            }
        )

    if not rows:
        return pd.DataFrame()
    return _normalize_search_documents(pd.DataFrame(rows))


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


def find_lgcv_db_path() -> Path | None:
    """충북 전용(lgcv) 데이터 파일 경로를 탐색한다.

    우선순위:
        1. LGCV_POLICY_DB_PATH 환경변수
        2. data/lgcv.db
        3. data/lgcv.sqlite
        4. lgcv.db (프로젝트 루트)

    위 후보가 모두 없으면 None을 반환한다. (기존 youth_policy.db 안의 lgcv
    테이블 탐색은 load_lgcv_df()에서 별도로 처리한다.)
    """
    env_path = os.getenv("LGCV_POLICY_DB_PATH")
    if env_path:
        path = Path(env_path)
        if path.exists():
            return path
        raise FileNotFoundError(f"LGCV_POLICY_DB_PATH was set, but no file exists at: {path}")

    root = project_root()
    candidates = [
        root / "data" / "lgcv.db",
        root / "data" / "lgcv.sqlite",
        root / "lgcv.db",
    ]
    for path in candidates:
        if path.exists():
            return path
    return None


def _read_recommendation_table(conn: sqlite3.Connection, table_names: tuple[str, ...]) -> pd.DataFrame | None:
    """후보 테이블 중 처음으로 존재하고 비어있지 않은 것을 표준 컬럼으로 normalize한다."""
    for table_name in table_names:
        if not _table_exists(conn, table_name):
            continue
        df = pd.read_sql(f"SELECT * FROM {table_name}", conn)
        if df.empty:
            continue
        # search_documents 계열 스키마는 title/summary를 추천 표준 컬럼으로 변환한다.
        if "title" in df.columns and "policy_name" not in df.columns:
            df = _normalize_search_documents(df)
        return df
    return None


def _read_lgcv_from_search_documents(conn: sqlite3.Connection) -> pd.DataFrame | None:
    """통합 search_documents에서 source_table='lgcv' 행만 읽어 표준 컬럼으로 normalize한다.

    최신 origin/main은 lgcv를 별도 테이블이 아니라 search_documents에 통합하므로
    (source_table='lgcv', domain='welfare'), 이 경로가 운영 환경의 핵심이다.
    """
    if not _table_exists(conn, TABLE_NAME):
        return None
    df = pd.read_sql(
        f"SELECT * FROM {TABLE_NAME} WHERE source_table = 'lgcv'", conn
    )
    if df.empty:
        return None
    if "title" in df.columns and "policy_name" not in df.columns:
        df = _normalize_search_documents(df)
    return df


def _read_welfare_chungbuk_local(conn: sqlite3.Connection) -> pd.DataFrame | None:
    """Read welfare_chungbuk_local as the actual Chungbuk lgcv source table."""
    if not _table_exists(conn, WELFARE_CHUNGBUK_LOCAL_TABLE_NAME):
        return None
    df = pd.read_sql(f"SELECT * FROM {WELFARE_CHUNGBUK_LOCAL_TABLE_NAME}", conn)
    if df.empty:
        return None
    normalized = _normalize_welfare_chungbuk_local(df)
    if normalized.empty:
        return None
    return normalized


def load_lgcv_df() -> pd.DataFrame | None:
    """충북 전용(lgcv) 데이터를 추천 표준 컬럼 형태의 DataFrame으로 로드한다.

    탐색 순서:
      1. LGCV_POLICY_DB_PATH 별도 파일: lgcv / lgcv_search_documents / search_documents
         (별도 파일의 search_documents는 lgcv 전용으로 간주)
      2. 기본 youth_policy.db 안의 lgcv / lgcv_search_documents 테이블
      3. 기본 youth_policy.db 안의 search_documents WHERE source_table='lgcv' (최신 통합 구조)

    어떤 경로에서도 데이터를 찾지 못하면 None을 반환하여 recommender가 기존 통합 DB로
    fallback할 수 있게 한다. search_text 표준 컬럼이 없으면 명확한 에러를 낸다.
    """
    lgcv_path = find_lgcv_db_path()
    if lgcv_path is not None:
        db_path = lgcv_path
        table_names = LGCV_TABLE_NAMES + (TABLE_NAME,)
    else:
        # 전용 파일이 없으면 기존 youth_policy.db를 본다.
        try:
            db_path = find_db_path()
        except FileNotFoundError:
            return None
        table_names = LGCV_TABLE_NAMES

    try:
        with sqlite3.connect(db_path) as conn:
            df = _read_recommendation_table(conn, table_names)
            # origin/main stores Chungbuk local welfare rows in this source
            # table before search_documents is rebuilt.
            if df is None or df.empty:
                df = _read_welfare_chungbuk_local(conn)
            # 별도 lgcv/lgcv_search_documents 테이블이 없으면 통합 search_documents에서
            # source_table='lgcv' 행을 읽는다(최신 운영 구조).
            if df is None or df.empty:
                df = _read_lgcv_from_search_documents(conn)
    except sqlite3.Error as exc:
        raise RuntimeError(f"Failed to read lgcv data from {db_path}: {exc}") from exc

    if df is None or df.empty:
        return None
    if "search_text" not in df.columns:
        raise ValueError(
            f"lgcv recommendation table in {db_path} must contain a search_text column."
        )
    return df
