import json
import os
import re


REGION_KEYWORDS = [
    "서울", "부산", "대구", "인천", "광주", "대전", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
    "노원", "성북", "천안", "충주", "부천", "청양", "계룡", "경산", "영광", "김해"
]

INTEREST_KEYWORDS = {
    "일자리": ["취업", "구직", "취준", "인턴", "일자리", "채용", "직무"],
    "창업": ["창업", "스타트업", "사업", "입주", "창업지원"],
    "주거": ["주거", "월세", "전세", "집", "주택", "임대", "자취"],
    "교육": ["교육", "강의", "훈련", "자격증", "역량", "SW", "소프트웨어"],
    "복지문화금융": ["복지", "문화", "예술", "금융", "대출", "저축", "지원금"],
    "참여기반": ["상담", "센터", "커뮤니티", "활동", "서포터즈", "참여"],
}

EMPLOYMENT_KEYWORDS = {
    "취업준비": ["취준", "취업준비", "구직", "구직자", "미취업"],
    "재직": ["재직", "직장인", "근무", "회사원"],
    "창업자": ["창업자", "사업자", "대표", "스타트업"],
    "학생": ["대학생", "학생", "재학", "휴학생"],
}


def extract_age(user_input: str):
    patterns = [
        r"(\d{1,2})\s*살",
        r"만\s*(\d{1,2})\s*세",
        r"(\d{1,2})\s*세",
    ]

    for pattern in patterns:
        match = re.search(pattern, user_input)
        if match:
            return int(match.group(1))

    return None


def extract_region(user_input: str):
    for region in REGION_KEYWORDS:
        if region in user_input:
            return region
    return None


def extract_interests(user_input: str):
    interests = []

    for category, keywords in INTEREST_KEYWORDS.items():
        if any(keyword.lower() in user_input.lower() for keyword in keywords):
            interests.append(category)

    return list(set(interests))


def extract_employment_status(user_input: str):
    for status, keywords in EMPLOYMENT_KEYWORDS.items():
        if any(keyword in user_input for keyword in keywords):
            return status
    return None


def extract_housing_status(user_input: str):
    if "월세" in user_input:
        return "월세"
    if "전세" in user_input:
        return "전세"
    if "자취" in user_input:
        return "자취"
    if "1인가구" in user_input or "1인 가구" in user_input:
        return "1인가구"
    return None


def extract_income(user_input: str):
    match = re.search(r"소득\s*(\d+)\s*만?원", user_input)
    if match:
        return int(match.group(1))
    return None


def rule_based_extract(user_input: str) -> dict:
    age = extract_age(user_input)
    region = extract_region(user_input)
    interests = extract_interests(user_input)
    employment_status = extract_employment_status(user_input)
    housing_status = extract_housing_status(user_input)
    income = extract_income(user_input)

    unclear_conditions = []

    if age is None:
        unclear_conditions.append("age")
    if region is None:
        unclear_conditions.append("region")
    if income is None:
        unclear_conditions.append("income")
    if not interests:
        unclear_conditions.append("interests")

    return {
        "age": age,
        "region": region,
        "employment_status": employment_status,
        "interests": interests,
        "income": income,
        "housing_status": housing_status,
        "keywords": user_input.split(),
        "unclear_conditions": unclear_conditions,
    }


def llm_extract(user_input: str) -> dict | None:
    """
    OPENAI_API_KEY가 있으면 LLM으로 조건 추출.
    없거나 실패하면 None 반환.
    """
    if not os.getenv("OPENAI_API_KEY"):
        return None

    try:
        from openai import OpenAI

        client = OpenAI()
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

        system_prompt = """
너는 청년정책 추천 시스템의 사용자 조건 추출기다.
사용자 문장에서 나이, 지역, 취업상태, 관심분야, 소득, 주거상태를 JSON으로 추출한다.
모르는 값은 null로 둔다.
관심분야는 다음 중에서만 고른다:
일자리, 창업, 주거, 교육, 복지문화금융, 참여기반.
반드시 JSON만 출력한다.
"""

        user_prompt = f"""
사용자 입력:
{user_input}

출력 형식:
{{
  "age": null,
  "region": null,
  "employment_status": null,
  "interests": [],
  "income": null,
  "housing_status": null,
  "keywords": [],
  "unclear_conditions": []
}}
"""

        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
        )

        content = response.choices[0].message.content.strip()

        if content.startswith("```"):
            content = content.replace("```json", "").replace("```", "").strip()

        return json.loads(content)

    except Exception as e:
        print("LLM 조건 추출 실패, 규칙 기반으로 대체합니다.")
        print("오류:", e)
        return None


def extract_user_condition(user_input: str) -> dict:
    result = llm_extract(user_input)

    if result is not None:
        return result

    return rule_based_extract(user_input)


if __name__ == "__main__":
    sample = "서울 사는 25살 취준생인데 월세 지원이나 취업 지원 정책이 궁금해요."
    print(extract_user_condition(sample))