# preprocessing.py
# ──────────────────────────────────────────────────────────────
# policies 테이블(원본)을 읽어서 전처리 후
# policies_processed 테이블에 저장
# ──────────────────────────────────────────────────────────────

import re

from backend.db import _ensure_search_documents_table, get_connection
from backend.config import POLICY_COLUMNS, POLICY_PROCESSED_COLUMNS
from backend.region_map import REGION_CODE_MAP, CODE_TO_SIDO, CODE_TO_SIGUNGU
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
# 법정동 코드 → 지역명 변환
# ════════════════════════════════════════════════════════════════

def convert_region_to_name(region_val) -> str:
    """
    법정동 코드를 한국어 지역명으로 변환
    예: "11110,11140,11680" → "서울"
    예: "44130,44150"       → "충남"
    예: "00" 또는 빈값      → "전국"
    """
    if not region_val or str(region_val).strip() in ("", "00", "None"):
        return "전국"
    
    region_name, _, _ = convert_region_to_parts(region_val)
    return region_name


def convert_region_to_parts(region_val) -> tuple[str, str, str]:
    """
    법정동 코드를 지역명/시도/시군구로 분리한다.
    예: "41370"       → ("경기 오산시", "경기", "오산시")
    예: "41370,41220" → ("경기 오산시, 경기 평택시", "경기", "오산시,평택시")
    예: "00"          → ("전국", "전국", "")
    """
    if not region_val or str(region_val).strip() in ("", "00", "None"):
        return "전국", "전국", ""

    codes = [c.strip() for c in str(region_val).split(",")]
    names = []
    sidos = []
    sigungus = []
    
    for code in codes:
        sido = CODE_TO_SIDO.get(code)
        sigungu = CODE_TO_SIGUNGU.get(code)
        if sido and sido not in sidos:
            sidos.append(sido)
        if sigungu and sigungu not in sigungus:
            sigungus.append(sigungu)
        if sido and sigungu:
            name = f"{sido} {sigungu}"
            if name not in names:
                names.append(name)
    
    if len(sidos) >= 10:
        return "전국", "전국", ""
    if not names and sidos:
        names = sidos
    return ", ".join(names) if names else "전국", ",".join(sidos) if sidos else "전국", ",".join(sigungus)

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
        row.get(p["region_name"]),
    ]
    return " ".join([part for part in parts if part])


# ════════════════════════════════════════════════════════════════
# 통합 검색 테이블 생성
# ════════════════════════════════════════════════════════════════

def _clean(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _join_parts(*parts) -> str:
    return " ".join(part for part in (_clean(part) for part in parts) if part)


def _table_exists(cursor, table_name: str) -> bool:
    cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    )
    return cursor.fetchone() is not None


def _date_yyyymmdd(value) -> str:
    text = re.sub(r"\D", "", _clean(value))
    if len(text) >= 8:
        return f"{text[:4]}-{text[4:6]}-{text[6:8]}"
    return _clean(value)


def _parse_age_bounds(*values) -> tuple[int | None, int | None]:
    text = " ".join(_clean(value) for value in values)
    numbers = [int(value) for value in re.findall(r"\d{1,2}", text)]
    if not numbers:
        return None, None
    if any(word in text for word in ["이하", "미만", "까지"]):
        return None, max(numbers)
    if any(word in text for word in ["이상", "초과", "부터"]):
        return min(numbers), None
    if len(numbers) >= 2:
        return min(numbers), max(numbers)
    return numbers[0], numbers[0]




def _region_from_address(value) -> str:
    text = _clean(value)
    if not text or text in {"-", "전국"}:
        return "전국"
    aliases = {
        "서울특별시": "서울",
        "부산광역시": "부산",
        "대구광역시": "대구",
        "인천광역시": "인천",
        "광주광역시": "광주",
        "대전광역시": "대전",
        "울산광역시": "울산",
        "세종특별자치시": "세종",
        "경기도": "경기",
        "강원특별자치도": "강원",
        "강원도": "강원",
        "충청북도": "충북",
        "충청남도": "충남",
        "전북특별자치도": "전북",
        "전라북도": "전북",
        "전라남도": "전남",
        "경상북도": "경북",
        "경상남도": "경남",
        "제주특별자치도": "제주",
    }
    for long_name, short_name in aliases.items():
        if long_name in text:
            return text.replace(long_name, short_name, 1)
    first = text.split()[0].strip()
    return first if first else "전국"


