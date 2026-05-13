# mock_ai.py
# ──────────────────────────────────────────────────────────────
# AI 모듈(ai/recommender.py)이 완성되기 전까지 사용할 가짜 함수.
# 실제 AI 모듈과 동일한 입출력 구조를 가진다.
# 6단계에서 실제 AI 모듈로 교체된다.
# ──────────────────────────────────────────────────────────────


def recommend_policy(user_input: str) -> dict:
    """
    실제 AI 모듈을 흉내내는 가짜 함수.
    어떤 입력이 들어와도 항상 동일한 더미 데이터를 반환한다.
    """
    print(f"[mock_ai] 받은 입력: {user_input}")

    return {
        "user_condition": {
            "age":               24,
            "region":            "서울",
            "status":            "대학생",
            "interest":          "주거",
            "employment_status": None,
            "income":            None,
            "housing_status":    None,
        },
        "recommendations": [
            {
                "policy_name":        "청년 월세 한시 특별지원 (mock)",
                "apply_possibility":  "높음",
                "reason":             "서울 거주 24세 대학생으로 주거 지원 조건에 해당합니다.",
                "support_content":    "월 최대 20만원, 최대 12개월 지원",
                "application_period": "2024.03.01 ~ 2024.12.31",
                "application_url":    "https://www.bokjiro.go.kr/",
                "checklist": [
                    "주민등록등본 준비",
                    "복지로 계정 생성",
                    "온라인 신청서 작성",
                ],
            },
            {
                "policy_name":        "서울시 청년 임차보증금 지원 (mock)",
                "apply_possibility":  "확인 필요",
                "reason":             "서울 거주 청년 대상이나 소득 조건 확인이 필요합니다.",
                "support_content":    "임차보증금 최대 7천만원 무이자 지원",
                "application_period": "2024.04.01 ~ 2024.06.30",
                "application_url":    "https://youth.seoul.go.kr/",
                "checklist": [
                    "소득 증빙 서류 준비",
                    "임대차 계약서 사본 준비",
                ],
            },
        ],
    }