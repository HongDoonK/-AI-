# models.py
# ──────────────────────────────────────────────────────────────
# FastAPI에서 주고받는 데이터의 '형식(틀)'을 정의하는 파일.
#
# 설계 원칙:
# - PolicyResult : AI 모듈이 반환하는 dict 구조에 맞춤 (백엔드 초안 명세 기준)
# 따라서 AI 담당자와 합의 후 PolicyResult 수정 필요
# - CenterResult : DB의 centers 테이블 컬럼명에 맞춤
#                  → main.py에서 변환 없이 dict 그대로 넘김 (코드 단순화)
# ──────────────────────────────────────────────────────────────

from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Optional


# ════════════════════════════════════════════════════════════════
# 1. 요청(Request) 모델 — 클라이언트 → 서버
# ════════════════════════════════════════════════════════════════
class RecommendRequest(BaseModel):
    """
    /recommend 엔드포인트의 요청 본문 형식.

    예시:
        {"user_input": "서울 사는 24살 대학생인데 월세 지원 받을 수 있어?"}
    """
    user_input: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="사용자가 자연어로 입력한 자신의 상황",
        examples=["서울 사는 24살 대학생인데 월세 지원 받을 수 있는 정책 있어?"],
    )


# ════════════════════════════════════════════════════════════════
# 2. 응답(Response) 모델 — 서버 → 클라이언트
# ════════════════════════════════════════════════════════════════

class PolicyResult(BaseModel):
    """
    추천 정책 1개의 형식.
    AI 모듈(recommend_policy)이 반환하는 정책 dict와 동일한 구조여야 한다.
    """

    # AI가 추가 필드를 보내도 무시 (호환성↑)
    model_config = ConfigDict(extra="ignore")

    policy_name:        str       = Field(..., description="정책명")
    apply_possibility:  str       = Field(
        default="확인 필요",
        description="신청 가능성 ('높음' / '확인 필요' / '낮음')",
    )
    reason:             str       = Field(default="", description="이 정책을 추천한 이유")
    support_content:    str       = Field(default="", description="지원 내용 요약")
    support_summary:    str       = Field(default="", description="지원 내용 추상 요약")
    application_period: str       = Field(default="", description="신청 기간")
    application_url:    str       = Field(default="", description="신청 URL")
    checklist:          list[str] = Field(
        default_factory=list,
        description="신청을 위한 행동 체크리스트",
    )
    match_score:       float | None = Field(None, description="검색 랭킹 점수")
    match_method:      str          = Field(default="", description="검색 방식")
    match_score_label: str          = Field(default="", description="화면 표시용 검색 점수")
    domain:            str          = Field(default="", description="검색 도메인 코드")
    domain_label:      str          = Field(default="", description="검색 도메인 표시명")
    source_table:      str          = Field(default="", description="원본 테이블")
    source_id:         str          = Field(default="", description="원본 행 ID")
    doc_id:            str          = Field(default="", description="통합 검색 문서 ID")
    source_label:      str          = Field(default="", description="원본 출처 표시명")
    region_name:       str          = Field(default="", description="정책 지역명")
    region_sido:       str          = Field(default="", description="정책 시도")
    region_sigungu:    str          = Field(default="", description="정책 시군구")
    region_match:      str          = Field(default="", description="지역 매칭 설명")
    match_badges:      list[str]    = Field(default_factory=list, description="추천 근거 배지")


class ChatMessage(BaseModel):
    role:    str = Field(default="user", description="메시지 역할: user 또는 assistant")
    content: str = Field(default="", max_length=3000, description="메시지 내용")


class ChatRequest(BaseModel):
    policy:       dict[str, Any]    = Field(default_factory=dict, description="선택된 추천 정책 카드")
    user_context: dict[str, Any]    = Field(default_factory=dict, description="사용자 조건")
    messages:     list[ChatMessage] = Field(default_factory=list, description="정책별 대화 내역")


class ChatResponse(BaseModel):
    answer:              str             = Field(default="", description="챗봇 답변")
    suggested_questions: list[str]       = Field(default_factory=list, description="후속 질문 예시")
    policy_context:      dict[str, Any]  = Field(default_factory=dict, description="답변에 사용한 정책 식별 정보")


class CenterResult(BaseModel):
    """
    청년센터 1개의 형식.
    DB의 centers 테이블 컬럼명과 동일하게 맞춤
    → main.py에서 변환 없이 dict를 그대로 넘기면 됨.
    """

    # DB가 추가 컬럼(center_id, center_daddr, center_ctpv_cd 등)을
    # 같이 반환해도 무시
    model_config = ConfigDict(extra="ignore")

    center_name: str           = Field(..., description="센터명")
    center_addr: str           = Field(default="", description="센터 주소")
    center_tel:  Optional[str] = Field(None, description="센터 전화번호")
    center_url:  Optional[str] = Field(None, description="센터 홈페이지 URL")


class RecommendResponse(BaseModel):
    """
    /recommend 엔드포인트의 최종 응답 형식.

    예시:
        {
            "user_condition": {"age": 24, "region": "서울", ...},
            "recommendations": [PolicyResult, ...],   # 최대 5개
            "centers":         [CenterResult, ...]
        }
    """
    user_condition:  dict                = Field(
        default_factory=dict,
        description="AI가 사용자 입력에서 추출한 조건 (나이, 지역, 상태 등)",
    )
    recommendations: list[PolicyResult]  = Field(
        default_factory=list,
        description="추천 정책 Top 5",
    )
    centers:         list[CenterResult]  = Field(
        default_factory=list,
        description="사용자 지역 기반 청년센터 목록",
    )
    message:         str                 = Field(
        default="",
        description="추천 결과 대신 사용자에게 보여줄 안내 메시지",
    )


class UserRequest(BaseModel):
    age:               int | None = None
    gender:            str | None = None
    region_sido:       str | None = None
    region_sigungu:    str | None = None
    employment_status: str | None = None


class UserResponse(BaseModel):
    user_id:           str
    age:               int | None = None
    gender:            str | None = None
    region_sido:       str | None = None
    region_sigungu:    str | None = None
    employment_status: str | None = None
    created_at:        str | None = None
