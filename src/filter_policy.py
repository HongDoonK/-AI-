import pandas as pd


POLICY_CSV = "youth_policy_clean.csv"

import pandas as pd


def debug_filter_steps(user_condition, policy_df):
    df = policy_df.copy()

    print("전체 정책 수:", len(df))
    print("사용자 조건:", user_condition)

    age = user_condition.get("age")
    region = user_condition.get("region")
    interests = user_condition.get("interests", [])

    # 1. 나이 조건 확인
    if "min_age" in df.columns and "max_age" in df.columns:
        df["min_age_num"] = pd.to_numeric(df["min_age"], errors="coerce")
        df["max_age_num"] = pd.to_numeric(df["max_age"], errors="coerce")

        print("min_age 결측 수:", df["min_age_num"].isna().sum())
        print("max_age 결측 수:", df["max_age_num"].isna().sum())

        if age is not None:
            age_mask = (
                ((df["min_age_num"].isna()) | (df["min_age_num"] <= age)) &
                ((df["max_age_num"].isna()) | (df["max_age_num"] >= age))
            )
            print("나이 필터 통과 수:", age_mask.sum())

    # 2. 관심분야 단어 포함 여부 확인
    if interests:
        for interest in interests:
            count = df["search_text"].fillna("").astype(str).str.contains(
                interest,
                case=False,
                na=False
            ).sum()
            print(f"'{interest}' 포함 정책 수:", count)

    # 3. 지역 단어 포함 여부 확인
    if region is not None:
        region_count = df["search_text"].fillna("").astype(str).str.contains(
            region,
            case=False,
            na=False
        ).sum()

        nationwide_count = df["search_text"].fillna("").astype(str).str.contains(
            "전국",
            case=False,
            na=False
        ).sum()

        print(f"'{region}' 포함 정책 수:", region_count)
        print("'전국' 포함 정책 수:", nationwide_count)


def normalize_region(region):
    if region is None:
        return None

    region = str(region)

    region_map = {
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
        "충청북도": "충북",
        "충청남도": "충남",
        "전라북도": "전북",
        "전라남도": "전남",
        "경상북도": "경북",
        "경상남도": "경남",
        "제주특별자치도": "제주",
    }

    return region_map.get(region, region)


def filter_policies(user_condition: dict, policy_df: pd.DataFrame) -> pd.DataFrame:
    """
    사용자 조건 기반 1차 필터링.
    너무 강하게 필터링하지 않고, 명확히 안 맞는 것만 제외한다.
    """

    df = policy_df.copy()

    age = user_condition.get("age")
    region = normalize_region(user_condition.get("region"))
    interests = user_condition.get("interests", [])

    # 1. 나이 필터링
    if age is not None:
        if "min_age" in df.columns and "max_age" in df.columns:
            df["min_age_num"] = pd.to_numeric(df["min_age"], errors="coerce")
            df["max_age_num"] = pd.to_numeric(df["max_age"], errors="coerce")

            df = df[
                ((df["min_age_num"].isna()) | (df["min_age_num"] <= age)) &
                ((df["max_age_num"].isna()) | (df["max_age_num"] >= age))
            ]

    # 2. 관심분야 필터링
    if interests:
        interest_pattern = "|".join(interests)

        target_cols = [
            col for col in [
                "category_large",
                "category_middle",
                "keyword",
                "description",
                "support_content",
                "search_text"
            ]
            if col in df.columns
        ]

        if target_cols:
            mask = False
            for col in target_cols:
                mask = mask | df[col].fillna("").astype(str).str.contains(
                    interest_pattern,
                    case=False,
                    na=False
                )
            df = df[mask]

    # 3. 지역 필터링
    # 현재 region_code가 실제 지역명인지 코드인지 데이터 확인이 필요하므로 search_text 기반으로 약하게 필터링
    if region is not None:
        if "search_text" in df.columns:
            region_mask = (
                df["search_text"].fillna("").astype(str).str.contains(region, na=False) |
                df["search_text"].fillna("").astype(str).str.contains("전국", na=False)
            )

            # 지역 필터링 결과가 너무 적으면 필터링하지 않음
            if region_mask.sum() >= 5:
                df = df[region_mask]

    return df.reset_index(drop=True)


# if __name__ == "__main__":
#     policy_df = pd.read_csv(POLICY_CSV)

#     user_condition = {
#         "age": 24,
#         "region": "서울",
#         "employment_status": None,
#         "interests": ["주거"],
#         "income": None,
#         "housing_status": "월세",
#         "unclear_conditions": ["income"]
#     }

#     filtered_df = filter_policies(user_condition, policy_df)

#     print("필터링 전:", len(policy_df))
#     print("필터링 후:", len(filtered_df))
#     print(filtered_df[["policy_name", "category_large", "category_middle"]].head())

if __name__ == "__main__":
    policy_df = pd.read_csv("youth_policy_clean.csv")

    user_condition = {
        "age": 24,
        "region": "서울",
        "employment_status": None,
        "interests": ["주거"],
        "income": None,
        "housing_status": "월세",
        "unclear_conditions": ["income", "employment_status"]
    }

    debug_filter_steps(user_condition, policy_df)