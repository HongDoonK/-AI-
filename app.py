from src.recommend_policy import recommend_policy_with_debug


def main():
    print("청년정책 추천 시스템")
    print("-" * 50)

    user_input = input("어떤 청년정책이 궁금한가요? ")

    result = recommend_policy_with_debug(user_input)

    print("\n[추출된 사용자 조건]")
    print(result["user_condition"])

    print("\n[1차 후보 정책 개수]")
    print(result["candidate_count"])

    print("\n[Top 5 정책]")
    top5 = result["top5_policies"]

    show_cols = [
        "policy_name",
        "keyword",
        "category_large",
        "category_middle",
        "support_content",
        "apply_period",
        "score",
    ]

    available_cols = [col for col in show_cols if col in top5.columns]
    print(top5[available_cols])

    print("\n[최종 추천 안내문]")
    print(result["answer"])


if __name__ == "__main__":
    main()