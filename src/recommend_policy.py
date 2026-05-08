import pandas as pd

from src.extract_user_condition import extract_user_condition
from src.filter_policy import filter_policies
from src.search_policy import search_top_policies
from src.generate_answer import generate_final_answer


def recommend_policy(user_input: str) -> str:
    user_condition = extract_user_condition(user_input)

    candidate_policies = filter_policies(user_condition)

    top5_policies = search_top_policies(
        user_input=user_input,
        candidate_policies=candidate_policies,
        top_k=5,
        search_k=50,
    )

    answer = generate_final_answer(
        user_input=user_input,
        user_condition=user_condition,
        top_policies=top5_policies,
    )

    return answer


def recommend_policy_with_debug(user_input: str):
    user_condition = extract_user_condition(user_input)
    candidate_policies = filter_policies(user_condition)

    top5_policies = search_top_policies(
        user_input=user_input,
        candidate_policies=candidate_policies,
        top_k=5,
        search_k=50,
    )

    answer = generate_final_answer(
        user_input=user_input,
        user_condition=user_condition,
        top_policies=top5_policies,
    )

    return {
        "user_condition": user_condition,
        "candidate_count": len(candidate_policies),
        "top5_policies": top5_policies,
        "answer": answer,
    }


if __name__ == "__main__":
    sample = "서울 사는 25살 취준생인데 월세 지원이나 취업 지원 정책이 궁금해요."
    print(recommend_policy(sample))