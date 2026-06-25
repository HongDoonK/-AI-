"""대화형 신청 도우미의 의도 라우터 (규칙 백본).

자유 발화를 대화 레벨 의도로 분류한다. 기존 INTENT_KEYWORDS(ai/chat_labels.py)를
재사용하되, 멀티턴 대화에 필요한 select/recommend 의도를 더한다. LLM 없이 항상
동작하며, ConverseAgent가 모호(unclear) 시 되묻기로 보강한다.

설계: docs/ADR-001-conversational-apply-flow.md §의도 라우팅 규칙
"""
from __future__ import annotations

import re

from ai.chat_labels import INTENT_KEYWORDS
from ai.condition_extractor import has_condition_signal

# 대화 의도 (ADR-001 표)
RECOMMEND = "recommend"            # /recommend 세션 시드 라벨로만 사용 (채팅은 더 이상 추천 생성 안 함)
NEED_RECOMMENDATION = "need_recommendation"  # 채팅 추천 요청 → Hero로 안내 (하드 분리)
SELECT = "select"
DOCS = "docs"
BENEFIT = "benefit"
ELIGIBILITY = "eligibility"
APPLY_HOW = "apply_how"
UNCLEAR = "unclear"

# 정책 선택을 가리키는 한국어 서수 (자유 발화에서 'N번째' 매핑)
_ORDINAL_WORDS = {
    "첫": 1, "하나": 1, "한": 1,
    "두": 2, "둘": 2,
    "세": 3, "셋": 3,
    "네": 4, "넷": 4,
    "다섯": 5,
}

_RECOMMEND_SIGNALS = ["추천", "정책 없", "정책없", "정책 있", "정책있", "알아봐", "찾아", "찾아줘", "뭐가 있", "뭐 있"]
_APPLY_DIRECT_WORDS = ["신청 방법", "신청은", "신청하려면", "어떻게 신청", "절차", "접수", "가입 방법", "가입은"]

# 금액을 직접 묻는 강한 benefit 신호. "월세"·"보증금"은 정책 분야·대상을 가리킬 수
# 있으므로 단독 strong-money로 쓰지 않는다(금액 문맥일 때만 아래 weak 경로로 benefit).
_STRONG_MONEY_SIGNALS = ["얼마", "금액", "총액", "한도", "금리"]
# apply/eligibility/strong-money/docs 신호가 모두 없을 때만 benefit으로 보는 약한 신호.
_WEAK_BENEFIT_SIGNALS = ["혜택", "지원", "내용", "월세", "보증금"]


def detect_selection(message: str) -> int | None:
    """발화에서 '몇 번째 정책'을 가리키는지 1-based 인덱스를 추출한다. 없으면 None."""
    text = str(message or "")
    match = re.search(r"정책\s*(\d+)", text) or re.search(r"(\d+)\s*번(?:째|)", text)
    if match:
        return int(match.group(1))
    for word, index in _ORDINAL_WORDS.items():
        if f"{word}번째" in text or f"{word} 번째" in text:
            return index
    return None


def _matches(message: str, intent_key: str) -> bool:
    return any(keyword in message for keyword in INTENT_KEYWORDS.get(intent_key, []))


def _policy_intent(text: str) -> str | None:
    """선택된 정책에 대한 상담 의도(서류/지원금/자격/신청방법). 없으면 None.

    우선순위(행위 의도 우선, 모호성 해소):
    1. 명시적 신청 방법 신호(신청 방법/신청하려면/접수/절차 등) → apply_how.
       "월세 지원 신청 방법"처럼 약한 benefit 단어가 붙어도 행위는 신청 방법이다.
    2. 명시적 금액 질문(얼마/금액/총액/한도/금리) → benefit.
       '얼마 받을 수 있어'는 strong-money('얼마')와 eligibility('받을 수')가 겹치지만
       기존 계약상 benefit이어야 하므로 eligibility보다 위에 둔다.
       '월세'·'보증금'은 strong-money가 아니라 금액 단어가 함께일 때만 5에서 benefit.
    3. 명시적 자격 신호(자격/대상/해당/가능/받을 수) → eligibility.
    4. 서류 → docs.
    5. 그 외 약한 benefit 표현(혜택/지원/내용/월세/보증금) → benefit.
    """
    if any(word in text for word in _APPLY_DIRECT_WORDS):
        return APPLY_HOW
    if any(word in text for word in _STRONG_MONEY_SIGNALS):
        return BENEFIT
    if _matches(text, "eligibility"):
        return ELIGIBILITY
    if _matches(text, "docs"):
        return DOCS
    if any(word in text for word in _WEAK_BENEFIT_SIGNALS):
        return BENEFIT
    return None


def classify_intent(message: str, *, has_selected: bool) -> str:
    """발화 → 대화 의도. has_selected는 현재 선택된 정책 존재 여부.

    하드 분리(에이전트 역할 분리 설계): 채팅은 새 추천을 만들지 않는다. 추천 요청·조건
    발화는 RECOMMEND가 아니라 NEED_RECOMMENDATION으로 분류되어 Hero "나의 상황 입력"으로
    안내된다. 단, 선택된 정책이 있으면 상담 의도(서류/지원금/자격/신청방법)를 추천
    재분류보다 먼저 판정해 "서류 찾아줘"·"지원금 찾아줘"가 안내로 새지 않게 한다.
    """
    text = str(message or "").strip()
    if not text:
        return UNCLEAR

    # 1) 명시적 정책 선택이 최우선 ('정책3', '3번')
    if detect_selection(text) is not None:
        return SELECT

    # 2) 선택 정책이 있으면 상담 의도를 추천 재분류보다 먼저 (R1 보호)
    if has_selected:
        intent = _policy_intent(text)
        if intent:
            return intent

    # 3) 추천 요청·조건 발화는 채팅에서 처리하지 않고 Hero로 안내 (하드 분리)
    if any(signal in text for signal in _RECOMMEND_SIGNALS):
        return NEED_RECOMMENDATION
    if not has_selected and has_condition_signal(text):
        return NEED_RECOMMENDATION

    # 4) 선택 정책이 없을 때의 상담 의도 (정책 필요 → ConverseAgent가 선택 유도)
    intent = _policy_intent(text)
    if intent:
        return intent
    return UNCLEAR
