"""정보 Agent: 지원금 정량화 (BenefitEstimator).

정책 컨텍스트(load_policy_context 결과)를 입력받아 지원 내용을
금액·주기·기간으로 구조화한다. "12개월간 매월 20만원, 최대 240만원" 같은
한 줄 답변(summary_line)을 만들어, 텍스트 bullet만 내놓던 기존
_build_user_summary["benefit"]의 약점을 정량화로 승격한다.

규칙 우선(정규식) → 비거나 자유서술이면 LLM 구조화 출력으로 보강 →
그래도 없으면 confidence='check_notice'. 수치는 지어내지 않는다.

설계: docs/ADR-001-conversational-apply-flow.md
"""
from __future__ import annotations

import re
from typing import Any

from ai.chat_text_utils import _clean
from ai.llm_client import llm_enabled, create_structured_output

# 한국어 금액 단위 → 원 환산 배수 (긴 단위부터 매칭해야 '백만원'이 '만원'으로 안 깨짐)
_UNIT_MULTIPLIER = [
    ("억원", 100_000_000), ("억", 100_000_000),
    ("천만원", 10_000_000), ("천만", 10_000_000),
    ("백만원", 1_000_000), ("백만", 1_000_000),
    ("만원", 10_000), ("만", 10_000),
    ("원", 1),
]
_UNIT_ALTERNATION = "|".join(unit for unit, _ in _UNIT_MULTIPLIER)
_AMOUNT_RE = re.compile(rf"([\d,]+(?:\.\d+)?)\s*({_UNIT_ALTERNATION})")
_MONTHLY_RE = re.compile(rf"(?:매월|월)\s*(?:최대\s*)?([\d,]+(?:\.\d+)?)\s*({_UNIT_ALTERNATION})")
_MONTHS_RE = re.compile(r"(?:최대\s*)?(\d+)\s*개월")
_YEARS_RE = re.compile(r"(?:최대\s*)?(\d+)\s*년\s*간?")
_TIMES_RE = re.compile(r"(?:최대\s*)?(\d+)\s*회")


def _to_won(number_text: str, unit: str) -> int | None:
    try:
        number = float(number_text.replace(",", ""))
    except ValueError:
        return None
    for candidate_unit, multiplier in _UNIT_MULTIPLIER:
        if unit == candidate_unit:
            return int(round(number * multiplier))
    return None


def _first_amount(text: str) -> int | None:
    match = _AMOUNT_RE.search(text)
    if match:
        return _to_won(match.group(1), match.group(2))
    # 단위 없는 순수 정수(예: hrd_trainings.real_man='1000000')도 원으로 취급
    bare = re.fullmatch(r"\s*([\d,]+)\s*", text or "")
    if bare:
        value = int(bare.group(1).replace(",", ""))
        return value if value > 0 else None
    return None


def format_won(won: int | None) -> str:
    """원 → 사람이 읽기 좋은 표기. 억/만원 단위로 떨어지면 단위 표기, 아니면 'N,NNN원'."""
    if not won or won <= 0:
        return ""
    eok, man, rem = won // 100_000_000, (won % 100_000_000) // 10_000, won % 10_000
    if rem:
        return f"{won:,}원"
    parts = []
    if eok:
        parts.append(f"{eok:,}억")
    if man:
        parts.append(f"{man:,}만")
    return ("".join(parts) + "원") if parts else f"{won:,}원"


def _months_from_text(text: str) -> int | None:
    month_match = _MONTHS_RE.search(text)
    if month_match:
        return int(month_match.group(1))
    year_match = _YEARS_RE.search(text)
    if year_match:
        return int(year_match.group(1)) * 12
    times_match = _TIMES_RE.search(text)
    if times_match:
        return int(times_match.group(1))
    return None


def _looks_like_loan(text: str) -> bool:
    return bool(re.search(r"대출|융자|금리|상환|거치", text))


