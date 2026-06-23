import json
import os
import sqlite3
import sys
import uuid

from backend.config import CENTER_COLUMNS, POLICY_COLUMNS, POLICY_PROCESSED_COLUMNS
from backend.region_map import get_region_code

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

_ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_DB_CANDIDATES = [
    os.path.join(_ROOT_DIR, "youth_policy.db"),
    os.path.join(_ROOT_DIR, "data", "youth_policy.db"),
    os.path.join(_ROOT_DIR, "backend", "youth_policy.db"),
]
DB_PATH = next((path for path in _DB_CANDIDATES if os.path.exists(path)), _DB_CANDIDATES[0])


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_users_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id           TEXT PRIMARY KEY,
            age               INTEGER,
            gender            TEXT,
            region_sido       TEXT,
            region_sigungu    TEXT,
            status            TEXT,
            interest          TEXT,
            employment_status TEXT,
            income            TEXT,
            housing_status    TEXT,
            created_at        TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)
    cursor.execute("PRAGMA table_info(users)")
    columns = {row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in cursor.fetchall()}
    if "gender" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN gender TEXT")


def _build_policies_ddl(table_name: str, columns: dict) -> str:
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
            {p['region_name']}         TEXT,
            {p['major_cd']}            TEXT,
            {p['job_cd']}              TEXT,
            {p['school_cd']}           TEXT,
            {p['special_cd']}          TEXT,
            {p['first_reg_date']}      TEXT,
            {p['last_mod_date']}       TEXT,
            {p['search_text']}         TEXT
        )
    """


def _ensure_search_documents_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_documents (
            doc_id            TEXT PRIMARY KEY,
            source_table      TEXT NOT NULL,
            source_id         TEXT NOT NULL,
            domain            TEXT NOT NULL,
            title             TEXT,
            summary           TEXT,
            region_name       TEXT,
            region_sido       TEXT,
            region_sigungu    TEXT,
            target            TEXT,
            min_age           INTEGER,
            max_age           INTEGER,
            employment_status TEXT,
            status            TEXT,
            apply_start_date  TEXT,
            apply_end_date    TEXT,
            url               TEXT,
            search_text       TEXT,
            raw_ref           TEXT,
            collected_at      TEXT
        )
    """)
    cursor.execute("PRAGMA table_info(search_documents)")
    columns = {row["name"] if isinstance(row, sqlite3.Row) else row[1] for row in cursor.fetchall()}
    if "region_sido" not in columns:
        cursor.execute("ALTER TABLE search_documents ADD COLUMN region_sido TEXT")
    if "region_sigungu" not in columns:
        cursor.execute("ALTER TABLE search_documents ADD COLUMN region_sigungu TEXT")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_documents_domain ON search_documents(domain)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_documents_region ON search_documents(region_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_documents_region_sido ON search_documents(region_sido)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_documents_region_sigungu ON search_documents(region_sigungu)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_search_documents_source ON search_documents(source_table, source_id)")


def _ensure_saved_policies_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS saved_policies (
            user_id     TEXT NOT NULL,
            policy_key  TEXT NOT NULL,
            policy_name TEXT,
            policy_json TEXT NOT NULL,
            created_at  TEXT DEFAULT (datetime('now', 'localtime')),
            PRIMARY KEY (user_id, policy_key)
        )
    """)
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_saved_policies_user ON saved_policies(user_id)"
    )


def policy_key(policy: dict) -> str:
    """프론트엔드 policyKey()와 동일한 규칙으로 정책 고유 키를 만든다."""
    doc_id = policy.get("doc_id")
    if doc_id:
        return str(doc_id)
    source_table = policy.get("source_table") or "policy"
    source_id = policy.get("source_id") or policy.get("policy_name") or "unknown"
    return f"{source_table}:{source_id}"


def create_tables():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(_build_policies_ddl("policies", POLICY_COLUMNS))
    cursor.execute(_build_policies_ddl("policies_processed", POLICY_PROCESSED_COLUMNS))

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

    _ensure_users_table(cursor)
    _ensure_search_documents_table(cursor)
    _ensure_saved_policies_table(cursor)

    conn.commit()
    conn.close()
    print("DB 테이블 생성 완료 (policies, policies_processed, centers, users, search_documents, saved_policies)")


def get_centers_by_region(region: str) -> list:
    c = CENTER_COLUMNS
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        f"""SELECT * FROM centers
            WHERE {c['center_ctpv_nm']} LIKE ?
            OR {c['center_sgg_nm']} LIKE ?""",
        (f"%{region}%", f"%{region}%"),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_policies_by_region(sido: str, sigungu: str) -> list:
    code = get_region_code(sido, sigungu)
    if not code:
        return []
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT * FROM policies_processed WHERE region LIKE ?",
        (f"%{code}%",),
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def save_user(user_data: dict) -> str:
    user_id = str(uuid.uuid4())
    conn = get_connection()
    cursor = conn.cursor()
    _ensure_users_table(cursor)
    cursor.execute(
        """
        INSERT INTO users (
            user_id, age, gender, region_sido, region_sigungu,
            status, interest, employment_status, income, housing_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            user_data.get("age"),
            user_data.get("gender"),
            user_data.get("region_sido"),
            user_data.get("region_sigungu"),
            user_data.get("status"),
            user_data.get("interest"),
            user_data.get("employment_status"),
            user_data.get("income"),
            user_data.get("housing_status"),
        ),
    )
    conn.commit()
    conn.close()
    return user_id


def get_user(user_id: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def save_policy_for_user(user_id: str, policy: dict) -> str:
    """사용자의 정책함에 정책 1개를 담는다. 같은 정책이면 덮어쓴다(중복 방지)."""
    key = policy_key(policy)
    conn = get_connection()
    cursor = conn.cursor()
    _ensure_saved_policies_table(cursor)
    cursor.execute(
        """
        INSERT INTO saved_policies (user_id, policy_key, policy_name, policy_json)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id, policy_key) DO UPDATE SET
            policy_name = excluded.policy_name,
            policy_json = excluded.policy_json
        """,
        (user_id, key, policy.get("policy_name", ""), json.dumps(policy, ensure_ascii=False)),
    )
    conn.commit()
    conn.close()
    return key


def get_saved_policies(user_id: str) -> list:
    """사용자가 담아둔 정책 목록을 최신순으로 반환한다."""
    conn = get_connection()
    cursor = conn.cursor()
    _ensure_saved_policies_table(cursor)
    cursor.execute(
        "SELECT policy_json FROM saved_policies WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    policies = []
    for row in rows:
        try:
            policies.append(json.loads(row["policy_json"]))
        except (json.JSONDecodeError, TypeError):
            continue
    return policies


def delete_saved_policy(user_id: str, key: str) -> bool:
    """정책함에서 정책 1개를 뺀다. 실제로 삭제됐으면 True."""
    conn = get_connection()
    cursor = conn.cursor()
    _ensure_saved_policies_table(cursor)
    cursor.execute(
        "DELETE FROM saved_policies WHERE user_id = ? AND policy_key = ?",
        (user_id, key),
    )
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


if __name__ == "__main__":
    create_tables()

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"\n테이블 목록: {[table['name'] for table in tables]}")

    for table in tables:
        cursor.execute(f"PRAGMA table_info({table['name']})")
        cols = cursor.fetchall()
        print(f"\n[{table['name']}] 컬럼 수: {len(cols)}")
        for col in cols:
            print(f"  {col['name']} ({col['type']})")

    conn.close()
    print("\nyouth_policy.db 확인 완료")
