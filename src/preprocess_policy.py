from pathlib import Path
import pandas as pd

from src.load_json import json_to_dataframe


RAW_POLICY_PATH = Path("data/raw/청년정책 api.txt")
RAW_CENTER_PATH = Path("data/raw/청년센터 api.txt")

POLICY_CLEAN_PATH = Path("data/processed/youth_policy_clean.csv")
CENTER_CLEAN_PATH = Path("data/processed/youth_center_clean.csv")


def safe_select_and_rename(df: pd.DataFrame, column_map: dict) -> pd.DataFrame:
    available_columns = [col for col in column_map.keys() if col in df.columns]
    return df[available_columns].rename(columns=column_map)


def clean_text(value) -> str:
    if pd.isna(value):
        return ""
    return str(value).replace("\r", " ").replace("\n", " ").strip()


def normalize_region_name(text: str) -> str:
    text = clean_text(text)

    replacements = {
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
        "전북특별자치도": "전북",
        "전라북도": "전북",
        "전라남도": "전남",
        "경상북도": "경북",
        "경상남도": "경남",
        "제주특별자치도": "제주",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def normalize_category(text: str) -> str:
    text = clean_text(text)

    if any(word in text for word in ["일자리", "취업", "창업", "인턴"]):
        return "일자리"
    if any(word in text for word in ["주거", "주택", "거주"]):
        return "주거"
    if any(word in text for word in ["교육", "직업훈련", "역량"]):
        return "교육"
    if any(word in text for word in ["복지", "문화", "금융", "예술"]):
        return "복지문화금융"
    if any(word in text for word in ["참여", "기반", "상담", "센터"]):
        return "참여기반"

    return text if text else "기타"


def to_int_or_zero(value) -> int:
    try:
        if pd.isna(value):
            return 0
        value = str(value).strip()
        if value == "":
            return 0
        return int(float(value))
    except Exception:
        return 0


def preprocess_policy():
    policy_df = json_to_dataframe(RAW_POLICY_PATH)

    policy_columns = {
        "plcyNo": "policy_id",
        "plcyNm": "policy_name",
        "plcyKywdNm": "keyword",
        "plcyExplnCn": "description",
        "lclsfNm": "category_large",
        "mclsfNm": "category_middle",
        "plcySprtCn": "support_content",
        "plcyAplyMthdCn": "apply_method",
        "aplyUrlAddr": "apply_url",
        "refUrlAddr1": "reference_url",
        "aplyYmd": "apply_period",
        "bizPrdBgngYmd": "business_start_date",
        "bizPrdEndYmd": "business_end_date",
        "bizPrdEtcCn": "business_period_text",
        "sprtTrgtMinAge": "min_age",
        "sprtTrgtMaxAge": "max_age",
        "earnCndSeCd": "income_code",
        "earnEtcCn": "income_condition",
        "addAplyQlfcCndCn": "extra_condition",
        "ptcpPrpTrgtCn": "target_condition",
        "zipCd": "region_code",
        "operInstCdNm": "operation_org",
        "sprvsnInstCdNm": "supervision_org",
        "sbmsnDcmntCn": "submit_documents",
        "srngMthdCn": "screening_method",
    }

    policy_df = safe_select_and_rename(policy_df, policy_columns)
    policy_df = policy_df.fillna("")

    for col in policy_df.columns:
        policy_df[col] = policy_df[col].apply(clean_text)

    if "policy_id" in policy_df.columns:
        policy_df = policy_df.drop_duplicates(subset=["policy_id"])
    else:
        policy_df = policy_df.drop_duplicates()

    if "min_age" in policy_df.columns:
        policy_df["min_age"] = policy_df["min_age"].apply(to_int_or_zero)
    else:
        policy_df["min_age"] = 0

    if "max_age" in policy_df.columns:
        policy_df["max_age"] = policy_df["max_age"].apply(to_int_or_zero)
    else:
        policy_df["max_age"] = 0

    if "category_large" not in policy_df.columns:
        policy_df["category_large"] = ""

    if "category_middle" not in policy_df.columns:
        policy_df["category_middle"] = ""

    policy_df["category_normalized"] = (
        policy_df["category_large"] + " " + policy_df["category_middle"]
    ).apply(normalize_category)

    search_cols = [
        "policy_name",
        "keyword",
        "description",
        "category_large",
        "category_middle",
        "category_normalized",
        "support_content",
        "apply_method",
        "income_condition",
        "extra_condition",
        "target_condition",
        "operation_org",
        "supervision_org",
    ]

    for col in search_cols:
        if col not in policy_df.columns:
            policy_df[col] = ""

    policy_df["search_text"] = policy_df[search_cols].agg(" ".join, axis=1)

    POLICY_CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    policy_df.to_csv(POLICY_CLEAN_PATH, index=False, encoding="utf-8-sig")

    print("youth_policy_clean.csv 생성 완료")
    print("저장 경로:", POLICY_CLEAN_PATH)
    print("정책 개수:", len(policy_df))

    return policy_df


def preprocess_center():
    center_df = json_to_dataframe(RAW_CENTER_PATH)

    center_columns = {
        "cntrSn": "center_id",
        "cntrNm": "center_name",
        "cntrAddr": "address",
        "cntrDaddr": "detail_address",
        "cntrTelno": "phone",
        "cntrUrlAddr": "homepage",
        "stdgCtpvCdNm": "province",
        "stdgSggCdNm": "city",
    }

    center_df = safe_select_and_rename(center_df, center_columns)
    center_df = center_df.fillna("")

    for col in center_df.columns:
        center_df[col] = center_df[col].apply(clean_text)

    if "center_id" in center_df.columns:
        center_df = center_df.drop_duplicates(subset=["center_id"])
    else:
        center_df = center_df.drop_duplicates()

    if "province" in center_df.columns:
        center_df["province_normalized"] = center_df["province"].apply(normalize_region_name)
    else:
        center_df["province_normalized"] = ""

    CENTER_CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    center_df.to_csv(CENTER_CLEAN_PATH, index=False, encoding="utf-8-sig")

    print("youth_center_clean.csv 생성 완료")
    print("저장 경로:", CENTER_CLEAN_PATH)
    print("센터 개수:", len(center_df))

    return center_df


if __name__ == "__main__":
    preprocess_policy()
    preprocess_center()