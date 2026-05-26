from __future__ import annotations

import re

from ai.llm_client import LLMUnavailable, create_structured_output


REGIONS = [
    "서울", "경기", "인천", "부산", "대구", "광주", "대전", "울산", "세종",
    "강원", "충북", "충청북도", "충남", "충청남도", "전북", "전라북도",
    "전남", "전라남도", "경북", "경상북도", "경남", "경상남도", "제주",
]

# "창업" alone is an interest, not an employment status. Treat only explicit
# founder/business-owner phrases as employment status.
EMPLOYMENT_KEYWORDS = {
    "미취업": ["미취업", "취준", "취업준비", "구직", "실업", "무직"],
    "재직": ["재직", "직장인", "근로자", "회사원", "일하고"],
    "창업": ["창업자", "예비창업자", "사업자", "자영업"],
}

STATUS_KEYWORDS = {
    "대학생": ["대학생", "재학생", "휴학생", "졸업예정"],
    "졸업생": ["졸업생", "졸업자"],
    "청년": ["청년"],
    "군인": ["군인"],
    "프리랜서": ["프리랜서"],
}

INTEREST_KEYWORDS = {
    "주거": ["월세", "전세", "주거", "임대", "보증금", "집", "기숙사", "무주택"],
    "취업": ["취업", "구직", "면접", "일자리", "채용", "자격증"],
    "창업": ["창업", "사업", "스타트업"],
    "교육": ["교육", "훈련", "강의", "학습", "장학", "학비"],
    "복지": ["복지", "건강", "상담", "문화", "생활"],
    "금융": ["금융", "대출", "저축", "자산", "소득", "지원금"],
}

HOUSING_KEYWORDS = ["월세", "전세", "자가", "임대", "무주택", "기숙사"]
INCOME_PATTERNS = [r"중위소득\s*\d+%?", r"\d+\s*만원", r"소득\s*(없|낮|적|부족)"]
GENDER_KEYWORDS = {
    "여성": ["여성", "여자"],
    "남성": ["남성", "남자"],
}


def _first_keyword(text: str, mapping: dict[str, list[str]]) -> str | None:
    for label, keywords in mapping.items():
        if any(keyword in text for keyword in keywords):
            return label
    return None


USER_CONDITION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "age": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "region": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "status": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "interest": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "employment_status": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "income": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "housing_status": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "gender": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    },
    "required": [
        "age",
        "region",
        "status",
        "interest",
        "employment_status",
        "income",
        "housing_status",
        "gender",
    ],
}


def _normalize_llm_condition(condition: dict) -> dict:
    normalized = {
        "age": condition.get("age"),
        "region": condition.get("region"),
        "status": condition.get("status"),
        "interest": condition.get("interest"),
        "employment_status": condition.get("employment_status"),
        "income": condition.get("income"),
        "housing_status": condition.get("housing_status"),
        "gender": condition.get("gender"),
    }
    if not isinstance(normalized["age"], int) or not 14 <= normalized["age"] <= 49:
        normalized["age"] = None
    return normalized


def extract_user_condition_with_llm(user_input: str) -> dict:
    system_prompt = (
        "You extract Korean youth policy recommendation conditions. "
        "Return only fields in the schema. Use null when the user did not provide a value. "
        "If the input contains both a question and saved profile, the direct question has priority. "
        "Use broad Korean labels such as 서울, 경기, 대학생, 취업, 주거, 창업, 교육, 복지, 금융, 월세."
    )
    user_prompt = f"사용자 입력:\n{user_input}"
    result = create_structured_output(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema_name="user_condition",
        schema=USER_CONDITION_SCHEMA,
        max_output_tokens=500,
    )
    return _normalize_llm_condition(result)


def extract_user_condition_rule_based(user_input: str) -> dict:
    raw_text = user_input or ""
    if "질문:" in raw_text and "저장된 사용자 정보:" in raw_text:
        question_text = raw_text.split("저장된 사용자 정보:", 1)[0].replace("질문:", "").strip()
        profile_text = raw_text.split("저장된 사용자 정보:", 1)[1].strip()
    else:
        question_text = raw_text
        profile_text = ""
    text = question_text
    fallback_text = f"{question_text} {profile_text}".strip()

    age = None
    age_match = re.search(r"(?:만\s*)?(\d{1,2})\s*(?:살|세)", text)
    if age_match:
        parsed_age = int(age_match.group(1))
        if 14 <= parsed_age <= 49:
            age = parsed_age
    if age is None and fallback_text != text:
        fallback_age_match = re.search(r"(?:만\s*)?(\d{1,2})\s*(?:살|세)", fallback_text)
        if fallback_age_match:
            parsed_age = int(fallback_age_match.group(1))
            if 14 <= parsed_age <= 49:
                age = parsed_age

    region = next((region for region in REGIONS if region in text), None)
    status = _first_keyword(text, STATUS_KEYWORDS)
    employment_status = _first_keyword(text, EMPLOYMENT_KEYWORDS)
    interest = _first_keyword(text, INTEREST_KEYWORDS)
    gender = _first_keyword(text, GENDER_KEYWORDS)
    housing_status = next((keyword for keyword in HOUSING_KEYWORDS if keyword in text), None)

    # The user's direct prompt has priority. Stored login profile is only used
    # when the prompt does not provide that condition.
    if region is None:
        region = next((region for region in REGIONS if region in fallback_text), None)
    if status is None:
        status = _first_keyword(fallback_text, STATUS_KEYWORDS)
    if employment_status is None:
        employment_status = _first_keyword(fallback_text, EMPLOYMENT_KEYWORDS)
    if interest is None:
        interest = _first_keyword(fallback_text, INTEREST_KEYWORDS)
    if gender is None:
        gender = _first_keyword(fallback_text, GENDER_KEYWORDS)
    # If the prompt explicitly names an interest, do not let a saved profile's
    # housing status pull the recommendation back toward housing.
    if housing_status is None and interest is None:
        housing_status = next((keyword for keyword in HOUSING_KEYWORDS if keyword in fallback_text), None)

    income = None
    for pattern in INCOME_PATTERNS:
        match = re.search(pattern, text)
        if match:
            income = match.group(0)
            break

    return {
        "age": age,
        "region": region,
        "status": status,
        "interest": interest,
        "employment_status": employment_status,
        "income": income,
        "housing_status": housing_status,
        "gender": gender,
    }


def extract_user_condition(user_input: str) -> dict:
    try:
        return extract_user_condition_with_llm(user_input)
    except Exception as exc:
        if not isinstance(exc, LLMUnavailable):
            print(f"[ai.condition_extractor] LLM extraction failed, using rule fallback: {exc}")
        return extract_user_condition_rule_based(user_input)
