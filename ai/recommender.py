from __future__ import annotations

from ai.condition_extractor import extract_user_condition
from ai.db_loader import load_policy_df
from ai.generator import generate_recommendations
from ai.retriever import retrieve_top_k


# Run from project root:
#   python -m backend.db
#   python -m backend.api_collector
#   python -m backend.preprocessing
#   uvicorn backend.main:app --reload
def recommend_policy(user_input: str) -> dict:
    df = load_policy_df()
    user_condition = extract_user_condition(user_input)
    top_policies = retrieve_top_k(user_input, user_condition, df, top_k=5)
    recommendations = generate_recommendations(user_input, user_condition, top_policies)
    return {
        "user_condition": user_condition,
        "recommendations": recommendations,
    }
