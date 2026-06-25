from __future__ import annotations

import re

from backend.region_map import REGION_CODE_MAP
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
    "창업": ["창업자", "예비창업자"],
    "자영업": ["사업자", "자영업"],
    "프리랜서": ["프리랜서"],
}

STATUS_KEYWORDS = {
    "대학생": ["대학생", "재학생", "휴학생", "졸업예정"],
    "졸업생": ["졸업생", "졸업자"],
    "청년": ["청년"],
    "군인": ["군인"],
}

INTEREST_KEYWORDS = {
    "주거": ["월세", "전세", "주거", "임대", "보증금", "집", "기숙사", "무주택"],
    "취업": ["취업", "구직", "면접", "일자리", "채용", "자격증"],
    "창업": ["창업", "사업", "스타트업"],
    "교육": ["교육", "훈련", "강의", "학습", "장학", "학비"],
    "금융": ["금융", "대출", "저축", "자산", "소득", "지원금", "목돈", "적금", "예금", "통장", "재테크", "투자", "주식"],
    "문화": ["문화", "문화생활", "공연", "전시", "예술", "관람"],
    "복지": ["복지", "건강", "상담", "생활지원"],
}

HOUSING_KEYWORDS = ["월세", "전세", "자가", "임대", "무주택", "기숙사"]
INCOME_PATTERNS = [r"중위소득\s*\d+%?", r"\d+\s*만원", r"소득\s*(없|낮|적|부족)"]
GENDER_KEYWORDS = {
    "여성": ["여성", "여자"],
    "남성": ["남성", "남자"],
}

REGION_ALIASES = {
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
    "강원도": "강원",
    "충청북도": "충북",
    "충청남도": "충남",
    "전북특별자치도": "전북",
    "전라북도": "전북",
    "전라남도": "전남",
    "경상북도": "경북",
    "경상남도": "경남",
    "제주특별자치도": "제주",
}


def _first_keyword(text: str, mapping: dict[str, list[str]]) -> str | None:
    for label, keywords in mapping.items():
        if any(keyword in text for keyword in keywords):
            return label
    return None


def _normalize_region_text(text: str) -> str:
    normalized = text or ""
    for long_name, short_name in REGION_ALIASES.items():
        normalized = normalized.replace(long_name, short_name)
    return normalized


def _extract_region_parts(text: str) -> tuple[str | None, str | None, str | None]:
    normalized = _normalize_region_text(text)
    sido = next((region for region in REGION_CODE_MAP if region in normalized), None)
    sigungu = None

    if sido:
        sigungu = next((name for name in REGION_CODE_MAP[sido] if name in normalized), None)
    else:
        for candidate_sido, sigungu_map in REGION_CODE_MAP.items():
            match = next((name for name in sigungu_map if name in normalized), None)
            if match:
                sido = candidate_sido
                sigungu = match
                break

    if not sido:
        return None, None, None
    region = f"{sido} {sigungu}".strip() if sigungu else sido
    return region, sido, sigungu


def _has_housing_keyword(text: str, keyword: str) -> bool:
    if keyword == "자가":
        return bool(re.search(r"(?<![가-힣])자가(?![가-힣])|자가\s*주택|자가\s*거주", text))
    return keyword in text


def _first_housing_keyword(text: str) -> str | None:
    return next((keyword for keyword in HOUSING_KEYWORDS if _has_housing_keyword(text, keyword)), None)


USER_CONDITION_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "age": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
        "region": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "region_sido": {"anyOf": [{"type": "string"}, {"type": "null"}]},
        "region_sigungu": {"anyOf": [{"type": "string"}, {"type": "null"}]},
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
        "region_sido",
        "region_sigungu",
        "status",
        "interest",
        "employment_status",
        "income",
        "housing_status",
        "gender",
    ],
}


def _normalize_llm_condition(condition: dict, source_text: str = "") -> dict:
    region, region_sido, region_sigungu = _extract_region_parts(
        " ".join(
            str(condition.get(key) or "")
            for key in ["region", "region_sido", "region_sigungu"]
        )
    )
    if not region_sigungu and source_text:
        source_region, source_sido, source_sigungu = _extract_region_parts(source_text)
        region = region or source_region
        region_sido = region_sido or source_sido
        region_sigungu = region_sigungu or source_sigungu
    normalized = {
        "age": condition.get("age"),
        "region": region or condition.get("region"),
        "region_sido": region_sido or condition.get("region_sido"),
        "region_sigungu": region_sigungu or condition.get("region_sigungu"),
        "status": condition.get("status"),
        "interest": condition.get("interest"),
        "employment_status": condition.get("employment_status"),
        "income": condition.get("income"),
        "housing_status": condition.get("housing_status"),
        "gender": condition.get("gender"),
    }
    if not isinstance(normalized["age"], int) or not 14 <= normalized["age"] <= 49:
        normalized["age"] = None
    if normalized["employment_status"] in {"대학생", "졸업생", "청년", "군인"}:
        normalized["status"] = normalized["status"] or normalized["employment_status"]
        normalized["employment_status"] = None
    return normalized


