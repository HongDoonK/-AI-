"""대화형 신청 도우미 오케스트레이터 (ConverseAgent).

자유 발화 한 턴을 받아 (1) 의도를 분류하고 (2) 기존 능력
—recommender · apply_agent · benefit_estimator · policy_chat_agent—
중 하나로 디스패치한 뒤 (3) 대화체 응답 + 후속 액션칩으로 직렬화한다.

DB에 의존하지 않는다. 세션 상태(selected_policy, last_recommendations)는
인자로 받고, 갱신된 상태를 응답에 실어 반환한다. 영속화는 호출 측
(backend/main.py + conversation_store)이 담당한다.

설계: docs/ADR-001-conversational-apply-flow.md
"""
from __future__ import annotations

from typing import Any

from ai.apply_agent import ApplyAgent, check_eligibility
from ai.benefit_estimator import estimate_benefit
from ai.chat_labels import INTENT_KEYWORDS
from ai.chat_text_utils import _clean
from ai.intent_router import (
    APPLY_HOW,
    BENEFIT,
    DOCS,
    ELIGIBILITY,
    RECOMMEND,
    SELECT,
    UNCLEAR,
    classify_intent,
    detect_selection,
)
from ai.policy_chat_agent import PolicyChatAgent
from ai.recommender import recommend_policy

_NEEDS_SELECT_INTENTS = {DOCS, BENEFIT, ELIGIBILITY, APPLY_HOW}
_SELECTION_APPLY_DOC_SIGNALS = [
    "신청할래",
    "신청할게",
    "신청해",
    "신청해야",
    "신청해봐",
    "신청해볼",
    "신청하겠",
    "신청하려고",
    "신청 준비",
]
_SELECTION_APPLY_HOW_SIGNALS = [
    "신청 방법",
    "신청은",
    "신청하려면",
    "어떻게 신청",
    "절차",
    "접수",
    "가입 방법",
    "가입은",
    "링크",
    "어디",
]


def _contains_any(text: str, words: list[str]) -> bool:
    return any(word in text for word in words)


def _followup_intent_after_selection(message: str) -> str | None:
    """'정책 N + 후속 요청' 발화에서 선택 뒤 바로 처리할 의도를 찾는다."""
    text = str(message or "").strip()
    if not text:
        return None
    if _contains_any(text, INTENT_KEYWORDS.get("docs", [])):
        return DOCS
    if _contains_any(text, INTENT_KEYWORDS.get("benefit", [])) or "얼마" in text or "받을 수" in text:
        return BENEFIT
    if _contains_any(text, _SELECTION_APPLY_HOW_SIGNALS):
        return APPLY_HOW
    if _contains_any(text, INTENT_KEYWORDS.get("eligibility", [])):
        return ELIGIBILITY
    if _contains_any(text, _SELECTION_APPLY_DOC_SIGNALS):
        return DOCS
    return None


def _policy_ref(rec: dict[str, Any], rank: int) -> dict[str, Any]:
    return {
        "rank": rank,
        "doc_id": _clean(rec.get("doc_id") or rec.get("policy_id")),
        "source_table": _clean(rec.get("source_table")),
        "source_id": _clean(rec.get("source_id")),
        "title": _clean(rec.get("policy_name") or rec.get("title")) or "정책명 확인 필요",
        "domain": _clean(rec.get("category_main") or rec.get("domain")),
    }


def _action(label: str, **kwargs: Any) -> dict[str, Any]:
    return {"label": label, **kwargs}


