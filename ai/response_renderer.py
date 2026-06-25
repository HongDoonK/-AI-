from __future__ import annotations

from typing import Any, Iterable

from ai.response_planner import ResponsePlan


_OPENINGS = {
    "docs": {
        "direct": "'{title}' 신청 서류를 바로 정리할게요.",
        "guided": "'{title}' 신청 준비에서 먼저 챙길 서류부터 볼게요.",
        "concise": "'{title}'의 필수 준비 서류입니다.",
    },
    "benefit": {
        "direct": "'{title}'에서 받을 수 있는 혜택의 핵심입니다.",
        "guided": "'{title}' 혜택을 금액과 기간 중심으로 풀어볼게요.",
        "concise": "'{title}' 지원 내용 요약입니다.",
    },
    "eligibility": {
        "direct": "'{title}' 신청 가능성을 조건별로 확인했어요.",
        "guided": "'{title}' 조건과 현재 정보를 차례로 비교해볼게요.",
        "concise": "'{title}' 자격 확인 결과입니다.",
    },
    "apply_how": {
        "direct": "'{title}' 신청 경로를 바로 안내할게요.",
        "guided": "'{title}' 신청을 시작할 수 있도록 순서대로 정리할게요.",
        "concise": "'{title}' 신청 방법입니다.",
    },
    "overview": {
        "direct": "'{title}'의 핵심 내용을 정리했어요.",
        "guided": "'{title}'을 이해하기 쉬운 순서로 살펴볼게요.",
        "concise": "'{title}' 요약입니다.",
    },
}

_FOLLOW_UPS = {
    "missing_user_condition": "나이와 거주 지역을 알려주면 신청 가능성을 더 좁혀볼까요?",
    "eligibility": "이 혜택이 본인 조건에 맞는지도 이어서 확인할까요?",
    "benefit": "받을 수 있는 금액과 기간도 이어서 볼까요?",
    "docs": "신청 전에 준비할 서류도 이어서 정리할까요?",
    "apply_how": "실제 신청 경로와 마감도 이어서 확인할까요?",
    "create_apply_plan": "바로 실행할 수 있게 신청 준비 체크리스트를 만들까요?",
    "contact": "담당 기관에 문의할 질문까지 정리할까요?",
}


def canonical_intent(intent: str) -> str:
    if intent in {"apply", "period"}:
        return "apply_how"
    return intent if intent in _OPENINGS else "overview"


def render_opening(title: str, intent: str, plan: ResponsePlan) -> str:
    if plan.repetition_mode == "confirm":
        return f"'{title}' 기준으로 다시 핵심만 확인해드릴게요."
    if plan.repetition_mode == "clarify":
        return f"'{title}'에서 방금 물어본 부분을 더 구체적으로 볼게요."
    template = _OPENINGS[canonical_intent(intent)][plan.opening_variant]
    return template.format(title=title)


def render_follow_up(plan: ResponsePlan, source_label: str = "정책 DB") -> str:
    return _FOLLOW_UPS.get(
        plan.follow_up_kind,
        f"{source_label} 기준으로 다른 항목도 이어서 확인할까요?",
    )


def section_item_limit(plan: ResponsePlan) -> int:
    if plan.detail_level == "compact":
        return 2
    if plan.detail_level == "focused":
        return 4
    return 6


def ordered_section_keys(plan: ResponsePlan, available: Iterable[str]) -> list[str]:
    available_set = set(available)
    ordered = [key for key in plan.section_order if key in available_set]
    ordered.extend(sorted(available_set.difference(ordered)))
    return ordered


def order_actions(actions: list[dict[str, Any]], plan: ResponsePlan) -> list[dict[str, Any]]:
    priority = {name: index for index, name in enumerate(plan.suggested_action_order)}

    def key(action: dict[str, Any]) -> tuple[int, str]:
        action_key = str(action.get("intent") or action.get("action") or "")
        return priority.get(action_key, len(priority)), action_key

    return sorted(actions, key=key)