def extract_user_condition_with_llm(user_input: str) -> dict:
    system_prompt = (
        "You extract Korean youth policy recommendation conditions. "
        "Return only fields in the schema. Use null when the user did not provide a value. "
        "If the input contains both a question and saved profile, the direct question has priority. "
        "Extract region_sido and region_sigungu separately when available, for example 경기 오산시. "
        "Keep school/life status and employment status separate: status can be 대학생, 졸업생, 청년, 군인, "
        "while employment_status should only be 미취업, 재직, 창업, 자영업, 프리랜서, or null. "
        "Use broad Korean labels such as 서울, 경기, 오산시, 대학생, 미취업, 재직, 취업, 주거, 창업, 교육, 문화, 복지, 금융, 월세."
    )
    user_prompt = f"사용자 입력:\n{user_input}"
    result = create_structured_output(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema_name="user_condition",
        schema=USER_CONDITION_SCHEMA,
        max_output_tokens=500,
    )
    normalized = _normalize_llm_condition(result, user_input)
    rule_based = extract_user_condition_rule_based(user_input)

    # Deterministic text signals are safer than LLM nulls or broad guesses for
    # routing. In particular, region_sigungu and interest control hard filters.
    for key in ["region", "region_sido", "region_sigungu", "interest", "housing_status"]:
        if rule_based.get(key):
            normalized[key] = rule_based[key]
    for key in ["age", "status", "employment_status", "income", "gender"]:
        if normalized.get(key) in (None, "") and rule_based.get(key):
            normalized[key] = rule_based[key]

    if normalized.get("region_sido") and normalized.get("region_sigungu"):
        normalized["region"] = f"{normalized['region_sido']} {normalized['region_sigungu']}"
    return normalized


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

    region, region_sido, region_sigungu = _extract_region_parts(text)
    status = _first_keyword(text, STATUS_KEYWORDS)
    employment_status = _first_keyword(text, EMPLOYMENT_KEYWORDS)
    interest = _first_keyword(text, INTEREST_KEYWORDS)
    gender = _first_keyword(text, GENDER_KEYWORDS)
    housing_status = _first_housing_keyword(text)

    # The user's direct prompt has priority. Stored login profile is only used
    # when the prompt does not provide that condition.
    if region is None:
        region, region_sido, region_sigungu = _extract_region_parts(fallback_text)
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
        housing_status = _first_housing_keyword(fallback_text)

    income = None
    for pattern in INCOME_PATTERNS:
        match = re.search(pattern, text)
        if match:
            income = match.group(0)
            break

    return {
        "age": age,
        "region": region,
        "region_sido": region_sido,
        "region_sigungu": region_sigungu,
        "status": status,
        "interest": interest,
        "employment_status": employment_status,
        "income": income,
        "housing_status": housing_status,
        "gender": gender,
    }


def has_condition_signal(user_input: str) -> bool:
    """Return True only when the raw input contains a recommendation condition."""
    text = user_input or ""
    if re.search(r"(?:만\s*)?(\d{1,2})\s*(?:살|세)", text):
        return True
    if _extract_region_parts(text)[0]:
        return True
    if _first_keyword(text, GENDER_KEYWORDS):
        return True
    if _first_keyword(text, EMPLOYMENT_KEYWORDS):
        return True
    if _first_keyword(text, INTEREST_KEYWORDS):
        return True
    if _first_housing_keyword(text):
        return True
    if any(re.search(pattern, text) for pattern in INCOME_PATTERNS):
        return True

    status = _first_keyword(text, STATUS_KEYWORDS)
    return bool(status and status != "청년")


def extract_user_condition(user_input: str) -> dict:
    try:
        return extract_user_condition_with_llm(user_input)
    except Exception as exc:
        if not isinstance(exc, LLMUnavailable):
            print(f"[ai.condition_extractor] LLM extraction failed, using rule fallback: {exc}")
        return extract_user_condition_rule_based(user_input)
