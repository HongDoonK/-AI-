from __future__ import annotations

from typing import Any

import pandas as pd

from ai.llm_client import LLMUnavailable, create_structured_output


VALID_POSSIBILITIES = {"높음", "확인 필요", "낮음"}

DOMAIN_LABELS = {
    "policy": "일반 정책",
    "policy_housing": "주거 정책",
    "policy_finance": "금융/복지 정책",
    "policy_training": "교육/훈련 정책",
    "policy_job": "취업 정책",
    "policy_startup": "창업 정책",
    "housing_notice": "임대 공고",
    "rental_house": "임대주택 단지",
    "loan": "청년 금융상품",
    "training": "직업훈련",
    "startup": "창업 공고",
}

SOURCE_LABELS = {
    "policies_processed": "온통청년 정책",
    "hrd_trainings": "HRD-Net 훈련",
    "kstartup_notices": "K-Startup 공고",
    "smallloan_youth": "청년 금융상품",
    "myhome_notices": "마이홈 임대공고",
    "rental_houses": "청년 임대주택",
}

RECOMMENDATIONS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "recommendations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "policy_name": {"type": "string"},
                    "apply_possibility": {"type": "string"},
                    "reason": {"type": "string"},
                    "support_content": {"type": "string"},
                    "application_period": {"type": "string"},
                    "application_url": {"type": "string"},
                    "checklist": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": [
                    "policy_name",
                    "apply_possibility",
                    "reason",
                    "support_content",
                    "application_period",
                    "application_url",
                    "checklist",
                ],
            },
        }
    },
    "required": ["recommendations"],
}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and pd.isna(value):
        return ""
    return str(value).strip()


