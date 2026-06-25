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
    # D1(ADR-002): Hero 추천을 대화 세션에 시드해 채팅과 공유 (둘 다 선택, additive)
    user_id:    str | None = Field(None, description="저장된 사용자 프로필 ID (추천 세션 시드용)")
    session_id: str | None = Field(None, description="대화 세션 ID (있으면 그 세션에 추천을 시드)")


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
    min_age:           int | None   = Field(None, description="지원대상 최소 연령")
    max_age:           int | None   = Field(None, description="지원대상 최대 연령")
    income_type:       str          = Field(default="", description="소득조건 구분 (무관/연소득/기타)")
    income_min:        int | None   = Field(None, description="소득 조건 하한 (만원, 연소득 기준)")
    income_max:        int | None   = Field(None, description="소득 조건 상한 (만원, 연소득 기준)")


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
    # D1(ADR-002): 채팅과 공유하는 단일 추천 세션 (additive — 기존 소비자 영향 없음)
    session_id:      str | None           = Field(
        None,
        description="대화 세션 ID — 채팅(/agent/converse)이 이 세션의 추천 목록을 이어받는다",
    )
    cards:           list[dict]           = Field(
        default_factory=list,
        description="채팅과 공유하는 추천 카드 ref (rank/doc_id/source_table/source_id/title/domain)",
    )


class UserRequest(BaseModel):
    age:               int | None = None
    gender:            str | None = None
    region_sido:       str | None = None
    region_sigungu:    str | None = None
    employment_status: str | None = None


class SavePolicyRequest(BaseModel):
    """정책함 담기 요청 — 추천 카드(정책 dict)를 그대로 보낸다."""
    policy: dict[str, Any] = Field(..., description="정책함에 담을 추천 정책 카드 전체")


class SavedPoliciesResponse(BaseModel):
    """정책함 목록 응답."""
    policies: list[PolicyResult] = Field(
        default_factory=list,
        description="사용자가 담아둔 정책 목록 (최신순)",
    )


class UserResponse(BaseModel):
    user_id:           str
    age:               int | None = None
    gender:            str | None = None
    region_sido:       str | None = None
    region_sigungu:    str | None = None
    employment_status: str | None = None
    created_at:        str | None = None


# ════════════════════════════════════════════════════════════════
# 3. 신청 도우미 (Apply Assistant Agent) — docs/AGENT_APPLY_DESIGN.md
# ════════════════════════════════════════════════════════════════

class ApplyPlanRequest(BaseModel):
    policy:  dict[str, Any]  = Field(..., description="추천 정책 식별 정보 (doc_id/source_table/source_id)")
    user_id: str | None      = Field(None, description="저장된 사용자 프로필 ID (선택)")


class ChecklistItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    item_id:    str         = Field(default="", description="체크리스트 항목 ID")
    kind:       str         = Field(default="action", description="document | eligibility | action")
    label:      str         = Field(..., description="항목 내용")
    help_label: str | None  = Field(None, description="발급처/도움말 라벨")
    help_url:   str | None  = Field(None, description="발급처/신청 링크")
    checked:    bool        = Field(default=False, description="체크 여부")


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    application_id:    str                  = Field(..., description="신청 건 ID")
    doc_id:            str                  = Field(default="", description="정책 문서 ID")
    policy_name:       str | None           = Field(None, description="정책명")
    status:            str                  = Field(..., description="preparing/ready/submitted/done/expired")
    eligibility:       str | None           = Field(None, description="ok | needs_info | ineligible")
    eligibility_notes: list[dict[str, Any]] = Field(default_factory=list, description="확인 필요/불일치 사유")
    apply_channel:     str | None           = Field(None, description="online | visit | mail | contact")
    apply_url:         str | None           = Field(None, description="신청 URL")
    apply_deadline:    str | None           = Field(None, description="마감일(ISO) 또는 '상시'")
    days_left:         int | None           = Field(None, description="마감까지 남은 일수")
    checklist:         list[ChecklistItem]  = Field(default_factory=list, description="신청 체크리스트")
    progress:          dict[str, int]       = Field(default_factory=dict, description="체크 진행률")
    next_action:       str | None           = Field(None, description="다음 행동 안내")
    created_at:        str | None           = None
    updated_at:        str | None           = None


class ApplicationStatusRequest(BaseModel):
    status: str = Field(..., description="전이할 상태")


class ItemCheckRequest(BaseModel):
    checked: bool = Field(..., description="체크 여부")


# ════════════════════════════════════════════════════════════════
# 4. 대화형 신청 도우미 (ConverseAgent) — docs/ADR-001-conversational-apply-flow.md
# ════════════════════════════════════════════════════════════════

class ConverseRequest(BaseModel):
    message:          str            = Field(default="", max_length=1000, description="사용자 발화 한 턴")
    session_id:       str | None     = Field(None, description="대화 세션 ID (없으면 새로 발급)")
    user_id:          str | None     = Field(None, description="저장된 사용자 프로필 ID (선택)")
    selected_doc_id:  str | None     = Field(None, description="프론트에서 카드 클릭으로 선택한 정책 doc_id (선택)")
    policy:           dict[str, Any] | None = Field(None, description="카드에서 직접 선택한 정책 ref")


class ConverseResponse(BaseModel):
    model_config = ConfigDict(extra="allow")  # intent별 cards/documents/benefit 등 가변 필드 허용

    session_id:        str                  = Field(..., description="대화 세션 ID")
    intent:            str                  = Field(..., description="분류된 의도")
    reply:             str                  = Field(..., description="대화체 응답")
    selected_policy:   dict[str, Any] | None = Field(None, description="현재 선택된 정책")
    suggested_actions: list[dict[str, Any]] = Field(default_factory=list, description="후속 액션칩")
