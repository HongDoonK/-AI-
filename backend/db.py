# db.py
# ──────────────────────────────────────────────────────────────
# SQLite DB 연결 및 테이블 생성
# ──────────────────────────────────────────────────────────────

import sqlite3
import os
from backend.config import POLICY_COLUMNS, POLICY_PROCESSED_COLUMNS, CENTER_COLUMNS

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "youth_policy.db")


def get_connection():
    """DB 연결을 반환하는 함수"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _build_policies_ddl(table_name: str, columns: dict) -> str:
    """policies 계열 테이블 CREATE 문 생성"""
    p = columns
    return f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            {p['policy_id']}           TEXT PRIMARY KEY,
            {p['policy_name']}         TEXT,
            {p['keyword']}             TEXT,
            {p['description']}         TEXT,
            {p['category_main']}       TEXT,
            {p['category_sub']}        TEXT,
            {p['support_content']}     TEXT,
            {p['pvsn_method']}         TEXT,
            {p['institution']}         TEXT,
            {p['institution_manager']} TEXT,
            {p['oper_inst']}           TEXT,
            {p['support_scale']}       TEXT,
            {p['arrive_seq']}          TEXT,
            {p['apply_period_type']}   TEXT,
            {p['biz_period_type']}     TEXT,
            {p['biz_start_date']}      TEXT,
            {p['biz_end_date']}        TEXT,
            {p['biz_period_etc']}      TEXT,
            {p['apply_method']}        TEXT,
            {p['selection_method']}    TEXT,
            {p['application_url']}     TEXT,
            {p['submit_docs']}         TEXT,
            {p['etc']}                 TEXT,
            {p['ref_url1']}            TEXT,
            {p['ref_url2']}            TEXT,
            {p['apply_period']}        TEXT,
            {p['min_age']}             TEXT,
            {p['max_age']}             TEXT,
            {p['age_limit']}           TEXT,
            {p['marriage_status']}     TEXT,
            {p['income_type']}         TEXT,
            {p['income_min']}          TEXT,
            {p['income_max']}          TEXT,
            {p['income_etc']}          TEXT,
            {p['apply_condition']}     TEXT,
            {p['excluded_target']}     TEXT,
            {p['region']}              TEXT,
            {p['major_cd']}            TEXT,
            {p['job_cd']}              TEXT,
            {p['school_cd']}           TEXT,
            {p['special_cd']}          TEXT,
            {p['first_reg_date']}      TEXT,
            {p['last_mod_date']}       TEXT,
            {p['search_text']}         TEXT
        )
    """


def create_tables():
    """policies, policies_processed, centers 테이블 생성"""
    conn = get_connection()
    cursor = conn.cursor()

    # ── policies 테이블 (원본) ────────────────────────────────
    cursor.execute(_build_policies_ddl("policies", POLICY_COLUMNS))

    # ── policies_processed 테이블 (전처리본) ──────────────────
    cursor.execute(_build_policies_ddl("policies_processed", POLICY_PROCESSED_COLUMNS))

    # ── centers 테이블 ────────────────────────────────────────
    c = CENTER_COLUMNS
    cursor.execute(f"""
        CREATE TABLE IF NOT EXISTS centers (
            {c['center_id']}      TEXT PRIMARY KEY,
            {c['center_name']}    TEXT,
            {c['center_tel']}     TEXT,
            {c['center_addr']}    TEXT,
            {c['center_daddr']}   TEXT,
            {c['center_url']}     TEXT,
            {c['center_ctpv_cd']} TEXT,
            {c['center_ctpv_nm']} TEXT,
            {c['center_sgg_cd']}  TEXT,
            {c['center_sgg_nm']}  TEXT
        )
    """)

    conn.commit()
    conn.close()
    print("✅ DB 테이블 생성 완료 (policies, policies_processed, centers)")


def get_centers_by_region(region: str) -> list:
    """시도명 또는 시군구명으로 청년센터 조회 (부분 일치)"""
    c = CENTER_COLUMNS
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"""SELECT * FROM centers
            WHERE {c['center_ctpv_nm']} LIKE ?
            OR {c['center_sgg_nm']} LIKE ?""",
        (f"%{region}%", f"%{region}%")
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ── 직접 실행 시 테이블 생성 테스트 ──────────────────────────
if __name__ == "__main__":
    create_tables()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"\n테이블 목록: {[t['name'] for t in tables]}")

    for table in tables:
        cursor.execute(f"PRAGMA table_info({table['name']})")
        cols = cursor.fetchall()
        print(f"\n[{table['name']}] 컬럼 수: {len(cols)}")
        for col in cols:
            print(f"  {col['name']} ({col['type']})")

    conn.close()
    print("\n✅ youth_policy.db 생성 완료")