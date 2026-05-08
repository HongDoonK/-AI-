import json
from pathlib import Path
import pandas as pd


RAW_POLICY_PATH = Path("data/raw/청년정책 api.txt")
RAW_CENTER_PATH = Path("data/raw/청년센터 api.txt")

PROCESSED_POLICY_RAW_PATH = Path("data/processed/youth_policy_raw.csv")
PROCESSED_CENTER_RAW_PATH = Path("data/processed/youth_center_raw.csv")


def load_json_txt(file_path: str | Path) -> dict:
    """
    txt 파일 안의 JSON을 읽는다.
    파일 앞에 '청년정책', '센터' 같은 제목이 붙어 있어도
    첫 번째 { 부터 마지막 } 까지만 잘라 JSON으로 파싱한다.
    """
    file_path = Path(file_path)

    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    start_idx = text.find("{")
    end_idx = text.rfind("}")

    if start_idx == -1 or end_idx == -1:
        raise ValueError(f"{file_path} 안에서 JSON 구조를 찾지 못했습니다.")

    json_text = text[start_idx:end_idx + 1]

    return json.loads(json_text)


def json_to_dataframe(file_path: str | Path) -> pd.DataFrame:
    data = load_json_txt(file_path)

    if "result" not in data:
        raise KeyError("JSON 안에 result 키가 없습니다.")

    if "youthPolicyList" not in data["result"]:
        raise KeyError("JSON 안에 result['youthPolicyList'] 키가 없습니다.")

    items = data["result"]["youthPolicyList"]
    return pd.DataFrame(items)


def save_raw_csv():
    """
    raw txt 파일을 그대로 DataFrame으로 변환해 raw csv로 저장한다.
    """
    Path("data/processed").mkdir(parents=True, exist_ok=True)

    policy_df = json_to_dataframe(RAW_POLICY_PATH)
    center_df = json_to_dataframe(RAW_CENTER_PATH)

    policy_df.to_csv(PROCESSED_POLICY_RAW_PATH, index=False, encoding="utf-8-sig")
    center_df.to_csv(PROCESSED_CENTER_RAW_PATH, index=False, encoding="utf-8-sig")

    print("정책 raw CSV 저장 완료:", PROCESSED_POLICY_RAW_PATH)
    print("정책 개수:", len(policy_df))

    print("센터 raw CSV 저장 완료:", PROCESSED_CENTER_RAW_PATH)
    print("센터 개수:", len(center_df))


if __name__ == "__main__":
    save_raw_csv()