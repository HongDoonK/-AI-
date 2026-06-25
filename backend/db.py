import json
import os
import sqlite3
import sys
import uuid

from backend.config import CENTER_COLUMNS, POLICY_COLUMNS, POLICY_PROCESSED_COLUMNS
from backend.region_map import get_region_codes

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


def _resolve_policy_db_path() -> str:
    env_path = os.getenv("YOUTH_POLICY_DB_PATH")
    if env_path:
        return env_path
    return next((path for path in _DB_CANDIDATES if os.path.exists(path)), _DB_CANDIDATES[0])


def _resolve_user_db_path() -> str:
    env_path = os.getenv("USER_DB_PATH")
    if env_path:
        return env_path
    return os.path.join(_ROOT_DIR, "data", "user_data.db")


DB_PATH = _resolve_policy_db_path()
USER_DB_PATH = _resolve_user_db_path()


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_user_connection():
    """사용자 런타임 데이터 전용 DB 연결 (정책 DB와 분리, git 비추적)."""
    user_db_path = os.getenv("USER_DB_PATH", USER_DB_PATH)
    os.makedirs(os.path.dirname(os.path.abspath(user_db_path)), exist_ok=True)
    conn = sqlite3.connect(user_db_path)
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
    """정책함(사용자별 저장 정책) 테이블 보장. 사용자 DB에 둔다."""
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
    """추천 카드(정책 dict)의 안정적인 식별 키를 만든다.

    프론트의 policyKey()와 동일한 규칙을 서버에서도 사용한다."""
    doc_id = policy.get("doc_id")
    if doc_id:
        return str(doc_id)
    source_table = policy.get("source_table") or "policy"
    source_id = policy.get("source_id") or policy.get("policy_name") or "unknown"
    return f"{source_table}:{source_id}"


def _migrate_legacy_users(policy_conn, user_conn):
    """과거에 정책 DB(youth_policy.db) 안에 저장된 users 데이터를
    분리된 사용자 DB로 1회 이전한다. 원본 행은 보존한다."""
    try:
        cursor = policy_conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        if cursor.fetchone() is None:
            return
        legacy_rows = cursor.execute("SELECT * FROM users").fetchall()
        if not legacy_rows:
            return
        user_cursor = user_conn.cursor()
        _ensure_users_table(user_cursor)
        migrated = 0
        for row in legacy_rows:
            data = dict(row)
            user_cursor.execute(
                """
                INSERT OR IGNORE INTO users (
                    user_id, age, gender, region_sido, region_sigungu,
                    status, interest, employment_status, income, housing_status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    data.get("user_id"),
                    data.get("age"),
                    data.get("gender"),
                    data.get("region_sido"),
                    data.get("region_sigungu"),
                    data.get("status"),
                    data.get("interest"),
                    data.get("employment_status"),
                    data.get("income"),
                    data.get("housing_status"),
                    data.get("created_at"),
                ),
            )
            migrated += user_cursor.rowcount if user_cursor.rowcount > 0 else 0
        user_conn.commit()
        if migrated:
            print(f"기존 정책 DB의 users {migrated}건을 사용자 DB로 이전했습니다.")
    except sqlite3.Error as exc:
        print(f"users 마이그레이션 중 경고(무시하고 계속): {exc}")


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

    _ensure_search_documents_table(cursor)

    conn.commit()

    user_conn = get_user_connection()
    user_cursor = user_conn.cursor()
    _ensure_users_table(user_cursor)
    _ensure_saved_policies_table(user_cursor)
    user_conn.commit()
    _migrate_legacy_users(conn, user_conn)
    user_conn.close()
    conn.close()
    print("DB 테이블 생성 완료 (정책 DB: policies, policies_processed, centers, search_documents / 사용자 DB: users, saved_policies)")


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
    codes = get_region_codes(sido, sigungu)
    if not codes:
        return []
    conn = get_connection()
    cursor = conn.cursor()
    # 코드 개수만큼 placeholder를 만들어 OR LIKE로 검색한다(통합 시의 하위 구 코드 포함).
    where = " OR ".join(["region LIKE ?"] * len(codes))
    cursor.execute(
        f"SELECT * FROM policies_processed WHERE {where}",
        [f"%{code}%" for code in codes],
    )
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def save_user(user_data: dict) -> str:
    user_id = str(uuid.uuid4())
    conn = get_user_connection()
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
    conn = get_user_connection()
    cursor = conn.cursor()
    _ensure_users_table(cursor)
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None


def save_policy_for_user(user_id: str, policy: dict) -> str:
    """사용자의 정책함에 정책을 저장한다. 같은 키면 갱신(업서트). 정책 키를 반환."""
    key = policy_key(policy)
    conn = get_user_connection()
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
    """사용자의 정책함 목록을 최신순으로 반환한다."""
    conn = get_user_connection()
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
    """정책함에서 정책을 삭제한다. 삭제되었으면 True."""
    conn = get_user_connection()
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
