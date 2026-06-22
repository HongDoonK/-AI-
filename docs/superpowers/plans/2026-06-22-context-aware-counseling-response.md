# Context-Aware Counseling Response Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 추천 이후의 `/chat`과 정책 선택 후 `/agent/converse`가 정책 사실을 바꾸지 않으면서 질문·사용자 조건·대화 이력에 따라 답변 초점, 섹션 순서, 설명 깊이, 후속 질문을 결정론적으로 달리하도록 만든다.

**Architecture:** 새 `ResponsePlanner`가 현재 질문과 최근 상담 이력에서 표현 계획만 계산하고, 새 공통 렌더링 유틸리티가 계획을 도입 문장·섹션 순서·항목 수·후속 질문·액션 순서에 적용한다. 정책 금액, 기간, 자격, 서류, URL은 기존 `PolicyChatAgent`, `ApplyAgent`, `BenefitEstimator`가 계속 계산하며 추천 엔진과 `/recommend`는 변경하지 않는다.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, SQLite, `unittest`/pytest, 기존 공급자 무관 LLM 어댑터

---

## Scope Guard

다음 파일과 흐름만 변경한다.

- 신규 계획 계층: `ai/response_planner.py`
- 신규 표현 유틸리티: `ai/response_renderer.py`
- 선택 정책 상담: `ai/policy_chat_agent.py`
- 대화형 상담: `ai/converse_agent.py`
- 세션 이력 전달 및 내부 계획 메타 저장: `backend/main.py`
- 관련 테스트와 README

다음은 변경하지 않는다.

- `ai/recommender.py`, `ai/retriever.py`, `ai/generator.py`
- `POST /recommend`의 검색, 순위, 추천 카드 생성
- `ai/benefit_estimator.py`의 수치 계산
- `ai/apply_agent.py`의 서류·신청 플랜 계산
- `backend/models.py`의 공개 API 스키마
- `ai/llm_client.py`의 temperature 또는 sampling 설정

## File Map

| File | Responsibility |
|---|---|
| `ai/response_planner.py` | 질문·정책·사용자 조건·최근 턴을 결정론적 `ResponsePlan`으로 변환 |
| `ai/response_renderer.py` | 계획에 맞는 도입부, 섹션 정렬, 항목 제한, 후속 질문, 액션 정렬 |
| `tests/test_response_planner.py` | 동일 맥락 안정성, 반복 질문 분류, 개인화 부족, 초점 선택 |
| `tests/test_response_renderer.py` | 계획에 따른 표현 및 순서 변경 검증 |
| `ai/policy_chat_agent.py` | `/chat`에서 공통 계획기를 LLM 및 규칙 경로 모두에 적용 |
| `tests/test_policy_chat_agent.py` | `/chat` LLM-off 다양화, 사실 보존, LLM 프롬프트 계획 전달 |
| `ai/converse_agent.py` | 정책 선택 이후 docs/benefit/eligibility/apply_how 답변을 계획 기반으로 렌더링 |
| `backend/main.py` | 기존 세션 턴을 Agent에 전달하고 계획 메타를 assistant 턴 payload에만 저장 |
| `tests/test_converse_agent.py` | 구조화 필드 보존과 맥락별 답변 변화 검증 |
| `tests/test_converse_api_smoke.py` | 멀티턴 계획 메타 저장, 직접 응답 비노출, 추천 경계 보존 |
| `README.md` | 상담 응답 다양화 원칙과 LLM-off 동작 설명 |

### Task 1: Deterministic ResponsePlanner

**Files:**
- Create: `ai/response_planner.py`
- Create: `tests/test_response_planner.py`

- [ ] **Step 1: Write the failing planner tests**

Create `tests/test_response_planner.py`:

```python
import unittest

from ai.response_planner import ResponsePlan, ResponsePlanner


POLICY = {
    "doc_id": "policies_processed:P001",
    "source_table": "policies_processed",
    "source_id": "P001",
    "domain": "policy_housing",
}


class ResponsePlannerTest(unittest.TestCase):
    def setUp(self):
        self.planner = ResponsePlanner()

    def test_same_context_returns_same_plan(self):
        kwargs = {
            "policy_context": POLICY,
            "intent": "benefit",
            "question": "그래서 총 얼마 받을 수 있어?",
            "user_context": {"age": 24, "region_sido": "서울"},
            "conversation_context": [],
        }
        self.assertEqual(self.planner.plan(**kwargs), self.planner.plan(**kwargs))

    def test_specific_benefit_question_focuses_total_amount(self):
        plan = self.planner.plan(
            policy_context=POLICY,
            intent="benefit",
            question="총 얼마 받을 수 있어?",
            user_context={},
            conversation_context=[],
        )
        self.assertEqual(plan.focus, "total_amount")
        self.assertEqual(plan.section_order[0], "amount")
        self.assertEqual(plan.detail_level, "focused")

    def test_missing_profile_focuses_required_user_information(self):
        plan = self.planner.plan(
            policy_context=POLICY,
            intent="eligibility",
            question="내가 신청 가능해?",
            user_context={},
            conversation_context=[],
        )
        self.assertEqual(plan.focus, "missing_user_condition")
        self.assertEqual(plan.follow_up_kind, "missing_user_condition")
        self.assertEqual(plan.section_order[0], "missing_info")

    def test_exact_repeat_becomes_confirm(self):
        history = [
            {"role": "user", "content": "필요한 서류가 뭐야?"},
            {
                "role": "assistant",
                "intent": "docs",
                "content": "서류 안내",
                "payload": {
                    "response_plan_meta": {
                        "focus": "document_preparation",
                        "repetition_mode": "fresh",
                    }
                },
            },
        ]
        plan = self.planner.plan(
            policy_context=POLICY,
            intent="docs",
            question="필요한 서류가 뭐야?",
            user_context={},
            conversation_context=history,
        )
        self.assertEqual(plan.repetition_mode, "confirm")
        self.assertEqual(plan.detail_level, "compact")

    def test_more_specific_repeat_becomes_clarify(self):
        history = [
            {"role": "user", "content": "필요한 서류가 뭐야?"},
            {"role": "assistant", "intent": "docs", "content": "서류 안내", "payload": None},
        ]
        plan = self.planner.plan(
            policy_context=POLICY,
            intent="docs",
            question="주민등록등본은 어디서 발급해?",
            user_context={},
            conversation_context=history,
        )
        self.assertEqual(plan.repetition_mode, "clarify")
        self.assertEqual(plan.focus, "issuance")
        self.assertEqual(plan.section_order[0], "issuance")

    def test_previous_follow_up_kind_is_not_reused_when_alternative_exists(self):
        history = [
            {
                "role": "assistant",
                "intent": "docs",
                "content": "서류 안내",
                "payload": {
                    "response_plan_meta": {
                        "follow_up_kind": "eligibility",
                    }
                },
            }
        ]
        plan = self.planner.plan(
            policy_context=POLICY,
            intent="docs",
            question="서류 알려줘",
            user_context={"age": 24, "region_sido": "서울"},
            conversation_context=history,
        )
        self.assertNotEqual(plan.follow_up_kind, "eligibility")

    def test_apply_deadline_question_puts_period_first(self):
        plan = self.planner.plan(
            policy_context=POLICY,
            intent="apply_how",
            question="신청 마감이 언제야?",
            user_context={},
            conversation_context=[],
        )
        self.assertEqual(plan.focus, "deadline_risk")
        self.assertEqual(plan.section_order[0], "period")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the planner tests and verify they fail**

Run:

```powershell
python -m pytest tests/test_response_planner.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'ai.response_planner'`.

- [ ] **Step 3: Implement the complete deterministic planner**

Create `ai/response_planner.py`:

```python
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
        "policy_summary": ("summary", "eligibility", "benefit", "apply", "next_step"),
    },
}

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
```

- [ ] **Step 4: Run the planner tests and verify they pass**

Run:

```powershell
python -m pytest tests/test_response_planner.py -q
```

Expected: `7 passed`.

- [ ] **Step 5: Commit the planner**

```powershell
git add ai/response_planner.py tests/test_response_planner.py
git commit -m "feat: 상담 응답 계획기 추가"
```

### Task 2: Shared Deterministic Renderer

**Files:**
- Create: `ai/response_renderer.py`
- Create: `tests/test_response_renderer.py`

- [ ] **Step 1: Write failing renderer tests**

Create `tests/test_response_renderer.py`:

```python
import unittest

from ai.response_planner import ResponsePlan
from ai.response_renderer import (
    order_actions,
    ordered_section_keys,
    render_follow_up,
    render_opening,
    section_item_limit,
)