def _estimate_cash(text: str) -> dict[str, Any]:
    """현금성 지원: 월 지급액 × 지급 개월 → 총액."""
    monthly_match = _MONTHLY_RE.search(text)
    monthly_won = _to_won(*monthly_match.groups()) if monthly_match else None
    months = _months_from_text(text)

    total_won = None
    if monthly_won and months:
        total_won = monthly_won * months
    # 원문에 '1인당 최대 N만원'처럼 총액이 명시되면 그 값을 신뢰
    explicit = re.search(rf"(?:1인당|총|최대)\s*([\d,]+(?:\.\d+)?)\s*({_UNIT_ALTERNATION})", text)
    if explicit:
        explicit_won = _to_won(explicit.group(1), explicit.group(2))
        # 월 지급액과 같은 값이면 총액이 아니라 월액을 다시 잡은 것이므로 무시
        if explicit_won and explicit_won != monthly_won:
            total_won = total_won or explicit_won

    if not monthly_won and not total_won:
        lump = _first_amount(text)
        if lump:
            total_won = lump

    if not monthly_won and not total_won:
        return _unknown(["support_content"])

    parts = []
    if months and monthly_won:
        parts.append(f"최대 {months}개월간 매월 {format_won(monthly_won)}씩")
    elif monthly_won:
        parts.append(f"매월 {format_won(monthly_won)}씩")
    if total_won:
        parts.append(f"최대 {format_won(total_won)}")
    summary_line = ", ".join(parts) + "을 지원받을 수 있어요." if parts else ""
    if monthly_won and not months:
        summary_line += " (지원 기간은 공고에서 확인하세요.)"
    return {
        "kind": "cash",
        "monthly_won": monthly_won,
        "months": months,
        "total_won": total_won,
        "summary_line": summary_line,
        "confidence": "exact" if (monthly_won and months) else "estimated",
        "sources": ["support_content"],
    }


def _estimate_loan_from_text(text: str) -> dict[str, Any]:
    limit_match = re.search(rf"한도[:\s]*(?:최대\s*)?([\d,]+(?:\.\d+)?)\s*({_UNIT_ALTERNATION})", text)
    limit_won = _to_won(*limit_match.groups()) if limit_match else _first_amount(text)
    rate_match = re.search(r"(?:연\s*)?(\d+(?:\.\d+)?\s*(?:~|∼|-)?\s*\d*(?:\.\d+)?\s*%(?:\s*이내)?)", text)
    rate_text = _clean(rate_match.group(1)) if rate_match else ("무이자" if "무이자" in text else "")
    term_match = re.search(r"기간[:\s]*(?:최대\s*)?(\d+)\s*년", text) or _YEARS_RE.search(text)
    term_months = int(term_match.group(1)) * 12 if term_match else None

    if not (limit_won or rate_text or term_months):
        return _unknown(["support_content"])
    pieces = []
    if limit_won:
        pieces.append(f"최대 {format_won(limit_won)}")
    if rate_text:
        pieces.append(f"연 {rate_text}" if not rate_text.startswith(("무", "연")) else rate_text)
    if term_months:
        pieces.append(f"최대 {term_months // 12}년 이내")
    summary_line = ("대출은 " + ", ".join(pieces) + " 조건이에요.") if pieces else ""
    return {
        "kind": "loan",
        "limit_won": limit_won,
        "rate_text": rate_text,
        "term_months": term_months,
        "summary_line": summary_line,
        "confidence": "exact" if (limit_won and term_months) else "estimated",
        "sources": ["support_content"],
    }


def _estimate_loan_from_fields(original: dict[str, Any]) -> dict[str, Any]:
    limit_raw = _clean(original.get("lnLmt"))
    limit_won = _first_amount(limit_raw) if limit_raw and limit_raw != "-" else None
    rate_text = _clean(original.get("irt"))
    term_raw = _clean(original.get("maxTotLnTrm"))
    term_match = re.search(r"(\d+)\s*년", term_raw)
    term_months = int(term_match.group(1)) * 12 if term_match else None
    pieces = []
    if limit_won:
        pieces.append(f"최대 {format_won(limit_won)}")
    elif limit_raw and limit_raw != "-":
        pieces.append(f"한도 {limit_raw}")
    if rate_text and rate_text != "-":
        pieces.append(rate_text if "무이자" in rate_text else f"금리 {rate_text}")
    if term_raw and term_raw != "-":
        pieces.append(f"기간 {term_raw}")
    summary_line = ("대출은 " + ", ".join(pieces) + " 조건이에요.") if pieces else ""
    return {
        "kind": "loan",
        "limit_won": limit_won,
        "rate_text": rate_text,
        "term_months": term_months,
        "summary_line": summary_line or "대출 조건은 취급 기관에서 확인이 필요해요.",
        "confidence": "exact" if pieces else "check_notice",
        "sources": ["lnLmt", "irt", "maxTotLnTrm"],
    }


