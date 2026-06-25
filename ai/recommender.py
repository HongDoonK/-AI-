from __future__ import annotations

import re

import pandas as pd

from ai.condition_extractor import extract_user_condition, has_condition_signal
from ai.db_loader import LgcvDataUnavailable, load_lgcv_df, load_policy_df
from ai.generator import generate_recommendations
from ai.retriever import retrieve_top_k

TARGET_RECOMMENDATION_COUNT = 5

try:
    from backend.region_map import REGION_CODE_MAP
except Exception:  # region_map은 추천 핵심 의존성이지만, 누락 시 충북 판별만 보수적으로 끈다.
    REGION_CODE_MAP = {}

NO_CONDITION_MESSAGE = (
    "조건이 부족하여 정책을 추천할 수 없습니다. "
    "나이, 성별, 시도/시군구, 재직 여부 또는 관심 분야를 입력해주세요."
)

# 충청북도 별칭과 시군구명. 사용자 조건에 이 중 하나라도 들어오면 충북으로 본다.
CHUNGBUK_ALIASES = ("충북", "충청북도")
CHUNGBUK_SIGUNGU = tuple(REGION_CODE_MAP.get("충북", {}).keys())


def _clean(value) -> str:
    return str(value or "").strip()


def _is_chungbuk_condition(condition: dict) -> bool:
    """region / region_sido / region_sigungu 텍스트로 충북 여부를 판별한다."""
    text = " ".join(
        _clean(condition.get(key))
        for key in ("region", "region_sido", "region_sigungu")
    )
    if not text:
        return False
    if any(alias in text for alias in CHUNGBUK_ALIASES):
        return True
    return any(sigungu and sigungu in text for sigungu in CHUNGBUK_SIGUNGU)


def _is_usable(top_policies: list, recommendations: list) -> bool:
    """lgcv 추천 결과를 그대로 쓸 수 있는지 판단한다."""
    if not top_policies:
        return False
    if not recommendations:
        return False
    if all(_clean(item.get("apply_possibility")) == "낮음" for item in recommendations):
        return False
    return True


def _has_meaningful_condition(condition: dict) -> bool:
    if not condition:
        return False

    meaningful_keys = [
        "age",
        "gender",
        "region",
        "region_sido",
        "region_sigungu",
        "interest",
        "employment_status",
        "income",
        "housing_status",
    ]
    if any(_clean(condition.get(key)) for key in meaningful_keys):
        return True

    # "청년"은 서비스의 기본 대상이라 개인화 조건으로 보지 않는다.
    status = _clean(condition.get("status"))
    return bool(status and status != "청년")


# Run from project root:
#   python -m backend.db
#   python -m backend.api_collector
#   python -m backend.preprocessing
#   uvicorn backend.main:app --reload
def recommend_policy(user_input: str) -> dict:
    if not has_condition_signal(user_input):
        return {
            "user_condition": {},
            "recommendations": [],
            "message": NO_CONDITION_MESSAGE,
        }

    user_condition = extract_user_condition(user_input)
    if not _has_meaningful_condition(user_condition):
        return {
            "user_condition": user_condition,
            "recommendations": [],
            "message": NO_CONDITION_MESSAGE,
        }

    # 충북 조건이면 충북 전용(lgcv) 데이터로 먼저 추천을 시도하고,
    # usable하지 않으면 기존 youth_policy.db 추천으로 fallback한다.
    if _is_chungbuk_condition(user_condition):
        # 충북 세부 지역(시군구)이 명시되면 "정확 지역 후보 k개 + 기존 검색 보충 5-k개"로
        # 조합한다. 광역(충북만)이면 기존 lgcv 우선 추천을 유지한다.
        if _clean(user_condition.get("region_sigungu")):
            return _recommend_chungbuk_sigungu(user_input, user_condition)
        lgcv_result = _recommend_from_lgcv(user_input, user_condition)
        if lgcv_result is not None:
            return lgcv_result
        fallback_reason = "lgcv 충북 지자체 복지서비스 후보가 없어 기존 통합 DB로 대체했습니다."
    else:
        fallback_reason = None

    df = load_policy_df()
    top_policies = retrieve_top_k(user_input, user_condition, df, top_k=5)
    recommendations = generate_recommendations(user_input, user_condition, top_policies)
    result = {
        "user_condition": user_condition,
        "recommendations": recommendations,
        "message": "",
        "recommendation_source": "default",
    }
    if fallback_reason:
        result["fallback_reason"] = fallback_reason
    return result


def _col_str(df: pd.DataFrame, column: str) -> pd.Series:
    """DataFrame 컬럼을 결측 없는 문자열 Series로 반환(없으면 빈 문자열)."""
    if column in df.columns:
        return df[column].fillna("").astype(str)
    return pd.Series([""] * len(df), index=df.index)


def _doc_id(item: dict) -> str:
    return _clean(item.get("doc_id") or item.get("policy_id") or item.get("source_id"))


