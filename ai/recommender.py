from __future__ import annotations

from ai.condition_extractor import extract_user_condition, has_condition_signal
from ai.db_loader import load_policy_df
from ai.generator import generate_recommendations
from ai.retriever import retrieve_top_k

NO_CONDITION_MESSAGE = (
    "조건이 부족하여 정책을 추천할 수 없습니다. "
    "나이, 성별, 시도/시군구, 재직 여부 또는 관심 분야를 입력해주세요."
)


def _clean(value) -> str:
    return str(value or "").strip()


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

    df = load_policy_df()
    user_condition = extract_user_condition(user_input)
    if not _has_meaningful_condition(user_condition):
        return {
            "user_condition": user_condition,
            "recommendations": [],
            "message": NO_CONDITION_MESSAGE,
        }
    top_policies = retrieve_top_k(user_input, user_condition, df, top_k=5)
    recommendations = generate_recommendations(user_input, user_condition, top_policies)
    return {
        "user_condition": user_condition,
        "recommendations": recommendations,
        "message": "",
    }
