import json
import pandas as pd


POLICY_FILE = "청년정책 api.txt"
CENTER_FILE = "청년센터 api.txt"


def load_json_txt(file_name):
    """
    txt 파일 안의 JSON을 읽는 함수.
    파일 앞에 제목이나 설명 문장이 있어도 첫 번째 {부터 JSON으로 파싱한다.
    """
    with open(file_name, "r", encoding="utf-8") as f:
        text = f.read()

    start_idx = text.find("{")

    if start_idx == -1:
        raise ValueError(f"{file_name} 안에서 JSON 시작 문자 '{{'를 찾지 못했습니다.")

    json_text = text[start_idx:]

    return json.loads(json_text)


# 1. 청년정책 API txt → CSV
policy_data = load_json_txt(POLICY_FILE)

policy_list = policy_data["result"]["youthPolicyList"]
policy_df = pd.DataFrame(policy_list)

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
    "sprtTrgtMinAge": "min_age",
    "sprtTrgtMaxAge": "max_age",
    "earnCndSeCd": "income_code",
    "earnEtcCn": "income_condition",
    "addAplyQlfcCndCn": "extra_condition",
    "ptcpPrpTrgtCn": "target_condition",
    "zipCd": "region_code",
}

available_policy_columns = [
    col for col in policy_columns.keys()
    if col in policy_df.columns
]

policy_df = policy_df[available_policy_columns].rename(columns=policy_columns)

policy_df = policy_df.fillna("")

if "policy_id" in policy_df.columns:
    policy_df = policy_df.drop_duplicates(subset=["policy_id"])
else:
    policy_df = policy_df.drop_duplicates()

search_cols = [
    "policy_name",
    "keyword",
    "description",
    "category_large",
    "category_middle",
    "support_content",
    "extra_condition",
    "target_condition",
]

for col in search_cols:
    if col not in policy_df.columns:
        policy_df[col] = ""

policy_df["search_text"] = (
    policy_df["policy_name"].astype(str) + " " +
    policy_df["keyword"].astype(str) + " " +
    policy_df["description"].astype(str) + " " +
    policy_df["category_large"].astype(str) + " " +
    policy_df["category_middle"].astype(str) + " " +
    policy_df["support_content"].astype(str) + " " +
    policy_df["extra_condition"].astype(str) + " " +
    policy_df["target_condition"].astype(str)
)

policy_df.to_csv("youth_policy_clean.csv", index=False, encoding="utf-8-sig")

print("youth_policy_clean.csv 생성 완료")
print("정책 개수:", len(policy_df))
print(policy_df.head())


# 2. 청년센터 API txt → CSV
center_data = load_json_txt(CENTER_FILE)

center_list = center_data["result"]["youthPolicyList"]
center_df = pd.DataFrame(center_list)

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

available_center_columns = [
    col for col in center_columns.keys()
    if col in center_df.columns
]

center_df = center_df[available_center_columns].rename(columns=center_columns)

center_df = center_df.fillna("")

if "center_id" in center_df.columns:
    center_df = center_df.drop_duplicates(subset=["center_id"])
else:
    center_df = center_df.drop_duplicates()

center_df.to_csv("youth_center_clean.csv", index=False, encoding="utf-8-sig")

print("youth_center_clean.csv 생성 완료")
print("센터 개수:", len(center_df))
print(center_df.head())