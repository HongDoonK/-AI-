"""신청 도우미 에이전트 (Phase 1: 규칙 기반).

추천된 정책 1건에 대해 적격성 판정 → 서류/자격/액션 체크리스트 →
신청 채널 결정 → D-day 계산을 수행해 '신청 플랜'을 만든다.
LLM 없이 항상 동작한다 (LLM 초안 작성은 Phase 2).

설계: docs/AGENT_APPLY_DESIGN.md
"""
from __future__ import annotations

from datetime import date
from typing import Any

from ai.chat_text_utils import _clean, _split_items
from ai.document_registry import find_issuer
from ai.policy_chat_agent import PolicyChatAgent
from ai.retriever import _extract_apply_end


def _to_int(value: Any) -> int | None:
    try:
        number = int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def check_eligibility(context: dict[str, Any], profile: dict[str, Any] | None) -> tuple[str, list[dict]]:
    """프로필과 정책 조건을 비교한다.

    반환: ("ok" | "needs_info" | "ineligible", notes)
    """
    profile = profile or {}
    notes: list[dict] = []
    ineligible = False

    min_age = _to_int(context.get("min_age"))
    max_age = _to_int(context.get("max_age"))
    age = _to_int(profile.get("age"))
    if min_age or max_age:
        if age is None:
            notes.append({"field": "age", "reason": "나이 정보가 없어 연령 조건을 확인할 수 없습니다."})
        elif (min_age and age < min_age) or (max_age and age > max_age):
            bounds = f"{min_age or '제한없음'}~{max_age or '제한없음'}세"
            notes.append({"field": "age", "reason": f"연령 조건({bounds})에 맞지 않습니다."})
            ineligible = True

    policy_sido = _clean(context.get("region_sido"))
    policy_region = _clean(context.get("region_name"))
    user_sido = _clean(profile.get("region_sido"))
    is_nationwide = "전국" in (policy_sido + " " + policy_region)
    if not is_nationwide and (policy_sido or policy_region):
        if not user_sido:
            notes.append({"field": "region", "reason": "거주 지역 정보가 없어 지역 조건을 확인할 수 없습니다."})
        elif user_sido not in policy_sido and user_sido not in policy_region:
            notes.append({
                "field": "region",
                "reason": f"정책 지역({policy_region or policy_sido})과 거주지({user_sido})가 다릅니다.",
            })
            ineligible = True

    if ineligible:
        return "ineligible", notes
    if notes:
        return "needs_info", notes
    return "ok", notes


def resolve_channel(context: dict[str, Any]) -> tuple[str, str]:
    """신청 채널과 URL을 결정한다. 반환: (channel, url)"""
    original = context.get("original") or {}
    url = (
        _clean(context.get("url"))
        or _clean(original.get("application_url"))
        or _clean(original.get("apply_url"))
        or _clean(original.get("detail_url"))
        or _clean(original.get("ref_url1"))
    )
    if url.startswith("http"):
        return "online", url

    apply_method = _clean(original.get("apply_method"))
    if "방문" in apply_method:
        return "visit", ""
    if "우편" in apply_method:
        return "mail", ""
    return "contact", ""


def compute_deadline(context: dict[str, Any]) -> tuple[str, int | None]:
    """마감일과 D-day를 계산한다. 반환: (deadline 표시 문자열, days_left)"""
    search_doc = context.get("search_document") or {}
    original = context.get("original") or {}
    end = (
        _extract_apply_end(search_doc.get("apply_end_date"))
        or _extract_apply_end(context.get("period"))
        or _extract_apply_end(original.get("apply_period"))
    )
    if end is None:
        return "상시", None
    return end.isoformat(), (end - date.today()).days