def _split_region_text(value) -> tuple[str, str, str]:
    text = _region_from_address(value)
    if not text or text == "전국":
        return "전국", "전국", ""

    parts = text.split()
    sido = parts[0] if parts else ""
    sigungu = ""
    if sido in REGION_CODE_MAP:
        for candidate in parts[1:]:
            if candidate in REGION_CODE_MAP[sido]:
                sigungu = candidate
                break
        if not sigungu and len(parts) > 1:
            sigungu = parts[1]

    region_name = f"{sido} {sigungu}".strip() if sigungu else sido
    return region_name or "전국", sido or "전국", sigungu


def _split_region_fields(sido_value, sigungu_value=None) -> tuple[str, str, str]:
    sido_text = _region_from_address(sido_value)
    sigungu_text = _clean(sigungu_value)
    if not sido_text or sido_text == "전국":
        return "전국", "전국", ""
    if sigungu_text:
        return f"{sido_text} {sigungu_text}", sido_text, sigungu_text
    return _split_region_text(sido_text)


def _infer_policy_domain(row: dict) -> str:
    text = _join_parts(
        row.get("category_main"),
        row.get("category_sub"),
        row.get("keyword"),
        row.get("policy_name"),
        row.get("search_text"),
    )
    if any(term in text for term in ["주거", "주택", "월세", "전세", "임대"]):
        return "policy_housing"
    if any(term in text for term in ["금융", "대출", "저축", "자산", "소득"]):
        return "policy_finance"
    if any(term in text for term in ["교육", "훈련", "강의", "학습", "장학"]):
        return "policy_training"
    if any(term in text for term in ["창업", "사업", "스타트업"]):
        return "policy_startup"
    if any(term in text for term in ["취업", "구직", "일자리", "면접", "채용"]):
        return "policy_job"
    return "policy"


def _insert_search_document(cursor, doc: dict):
    columns = [
        "doc_id",
        "source_table",
        "source_id",
        "domain",
        "title",
        "summary",
        "region_name",
        "region_sido",
        "region_sigungu",
        "target",
        "min_age",
        "max_age",
        "employment_status",
        "status",
        "apply_start_date",
        "apply_end_date",
        "url",
        "search_text",
        "raw_ref",
        "collected_at",
    ]
    placeholders = ", ".join(["?"] * len(columns))
    cursor.execute(
        f"INSERT OR REPLACE INTO search_documents ({', '.join(columns)}) VALUES ({placeholders})",
        [doc.get(column) for column in columns],
    )