def _short(value: Any, limit: int = 95) -> str:
    text = " ".join(_clean(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _age_matches(condition: dict, row: dict) -> bool | None:
    age = condition.get("age")
    if age is None:
        return None
    min_age = pd.to_numeric(row.get("min_age"), errors="coerce")
    max_age = pd.to_numeric(row.get("max_age"), errors="coerce")
    min_age = None if pd.isna(min_age) or int(min_age) == 0 else int(min_age)
    max_age = None if pd.isna(max_age) or int(max_age) == 0 else int(max_age)
    if min_age is None and max_age is None:
        return None
    if min_age is not None and age < min_age:
        return False
    if max_age is not None and age > max_age:
        return False
    return True


def _row_text(row: dict, columns: list[str]) -> str:
    return " ".join(_clean(row.get(col)) for col in columns)


def _policy_focus(row: dict) -> str:
    category = " / ".join(
        value for value in [_clean(row.get("category_main")), _clean(row.get("category_sub"))] if value
    )
    keyword = _clean(row.get("keyword"))
    if category and keyword:
        return f"{category} 분야, 키워드 {keyword}"
    return category or keyword or "세부 분야 확인 필요"


def _score_label(row: dict) -> str:
    score = pd.to_numeric(row.get("score"), errors="coerce")
    if pd.isna(score):
        return ""
    method = _clean(row.get("match_method"))
    if "FAISS" in method:
        return f"{float(score):.3f}"
    return f"{float(score):.1f}"


def _region_match_label(condition: dict, row: dict) -> str:
    wanted_sigungu = _clean(condition.get("region_sigungu"))
    wanted_sido = _clean(condition.get("region_sido")) or _clean(condition.get("region"))
    row_region = _clean(row.get("region_name"))
    row_sido = _clean(row.get("region_sido"))
    row_sigungu = _clean(row.get("region_sigungu"))

    if row_sido == "전국" or row_region == "전국":
        return "전국 단위"
    if wanted_sigungu and wanted_sigungu in row_sigungu:
        return f"{wanted_sigungu} 일치"
    if wanted_sido and wanted_sido in row_sido:
        return f"{wanted_sido} 지역"
    if row_region:
        return row_region
    return "지역 확인 필요"


def _metadata(row: dict, condition: dict) -> dict:
    domain = _clean(row.get("domain")) or _clean(row.get("category_main"))
    source_table = _clean(row.get("source_table")) or _clean(row.get("category_sub"))
    region_label = _region_match_label(condition, row)
    score_label = _score_label(row)
    method = _clean(row.get("match_method")) or "검색 점수"
    domain_label = DOMAIN_LABELS.get(domain, domain or "분야 확인")
    source_label = SOURCE_LABELS.get(source_table, source_table or "출처 확인")
    badges = [region_label, domain_label, source_label]
    if score_label:
        badges.append(f"{method} {score_label}")
    return {
        "match_score": None if not score_label else float(pd.to_numeric(row.get("score"), errors="coerce")),
        "match_method": method,
        "match_score_label": score_label,
        "domain": domain,
        "domain_label": domain_label,
        "source_table": source_table,
        "source_label": source_label,
        "region_name": _clean(row.get("region_name")),
        "region_sido": _clean(row.get("region_sido")),
        "region_sigungu": _clean(row.get("region_sigungu")),
        "region_match": region_label,
        "match_badges": badges,
    }


def _attach_metadata(recommendations: list[dict], top_policies: list[dict], condition: dict) -> list[dict]:
    by_name = {_clean(row.get("policy_name")): row for row in top_policies}
    enriched = []
    for index, item in enumerate(recommendations):
        row = by_name.get(_clean(item.get("policy_name")))
        if row is None and index < len(top_policies):
            row = top_policies[index]
        enriched_item = dict(item)
        if row is not None:
            enriched_item.update(_metadata(row, condition))
        enriched.append(enriched_item)
    return enriched


def _specific_reason_parts(condition: dict, row: dict) -> list[str]:
    parts = []
    search_text = _row_text(
        row,
        [
            "search_text", "policy_name", "description", "keyword", "support_content",
            "region_name", "region_sido", "region_sigungu", "school_cd", "job_cd",
        ],
    )
    school_text = _row_text(row, ["school_cd", "search_text"])
    job_text = _row_text(row, ["job_cd", "search_text"])

    age_match = _age_matches(condition, row)
    if age_match is True:
        parts.append(f"{condition['age']}세 기준 연령 범위에 들어갑니다")
    elif age_match is False:
        parts.append("연령 조건은 공고문에서 추가 확인이 필요합니다")

    interest = condition.get("interest")
    if interest and interest in search_text:
        parts.append(f"요청한 관심 분야인 {interest}와 정책 내용이 맞닿아 있습니다")

    status = condition.get("status")
    if status and status in school_text:
        parts.append(f"{status} 상태와 관련된 학력/대상 조건이 확인됩니다")

    employment = condition.get("employment_status")
    if employment and employment in job_text:
        parts.append(f"{employment} 조건과 연결되는 취업 요건이 있습니다")

    housing = condition.get("housing_status")
    if housing and housing in search_text:
        parts.append(f"{housing} 상황과 직접 관련된 지원 내용이 포함됩니다")

    region = condition.get("region") or " ".join(
        value for value in [condition.get("region_sido"), condition.get("region_sigungu")] if value
    )
    if region and region in search_text:
        parts.append(f"{region} 지역 정보가 정책 설명에 포함됩니다")

    gender = condition.get("gender")
    if gender and gender in search_text:
        parts.append(f"{gender} 대상 조건이 언급됩니다")

    return parts


def _possibility(condition: dict, row: dict, parts: list[str]) -> str:
    age_match = _age_matches(condition, row)
    if age_match is False:
        return "낮음"
    if len(parts) >= 2 or age_match is True:
        return "높음"
    return "확인 필요"


def _reason(condition: dict, row: dict, parts: list[str]) -> str:
    name = _clean(row.get("policy_name")) or "이 정책"
    focus = _policy_focus(row)
    support = _short(row.get("support_content"), 90)
    institution = _clean(row.get("oper_inst")) or _clean(row.get("institution"))

    sentences = []
    if parts:
        sentences.append("; ".join(parts[:3]) + ".")
    else:
        sentences.append(f"{name}은 {focus} 정책으로 분류되어 입력 조건과 함께 검토할 만합니다.")

    if support:
        sentences.append(f"주요 지원은 {support}입니다.")
    if institution:
        sentences.append(f"운영/주관 기관은 {institution}입니다.")
    return " ".join(sentences)


def _checklist(row: dict) -> list[str]:
    checklist = []

    apply_period = _clean(row.get("apply_period"))
    apply_method = _short(row.get("apply_method"), 110)
    submit_docs = _short(row.get("submit_docs"), 120)
    apply_condition = _short(row.get("apply_condition"), 120)
    income_info = " / ".join(
        value for value in [_clean(row.get("income_type")), _short(row.get("income_etc"), 80)] if value
    )
    url = _clean(row.get("application_url"))
    ref_url = _clean(row.get("ref_url1")) or _clean(row.get("ref_url2"))

    if apply_period:
        checklist.append(f"신청 기간 확인: {apply_period}")
    else:
        checklist.append("신청 기간이 비어 있으므로 공고문 또는 담당 기관에 접수 가능 여부 확인하기")

    if apply_condition:
        checklist.append(f"자격 조건 확인: {apply_condition}")
    else:
        checklist.append("나이, 거주지, 학력/취업 상태 등 기본 자격 조건 확인하기")

    if income_info:
        checklist.append(f"소득 조건 확인: {income_info}")

    if submit_docs:
        checklist.append(f"제출 서류 준비: {submit_docs}")
    else:
        checklist.append("주민등록등본, 신분증, 소득 증빙 등 기본 서류 준비하기")

    if apply_method:
        checklist.append(f"신청 방법 확인: {apply_method}")
    elif url or ref_url:
        checklist.append("신청/참고 링크에서 접수 절차와 최신 공고 확인하기")
    else:
        checklist.append("담당 기관에 신청 방법과 접수 창구 문의하기")

    return checklist


def _compact_policy(row: dict) -> dict:
    return {
        "policy_name": _clean(row.get("policy_name")),
        "category_main": _clean(row.get("category_main")),
        "category_sub": _clean(row.get("category_sub")),
        "keyword": _clean(row.get("keyword")),
        "domain": _clean(row.get("domain")),
        "source_table": _clean(row.get("source_table")),
        "region_name": _clean(row.get("region_name")),
        "region_sido": _clean(row.get("region_sido")),
        "region_sigungu": _clean(row.get("region_sigungu")),
        "score": _clean(row.get("score")),
        "match_method": _clean(row.get("match_method")),
        "description": _short(row.get("description"), 180),
        "support_content": _short(row.get("support_content"), 220),
        "apply_period": _clean(row.get("apply_period")),
        "apply_condition": _short(row.get("apply_condition"), 220),
        "submit_docs": _short(row.get("submit_docs"), 180),
        "apply_method": _short(row.get("apply_method"), 180),
        "min_age": _clean(row.get("min_age")),
        "max_age": _clean(row.get("max_age")),
        "job_cd": _clean(row.get("job_cd")),
        "school_cd": _clean(row.get("school_cd")),
        "income_type": _clean(row.get("income_type")),
        "income_etc": _short(row.get("income_etc"), 160),
        "application_url": _clean(row.get("application_url")) or _clean(row.get("ref_url1")),
    }


def generate_recommendations_with_llm(
    user_input: str,
    user_condition: dict,
    top_policies: list[dict],
) -> list[dict]:
    import json

    candidates = [_compact_policy(row) for row in top_policies[:5]]
    system_prompt = (
        "You are a Korean youth policy recommendation assistant. "
        "Use only the provided policy candidates. Do not invent policy names, URLs, periods, or benefits. "
        "Write concise Korean explanations that a student can understand. "
        "apply_possibility must be one of: 높음, 확인 필요, 낮음. "
        "Each checklist should contain 3 to 5 practical application checks."
    )
    user_prompt = (
        "사용자 입력:\n"
        f"{user_input}\n\n"
        "추출된 사용자 조건:\n"
        f"{json.dumps(user_condition, ensure_ascii=False)}\n\n"
        "정책 후보:\n"
        f"{json.dumps(candidates, ensure_ascii=False)}"
    )
    result = create_structured_output(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        schema_name="policy_recommendations",
        schema=RECOMMENDATIONS_SCHEMA,
        max_output_tokens=2200,
    )
    recommendations = result.get("recommendations", [])
    if not isinstance(recommendations, list):
        raise LLMUnavailable("LLM recommendations payload is not a list.")
    return _attach_metadata(recommendations[:5], top_policies, user_condition)


def generate_recommendations_rule_based(user_input: str, user_condition: dict, top_policies: list[dict]) -> list[dict]:
    recommendations = []
    for row in top_policies[:5]:
        parts = _specific_reason_parts(user_condition, row)
        possibility = _possibility(user_condition, row, parts)
        if possibility not in VALID_POSSIBILITIES:
            possibility = "확인 필요"

        item = {
            "policy_name": _clean(row.get("policy_name")) or "정책명 미상",
            "apply_possibility": possibility,
            "reason": _reason(user_condition, row, parts),
            "support_content": _clean(row.get("support_content")),
            "application_period": _clean(row.get("apply_period")),
            "application_url": _clean(row.get("application_url")) or _clean(row.get("ref_url1")),
            "checklist": _checklist(row)[:5],
        }
        item.update(_metadata(row, user_condition))
        recommendations.append(item)
    return recommendations


def generate_recommendations(user_input: str, user_condition: dict, top_policies: list[dict]) -> list[dict]:
    try:
        return generate_recommendations_with_llm(user_input, user_condition, top_policies)
    except Exception as exc:
        if not isinstance(exc, LLMUnavailable):
            print(f"[ai.generator] LLM generation failed, using rule fallback: {exc}")
        return generate_recommendations_rule_based(user_input, user_condition, top_policies)
