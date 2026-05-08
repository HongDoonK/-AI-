from pathlib import Path
import pandas as pd


POLICY_CSV_PATH = Path("data/processed/youth_policy_clean.csv")


def load_policy_df(path: str | Path = POLICY_CSV_PATH) -> pd.DataFrame:
    return pd.read_csv(path).fillna("")


def age_filter(df: pd.DataFrame, age):
    if age is None:
        return df

    if "min_age" not in df.columns or "max_age" not in df.columns:
        return df

    filtered_rows = []

    for _, row in df.iterrows():
        min_age = int(row.get("min_age", 0) or 0)
        max_age = int(row.get("max_age", 0) or 0)

        # 0은 제한 없음으로 처리
        min_ok = True if min_age == 0 else age >= min_age
        max_ok = True if max_age == 0 else age <= max_age

        if min_ok and max_ok:
            filtered_rows.append(row)

    if not filtered_rows:
        return df

    return pd.DataFrame(filtered_rows)


def interest_filter(df: pd.DataFrame, interests: list):
    if not interests:
        return df

    if "category_normalized" not in df.columns and "search_text" not in df.columns:
        return df

    pattern = "|".join(interests)

    mask = pd.Series([False] * len(df), index=df.index)

    if "category_normalized" in df.columns:
        mask = mask | df["category_normalized"].astype(str).str.contains(pattern, case=False, na=False)

    if "search_text" in df.columns:
        mask = mask | df["search_text"].astype(str).str.contains(pattern, case=False, na=False)

    result = df[mask]

    # 너무 많이 제외되면 원본 유지
    if len(result) == 0:
        return df

    return result


def keyword_filter(df: pd.DataFrame, keywords: list):
    if not keywords or "search_text" not in df.columns:
        return df

    meaningful_keywords = [
        kw for kw in keywords
        if len(str(kw)) >= 2 and kw not in ["사는", "인데", "정책", "지원", "궁금해요"]
    ]

    if not meaningful_keywords:
        return df

    pattern = "|".join(meaningful_keywords)
    result = df[df["search_text"].astype(str).str.contains(pattern, case=False, na=False)]

    if len(result) == 0:
        return df

    return result


def filter_policies(user_condition: dict, policy_df: pd.DataFrame | None = None) -> pd.DataFrame:
    if policy_df is None:
        policy_df = load_policy_df()

    df = policy_df.copy()

    age = user_condition.get("age")
    interests = user_condition.get("interests", [])
    keywords = user_condition.get("keywords", [])

    df = age_filter(df, age)
    df = interest_filter(df, interests)
    df = keyword_filter(df, keywords)

    # 후보가 너무 적으면 원본에서 검색하도록 복구
    if len(df) < 5:
        return policy_df.copy()

    return df


if __name__ == "__main__":
    sample_condition = {
        "age": 25,
        "region": "서울",
        "interests": ["주거", "일자리"],
        "keywords": ["서울", "25살", "취준생", "월세", "취업"],
    }

    result = filter_policies(sample_condition)
    print(result[["policy_name", "category_normalized"]].head())
    print("후보 개수:", len(result))