def rebuild_search_documents():
    """
    여러 원본 테이블을 추천/임베딩용 공통 문서 테이블로 통합한다.
    원본 테이블은 유지하고 search_documents만 재생성한다.
    """
    print("\n[통합 검색 문서 생성 시작]")

    conn = get_connection()
    cursor = conn.cursor()
    _ensure_search_documents_table(cursor)
    cursor.execute("DELETE FROM search_documents")

    saved = 0

    if _table_exists(cursor, "policies_processed"):
        for row in cursor.execute("SELECT * FROM policies_processed").fetchall():
            item = dict(row)
            source_id = _clean(item.get("policy_id"))
            summary = _join_parts(item.get("description"), item.get("support_content"))
            region_name, region_sido, region_sigungu = convert_region_to_parts(item.get("region"))
            _insert_search_document(cursor, {
                "doc_id": f"policies_processed:{source_id}",
                "source_table": "policies_processed",
                "source_id": source_id,
                "domain": _infer_policy_domain(item),
                "title": item.get("policy_name"),
                "summary": summary,
                "region_name": region_name,
                "region_sido": region_sido,
                "region_sigungu": region_sigungu,
                "target": _join_parts(item.get("school_cd"), item.get("job_cd"), item.get("special_cd")),
                "min_age": item.get("min_age"),
                "max_age": item.get("max_age"),
                "employment_status": item.get("job_cd"),
                "status": item.get("school_cd"),
                "apply_start_date": item.get("biz_start_date"),
                "apply_end_date": item.get("biz_end_date"),
                "url": item.get("application_url") or item.get("ref_url1") or item.get("ref_url2"),
                "search_text": item.get("search_text") or _join_parts(item.get("policy_name"), summary),
                "raw_ref": source_id,
                "collected_at": item.get("last_mod_date"),
            })
            saved += 1

    if _table_exists(cursor, "welfare_central"):
        welfare_rows = cursor.execute(
            "SELECT * FROM welfare_central"
        ).fetchall()

        for row in welfare_rows:
            item = dict(row)

            source_id = _clean(item.get("service_id"))

            if not source_id:
                print("⚠️ service_id가 없는 welfare_central 행을 건너뜁니다.")
                continue

            summary = _join_parts(
                item.get("summary"),
                item.get("detail_summary"),
                item.get("support_content"),
            )

            target = _join_parts(
                item.get("life_cycle"),
                item.get("target_group"),
                item.get("target_detail"),
                item.get("selection_criteria"),
            )

            search_text = _clean(item.get("search_text"))

            if not search_text:
                search_text = _join_parts(
                    item.get("service_name"),
                    item.get("interest_theme"),
                    summary,
                    target,
                    item.get("application_method"),
                    item.get("ministry"),
                    item.get("department"),
                    item.get("responsible_agency"),
                )

            _insert_search_document(cursor, {
                "doc_id": f"welfare_central:{source_id}",
                "source_table": "welfare_central",
                "source_id": source_id,
                "domain": "welfare",
                "title": item.get("service_name"),
                "summary": summary,
                "region_name": "전국",
                "region_sido": "전국",
                "region_sigungu": "",
                "target": target,
                "min_age": None,
                "max_age": None,
                "employment_status": "",
                "status": item.get("life_cycle"),
                "apply_start_date": "",
                "apply_end_date": "",
                "url": (
                    item.get("service_url")
                    or item.get("homepage")
                    or ""
                ),
                "search_text": search_text,
                "raw_ref": source_id,
                "collected_at": item.get("imported_at"),
            })

            saved += 1

    if _table_exists(cursor, "hrd_trainings"):
        for row in cursor.execute("SELECT * FROM hrd_trainings").fetchall():
            item = dict(row)
            source_id = _clean(item.get("id") or item.get("trpr_id"))
            region_name, region_sido, region_sigungu = _split_region_text(item.get("address"))
            _insert_search_document(cursor, {
                "doc_id": f"hrd_trainings:{source_id}",
                "source_table": "hrd_trainings",
                "source_id": source_id,
                "domain": "training",
                "title": item.get("title"),
                "summary": _join_parts(item.get("sub_title"), item.get("train_target"), item.get("address")),
                "region_name": region_name,
                "region_sido": region_sido,
                "region_sigungu": region_sigungu,
                "target": item.get("train_target"),
                "employment_status": item.get("train_target"),
                "status": item.get("train_target"),
                "apply_start_date": item.get("tra_start_date"),
                "apply_end_date": item.get("tra_end_date"),
                "url": item.get("title_link"),
                "search_text": item.get("search_text") or _join_parts(item.get("title"), item.get("sub_title"), item.get("train_target"), item.get("address"), item.get("ncs_cd")),
                "raw_ref": item.get("trpr_id"),
                "collected_at": item.get("collected_at"),
            })
            saved += 1

    if _table_exists(cursor, "kstartup_notices"):
        for row in cursor.execute("SELECT * FROM kstartup_notices").fetchall():
            item = dict(row)
            source_id = _clean(item.get("pbanc_sn"))
            min_age, max_age = _parse_age_bounds(item.get("target_age"))
            region_name, region_sido, region_sigungu = _split_region_text(item.get("region") or "전국")
            _insert_search_document(cursor, {
                "doc_id": f"kstartup_notices:{source_id}",
                "source_table": "kstartup_notices",
                "source_id": source_id,
                "domain": "startup",
                "title": item.get("notice_name"),
                "summary": item.get("description"),
                "region_name": region_name,
                "region_sido": region_sido,
                "region_sigungu": region_sigungu,
                "target": _join_parts(item.get("target"), item.get("target_detail"), item.get("business_age"), item.get("target_age")),
                "min_age": min_age,
                "max_age": max_age,
                "employment_status": "창업",
                "status": item.get("target"),
                "apply_start_date": _date_yyyymmdd(item.get("apply_start_date")),
                "apply_end_date": _date_yyyymmdd(item.get("apply_end_date")),
                "url": item.get("apply_url") or item.get("detail_url"),
                "search_text": item.get("search_text") or _join_parts(item.get("notice_name"), item.get("category"), item.get("organization"), item.get("target"), item.get("description")),
                "raw_ref": source_id,
                "collected_at": item.get("collected_at"),
            })
            saved += 1

    if _table_exists(cursor, "smallloan_youth"):
        for row in cursor.execute("SELECT * FROM smallloan_youth").fetchall():
            item = dict(row)
            source_id = _clean(item.get("id") or item.get("snq"))
            min_age, max_age = _parse_age_bounds(item.get("age"))
            region_name, region_sido, region_sigungu = _split_region_text(
                item.get("rsdAreaPamtEqltIstm") or item.get("rsdArea") or "전국"
            )
            search_text = _join_parts(
                item.get("finPrdNm"), item.get("usge"), item.get("trgt"), item.get("suprTgtDtlCond"),
                item.get("age"), item.get("incm"), item.get("ofrInstNm"), item.get("irt"), item.get("lnLmt"),
                item.get("rsdAreaPamtEqltIstm"), item.get("tgtFltr"),
            )
            _insert_search_document(cursor, {
                "doc_id": f"smallloan_youth:{source_id}",
                "source_table": "smallloan_youth",
                "source_id": source_id,
                "domain": "loan",
                "title": item.get("finPrdNm"),
                "summary": _join_parts(item.get("lnLmt"), item.get("irt"), item.get("suprTgtDtlCond")),
                "region_name": region_name,
                "region_sido": region_sido,
                "region_sigungu": region_sigungu,
                "target": _join_parts(item.get("trgt"), item.get("tgtFltr"), item.get("suprTgtDtlCond")),
                "min_age": min_age,
                "max_age": max_age,
                "employment_status": item.get("trgt"),
                "status": item.get("trgt"),
                "apply_end_date": item.get("mgmDln"),
                "url": item.get("rltSite"),
                "search_text": search_text,
                "raw_ref": item.get("snq"),
                "collected_at": item.get("collected_at"),
            })
            saved += 1

    if _table_exists(cursor, "myhome_notices"):
        for row in cursor.execute("SELECT * FROM myhome_notices").fetchall():
            item = dict(row)
            source_id = _clean(item.get("id") or item.get("notice_id"))
            region_name, region_sido, region_sigungu = _split_region_text(item.get("region_name"))
            search_text = _join_parts(
                item.get("notice_name"), item.get("region_name"), item.get("house_name"),
                item.get("supply_type"), item.get("house_type"), item.get("deposit"),
                item.get("monthly_rent"), item.get("status"), item.get("youth_keyword"),
            )
            _insert_search_document(cursor, {
                "doc_id": f"myhome_notices:{source_id}",
                "source_table": "myhome_notices",
                "source_id": source_id,
                "domain": "housing_notice",
                "title": item.get("notice_name"),
                "summary": _join_parts(item.get("supply_inst"), item.get("house_type"), item.get("supply_type"), item.get("house_name")),
                "region_name": region_name,
                "region_sido": region_sido,
                "region_sigungu": region_sigungu,
                "target": item.get("youth_keyword"),
                "status": item.get("status"),
                "apply_start_date": _date_yyyymmdd(item.get("begin_date")),
                "apply_end_date": _date_yyyymmdd(item.get("end_date")),
                "url": item.get("detail_url") or item.get("myhome_url"),
                "search_text": search_text,
                "raw_ref": item.get("notice_id"),
                "collected_at": item.get("post_date"),
            })
            saved += 1

    if _table_exists(cursor, "rental_houses"):
        for row in cursor.execute("SELECT * FROM rental_houses").fetchall():
            item = dict(row)
            source_id = _clean(item.get("id") or item.get("hsmpSn"))
            region_name, region_sido, region_sigungu = _split_region_fields(item.get("brtcNm"), item.get("signguNm"))
            search_text = _join_parts(
                item.get("hsmpNm"), item.get("rnAdres"), region_name, item.get("suplyTyNm"),
                item.get("styleNm"), item.get("houseTyNm"), item.get("bassRentGtn"),
                item.get("bassMtRntchrg"), item.get("youth_filter_keyword"),
            )
            _insert_search_document(cursor, {
                "doc_id": f"rental_houses:{source_id}",
                "source_table": "rental_houses",
                "source_id": source_id,
                "domain": "rental_house",
                "title": item.get("hsmpNm"),
                "summary": _join_parts(item.get("insttNm"), item.get("suplyTyNm"), item.get("houseTyNm"), item.get("rnAdres")),
                "region_name": region_name,
                "region_sido": region_sido,
                "region_sigungu": region_sigungu,
                "target": item.get("youth_filter_keyword"),
                "status": item.get("suplyTyNm"),
                "url": "",
                "search_text": search_text,
                "raw_ref": item.get("hsmpSn"),
                "collected_at": item.get("competDe"),
            })
            saved += 1

    conn.commit()
    conn.close()
    print(f"  ✅ search_documents 테이블에 {saved}건 저장 완료")


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

        # 코드 컬럼 → 텍스트 변환
        for col_name, code_map in COLUMN_CODE_MAPS.items():
            row_dict[col_name] = convert_code(row_dict.get(col_name), code_map)

        # 변환된 텍스트로 search_text 생성
        row_dict[p["region_name"]] = convert_region_to_name(row_dict.get(p["region"]))
        row_dict[p["search_text"]] = make_search_text(row_dict)

        # policies_processed에 저장
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
    rebuild_search_documents()


# ── 직접 실행 시 ──────────────────────────────────────────────
if __name__ == "__main__":
    preprocess_policies()
