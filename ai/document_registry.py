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


# 도메인별 기본 제출 서류 (submit_docs가 없는 소스 테이블용 fallback)
# 실데이터 검증: smallloan_youth/rental_houses 등은 서류 컬럼이 없어
# 일반적인 해당 분야 필수 서류를 안내한다.
DOMAIN_DEFAULT_DOCUMENTS: dict[str, list[str]] = {
    "loan": [
        "신분증",
        "소득 증빙 서류 (소득금액증명 또는 재직증명서)",
        "임대차계약서 사본 (전월세 상품인 경우)",
        "주민등록등본",
    ],
    "rental_house": [
        "신분증",
        "주민등록등본",
        "소득·자산 증빙 서류",
        "무주택 확인 서류 (지방세 세목별 과세증명 등)",
    ],
    "housing_notice": [
        "신분증",
        "주민등록등본",
        "소득·자산 증빙 서류",
        "무주택 확인 서류 (지방세 세목별 과세증명 등)",
    ],
    "policy_housing": [
        "신분증",
        "주민등록등본",
        "소득 증빙 서류",
        "임대차계약서 사본 (해당 시)",
    ],
    "policy_finance": [
        "신분증",
        "주민등록등본",
        "소득 또는 근로 증빙 서류",
        "본인 명의 통장사본",
    ],
    "training": [
        "신분증",
        "국민내일배움카드 (HRD-Net에서 발급)",
    ],
    "startup": [
        "사업계획서",
        "신분증",
        "사업자등록증명 (기창업자인 경우)",
    ],
}

STUDENT_LOAN_DOCUMENTS = [
    "신분증",
    "재학증명서 또는 학적 확인 서류",
    "학자금 지원구간 산정 정보 확인",
    "본인 명의 계좌 정보",
]

# 도메인별 대표 포털 (신청 URL이 없을 때 안내 링크)
DOMAIN_FALLBACK_LINKS: dict[str, dict[str, str]] = {
    "rental_house": {"help_label": "마이홈포털에서 공고 확인", "help_url": "https://www.myhome.go.kr/"},
    "housing_notice": {"help_label": "마이홈포털에서 공고 확인", "help_url": "https://www.myhome.go.kr/"},
    "loan": {"help_label": "서민금융진흥원 금융상품 안내", "help_url": "https://www.kinfa.or.kr/"},
    "training": {"help_label": "HRD-Net에서 과정 검색", "help_url": "https://www.work24.go.kr/"},
    "startup": {"help_label": "K-Startup 공고 확인", "help_url": "https://www.k-startup.go.kr/"},
}


def default_documents_for_domain(domain: str) -> list[str]:
    return list(DOMAIN_DEFAULT_DOCUMENTS.get(str(domain or ""), []))


def default_documents_for_policy(context: dict) -> list[str]:
    """정책 문맥까지 고려한 기본 서류.

    같은 loan 도메인이라도 학자금대출과 전월세 대출은 준비 서류가 다르다.
    """
    domain = str(context.get("domain") or "")
    text = " ".join(
        str(context.get(key) or "")
        for key in ["title", "summary", "target", "source_table"]
    )
    if domain == "loan" and "학자금" in text:
        return list(STUDENT_LOAN_DOCUMENTS)
    return default_documents_for_domain(domain)


def fallback_link_for_domain(domain: str) -> dict | None:
    return DOMAIN_FALLBACK_LINKS.get(str(domain or ""))
