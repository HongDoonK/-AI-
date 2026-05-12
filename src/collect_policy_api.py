import requests
import json
import time


BASE_URL = "여기에_청년정책_API_URL_입력"
API_KEY = "여기에_API_KEY_입력"

OUTPUT_FILE = "청년정책_api_all.json"


def collect_all_policies():
    all_policies = []

    page_num = 1
    page_size = 100

    total_count = None

    while True:
        params = {
            "apiKeyNm": API_KEY,
            "pageNum": page_num,
            "pageSize": page_size,
        }

        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()

        data = response.json()

        if total_count is None:
            total_count = data["result"]["pagging"]["totCount"]
            print("전체 정책 수:", total_count)

        policy_list = data["result"]["youthPolicyList"]

        if not policy_list:
            break

        all_policies.extend(policy_list)

        print(f"{page_num}페이지 수집 완료 / 누적 {len(all_policies)}개")

        if len(all_policies) >= total_count:
            break

        page_num += 1
        time.sleep(0.2)

    result = {
        "resultCode": 200,
        "resultMessage": "전체 페이지 수집 완료",
        "result": {
            "pagging": {
                "totCount": len(all_policies),
                "pageNum": 1,
                "pageSize": len(all_policies)
            },
            "youthPolicyList": all_policies
        }
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print("저장 완료:", OUTPUT_FILE)
    print("최종 수집 정책 수:", len(all_policies))


if __name__ == "__main__":
    collect_all_policies()