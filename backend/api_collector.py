# api_collector.py
# ──────────────────────────────────────────────────────────────
# API 호출 및 DB 저장 (원본 데이터)
<<<<<<< HEAD
# 전처리는 preprocessing.py에서 따로 처리합니다.
=======
# 전처리는 preprocessing.py에서 따로 처리
>>>>>>> 434c1d83d10b76786e7035fb7352f5b5089ab794
# ──────────────────────────────────────────────────────────────

import os
import requests
from dotenv import load_dotenv
from backend.db import get_connection, create_tables
from backend.config import (
    POLICY_API_FIELD_MAP, CENTER_API_FIELD_MAP,
    POLICY_COLUMNS, CENTER_COLUMNS,
)

load_dotenv()

POLICY_API_KEY = os.getenv("YOUTH_POLICY_API_KEY", "")
CENTER_API_KEY = os.getenv("YOUTH_CENTER_API_KEY", "")

POLICY_API_URL = "https://www.youthcenter.go.kr/go/ythip/getPlcy"
CENTER_API_URL = "https://www.youthcenter.go.kr/go/ythip/getSpace"

# 무한루프 방지 (최대 페이지 수)
MAX_PAGES = 100


# ── 빈 값 처리 ────────────────────────────────────────────────
def clean_value(value):
    """빈 문자열, 공백은 None으로 변환"""
    if value is None:
        return None
    if str(value).strip() == "":
        return None
    return value


# ── API 데이터 번역 ───────────────────────────────────────────
def translate_row(item: dict, field_map: dict) -> dict:
    """
    API 응답 한 건을 field_map 기준으로 DB 컬럼명으로 번역
    field_map에 없는 필드는 무시, 빈 값은 None 처리
    """
    row = {}
    for api_field, db_col in field_map.items():
        value = item.get(api_field)
        row[db_col] = clean_value(value)
    return row


# ── API 페이지 수집 (공통 함수) ───────────────────────────────
def fetch_all_pages(url: str, api_key: str, list_key: str, label: str) -> list:
    """
    페이지를 순회하면서 모든 데이터 수집
    list_key : 응답 JSON에서 데이터 리스트가 들어있는 키 이름
    label    : 로그 출력용 라벨 (정책 / 센터)
    """
    all_items = []
    page_num  = 1
    page_size = 100

    while page_num <= MAX_PAGES:
        params = {
            "apiKeyNm": api_key,
            "pageNum":  page_num,
            "pageSize": page_size,
            "rtnType":  "json",
        }
        try:
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            print(f"  ❌ API 호출 오류 (page {page_num}): {e}")
            break

        items = data.get("result", {}).get(list_key, [])
        if not items:
            break

        all_items.extend(items)
        tot_count = data.get("result", {}).get("pagging", {}).get("totCount", 0)
        print(f"  [{label}] 페이지 {page_num} 수집 완료 ({len(all_items)}/{tot_count}건)")

        if len(all_items) >= tot_count:
            break
        page_num += 1
    else:
        print(f"  ⚠️  최대 페이지({MAX_PAGES})에 도달하여 중단합니다.")

    print(f"  [{label}] 총 {len(all_items)}건 수집 완료")
    return all_items


# ── 정책 데이터 수집 및 저장 ──────────────────────────────────
def collect_policies():
    """청년정책 API 전체 호출 후 DB 저장 (원본 그대로)"""
    print("\n[정책 데이터 수집 시작]")

    if not POLICY_API_KEY:
        print("  ❌ YOUTH_POLICY_API_KEY가 .env에 없습니다.")
        return

    items = fetch_all_pages(
        url=POLICY_API_URL,
        api_key=POLICY_API_KEY,
        list_key="youthPolicyList",
        label="정책",
    )
    _save_policies(items)


def _save_policies(items: list):
    """번역된 정책 데이터를 DB에 저장 (원본 그대로 저장, 전처리는 preprocessing.py)"""
    if not items:
        print("  ⚠️  저장할 데이터가 없습니다.")
        return

    p    = POLICY_COLUMNS
    conn = get_connection()
    cursor = conn.cursor()

    cols             = list(p.values())
    col_names        = ", ".join(cols)
    col_placeholders = ", ".join(["?"] * len(cols))

    saved = 0
    for item in items:
        row = translate_row(item, POLICY_API_FIELD_MAP)
        # search_text는 preprocessing.py에서 채워집니다
        values = [row.get(col) for col in cols]
        cursor.execute(
            f"INSERT OR REPLACE INTO policies ({col_names}) VALUES ({col_placeholders})",
            values
        )
        saved += 1

    conn.commit()
    conn.close()
    print(f"  ✅ policies 테이블에 {saved}건 저장 완료 (전처리 전)")


# ── 청년센터 데이터 수집 및 저장 ─────────────────────────────
def collect_centers():
    """청년센터 API 전체 호출 후 DB 저장"""
    print("\n[청년센터 데이터 수집 시작]")

    if not CENTER_API_KEY:
        print("  ❌ YOUTH_CENTER_API_KEY가 .env에 없습니다.")
        return

    # 센터 API도 응답에서 youthPolicyList 키 사용
    items = fetch_all_pages(
        url=CENTER_API_URL,
        api_key=CENTER_API_KEY,
        list_key="youthPolicyList",
        label="센터",
    )
    _save_centers(items)


def _save_centers(items: list):
    """번역된 센터 데이터를 DB에 저장"""
    if not items:
        print("  ⚠️  저장할 데이터가 없습니다.")
        return

    c    = CENTER_COLUMNS
    conn = get_connection()
    cursor = conn.cursor()

    cols             = list(c.values())
    col_names        = ", ".join(cols)
    col_placeholders = ", ".join(["?"] * len(cols))

    saved = 0
    for item in items:
        row    = translate_row(item, CENTER_API_FIELD_MAP)
        values = [row.get(col) for col in cols]

        cursor.execute(
            f"INSERT OR REPLACE INTO centers ({col_names}) VALUES ({col_placeholders})",
            values
        )
        saved += 1

    conn.commit()
    conn.close()
    print(f"  ✅ centers 테이블에 {saved}건 저장 완료")


# ── 직접 실행 시 ──────────────────────────────────────────────
if __name__ == "__main__":
    create_tables()
    collect_policies()
    collect_centers()