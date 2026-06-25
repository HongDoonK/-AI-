from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any


_INTENT_ALIASES = {
    "apply": "apply_how",
    "period": "apply_how",
}

_SPECIFIC_WORDS = {
    "얼마", "총", "월", "개월", "언제", "마감", "어디", "발급", "링크",
    "온라인", "방문", "소득", "나이", "지역", "서류",
}

_INTENT_WORDS = {
    "docs": ("서류", "준비물", "발급", "제출"),
    "benefit": ("혜택", "지원금", "얼마", "금액", "받을 수"),
    "eligibility": ("자격", "조건", "가능해", "대상"),
    "apply_how": ("신청", "접수", "링크", "마감", "기간"),
}

_SECTION_ORDERS = {
    "docs": {
        "issuance": ("issuance", "documents", "apply_link", "next_step"),
        "deadline_risk": ("period", "documents", "apply_link", "next_step"),
        "document_preparation": ("documents", "issuance", "apply_link", "next_step"),
    },
    "benefit": {
        "total_amount": ("amount", "duration", "eligibility", "next_step"),
        "duration": ("duration", "amount", "eligibility", "next_step"),
        "personal_fit": ("eligibility", "amount", "duration", "next_step"),
        "core_benefit": ("summary", "amount", "duration", "next_step"),
    },
    "eligibility": {
        "missing_user_condition": ("missing_info", "requirements", "next_step"),
        "eligibility_gap": ("reasons", "requirements", "next_step"),
        "personal_fit": ("summary", "reasons", "requirements", "next_step"),
    },
    "apply_how": {
        "deadline_risk": ("period", "method", "links", "documents", "contact", "next_step"),
        "application_channel": ("method", "links", "period", "documents", "contact", "next_step"),
        "next_step": ("method", "period", "links", "documents", "contact", "next_step"),
    },
    "overview": {
        "policy_summary": ("summary", "eligibility", "amount", "method", "next_step"),
    },
}

# 계획기와 모든 렌더러(/chat·/agent/converse)가 공유하는 정규 섹션 키 계약.
# 렌더러는 반드시 이 키로 섹션을 구성해야 ordered_section_keys()가 계획을 보존한다.
SECTION_KEYS = frozenset(
    key
    for focus_map in _SECTION_ORDERS.values()
    for order in focus_map.values()
    for key in order
)

_FOLLOW_UP_CANDIDATES = {
    "docs": ("eligibility", "benefit", "create_apply_plan"),
    "benefit": ("eligibility", "docs", "create_apply_plan"),
    "eligibility": ("docs", "benefit", "create_apply_plan"),
    "apply_how": ("docs", "create_apply_plan", "contact"),
    "overview": ("eligibility", "docs", "apply_how"),
}

_ACTION_ORDERS = {
    "docs": ("benefit", "eligibility", "create_apply_plan"),
    "benefit": ("eligibility", "docs", "create_apply_plan"),
    "eligibility": ("docs", "benefit", "create_apply_plan"),
    "apply_how": ("docs", "benefit", "create_apply_plan"),
    "overview": ("eligibility", "docs", "apply_how"),
}


@dataclass(frozen=True)
class ResponsePlan:
    focus: str
    section_order: tuple[str, ...]
    detail_level: str
    opening_variant: str
    repetition_mode: str
    follow_up_kind: str
    suggested_action_order: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["section_order"] = list(self.section_order)
        data["suggested_action_order"] = list(self.suggested_action_order)
        return data


