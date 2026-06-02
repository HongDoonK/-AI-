from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from ai.llm_client import LLMUnavailable, create_chat_response, get_model_name, llm_enabled


def _chat_value(value: Any, fallback: str = "확인 필요") -> str:
    if value is None or value == "":
        return fallback
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if item) or fallback
    return str(value)


def _latest_user_question(messages: list[dict[str, str]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user" and message.get("content"):
            return message["content"]
    return "이 정책에 대해 알려줘"


def _previous_assistant_answers(messages: list[dict[str, str]]) -> list[str]:
    return [
        message["content"]
        for message in messages
        if message.get("role") == "assistant" and message.get("content")
    ][-3:]


def _question_wants_checklist(question: str) -> bool:
    checklist_keywords = [
        "신청",
        "방법",
        "어떻게",
        "절차",
        "다음",
        "서류",
        "준비",
        "필요",
        "조건",
        "자격",
        "기간",
        "언제",
        "마감",
        "해야",
        "뭐부터",
    ]
    return any(keyword in question for keyword in checklist_keywords)


class PolicyChatAgent:
    """LLM-backed 상담 에이전트 for one selected youth policy card."""

    def __init__(self, *, max_context_messages: int = 10, max_output_tokens: int = 900):
        self.max_context_messages = max_context_messages
        self.max_output_tokens = max_output_tokens

    def answer(self, *, policy: dict[str, Any], user_context: dict[str, Any], messages: list[dict[str, str]]) -> str:
        latest_question = _latest_user_question(messages)
        previous_answers = _previous_assistant_answers(messages)
        fallback_answer = self._fallback_answer(policy, latest_question)
        system_prompt = self._build_system_prompt(
            policy=policy,
            user_context=user_context,
            latest_question=latest_question,
            previous_answers=previous_answers,
        )

        try:
            answer = create_chat_response(
                system_prompt=system_prompt,
                messages=messages[-self.max_context_messages :],
                max_output_tokens=self.max_output_tokens,
            )
        except LLMUnavailable:
            return fallback_answer

        return self._dedupe_answer(answer, previous_answers, fallback_answer)

    def status(self) -> dict[str, Any]:
        return {
            "agent": "policy_chat_agent",
            "llm_enabled": llm_enabled(),
            "model": get_model_name(),
        }

    def _build_system_prompt(
        self,
        *,
        policy: dict[str, Any],
        user_context: dict[str, Any],
        latest_question: str,
        previous_answers: list[str],
    ) -> str:
        policy_context = {
            "정책명": _chat_value(policy.get("policy_name")),
            "신청 가능성": _chat_value(policy.get("apply_possibility")),
            "추천 이유": _chat_value(policy.get("reason")),
            "지원 내용": _chat_value(policy.get("support_content")),
            "신청 기간": _chat_value(policy.get("application_period")),
            "신청 URL": _chat_value(policy.get("application_url") or policy.get("url") or policy.get("ref_url")),
            "체크리스트": _chat_value(policy.get("checklist")),
            "추천 근거": _chat_value(policy.get("match_badges")),
            "지역": _chat_value(policy.get("region_name") or policy.get("region_sido")),
        }
        return (
            "너는 사용자가 선택한 청년 정책 카드 하나만 상담하는 한국어 LLM 에이전트다.\n"
            "역할: 정책 추천 카드에 대해 실제 상담원처럼 대화하면서, 사용자가 지금 묻는 것에만 집중한다.\n"
            "대화 방식:\n"
            "- 최신 질문에 바로 답하고, 이전 assistant 답변을 반복하거나 재포장하지 마라.\n"
            "- 사용자가 짧게 이어서 물으면 대화 흐름을 이용해 의도를 보완해라.\n"
            "- 정책 정보에 없는 내용은 추측하지 말고 '확인 필요'라고 말해라.\n"
            "- 일반 질문은 2~4문장으로 자연스럽게 답해라.\n"
            "- 신청 방법, 절차, 서류, 자격, 기간, 다음 행동을 물으면 짧은 설명 뒤 체크리스트를 포함해라.\n"
            "- 체크리스트가 필요할 때는 각 줄을 반드시 '- [ ] '로 시작하고 3~5개만 작성해라.\n"
            "- 불필요한 인사말, 전체 정책 요약, 같은 결론 반복은 하지 마라.\n\n"
            f"최신 질문: {latest_question}\n"
            f"체크리스트 필요 여부: {_question_wants_checklist(latest_question)}\n"
            f"반복 금지 대상 assistant 답변: {previous_answers}\n"
            f"선택된 정책 정보: {policy_context}\n"
            f"사용자 조건: {user_context}"
        )

    def _dedupe_answer(self, answer: str, previous_answers: list[str], fallback: str) -> str:
        normalized = " ".join(answer.split())
        previous_normalized = {" ".join(item.split()) for item in previous_answers}
        if not normalized:
            return fallback
        if normalized in previous_normalized:
            return fallback
        for previous in previous_normalized:
            if not previous:
                continue
            if SequenceMatcher(None, normalized, previous).ratio() >= 0.78:
                return fallback
        return answer

    def _fallback_answer(self, policy: dict[str, Any], latest_question: str) -> str:
        name = _chat_value(policy.get("policy_name"), "선택한 정책")
        possibility = _chat_value(policy.get("apply_possibility"))
        reason = _chat_value(policy.get("reason"))
        support = _chat_value(policy.get("support_content"))
        period = _chat_value(policy.get("application_period"))
        url = _chat_value(policy.get("application_url") or policy.get("url") or policy.get("ref_url"), "확인 필요")
        checklist = policy.get("checklist") if isinstance(policy.get("checklist"), list) else []
        question = latest_question.lower()

        if any(keyword in question for keyword in ["서류", "준비", "필요"]):
            steps = checklist[:4] or ["공고문에서 제출 서류 확인", "신분/거주/소득 등 자격 증빙 준비", "누락 서류가 없는지 최종 확인"]
            headline = f"{name} 신청 준비는 제출 서류와 자격 증빙을 먼저 확인하는 게 핵심입니다."
        elif any(keyword in question for keyword in ["신청", "방법", "어떻게", "절차"]):
            steps = checklist[:4] or ["신청 가능 기간 확인", "신청 자격 확인", "온라인 신청 페이지 접속", "제출 후 접수 상태 확인"]
            headline = f"{name}은 신청 기간과 자격을 확인한 뒤 안내된 신청 경로로 진행하면 됩니다."
        elif any(keyword in question for keyword in ["기간", "언제", "마감"]):
            steps = [f"신청 기간 확인: {period}", "마감 전 제출 가능한지 일정 확인", "기간이 '상시'가 아니면 공고문에서 접수 시간을 재확인"]
            headline = f"{name}의 신청 기간은 {period}입니다."
        elif any(keyword in question for keyword in ["지원", "얼마", "내용", "혜택"]):
            return (
                f"{name}의 핵심 지원 내용은 {support}입니다. "
                f"다만 금액, 횟수, 한도처럼 세부 기준은 공고문마다 달라질 수 있어서 신청 URL({url})에서 최종 확인이 필요해요."
            )
        elif any(keyword in question for keyword in ["나", "맞아", "가능", "될까", "자격", "조건"]):
            return (
                f"현재 추천 결과상 {name}의 신청 가능성은 '{possibility}'으로 보입니다. "
                f"추천 근거는 이렇게 정리돼요: {reason} "
                "다만 최종 자격은 소득, 거주지, 재직/재학 상태 같은 세부 조건으로 달라질 수 있어 공고문 확인이 필요해요."
            )
        else:
            return (
                f"{latest_question}에 대해 보면, {name}에서는 우선 {support} 부분을 확인하면 좋습니다. "
                f"신청 기간은 {period}이고, 세부 조건은 신청 URL({url})에서 확인이 필요해요. "
                "원하면 제가 바로 신청 순서나 필요한 서류 기준으로 정리해드릴게요."
            )

        checklist_text = "\n".join(f"- [ ] {step}" for step in steps[:5])
        return (
            f"{headline}\n"
            f"{checklist_text}\n"
            f"주의/확인 필요: 세부 조건은 정책 공고문 기준으로 달라질 수 있으니 신청 URL({url})에서 최종 확인하세요."
        )
