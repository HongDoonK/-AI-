# preprocessing.py
# ──────────────────────────────────────────────────────────────
# policies 테이블(원본)을 읽어서 전처리 후
# policies_processed 테이블에 저장
# ──────────────────────────────────────────────────────────────

from backend.db import get_connection
from backend.config import POLICY_COLUMNS, POLICY_PROCESSED_COLUMNS


# ════════════════════════════════════════════════════════════════
# 코드 변환 딕셔너리 (API코드정보.xlsx 기반)
# ════════════════════════════════════════════════════════════════

PVSN_METHOD_MAP = {
    "0042001": "인프라 구축",
    "0042002": "프로그램",
    "0042003": "직접대출",
    "0042004": "공공기관",
    "0042005": "계약(위탁운영)",
    "0042006": "보조금",
    "0042007": "대출보증",
    "0042008": "공적보험",
    "0042009": "조세지출",
    "0042010": "바우처",
    "0042011": "정보제공",
    "0042012": "경제적 규제",
    "0042013": "기타",
}

APPLY_PERIOD_TYPE_MAP = {
    "0057001": "특정기간",
    "0057002": "상시",
    "0057003": "마감",
}

BIZ_PERIOD_TYPE_MAP = {
    "0056001": "특정기간",
    "0056002": "기타",
}

MARRIAGE_STATUS_MAP = {
    "0055001": "기혼",
    "0055002": "미혼",
    "0055003": "제한없음",
}

INCOME_TYPE_MAP = {
    "0043001": "무관",
    "0043002": "연소득",
    "0043003": "기타",
}

MAJOR_CD_MAP = {
    "0011001": "인문계열",
    "0011002": "사회계열",
    "0011003": "상경계열",
    "0011004": "이학계열",
    "0011005": "공학계열",
    "0011006": "예체능계열",
    "0011007": "농산업계열",
    "0011008": "기타",
    "0011009": "제한없음",
}

JOB_CD_MAP = {
    "0013001": "재직자",
    "0013002": "자영업자",
    "0013003": "미취업자",
    "0013004": "프리랜서",
    "0013005": "일용근로자",
    "0013006": "(예비)창업자",
    "0013007": "단기근로자",
    "0013008": "영농종사자",
    "0013009": "기타",
    "0013010": "제한없음",
}

SCHOOL_CD_MAP = {
    "0049001": "고졸 미만",
    "0049002": "고교 재학",
    "0049003": "고졸 예정",
    "0049004": "고교 졸업",
    "0049005": "대학 재학",
    "0049006": "대졸 예정",
    "0049007": "대학 졸업",
    "0049008": "석·박사",
    "0049009": "기타",
    "0049010": "제한없음",
}

SPECIAL_CD_MAP = {
    "0014001": "중소기업",
    "0014002": "여성",
    "0014003": "기초생활수급자",
    "0014004": "한부모가정",
    "0014005": "장애인",
    "0014006": "농업인",
    "0014007": "군인",
    "0014008": "지역인재",
    "0014009": "기타",
    "0014010": "제한없음",
}

# 어떤 컬럼을 어떤 매핑으로 변환할지 정의
COLUMN_CODE_MAPS = {
    POLICY_COLUMNS["pvsn_method"]:       PVSN_METHOD_MAP,
    POLICY_COLUMNS["apply_period_type"]: APPLY_PERIOD_TYPE_MAP,
    POLICY_COLUMNS["biz_period_type"]:   BIZ_PERIOD_TYPE_MAP,
    POLICY_COLUMNS["marriage_status"]:   MARRIAGE_STATUS_MAP,
    POLICY_COLUMNS["income_type"]:       INCOME_TYPE_MAP,
    POLICY_COLUMNS["major_cd"]:          MAJOR_CD_MAP,
    POLICY_COLUMNS["job_cd"]:            JOB_CD_MAP,
    POLICY_COLUMNS["school_cd"]:         SCHOOL_CD_MAP,
    POLICY_COLUMNS["special_cd"]:        SPECIAL_CD_MAP,
}


# ════════════════════════════════════════════════════════════════
# 코드값 → 텍스트 변환
# ════════════════════════════════════════════════════════════════

def convert_code(value, code_map: dict) -> str:
    """
    코드값을 텍스트로 변환
    콤마로 여러 코드가 들어있는 경우도 처리
    예: "0013006,0013009" → "(예비)창업자, 기타"
    매핑에 없으면 원본 그대로 반환
    """
    if not value:
        return value
    codes     = [c.strip() for c in str(value).split(",")]
    converted = [code_map.get(c, c) for c in codes]
    return ", ".join(converted)


# ════════════════════════════════════════════════════════════════
# search_text 생성 (임베딩용 통합 텍스트)
# ════════════════════════════════════════════════════════════════

def make_search_text(row: dict) -> str:
    """
    AI 모듈 임베딩용 통합 텍스트 생성
    변환된 텍스트 기준으로 생성
    """
    p = POLICY_COLUMNS
    parts = [
        row.get(p["policy_name"]),
        row.get(p["description"]),
        row.get(p["keyword"]),
        row.get(p["category_main"]),
        row.get(p["category_sub"]),
        row.get(p["support_content"]),
    ]
    return " ".join([part for part in parts if part])


# ════════════════════════════════════════════════════════════════
# 전처리 실행 → policies_processed에 저장
# ════════════════════════════════════════════════════════════════

def preprocess_policies():
    """
    policies 테이블(원본)을 읽어서 전처리 후
    policies_processed 테이블에 INSERT OR REPLACE
    원본 policies 테이블은 건드리지 않음
    """
    print("\n[정책 데이터 전처리 시작]")

    p    = POLICY_PROCESSED_COLUMNS
    conn = get_connection()
    cursor = conn.cursor()

    # 원본 테이블에서 전체 조회
    cursor.execute("SELECT * FROM policies")
    rows = cursor.fetchall()

    if not rows:
        print("  ⚠️  policies 테이블에 데이터가 없습니다. 먼저 api_collector를 실행하세요.")
        conn.close()
        return

    # policies_processed 테이블 초기화
    cursor.execute("DELETE FROM policies_processed")

    cols             = list(p.values())
    col_names        = ", ".join(cols)
    col_placeholders = ", ".join(["?"] * len(cols))

    saved = 0
    for row in rows:
        row_dict = dict(row)

        # ① 코드 컬럼 → 텍스트 변환
        for col_name, code_map in COLUMN_CODE_MAPS.items():
            row_dict[col_name] = convert_code(row_dict.get(col_name), code_map)

        # ② 변환된 텍스트로 search_text 생성
        row_dict[p["search_text"]] = make_search_text(row_dict)

        # ③ policies_processed에 저장
        values = [row_dict.get(col) for col in cols]
        cursor.execute(
            f"INSERT OR REPLACE INTO policies_processed ({col_names}) VALUES ({col_placeholders})",
            values
        )
        saved += 1

    conn.commit()
    conn.close()
    print(f"  ✅ policies_processed 테이블에 {saved}건 저장 완료")
    print(f"  ✅ policies 테이블(원본)은 그대로 유지됩니다.")


# ── 직접 실행 시 ──────────────────────────────────────────────
if __name__ == "__main__":
    preprocess_policies()