class ConverseAgent:
    def __init__(self, chat_agent: PolicyChatAgent | None = None, apply_agent: ApplyAgent | None = None):
        self.chat_agent = chat_agent or PolicyChatAgent()
        self.apply_agent = apply_agent or ApplyAgent(chat_agent=self.chat_agent)

    def respond(
        self,
        *,
        message: str,
        selected_policy: dict[str, Any] | None = None,
        last_recommendations: list[dict[str, Any]] | None = None,
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        last_recommendations = last_recommendations or []
        intent = classify_intent(message, has_selected=bool(selected_policy))

        if intent == RECOMMEND:
            return self._handle_recommend(message)
        if intent == SELECT:
            return self._handle_select(message, selected_policy, last_recommendations, profile)
        if intent in _NEEDS_SELECT_INTENTS:
            policy = self._resolve_policy(message, selected_policy, last_recommendations)
            if not policy:
                return self._need_select(last_recommendations, intent)
            return self._handle_policy_intent(intent, policy, profile, last_recommendations)
        return self._handle_unclear(selected_policy, last_recommendations)

    # ── 의도별 핸들러 ────────────────────────────────────────────────
    def _handle_recommend(self, message: str) -> dict[str, Any]:
        result = recommend_policy(message)
        recs = (result.get("recommendations") or [])[:5]
        if not recs:
            return {
                "intent": RECOMMEND,
                "reply": result.get("message") or "조건을 더 알려주시면 정책을 찾아드릴게요.",
                "cards": [],
                "selected_policy": None,
                "last_recommendations": [],
                "suggested_actions": [],
            }
        cards = [_policy_ref(rec, i + 1) for i, rec in enumerate(recs)]
        lines = ["회원님 조건 기준으로 신청 가능한 정책 {}개를 찾았어요.".format(len(cards))]
        for card in cards:
            domain = f" [{card['domain']}]" if card["domain"] else ""
            lines.append(f"  {card['rank']}. {card['title']}{domain}")
        lines.append("\n번호로 정책을 골라 주세요. 예: \"정책 3 신청할래\"")
        return {
            "intent": RECOMMEND,
            "reply": "\n".join(lines),
            "cards": cards,
            "selected_policy": None,  # 새 추천 시 이전 선택 해제
            "last_recommendations": cards,
            "suggested_actions": [
                _action(f"{card['rank']}번 선택", intent=SELECT, ordinal=card["rank"])
                for card in cards[:3]
            ],
        }

    def _handle_select(
        self,
        message: str,
        selected_policy: dict[str, Any] | None,
        last_recommendations: list[dict[str, Any]],
        profile: dict[str, Any] | None,
    ) -> dict[str, Any]:
        policy = self._resolve_policy(message, selected_policy, last_recommendations)
        if not policy:
            return self._need_select(last_recommendations, SELECT)
        followup_intent = _followup_intent_after_selection(message)
        if followup_intent:
            return self._handle_policy_intent(followup_intent, policy, profile, last_recommendations)
        return self.select(policy)

    def select(self, policy_ref: dict[str, Any]) -> dict[str, Any]:
        policy = {
            **policy_ref,
            "title": _clean(policy_ref.get("title") or policy_ref.get("policy_name")) or "정책명 확인 필요",
        }
        return {
            "intent": SELECT,
            "reply": (
                f"'{policy['title']}'을(를) 선택하셨어요. "
                "필요한 서류, 받을 수 있는 지원 금액, 신청 자격 중 무엇을 먼저 볼까요?"
            ),
            "selected_policy": policy,
            "suggested_actions": [
                _action("필요 서류 보기", intent=DOCS),
                _action("얼마 받는지 보기", intent=BENEFIT),
                _action("신청 자격 확인", intent=ELIGIBILITY),
            ],
        }

    def _handle_policy_intent(
        self,
        intent: str,
        policy: dict[str, Any],
        profile: dict[str, Any] | None,
        last_recommendations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        context = self.chat_agent.load_policy_context(policy)
        title = _clean(context.get("title")) or policy["title"]
        base = {"intent": intent, "selected_policy": policy}

        if intent == DOCS:
            plan = self.apply_agent.build_plan(policy, profile)
            documents = [
                {"label": item["label"], "help_label": item.get("help_label"), "help_url": item.get("help_url")}
                for item in plan["checklist"]
                if item["kind"] == "document"
            ]
            lines = [f"'{title}' 신청에 필요한 서류와 발급처입니다."]
            for doc in documents:
                where = doc["help_label"] or "공고/담당 기관에서 확인"
                url = f" ({doc['help_url']})" if doc.get("help_url") else ""
                lines.append(f"  - {doc['label']} → {where}{url}")
            if plan.get("apply_url"):
                lines.append(f"\n신청 페이지: {plan['apply_url']}")
            lines.append(f"\n{plan.get('next_action', '')}".rstrip())
            return {**base, "reply": "\n".join(lines), "documents": documents,
                    "apply_channel": plan.get("apply_channel"), "apply_url": plan.get("apply_url"),
                    "suggested_actions": [
                        _action("얼마 받는지 보기", intent=BENEFIT),
                        _action("신청 준비 시작", action="create_apply_plan"),
                    ]}

        if intent == BENEFIT:
            benefit = estimate_benefit(context)
            return {**base, "reply": f"'{title}' — {benefit['summary_line']}", "benefit": benefit,
                    "suggested_actions": [
                        _action("필요 서류 보기", intent=DOCS),
                        _action("신청 준비 시작", action="create_apply_plan"),
                    ]}

        if intent == ELIGIBILITY:
            if profile is None:
                return {
                    **base,
                    "reply": (
                        f"'{title}' 신청 자격을 확인하려면 프로필(나이·지역·취업 상태 등)이 필요해요. "
                        "왼쪽 '조건 저장' 폼에서 프로필을 저장하면 더 정확한 적격성 안내를 드릴게요."
                    ),
                    "eligibility": "needs_info",
                    "eligibility_notes": [{"reason": "프로필 미설정 — 나이·지역·취업 상태를 저장하면 자동 비교합니다."}],
                    "suggested_actions": [
                        _action("필요 서류 보기", intent=DOCS),
                        _action("얼마 받는지 보기", intent=BENEFIT),
                    ],
                }
            eligibility, notes = check_eligibility(context, profile)
            label = {"ok": "신청 조건에 맞아 보여요.",
                     "needs_info": "대체로 맞지만 확인이 필요한 항목이 있어요.",
                     "ineligible": "프로필 기준으로는 조건에 맞지 않을 수 있어요."}.get(eligibility, "")
            lines = [f"'{title}' 신청 자격을 확인했어요. {label}"]
            for note in notes:
                lines.append(f"  - {note['reason']}")
            return {**base, "reply": "\n".join(lines), "eligibility": eligibility, "eligibility_notes": notes,
                    "suggested_actions": [
                        _action("필요 서류 보기", intent=DOCS),
                        _action("얼마 받는지 보기", intent=BENEFIT),
                    ]}

        # APPLY_HOW
        summary = self.chat_agent._build_user_summary(context)
        detail = self.chat_agent._build_apply_detail(context, summary)
        lines = [f"'{title}' 신청 방법입니다."]
        for heading, key in [("신청 방법", "method"), ("신청 기간", "period"), ("신청 링크", "links"), ("문의처", "contact")]:
            items = detail.get(key) or []
            if items:
                lines.append(f"\n{heading}")
                lines.extend(f"  - {item}" for item in items[:4])
        return {**base, "reply": "\n".join(lines), "apply_detail": detail,
                "suggested_actions": [
                    _action("필요 서류 보기", intent=DOCS),
                    _action("얼마 받는지 보기", intent=BENEFIT),
                ]}

    # ── 보조 ────────────────────────────────────────────────────────
    def _resolve_policy(
        self,
        message: str,
        selected_policy: dict[str, Any] | None,
        last_recommendations: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        index = detect_selection(message)
        if index is not None and 1 <= index <= len(last_recommendations):
            return last_recommendations[index - 1]
        return selected_policy

    def _need_select(self, last_recommendations: list[dict[str, Any]], intent: str) -> dict[str, Any]:
        if last_recommendations:
            reply = "어떤 정책 기준으로 알려드릴까요? 아래에서 번호로 골라 주세요."
        else:
            reply = "먼저 어떤 상황인지 알려주시면 정책을 추천해 드릴게요. 예: \"서울 26살 직장인, 목돈 마련하고 싶어\""
        return {
            "intent": "need_select",
            "reply": reply,
            "cards": last_recommendations,
            "requested_intent": intent,
            "selected_policy": None,
            "suggested_actions": [
                _action(f"{card['rank']}번 선택", intent=SELECT, ordinal=card["rank"])
                for card in last_recommendations[:3]
            ],
        }

    def _handle_unclear(
        self,
        selected_policy: dict[str, Any] | None,
        last_recommendations: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if selected_policy:
            reply = (
                f"'{selected_policy['title']}'에 대해 필요한 서류, 받을 금액, 신청 자격 중 "
                "무엇이 궁금한지 알려 주세요."
            )
            actions = [
                _action("필요 서류 보기", intent=DOCS),
                _action("얼마 받는지 보기", intent=BENEFIT),
                _action("신청 자격 확인", intent=ELIGIBILITY),
            ]
        else:
            reply = "어떤 분야의 정책을 찾으시는지, 또는 본인 상황을 한 문장으로 알려 주세요."
            actions = [
                _action(f"{card['rank']}번 선택", intent=SELECT, ordinal=card["rank"])
                for card in last_recommendations[:3]
            ]
        return {
            "intent": UNCLEAR,
            "reply": reply,
            "selected_policy": selected_policy,
            "suggested_actions": actions,
        }