def _estimate_housing(original: dict[str, Any], source_table: str) -> dict[str, Any]:
    if source_table == "myhome_notices":
        deposit = original.get("deposit")
        rent = original.get("monthly_rent")
    else:  # rental_houses
        deposit = original.get("bassRentGtn")
        rent = original.get("bassMtRntchrg")
    deposit_won = int(deposit) if str(deposit or "").strip().lstrip("-").isdigit() and int(deposit) > 0 else None
    rent_won = int(rent) if str(rent or "").strip().lstrip("-").isdigit() and int(rent) > 0 else None
    if not (deposit_won or rent_won):
        return _unknown(["deposit", "monthly_rent"], note="단지/공고에 보증금·월세가 0 또는 미기재예요. 실제 모집공고에서 확인하세요.")
    pieces = []
    if deposit_won:
        pieces.append(f"보증금 {format_won(deposit_won)}")
    if rent_won:
        pieces.append(f"월 임대료 {format_won(rent_won)}")
    summary_line = " / ".join(pieces) + " 수준으로 거주할 수 있어요. (거주 기간·자격은 공고 확인)"
    return {
        "kind": "housing",
        "deposit_won": deposit_won,
        "monthly_rent_won": rent_won,
        "lease_months": None,
        "summary_line": summary_line,
        "confidence": "exact",
        "sources": ["deposit", "monthly_rent"],
    }


def _estimate_training(original: dict[str, Any]) -> dict[str, Any]:
    own = _first_amount(_clean(original.get("real_man")))
    total = _first_amount(_clean(original.get("course_man")))
    if not (own or total):
        return _unknown(["real_man", "course_man"])
    base = total or own
    summary_line = (
        f"훈련비는 {format_won(base)}이고, 국민내일배움카드 대상이면 자기부담금이 크게 줄어요."
    )
    return {
        "kind": "training",
        "course_won": total,
        "self_pay_won": own,
        "summary_line": summary_line,
        "confidence": "estimated",
        "sources": ["real_man", "course_man"],
    }


def _unknown(sources: list[str], note: str = "") -> dict[str, Any]:
    return {
        "kind": "unknown",
        "summary_line": note or "지원 금액이 공고 원문에 정량으로 나와 있지 않아 공고에서 확인이 필요해요.",
        "confidence": "check_notice",
        "sources": sources,
    }


_LLM_SCHEMA = {
    "type": "object",
    "properties": {
        "kind": {"type": "string", "enum": ["cash", "housing", "loan", "training", "unknown"]},
        "monthly_won": {"type": ["integer", "null"]},
        "months": {"type": ["integer", "null"]},
        "total_won": {"type": ["integer", "null"]},
        "summary_line": {"type": "string"},
    },
    "required": ["kind", "summary_line"],
    "additionalProperties": False,
}


def _estimate_with_llm(text: str) -> dict[str, Any] | None:
    if not llm_enabled() or not text:
        return None
    try:
        raw = create_structured_output(
            system_prompt=(
                "너는 한국 청년 정책의 지원 금액을 구조화하는 분석기다. "
                "원문에 실제로 적힌 숫자만 사용하고, 없는 값은 null로 둔다. 금액은 원 단위 정수."
            ),
            user_prompt=f"다음 지원 내용에서 금액/주기/기간을 구조화해줘:\n{text[:1200]}",
            schema_name="benefit_estimate",
            schema=_LLM_SCHEMA,
            max_output_tokens=300,
        )
    except Exception as exc:  # 401/네트워크 등 비-LLMUnavailable 포함 광범위 처리
        print(f"[ai.benefit_estimator] LLM estimate unavailable, skipping: {exc}")
        return None
    if not _clean(raw.get("summary_line")):
        return None
    raw["confidence"] = "estimated"
    raw["sources"] = ["llm"]
    return raw


def estimate_benefit(context: dict[str, Any]) -> dict[str, Any]:
    """정책 컨텍스트에서 구조화된 지원금을 산출한다.

    반환 dict의 공통 키: kind, summary_line, confidence, sources.
    kind별 추가 키 — cash: monthly_won/months/total_won,
    housing: deposit_won/monthly_rent_won/lease_months, loan: limit_won/rate_text/term_months,
    training: course_won/self_pay_won.
    """
    source_table = _clean(context.get("source_table"))
    original = context.get("original") or {}

    if source_table in {"myhome_notices", "rental_houses"}:
        return _estimate_housing(original, source_table)
    if source_table == "smallloan_youth":
        return _estimate_loan_from_fields(original)
    if source_table == "hrd_trainings":
        return _estimate_training(original)

    # policies_processed / kstartup_notices / 검색문서 기반 → 지원 내용 텍스트 파싱
    text = _clean(original.get("support_content")) or _clean(context.get("summary"))
    if not text:
        return _unknown(["support_content"])

    result = _estimate_loan_from_text(text) if _looks_like_loan(text) else _estimate_cash(text)
    if result["kind"] != "unknown":
        return result

    # 규칙이 못 뽑으면 LLM 보강 → 그래도 없으면 check_notice
    return _estimate_with_llm(text) or _unknown(["support_content"])
