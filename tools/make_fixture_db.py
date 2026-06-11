"""테스트용 소형 fixture DB 생성 스크립트.

실제 79MB youth_policy.db 대신, 추천/검색 로직 테스트에 필요한
최소 스키마와 샘플 데이터만 담은 SQLite 파일을 만든다.

사용법:
    python -m tools.make_fixture_db [출력경로]

기본 출력 경로: tests/fixtures/fixture_youth_policy.db
"""
from __future__ import annotations

import os
import sqlite3
import sys

DEFAULT_OUTPUT = os.path.join("tests", "fixtures", "fixture_youth_policy.db")

SEARCH_DOCUMENTS_DDL = """
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
"""

CENTERS_DDL = """
CREATE TABLE IF NOT EXISTS centers (
    center_id      TEXT PRIMARY KEY,
    center_name    TEXT,
    center_tel     TEXT,
    center_addr    TEXT,
    center_daddr   TEXT,
    center_url     TEXT,
    center_ctpv_cd TEXT,
    center_ctpv_nm TEXT,
    center_sgg_cd  TEXT,
    center_sgg_nm  TEXT
)
"""

POLICIES_PROCESSED_MINI_DDL = """
CREATE TABLE IF NOT EXISTS policies_processed (
    policy_id    TEXT PRIMARY KEY,
    policy_name  TEXT,
    description  TEXT,
    support_content TEXT,
    apply_period TEXT,
    min_age      TEXT,
    max_age      TEXT,
    region       TEXT,
    region_name  TEXT,
    search_text  TEXT
)
"""

SAMPLE_DOCUMENTS = [
    # (doc_id, source_table, source_id, domain, title, summary, region_name,
    #  region_sido, region_sigungu, target, min_age, max_age,
    #  employment_status, status, apply_start, apply_end, url, search_text)
    ("policies_processed:P001", "policies_processed", "P001", "policy_housing",
     "청년 월세 지원", "서울 거주 청년에게 월세를 지원합니다", "서울",
     "서울", "", "무주택 청년", 19, 34, "", "", "", "",
     "https://example.com/p001", "청년 월세 지원 서울 주거 임대 무주택 보증금"),
    ("policies_processed:P002", "policies_processed", "P002", "policy_finance",
     "청년 자산형성 적금", "전국 청년 대상 자산형성 적금 상품", "전국",
     "전국", "", "근로 청년", 19, 34, "재직", "", "", "",
     "https://example.com/p002", "청년 자산형성 적금 저축 금융 목돈 전국"),
    ("policies_processed:P003", "policies_processed", "P003", "policy_job",
     "청년 취업 성공 패키지", "미취업 청년 취업 지원 프로그램", "경기",
     "경기", "수원시", "미취업 청년", 18, 39, "미취업", "", "", "",
     "https://example.com/p003", "청년 취업 성공 패키지 일자리 구직 경기 수원"),
    ("policies_processed:P004", "policies_processed", "P004", "policy_training",
     "청년 직무 교육", "직무 역량 강화 교육 과정", "서울",
     "서울", "관악구", "대학생/졸업생", 19, 29, "", "대학생", "", "",
     "https://example.com/p004", "청년 직무 교육 훈련 강의 학습 서울 관악"),
    ("policies_processed:P005", "policies_processed", "P005", "policy_startup",
     "청년 창업 지원금", "예비창업자 사업화 자금 지원", "부산",
     "부산", "", "예비창업자", 19, 39, "창업", "", "", "",
     "https://example.com/p005", "청년 창업 지원금 스타트업 사업화 부산"),
    ("policies_processed:P006", "policies_processed", "P006", "policy",
     "마감된 과거 정책", "이미 종료된 정책(필터링 대상)", "서울",
     "서울", "", "청년", 19, 34, "", "", "2024-01-01", "2024-12-31",
     "https://example.com/p006", "마감 종료 과거 정책 서울"),
    ("policies_processed:P007", "policies_processed", "P007", "policy_housing",
     "전세보증금 대출 이자 지원", "전국 청년 전세자금 이자 지원", "전국",
     "전국", "", "무주택 청년", 19, 39, "", "", "", "",
     "https://example.com/p007", "전세 보증금 대출 이자 지원 주거 전세자금 전국"),
    ("policies_processed:P008", "policies_processed", "P008", "policy_finance",
     "고연령 제외 테스트 정책", "40세 이상만 신청 가능(연령 필터 대상)", "전국",
     "전국", "", "중장년", 40, 64, "", "", "", "",
     "https://example.com/p008", "중장년 금융 지원 전국"),
]

SAMPLE_CENTERS = [
    ("C001", "서울청년센터 관악", "09:00-18:00", "서울 관악구", "", "https://example.com/c001",
     "11", "서울특별시", "11620", "관악구"),
    ("C002", "수원청년지원센터", "09:00-18:00", "경기 수원시", "", "https://example.com/c002",
     "41", "경기도", "41110", "수원시"),
]

SAMPLE_POLICIES_PROCESSED = [
    ("P001", "청년 월세 지원", "서울 거주 청년에게 월세를 지원합니다",
     "월 20만원 최대 12개월", "", "19", "34", "11000", "서울",
     "청년 월세 지원 서울 주거 임대 무주택 보증금"),
    ("P002", "청년 자산형성 적금", "전국 청년 대상 자산형성 적금 상품",
     "정부 매칭 적립", "", "19", "34", "", "전국",
     "청년 자산형성 적금 저축 금융 목돈 전국"),
]


def build_fixture_db(output_path: str = DEFAULT_OUTPUT) -> str:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    if os.path.exists(output_path):
        os.remove(output_path)

    conn = sqlite3.connect(output_path)
    cursor = conn.cursor()
    cursor.execute(SEARCH_DOCUMENTS_DDL)
    cursor.execute(CENTERS_DDL)
    cursor.execute(POLICIES_PROCESSED_MINI_DDL)

    for doc in SAMPLE_DOCUMENTS:
        cursor.execute(
            """
            INSERT INTO search_documents (
                doc_id, source_table, source_id, domain, title, summary,
                region_name, region_sido, region_sigungu, target,
                min_age, max_age, employment_status, status,
                apply_start_date, apply_end_date, url, search_text,
                raw_ref, collected_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, '', '')
            """,
            doc,
        )

    cursor.executemany(
        "INSERT INTO centers VALUES (?,?,?,?,?,?,?,?,?,?)",
        SAMPLE_CENTERS,
    )
    cursor.executemany(
        "INSERT INTO policies_processed VALUES (?,?,?,?,?,?,?,?,?,?)",
        SAMPLE_POLICIES_PROCESSED,
    )

    conn.commit()
    conn.close()
    print(f"fixture DB 생성 완료: {output_path} (search_documents {len(SAMPLE_DOCUMENTS)}건)")
    return output_path


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUTPUT
    build_fixture_db(target)
