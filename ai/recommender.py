from __future__ import annotations

from ai.condition_extractor import extract_user_condition, has_condition_signal
from ai.db_loader import LgcvDataUnavailable, load_lgcv_df, load_policy_df
from ai.generator import generate_recommendations
from ai.retriever import retrieve_top_k

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
CHUNGBUK_SIGUNGU = tuple(REGION_CODE_MAP.get("충북", {}).keys()) + ("청주시",)


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
