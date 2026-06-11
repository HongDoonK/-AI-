"""제출 서류명 → 발급처 매핑 레지스트리.

정부 발급처 URL은 변동이 적어 정적 매핑이 LLM 추론보다 정확하고 저렴하다.
(docs/AGENT_APPLY_DESIGN.md §8 트레이드오프 참조)
"""
from __future__ import annotations

# (키워드 튜플, 발급처 라벨, 발급 URL)
_ISSUERS: list[tuple[tuple[str, ...], str, str]] = [
    (("주민등록등본", "주민등록초본", "등본", "초본"),
     "정부24에서 발급",
     "https://www.gov.kr/main?CappBizCD=13100000015&HighCtgCD=A01010&a=AA020InfoCappViewApp"),
    (("가족관계증명서", "혼인관계증명서", "기본증명서"),
     "대법원 전자가족관계등록시스템에서 발급",
     "https://efamily.scourt.go.kr/"),
    (("소득금액증명", "사실증명", "납세증명", "소득증빙"),
     "홈택스에서 발급",
     "https://hometax.go.kr/"),
    (("건강보험", "보험료 납부확인", "자격득실"),
     "국민건강보험공단에서 발급",
     "https://www.nhis.or.kr/"),
    (("재학증명서", "졸업증명서", "성적증명서", "휴학증명서"),
     "소속 학교 또는 정부24에서 발급",
     "https://www.gov.kr/"),
    (("사업자등록증", "사업자등록증명"),
     "홈택스에서 발급",
     "https://hometax.go.kr/"),
    (("고용보험", "피보험자격"),
     "고용보험 홈페이지에서 발급",
     "https://www.ei.go.kr/"),
    (("통장사본", "계좌"),
     "거래 은행 앱/창구에서 발급",
     ""),
    (("임대차계약서", "전세계약서", "월세계약서"),
     "본인 보관 계약서 사본 준비",
     ""),
    (("신분증",),
     "본인 신분증 지참",
     ""),
]


def find_issuer(document_label: str) -> dict | None:
    """서류명에서 발급처를 찾는다. 못 찾으면 None."""
    text = str(document_label or "")
    for keywords, help_label, help_url in _ISSUERS:
        if any(keyword in text for keyword in keywords):
            return {"help_label": help_label, "help_url": help_url}
    return None