def _combined_chungbuk_corpus() -> pd.DataFrame:
    """충북 세부지역 조합 추천용 코퍼스.

    충북 전용(lgcv) 데이터를 우선 배치하고(별도 lgcv 파일/통합 search_documents 모두 포함)
    그 위에 기존 통합 DB(load_policy_df)를 합친다. 동일 doc_id는 lgcv 쪽을 우선 보존한다.
    데이터가 일부 없어도(예: 통합 테이블 부재) 가능한 만큼만 합친다.
    """
    frames: list[pd.DataFrame] = []
    try:
        lgcv_df = load_lgcv_df()
    except (LgcvDataUnavailable, FileNotFoundError, ValueError, RuntimeError):
        lgcv_df = None
    if lgcv_df is not None and not lgcv_df.empty:
        frames.append(lgcv_df)
    try:
        frames.append(load_policy_df())
    except (FileNotFoundError, ValueError, RuntimeError):
        pass

    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True, sort=False)
    if "doc_id" in combined.columns:
        combined = combined.drop_duplicates(subset=["doc_id"], keep="first")
    return combined.reset_index(drop=True)


def _exact_sigungu_df(df: pd.DataFrame, sigungu: str) -> pd.DataFrame:
    """region_sigungu가 정확히 일치하거나 region_name에 시군구가 포함된 후보만 추린다."""
    exact = _col_str(df, "region_sigungu").str.strip().eq(sigungu)
    in_name = _col_str(df, "region_name").str.contains(re.escape(sigungu), na=False)
    return df[exact | in_name]


def _fill_pool_df(df: pd.DataFrame, sigungu: str) -> pd.DataFrame:
    """보충 후보 풀: source_table='lgcv'이면서 시군구가 요청 지역이 아닌 행을 제외한다.

    (충주시/제천시 등 다른 충북 시군 lgcv 후보 제외. 전국 후보는 그대로 둔다.)
    """
    is_lgcv = _col_str(df, "source_table").eq("lgcv")
    sig = _col_str(df, "region_sigungu").str.strip()
    mismatched_lgcv = is_lgcv & sig.ne(sigungu)
    return df[~mismatched_lgcv]


def _merge_unique(*lists: list[dict]) -> list[dict]:
    """여러 후보 리스트를 순서대로 합치고 doc_id 기준 중복을 제거한다."""
    merged: list[dict] = []
    seen: set[str] = set()
    for candidates in lists:
        for item in candidates:
            key = _doc_id(item)
            if key and key in seen:
                continue
            if key:
                seen.add(key)
            merged.append(item)
    return merged


def _recommend_chungbuk_sigungu(user_input: str, user_condition: dict) -> dict:
    """충북 세부 지역 추천: 정확 지역 후보 k개 + 기존 검색 보충 5-k개로 조합한다."""
    sigungu = _clean(user_condition.get("region_sigungu"))
    corpus = _combined_chungbuk_corpus()
    top_k = TARGET_RECOMMENDATION_COUNT

    local_top: list[dict] = []
    if not corpus.empty:
        local_df = _exact_sigungu_df(corpus, sigungu)
        if not local_df.empty:
            local_top = retrieve_top_k(user_input, user_condition, local_df, top_k=top_k)

    remaining = top_k - len(local_top)
    fill_top: list[dict] = []
    if remaining > 0 and not corpus.empty:
        fill_df = _fill_pool_df(corpus, sigungu)
        if not fill_df.empty:
            fill_top = retrieve_top_k(user_input, user_condition, fill_df, top_k=top_k)

    top_policies = _merge_unique(local_top, fill_top)[:top_k]
    recommendations = generate_recommendations(user_input, user_condition, top_policies)

    # 정확 지역(lgcv) 후보가 앞에 포함되면 lgcv, 아니면 전국/기존 검색 보충이므로 default.
    local_has_lgcv = any(str(item.get("source_table")) == "lgcv" for item in local_top)
    return {
        "user_condition": user_condition,
        "recommendations": recommendations,
        "message": "",
        "recommendation_source": "lgcv" if local_has_lgcv else "default",
    }


def _recommend_from_lgcv(user_input: str, user_condition: dict) -> dict | None:
    """충북 전용(lgcv) 데이터 기반 추천. usable하지 않으면 None을 반환해 fallback을 유도한다."""
    try:
        lgcv_df = load_lgcv_df()
    except LgcvDataUnavailable:
        return None
    if lgcv_df is None or lgcv_df.empty:
        return None

    top_policies = retrieve_top_k(user_input, user_condition, lgcv_df, top_k=5)
    recommendations = generate_recommendations(user_input, user_condition, top_policies)
    if not _is_usable(top_policies, recommendations):
        return None

    return {
        "user_condition": user_condition,
        "recommendations": recommendations,
        "message": "",
        "recommendation_source": "lgcv",
    }