class ResponsePlanner:
    def plan(
        self,
        *,
        policy_context: dict[str, Any],
        intent: str,
        question: str,
        user_context: dict[str, Any] | None,
        conversation_context: list[dict[str, Any]] | None,
    ) -> ResponsePlan:
        canonical_intent = _INTENT_ALIASES.get(intent, intent)
        if canonical_intent not in _SECTION_ORDERS:
            canonical_intent = "overview"

        history = conversation_context or []
        normalized_question = self._normalize(question)
        previous_user_question = self._latest_user_question(history)
        previous_intent = self._latest_assistant_intent(history)
        repetition_mode = self._repetition_mode(
            canonical_intent=canonical_intent,
            normalized_question=normalized_question,
            previous_question=previous_user_question,
            previous_intent=previous_intent,
        )
        focus = self._focus(
            intent=canonical_intent,
            question=normalized_question,
            user_context=user_context or {},
            repetition_mode=repetition_mode,
        )
        detail_level = self._detail_level(normalized_question, repetition_mode)
        follow_up_kind = self._follow_up_kind(
            intent=canonical_intent,
            user_context=user_context or {},
            history=history,
        )
        policy_key = str(
            policy_context.get("doc_id")
            or f"{policy_context.get('source_table', '')}:{policy_context.get('source_id', '')}"
        )
        opening_variant = self._stable_variant(
            policy_key,
            canonical_intent,
            focus,
            repetition_mode,
            detail_level,
        )
        return ResponsePlan(
            focus=focus,
            section_order=_SECTION_ORDERS[canonical_intent][focus],
            detail_level=detail_level,
            opening_variant=opening_variant,
            repetition_mode=repetition_mode,
            follow_up_kind=follow_up_kind,
            suggested_action_order=_ACTION_ORDERS[canonical_intent],
        )

    def _normalize(self, text: str) -> str:
        return re.sub(r"\s+", " ", str(text or "").strip().lower())

    def _latest_user_question(self, history: list[dict[str, Any]]) -> str:
        for turn in reversed(history):
            if turn.get("role") == "user":
                return self._normalize(turn.get("content", ""))
        return ""

    def _latest_assistant_intent(self, history: list[dict[str, Any]]) -> str:
        for index in range(len(history) - 1, -1, -1):
            turn = history[index]
            if turn.get("role") != "assistant":
                continue
            intent = str(turn.get("intent") or "")
            if not intent:
                payload = turn.get("payload") or {}
                intent = str(payload.get("intent") or "")
            if intent:
                return _INTENT_ALIASES.get(intent, intent)
            for previous in reversed(history[:index]):
                if previous.get("role") == "user":
                    return self._infer_intent(previous.get("content", ""))
        return ""

    def _infer_intent(self, text: str) -> str:
        normalized = self._normalize(text)
        for intent, words in _INTENT_WORDS.items():
            if any(word in normalized for word in words):
                return intent
        return "overview"

    def _repetition_mode(
        self,
        *,
        canonical_intent: str,
        normalized_question: str,
        previous_question: str,
        previous_intent: str,
    ) -> str:
        if previous_intent != canonical_intent:
            return "fresh"
        if normalized_question and normalized_question == previous_question:
            return "confirm"
        if any(word in normalized_question for word in _SPECIFIC_WORDS):
            return "clarify"
        return "deepen"

    def _focus(
        self,
        *,
        intent: str,
        question: str,
        user_context: dict[str, Any],
        repetition_mode: str,
    ) -> str:
        if intent == "docs":
            if any(word in question for word in ("발급", "어디서", "준비처")):
                return "issuance"
            if any(word in question for word in ("마감", "언제까지", "기간")):
                return "deadline_risk"
            return "document_preparation"
        if intent == "benefit":
            if any(word in question for word in ("총", "얼마", "금액")):
                return "total_amount"
            if any(word in question for word in ("기간", "개월", "언제까지")):
                return "duration"
            if any(word in question for word in ("내가", "나는", "받을 수")):
                return "personal_fit"
            return "core_benefit"
        if intent == "eligibility":
            if not self._has_minimum_profile(user_context):
                return "missing_user_condition"
            if repetition_mode in {"clarify", "deepen"}:
                return "eligibility_gap"
            return "personal_fit"
        if intent == "apply_how":
            if any(word in question for word in ("마감", "기간", "언제")):
                return "deadline_risk"
            if any(word in question for word in ("어디", "온라인", "방문", "링크", "접수")):
                return "application_channel"
            return "next_step"
        return "policy_summary"

    def _has_minimum_profile(self, user_context: dict[str, Any]) -> bool:
        has_age = user_context.get("age") not in (None, "")
        has_region = bool(user_context.get("region") or user_context.get("region_sido"))
        return has_age and has_region

    def _detail_level(self, question: str, repetition_mode: str) -> str:
        if repetition_mode == "confirm":
            return "compact"
        if any(word in question for word in _SPECIFIC_WORDS):
            return "focused"
        return "standard"

    def _used_follow_up_kinds(self, history: list[dict[str, Any]]) -> set[str]:
        used: set[str] = set()
        for turn in history:
            payload = turn.get("payload") or {}
            meta = payload.get("response_plan_meta") or {}
            kind = meta.get("follow_up_kind")
            if kind:
                used.add(str(kind))
            if turn.get("role") == "user":
                inferred_intent = self._infer_intent(turn.get("content", ""))
                candidates = _FOLLOW_UP_CANDIDATES.get(inferred_intent, ())
                if candidates:
                    used.add(candidates[0])
        return used

    def _follow_up_kind(
        self,
        *,
        intent: str,
        user_context: dict[str, Any],
        history: list[dict[str, Any]],
    ) -> str:
        if intent == "eligibility" and not self._has_minimum_profile(user_context):
            return "missing_user_condition"
        used = self._used_follow_up_kinds(history)
        for candidate in _FOLLOW_UP_CANDIDATES[intent]:
            if candidate not in used:
                return candidate
        return _FOLLOW_UP_CANDIDATES[intent][0]

    def _stable_variant(self, *parts: str) -> str:
        raw = "|".join(str(part) for part in parts)
        index = int(hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8], 16) % 3
        return ("direct", "guided", "concise")[index]