def build_checklist(
    context: dict[str, Any],
    eligibility_notes: list[dict],
    channel: str,
    url: str,
    deadline: str,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    original = context.get("original") or {}

    # 1) 서류 항목
    documents = _split_items(original.get("submit_docs"))[:8]
    if not documents:
        documents = ["신분증", "공고문에서 제출 서류 확인"]
    for doc in documents:
        issuer = find_issuer(doc) or {}
        items.append({
            "kind": "document",
            "label": doc if len(doc) < 60 else doc[:59] + "…",
            "help_label": issuer.get("help_label"),
            "help_url": issuer.get("help_url"),
        })

    # 2) 자격 확인 항목 (적격성 판정에서 확인 못 한 것)
    for note in eligibility_notes:
        items.append({"kind": "eligibility", "label": note["reason"].rstrip(".") + " — 확인 필요"})
    target = _clean(context.get("target"))
    if "무주택" in target:
        items.append({"kind": "eligibility", "label": "무주택 요건 확인"})
    income_type = _clean(original.get("income_type"))
    if income_type and income_type != "무관":
        items.append({"kind": "eligibility", "label": f"소득 조건 확인: {income_type}"})

    # 3) 액션 항목 (채널별)
    if deadline == "상시":
        items.append({"kind": "action", "label": "공고문에서 정확한 접수 기한 확인"})
    if channel == "online":
        items.append({
            "kind": "action",
            "label": "신청 페이지에서 본인인증 후 신청서 제출",
            "help_label": "신청 페이지 열기",
            "help_url": url,
        })
    elif channel == "visit":
        items.append({"kind": "action", "label": "주관 기관 방문 신청 (방문 전 전화로 필요 서류 재확인)"})
    elif channel == "mail":
        items.append({"kind": "action", "label": "우편 접수 (마감일 도착분 기준인지 확인)"})
    else:
        contact = _clean(original.get("contact") or original.get("cnpl") or original.get("tel_no"))
        label = "주관 기관에 신청 방법 문의"
        if contact:
            label += f" ({contact})"
        items.append({"kind": "action", "label": label})
    items.append({"kind": "action", "label": "제출 후 접수 완료(접수번호) 확인"})
    return items


def _next_action_message(eligibility: str, checklist: list[dict], channel: str) -> str:
    if eligibility == "ineligible":
        return "프로필 기준으로는 신청 조건에 맞지 않습니다. 조건이 바뀌었거나 예외가 있는지 공고문을 확인하세요."
    doc_count = sum(1 for item in checklist if item["kind"] == "document")
    if channel == "online":
        return f"서류 {doc_count}건을 준비한 뒤 신청 페이지에서 본인인증 후 제출하세요."
    if channel == "visit":
        return f"서류 {doc_count}건을 준비해 주관 기관에 방문 신청하세요."
    if channel == "mail":
        return f"서류 {doc_count}건을 준비해 우편으로 접수하세요."
    return "신청 경로가 명시되지 않은 정책입니다. 먼저 주관 기관에 문의하세요."


class ApplyAgent:
    """신청 플랜 생성 오케스트레이터 (①~⑤)."""

    def __init__(self, chat_agent: PolicyChatAgent | None = None):
        self.chat_agent = chat_agent or PolicyChatAgent()

    def build_plan(self, policy: dict[str, Any], profile: dict[str, Any] | None) -> dict[str, Any]:
        context = self.chat_agent.load_policy_context(policy)
        eligibility, notes = check_eligibility(context, profile)
        channel, url = resolve_channel(context)
        deadline, days_left = compute_deadline(context)
        checklist = build_checklist(context, notes, channel, url, deadline)
        return {
            "doc_id": context.get("doc_id") or _clean(policy.get("doc_id")),
            "source_table": context.get("source_table"),
            "source_id": context.get("source_id"),
            "policy_name": context.get("title"),
            "eligibility": eligibility,
            "eligibility_notes": notes,
            "apply_channel": channel,
            "apply_url": url,
            "apply_deadline": deadline,
            "days_left": days_left,
            "checklist": checklist,
            "draft_answers": None,  # Phase 2 (LLM)
            "next_action": _next_action_message(eligibility, checklist, channel),
        }