class ResponseRendererTest(unittest.TestCase):
    def _plan(self, **overrides):
        values = {
            "focus": "total_amount",
            "section_order": ("amount", "duration", "next_step"),
            "detail_level": "focused",
            "opening_variant": "direct",
            "repetition_mode": "fresh",
            "follow_up_kind": "eligibility",
            "suggested_action_order": ("eligibility", "docs", "create_apply_plan"),
        }
        values.update(overrides)
        return ResponsePlan(**values)

    def test_section_order_uses_plan_and_keeps_unknown_sections_last(self):
        plan = self._plan()
        keys = ordered_section_keys(plan, {"duration", "amount", "contact"})
        self.assertEqual(keys, ["amount", "duration", "contact"])

    def test_compact_repeat_limits_items(self):
        plan = self._plan(detail_level="compact", repetition_mode="confirm")
        self.assertEqual(section_item_limit(plan), 2)

    def test_opening_changes_for_confirm_mode(self):
        plan = self._plan(repetition_mode="confirm")
        opening = render_opening("청년 월세 지원", "benefit", plan)
        self.assertIn("다시 핵심만", opening)

    def test_follow_up_is_selected_from_plan(self):
        plan = self._plan(follow_up_kind="eligibility")
        self.assertIn("조건", render_follow_up(plan, "통합청년 정책"))

    def test_actions_follow_planned_order(self):
        plan = self._plan()
        actions = [
            {"label": "서류", "intent": "docs"},
            {"label": "준비", "action": "create_apply_plan"},
            {"label": "자격", "intent": "eligibility"},
        ]
        ordered = order_actions(actions, plan)
        self.assertEqual([item.get("intent") or item.get("action") for item in ordered],
                         ["eligibility", "docs", "create_apply_plan"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run renderer tests and verify failure**

Run:

```powershell
python -m pytest tests/test_response_renderer.py -q
```

Expected: collection fails with `ModuleNotFoundError: No module named 'ai.response_renderer'`.

- [ ] **Step 3: Implement renderer helpers**

Create `ai/response_renderer.py`:

```python
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
```

- [ ] **Step 4: Run renderer and planner tests**

Run:

```powershell
python -m pytest tests/test_response_planner.py tests/test_response_renderer.py -q
```

Expected: `12 passed`.

- [ ] **Step 5: Commit renderer**

```powershell
git add ai/response_renderer.py tests/test_response_renderer.py
git commit -m "feat: 상담 응답 렌더링 유틸 추가"
```

### Task 3: Apply the Plan to `/chat`

**Files:**
- Modify: `ai/policy_chat_agent.py:37-83`
- Modify: `ai/policy_chat_agent.py:407-583`
- Create: `tests/test_policy_chat_agent.py`

- [ ] **Step 1: Write failing `/chat` planning tests**

Create `tests/test_policy_chat_agent.py`:

```python
import unittest
from unittest import mock

from tests.util_fixture import set_test_env

set_test_env()

from ai.policy_chat_agent import PolicyChatAgent


P001 = {
    "doc_id": "policies_processed:P001",
    "source_table": "policies_processed",
    "source_id": "P001",
    "policy_name": "청년 월세 지원",
}


class PolicyChatAgentTest(unittest.TestCase):
    def setUp(self):
        self.agent = PolicyChatAgent()

    def test_same_context_has_stable_rule_answer(self):
        messages = [{"role": "user", "content": "총 얼마 받을 수 있어?"}]
        first = self.agent.answer(policy=P001, user_context={}, messages=messages)
        second = self.agent.answer(policy=P001, user_context={}, messages=messages)
        self.assertEqual(first["answer"], second["answer"])
        self.assertEqual(first["suggested_questions"], second["suggested_questions"])

    def test_follow_up_context_changes_structure_but_keeps_policy_identity(self):
        broad = self.agent.answer(
            policy=P001,
            user_context={},
            messages=[{"role": "user", "content": "필요한 서류가 뭐야?"}],
        )
        specific = self.agent.answer(
            policy=P001,
            user_context={},
            messages=[
                {"role": "user", "content": "필요한 서류가 뭐야?"},
                {"role": "assistant", "content": broad["answer"]},
                {"role": "user", "content": "그 서류는 어디서 발급해?"},
            ],
        )
        self.assertNotEqual(broad["answer"], specific["answer"])
        self.assertEqual(broad["policy_context"]["doc_id"], specific["policy_context"]["doc_id"])
        self.assertIn("구체적으로", specific["answer"])

    def test_missing_profile_asks_for_user_conditions_first(self):
        result = self.agent.answer(
            policy=P001,
            user_context={},
            messages=[{"role": "user", "content": "내가 신청 가능해?"}],
        )
        self.assertIn("나이", result["answer"])
        self.assertIn("거주 지역", result["answer"])

    def test_llm_prompt_contains_response_plan(self):
        with mock.patch(
            "ai.policy_chat_agent.create_chat_response",
            return_value="계획에 따른 답변",
        ) as create:
            result = self.agent.answer(
                policy=P001,
                user_context={"age": 24, "region_sido": "서울"},
                messages=[{"role": "user", "content": "총 얼마 받을 수 있어?"}],
            )
        self.assertEqual(result["answer"], "계획에 따른 답변")
        self.assertIn("응답 계획", create.call_args.kwargs["system_prompt"])
        self.assertIn("total_amount", create.call_args.kwargs["system_prompt"])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify the plan assertions fail**

Run:

```powershell
python -m pytest tests/test_policy_chat_agent.py -q
```

Expected: at least the context-specific structure and LLM prompt assertions fail because `PolicyChatAgent` does not yet create a `ResponsePlan`.

- [ ] **Step 3: Add planner and renderer dependencies to `PolicyChatAgent`**

At the import block in `ai/policy_chat_agent.py`, add:

```python
from ai.response_planner import ResponsePlan, ResponsePlanner
from ai.response_renderer import (
    ordered_section_keys,
    render_follow_up,
    render_opening,
    section_item_limit,
)
```

Replace the constructor with:

```python
def __init__(self, response_planner: ResponsePlanner | None = None):
    self.db_path = find_db_path()
    self._context_cache: dict[str, dict[str, Any]] = {}
    self.response_planner = response_planner or ResponsePlanner()
```

- [ ] **Step 4: Build one plan per `/chat` answer and share it across both generation paths**

In `PolicyChatAgent.answer()`, after `policy_context` is loaded, calculate the intent and plan before `suggested_questions`:

```python
intents = self._detect_intents(question)
primary_intent = intents[0] if intents else "overview"
conversation_context = [
    {"role": message["role"], "content": message["content"]}
    for message in normalized_messages[:-1]
]
response_plan = self.response_planner.plan(
    policy_context=policy_context,
    intent=primary_intent,
    question=question,
    user_context=user_context or {},
    conversation_context=conversation_context,
)
base_questions = self._suggest_questions(policy_context)
planned_follow_up = render_follow_up(response_plan, policy_context.get("source_label", "정책 DB"))
suggested_questions = [
    planned_follow_up,
    *(item for item in base_questions if item != planned_follow_up),
][:3]
```

Pass `response_plan=response_plan` to `_llm_answer()` and `_rule_answer()`. Update both signatures:

```python
def _llm_answer(
    self,
    *,
    policy_context: dict[str, Any],
    user_context: dict[str, Any],
    messages: list[dict[str, str]],
    response_plan: ResponsePlan,
) -> str:
```

```python
def _rule_answer(
    self,
    question: str,
    policy_context: dict[str, Any],
    user_context: dict[str, Any],
    response_plan: ResponsePlan,
) -> str:
```

Use these exact calls in `answer()`:

```python
answer = self._llm_answer(
    policy_context=policy_context,
    user_context=user_context or {},
    messages=normalized_messages,
    response_plan=response_plan,
)
```

```python
answer = self._rule_answer(
    question,
    policy_context,
    user_context or {},
    response_plan,
)
```

Keep the existing empty-question early return before planning.

- [ ] **Step 5: Put the plan into the grounded LLM prompt**

Append this text to the existing `system_prompt` in `_llm_answer()`:

```python
system_prompt += (
    "\n\n이번 턴의 응답 계획:\n"
    f"{json.dumps(response_plan.to_dict(), ensure_ascii=False)}\n"
    "focus를 첫 부분에서 다루고 section_order 순서로 설명하라. "
    "detail_level이 compact면 이미 설명한 내용을 짧게 확인하고, focused면 질문한 세부사항에 집중하라. "
    "repetition_mode가 confirm이면 장황하게 반복하지 말고 핵심만 재확인하라. "
    "마지막 질문은 follow_up_kind에 해당하는 한 가지 질문만 사용하라. "
    "이 계획은 표현 순서만 정하며 새로운 정책 사실을 만들 권한을 주지 않는다."
)
```

Do not change `create_chat_response()` or any sampling parameter.

- [ ] **Step 6: Apply the plan to rule-based structured and application answers**

Update `_apply_detail_answer()` and `_structured_answer()` to accept `response_plan: ResponsePlan`.

Use these signatures:

```python
def _apply_detail_answer(
    self,
    title: str,
    policy_context: dict[str, Any],
    source_label: str,
    intents: list[str],
    response_plan: ResponsePlan,
) -> str:
```

```python
def _structured_answer(
    self,
    title: str,
    policy_context: dict[str, Any],
    source_label: str,
    intents: list[str],
    user_context: dict[str, Any],
    response_plan: ResponsePlan,
) -> str:
```

Use this complete section assembly pattern in `_apply_detail_answer()`:

```python
sections = {
    "method": ("신청 방법", detail["method"]),
    "period": ("신청 기간", detail["period"]),
    "links": ("신청 링크", detail["links"]),
    "documents": ("준비물/서류", detail["docs"]),
    "contact": ("문의처/담당 기관", detail["contact"]),
    "next_step": ("확인 필요", detail["notes"]),
}
limit = section_item_limit(response_plan)
lines = [render_opening(title, "apply_how", response_plan)]
for key in ordered_section_keys(response_plan, sections):
    heading, items = sections[key]
    if not items:
        continue
    lines.append(f"\n{heading}")
    lines.extend(f"- {item}" for item in items[:limit])
lines.append(f"\n{render_follow_up(response_plan, source_label)}")
return "\n".join(lines)
```

Use this complete section assembly pattern in `_structured_answer()`:

```python
sections = {
    "personal_fit": ("내 조건 기준 체크", personal_fit),
    "documents": ("필요한 서류", summary["docs"]),
    "eligibility": ("조건", summary["eligibility"]),
    "benefit": ("지원 받을 수 있는 내용(금액)", summary["benefit"]),
    "apply": ("신청 방법/기간", summary["apply"]),
    "notes": ("확인 필요", summary["notice"]),
}
limit = section_item_limit(response_plan)
lines = [render_opening(title, intents[0] if intents else "overview", response_plan)]
for key in ordered_section_keys(response_plan, sections):
    heading, items = sections[key]
    if not items:
        continue
    lines.append(f"\n{heading}")
    lines.extend(f"- {item}" for item in items[:limit])
lines.append(f"\n{render_follow_up(response_plan, source_label)}")
return "\n".join(lines)
```

For the generic `_rule_answer()` path:

```python
facts = policy_context.get("facts", {})
summary = policy_context.get("policy_profile") or self._build_user_summary(policy_context)
personal_fit = self._build_personal_fit(policy_context, user_context, summary)
sections: dict[str, tuple[str, list[str]]] = {}
section_keys = {
    "docs": "documents",
    "benefit": "amount",
    "eligibility": "eligibility",
    "apply": "method",
    "period": "period",
    "contact": "contact",
    "overview": "summary",
}
if personal_fit:
    sections["personal_fit"] = ("내 조건 기준 체크", personal_fit)
for intent in intents[:3]:
    values = facts.get(intent, [])
    if values:
        sections[section_keys.get(intent, intent)] = ("", values)

limit = section_item_limit(response_plan)
lines = [render_opening(title, intents[0], response_plan)]
for key in ordered_section_keys(response_plan, sections):
    heading, items = sections[key]
    if heading:
        lines.append(f"\n{heading}")
    lines.extend(item if item.startswith("- ") else f"- {item}" for item in items[:limit])

if not any(line.startswith("- ") for line in lines):
    lines.append("- DB에 세부 정보가 부족해 상세 공고나 담당 기관 확인이 필요합니다.")
url = policy_context.get("url")
if url and not any("링크" in line or "URL" in line for line in lines):
    lines.append(f"- 확인 링크: {url}")
lines.append(f"\n{render_follow_up(response_plan, source_label)}")
return "\n".join(lines)
```

When calling `_apply_detail_answer()` and `_structured_answer()`, pass `response_plan`.

Use these exact calls:

```python
return self._apply_detail_answer(
    title,
    policy_context,
    source_label,
    intents,
    response_plan,
)
```

```python
return self._structured_answer(
    title,
    policy_context,
    source_label,
    intents,
    user_context,
    response_plan,
)
```

- [ ] **Step 7: Run focused `/chat` tests**

Run:

```powershell
python -m pytest tests/test_policy_chat_agent.py tests/test_api_smoke.py tests/test_llm_client.py -q
```

Expected: all tests pass. The exact count may include existing tests, but there must be zero failures.

- [ ] **Step 8: Commit `/chat` integration**

```powershell
git add ai/policy_chat_agent.py tests/test_policy_chat_agent.py
git commit -m "feat: 정책 상담에 맥락 기반 응답 계획 적용"
```

### Task 4: Apply the Plan to `/agent/converse` and Persist Internal Context

**Files:**
- Modify: `ai/converse_agent.py:102-303`
- Modify: `backend/main.py:252-318`
- Modify: `tests/test_converse_agent.py`
- Modify: `tests/test_converse_api_smoke.py`

- [ ] **Step 1: Add failing Agent-level tests**

Append to `tests/test_converse_agent.py`:

```python
    def test_docs_response_plan_changes_on_specific_follow_up_without_changing_documents(self):
        first = self.agent.respond(
            message="필요한 서류가 뭐야?",
            selected_policy=P001,
            last_recommendations=[P001],
            profile={"age": 26, "region_sido": "서울"},
            conversation_context=[],
        )
        history = [
            {"role": "user", "content": "필요한 서류가 뭐야?"},
            {
                "role": "assistant",
                "intent": "docs",
                "content": first["reply"],
                "payload": {"response_plan_meta": first["_response_plan_meta"]},
            },
        ]
        second = self.agent.respond(
            message="그 서류는 어디서 발급해?",
            selected_policy=P001,
            last_recommendations=[P001],
            profile={"age": 26, "region_sido": "서울"},
            conversation_context=history,
        )
        self.assertEqual(first["documents"], second["documents"])
        self.assertNotEqual(first["reply"], second["reply"])
        self.assertEqual(second["_response_plan_meta"]["focus"], "issuance")

    def test_benefit_structured_value_is_unchanged_by_history(self):
        first = self.agent.respond(
            message="얼마 받을 수 있어?",
            selected_policy=P001,
            last_recommendations=[P001],
            profile=None,
            conversation_context=[],
        )
        second = self.agent.respond(
            message="총액만 다시 알려줘",
            selected_policy=P001,
            last_recommendations=[P001],
            profile=None,
            conversation_context=[
                {"role": "user", "content": "얼마 받을 수 있어?"},
                {
                    "role": "assistant",
                    "intent": "benefit",
                    "content": first["reply"],
                    "payload": {"response_plan_meta": first["_response_plan_meta"]},
                },
            ],
        )
        self.assertEqual(first["benefit"], second["benefit"])
        self.assertEqual(second["benefit"]["monthly_won"], 200_000)
        self.assertEqual(second["benefit"]["months"], 12)
```

- [ ] **Step 2: Add failing API-level metadata tests**

Append to `tests/test_converse_api_smoke.py`:

```python
    def test_response_plan_meta_is_stored_in_history_but_not_returned_publicly(self):
        selected = self.client.post(
            "/agent/converse",
            json={"message": "", "policy": SEEDED_POLICY},
        ).json()
        session_id = selected["session_id"]

        response = self._say("필요한 서류가 뭐야?", session_id=session_id)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_response_plan_meta", response.json())
        self.assertNotIn("response_plan_meta", response.json())

        turns = self.client.get(f"/agent/converse/{session_id}").json()["turns"]
        assistant_turn = next(
            turn for turn in reversed(turns)
            if turn["role"] == "assistant" and turn["intent"] == "docs"
        )
        self.assertIn("response_plan_meta", assistant_turn["payload"])

    def test_multiturn_follow_up_changes_focus_without_changing_selected_policy(self):
        selected = self.client.post(
            "/agent/converse",
            json={"message": "", "policy": SEEDED_POLICY},
        ).json()
        session_id = selected["session_id"]
        first = self._say("필요한 서류가 뭐야?", session_id=session_id).json()
        second = self._say("그 서류는 어디서 발급해?", session_id=session_id).json()
        self.assertEqual(first["selected_policy"]["doc_id"], second["selected_policy"]["doc_id"])
        self.assertEqual(first["documents"], second["documents"])
        self.assertNotEqual(first["reply"], second["reply"])
```

- [ ] **Step 3: Run focused tests and verify failure**

Run:

```powershell
python -m pytest tests/test_converse_agent.py tests/test_converse_api_smoke.py -q
```

Expected: failures report that `ConverseAgent.respond()` does not accept `conversation_context` and no response plan metadata exists.

- [ ] **Step 4: Inject the shared planner into `ConverseAgent`**

Add imports to `ai/converse_agent.py`:

```python
from ai.response_planner import ResponsePlanner
from ai.response_renderer import (
    order_actions,
    ordered_section_keys,
    render_follow_up,
    render_opening,
    section_item_limit,
)
```

Replace the constructor:

```python
def __init__(
    self,
    chat_agent: PolicyChatAgent | None = None,
    apply_agent: ApplyAgent | None = None,
    response_planner: ResponsePlanner | None = None,
):
    self.chat_agent = chat_agent or PolicyChatAgent()
    self.apply_agent = apply_agent or ApplyAgent(chat_agent=self.chat_agent)
    self.response_planner = response_planner or ResponsePlanner()
```

Add the optional argument to `respond()`:

```python
conversation_context: list[dict[str, Any]] | None = None,
```

Replace the relevant `respond()` calls with:

```python
if intent == SELECT:
    return self._handle_select(
        message,
        selected_policy,
        last_recommendations,
        profile,
        conversation_context or [],
    )
if intent in _NEEDS_SELECT_INTENTS:
    policy = self._resolve_policy(message, selected_policy, last_recommendations)
    if not policy:
        return self._need_select(last_recommendations, intent)
    return self._handle_policy_intent(
        intent,
        policy,
        profile,
        last_recommendations,
        message,
        conversation_context or [],
    )
```

Replace `_handle_select()` with this signature and follow-up dispatch:

```python
def _handle_select(
    self,
    message: str,
    selected_policy: dict[str, Any] | None,
    last_recommendations: list[dict[str, Any]],
    profile: dict[str, Any] | None,
    conversation_context: list[dict[str, Any]],
) -> dict[str, Any]:
    policy = self._resolve_policy(message, selected_policy, last_recommendations)
    if not policy:
        return self._need_select(last_recommendations, SELECT)
    followup_intent = _followup_intent_after_selection(message)
    if followup_intent:
        return self._handle_policy_intent(
            followup_intent,
            policy,
            profile,
            last_recommendations,
            message,
            conversation_context,
        )
    return self.select(policy)
```

Replace `_handle_policy_intent()` with this signature:

```python
def _handle_policy_intent(
    self,
    intent: str,
    policy: dict[str, Any],
    profile: dict[str, Any] | None,
    last_recommendations: list[dict[str, Any]],
    message: str,
    conversation_context: list[dict[str, Any]],
) -> dict[str, Any]:
```

Do not invoke the planner for `NEED_RECOMMENDATION`, `need_select`, a plain `SELECT`, or `UNCLEAR`.

- [ ] **Step 5: Build one plan inside `_handle_policy_intent()`**

Add `message` and `conversation_context` parameters to `_handle_policy_intent()`. Immediately after loading `context`, add:

```python
response_plan = self.response_planner.plan(
    policy_context=context,
    intent=intent,
    question=message,
    user_context=profile or {},
    conversation_context=conversation_context,
)
plan_meta = response_plan.to_dict()
base = {
    "intent": intent,
    "selected_policy": policy,
    "_response_plan_meta": plan_meta,
}
```

Every return path from `_handle_policy_intent()` must retain `_response_plan_meta`.

Add this helper method to `ConverseAgent` so all four intent paths use one rendering sequence:

```python
def _render_planned_sections(
    self,
    *,
    title: str,
    intent: str,
    response_plan: ResponsePlan,
    sections: dict[str, tuple[str, list[str]]],
    source_label: str,
) -> str:
    limit = section_item_limit(response_plan)
    lines = [render_opening(title, intent, response_plan)]
    for key in ordered_section_keys(response_plan, sections):
        heading, items = sections[key]
        if not items:
            continue
        if heading:
            lines.append(f"\n{heading}")
        lines.extend(f"  - {item}" for item in items[:limit])
    lines.append(f"\n{render_follow_up(response_plan, source_label)}")
    return "\n".join(lines)
```

- [ ] **Step 6: Replace the four hard-coded reply assemblers with planned sections**

For `DOCS`, preserve the existing `documents`, `apply_channel`, and `apply_url`, but render:

```python
sections = {
    "documents": (
        "준비 서류",
        [
            f"{doc['label']} → {doc['help_label'] or '공고/담당 기관에서 확인'}"
            + (f" ({doc['help_url']})" if doc.get("help_url") else "")
            for doc in documents
        ],
    ),
    "issuance": (
        "발급처 확인",
        [
            f"{doc['label']}: {doc['help_label'] or '공고/담당 기관에서 확인'}"
            for doc in documents
        ] if response_plan.focus == "issuance" else [],
    ),
    "apply_link": (
        "신청 페이지",
        [plan["apply_url"]] if plan.get("apply_url") else [],
    ),
    "next_step": (
        "다음 행동",
        [plan["next_action"]] if plan.get("next_action") else [],
    ),
}
reply = self._render_planned_sections(
    title=title,
    intent=intent,
    response_plan=response_plan,
    sections=sections,
    source_label=context.get("source_label", "정책 DB"),
)
actions = order_actions(
    [
        _action("얼마 받는지 보기", intent=BENEFIT),
        _action("신청 자격 확인", intent=ELIGIBILITY),
        _action("신청 준비 시작", action="create_apply_plan"),
    ],
    response_plan,
)
return {
    **base,
    "reply": reply,
    "documents": documents,
    "apply_channel": plan.get("apply_channel"),
    "apply_url": plan.get("apply_url"),
    "suggested_actions": actions,
}
```

For `BENEFIT`, preserve the entire `benefit` dictionary and render:

```python
sections = {
    "summary": (
        "",
        [benefit["summary_line"]] if response_plan.focus == "core_benefit" else [],
    ),
    "amount": ("지원 금액", [benefit["summary_line"]]),
    "duration": (
        "지원 기간",
        [f"{benefit['months']}개월"] if benefit.get("months") else [],
    ),
    "eligibility": (
        "추가 확인",
        ["실제 수령 여부는 정책 자격 조건 확인이 필요합니다."],
    ),
}
reply = self._render_planned_sections(
    title=title,
    intent=intent,
    response_plan=response_plan,
    sections=sections,
    source_label=context.get("source_label", "정책 DB"),
)
actions = order_actions(
    [
        _action("신청 자격 확인", intent=ELIGIBILITY),
        _action("필요 서류 보기", intent=DOCS),
        _action("신청 준비 시작", action="create_apply_plan"),
    ],
    response_plan,
)
return {
    **base,
    "reply": reply,
    "benefit": benefit,
    "suggested_actions": actions,
}
```

For `ELIGIBILITY`, preserve `eligibility` and `eligibility_notes`. Use:

```python
if profile is None:
    sections = {
        "missing_info": (
            "먼저 필요한 정보",
            ["나이", "거주 지역", "취업 상태 등 정책별 조건"],
        ),
        "requirements": (
            "확인 방법",
            ["왼쪽 '조건 저장' 폼에 프로필을 저장하면 정책 조건과 자동 비교합니다."],
        ),
    }
else:
    sections = {
        "summary": ("판정", [label]),
        "reasons": ("판정 근거", [note["reason"] for note in notes]),
        "requirements": (
            "추가 확인",
            ["DB에 없는 세부 기준은 공식 공고에서 최종 확인해야 합니다."],
        ),
    }

reply = self._render_planned_sections(
    title=title,
    intent=intent,
    response_plan=response_plan,
    sections=sections,
    source_label=context.get("source_label", "정책 DB"),
)
actions = order_actions(
    [
        _action("필요 서류 보기", intent=DOCS),
        _action("얼마 받는지 보기", intent=BENEFIT),
        _action("신청 준비 시작", action="create_apply_plan"),
    ],
    response_plan,
)
if profile is None:
    return {
        **base,
        "reply": reply,
        "eligibility": "needs_info",
        "eligibility_notes": [
            {"reason": "프로필 미설정 — 나이·지역·취업 상태를 저장하면 자동 비교합니다."}
        ],
        "suggested_actions": actions,
    }
return {
    **base,
    "reply": reply,
    "eligibility": eligibility,
    "eligibility_notes": notes,
    "suggested_actions": actions,
}
```

For `APPLY_HOW`, preserve the existing `apply_detail` dictionary and use:

```python
sections = {
    "method": ("신청 방법", detail.get("method") or []),
    "period": ("신청 기간", detail.get("period") or []),
    "links": ("신청 링크", detail.get("links") or []),
    "documents": ("준비 서류", detail.get("docs") or []),
    "contact": ("문의처", detail.get("contact") or []),
    "next_step": ("다음 행동", detail.get("notes") or []),
}
reply = self._render_planned_sections(
    title=title,
    intent=intent,
    response_plan=response_plan,
    sections=sections,
    source_label=context.get("source_label", "정책 DB"),
)
actions = order_actions(
    [
        _action("필요 서류 보기", intent=DOCS),
        _action("얼마 받는지 보기", intent=BENEFIT),
        _action("신청 준비 시작", action="create_apply_plan"),
    ],
    response_plan,
)
return {
    **base,
    "reply": reply,
    "apply_detail": detail,
    "suggested_actions": actions,
}
```

Do not change any structured fact-producing call.

- [ ] **Step 7: Pass prior turns from FastAPI and store private metadata**

In `backend/main.py`, load history before adding the current user turn:

```python
conversation_context = conversation_store.get_turns(session_id)
conversation_store.add_turn(session_id, "user", request.message)
```

Pass it to `respond()`:

```python
conversation_context=conversation_context,
```

Before storing the assistant turn, remove private metadata from the direct response:

```python
response_plan_meta = result.pop("_response_plan_meta", None)
assistant_payload = {key: value for key, value in result.items() if key != "reply"}
if response_plan_meta:
    assistant_payload["response_plan_meta"] = response_plan_meta
```

Then call:

```python
conversation_store.add_turn(
    session_id,
    "assistant",
    result["reply"],
    intent=result.get("intent"),
    payload=assistant_payload,
)
```

Do not add fields to `ConverseResponse` or `ChatResponse`.

- [ ] **Step 8: Run Agent and API tests**

Run:

```powershell
python -m pytest tests/test_converse_agent.py tests/test_converse_api_smoke.py tests/test_backend_routes.py -q
```

Expected: zero failures. Existing recommendation separation tests must continue to pass.

- [ ] **Step 9: Commit converse integration**

```powershell
git add ai/converse_agent.py backend/main.py tests/test_converse_agent.py tests/test_converse_api_smoke.py
git commit -m "feat: 대화형 상담에 맥락 기반 응답 적용"
```

### Task 5: Documentation and Full Regression Verification

**Files:**
- Modify: `README.md:21-47`
- Modify: `README.md:272-342`

- [ ] **Step 1: Add the counseling-response behavior to README**

Add this subsection after the policy consultation API explanation:

```markdown
#### 상담 답변의 맥락 기반 구성

정책 추천이 끝나고 특정 정책을 선택한 뒤에는 `/chat`과 `/agent/converse`가 같은
`ResponsePlanner`를 사용합니다. 정책 금액·기간·자격·서류·URL은 기존 DB와 규칙 결과를
그대로 사용하고, 현재 질문과 이전 상담 흐름에 따라 강조점, 섹션 순서, 설명 길이,
후속 질문만 조정합니다.

- 같은 정책·질문·사용자 조건·대화 단계에서는 같은 계획을 사용합니다.
- 추가 질문이 구체화되면 발급처, 총액, 마감, 신청 경로처럼 필요한 부분을 먼저 보여줍니다.
- `LLM_PROVIDER=none`에서도 규칙 기반 렌더러가 동일한 계획을 사용합니다.
- 추천 목록과 순위는 이 기능의 영향을 받지 않습니다.
```

- [ ] **Step 2: Verify no recommendation code was changed**

Run:

```powershell
git diff HEAD~4 --name-only
```

Expected changed implementation files are limited to:

```text
ai/response_planner.py
ai/response_renderer.py
ai/policy_chat_agent.py
ai/converse_agent.py
backend/main.py
tests/test_response_planner.py
tests/test_response_renderer.py
tests/test_policy_chat_agent.py
tests/test_converse_agent.py
tests/test_converse_api_smoke.py
README.md
```

If `ai/recommender.py`, `ai/retriever.py`, `ai/generator.py`, or the `/recommend` implementation changed, revert only those out-of-scope changes before continuing.

- [ ] **Step 3: Run all focused backend tests**

Run:

```powershell
python -m pytest tests/test_response_planner.py tests/test_response_renderer.py tests/test_policy_chat_agent.py tests/test_converse_agent.py tests/test_converse_api_smoke.py tests/test_api_smoke.py tests/test_llm_client.py -q
```

Expected: zero failures.

- [ ] **Step 4: Run the complete Python suite**

Run:

```powershell
python -m pytest -q
```

Expected: zero failures.

- [ ] **Step 5: Run frontend regression tests and build**

Run:

```powershell
Set-Location frontend
npm test
npm run build
Set-Location ..
```

Expected: all frontend tests pass and the production build exits with code 0.

- [ ] **Step 6: Run formatting and repository checks**

Run:

```powershell
git diff --check
git status --short
```

Expected: `git diff --check` has no output. `git status --short` shows only the intended README change before the final commit.

- [ ] **Step 7: Commit documentation**

```powershell
git add README.md
git commit -m "docs: 상담 응답 계획 방식 설명"
```

- [ ] **Step 8: Re-run final verification after all commits**

Run:

```powershell
python -m pytest -q
Set-Location frontend
npm test
npm run build
Set-Location ..
git status --short
```

Expected: all commands exit 0 and the worktree is clean.

## Acceptance Checklist

- [ ] `/recommend`의 검색, 순위, 카드 내용은 변경되지 않았다.
- [ ] `/chat`과 정책 선택 후 `/agent/converse`만 `ResponsePlanner`를 사용한다.
- [ ] 같은 맥락의 규칙 기반 답변은 안정적으로 동일하다.
- [ ] 구체화된 후속 질문에서는 초점이나 섹션 순서가 달라진다.
- [ ] `LLM_PROVIDER=none`에서도 계획 기반 구조가 적용된다.
- [ ] LLM 경로의 프롬프트는 계획을 따르되 DB 밖 사실을 만들지 않는다.
- [ ] `documents`, `benefit`, `eligibility`, `eligibility_notes`, `apply_detail` 값은 기존 계산 결과를 보존한다.
- [ ] 계획 메타는 `/agent/converse` 직접 응답에 노출되지 않고 assistant 턴 payload에 저장된다.
- [ ] 정책 미선택, 추천 유도, 단순 선택 응답에는 계획기가 개입하지 않는다.
- [ ] 전체 Python 테스트, frontend 테스트, frontend build가 통과한다.
