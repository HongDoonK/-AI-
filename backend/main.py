from contextlib import asynccontextmanager
import os

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args, **kwargs):
        return False

from ai.apply_agent import ApplyAgent
from ai.converse_agent import ConverseAgent, _policy_ref
from ai.intent_router import RECOMMEND
from ai.policy_chat_agent import PolicyChatAgent
from ai.recommender import recommend_policy
from backend import application_store, conversation_store
from backend.db import create_tables, get_centers_by_region, get_user, save_user
from backend.models import (
    ApplicationResponse,
    ApplicationStatusRequest,
    ApplyPlanRequest,
    ChatRequest,
    ChatResponse,
    ConverseRequest,
    ConverseResponse,
    ItemCheckRequest,
    RecommendRequest,
    RecommendResponse,
    UserRequest,
    UserResponse,
)


policy_chat_agent = PolicyChatAgent()
apply_agent = ApplyAgent(chat_agent=policy_chat_agent)
converse_agent = ConverseAgent(chat_agent=policy_chat_agent, apply_agent=apply_agent)


def _prepend_policy_ref(
    recommendations: list[dict],
    selected_policy: dict,
) -> list[dict]:
    selected_doc_id = selected_policy.get("doc_id")
    deduped = [
        card for card in recommendations
        if not selected_doc_id or card.get("doc_id") != selected_doc_id
    ]
    cards = [selected_policy, *deduped]
    return [{**card, "rank": index + 1} for index, card in enumerate(cards)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("=" * 50)
    print("청년 맞춤 정책 안내 AI 서버 시작")
    load_dotenv()
    print(".env 로드 완료")
    create_tables()
    print("=" * 50)
    yield
    print("서버 종료")


app = FastAPI(
    title="청년 맞춤 정책 안내 AI",
    description="공공 청년 정책 기반 추천, 상담, 신청 준비 리포트 서비스",
    version="0.2.0",
    lifespan=lifespan,
)

frontend_origins = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "청년 맞춤 정책 안내 AI 서버 동작 중",
    }


@app.post("/recommend", response_model=RecommendResponse)
def recommend(request: RecommendRequest):
    try:
        result = recommend_policy(request.user_input)
        user_condition = result.get("user_condition", {})
        recommendations = result.get("recommendations", [])
        message = result.get("message", "")

        region = user_condition.get("region", "")
        centers = get_centers_by_region(region) if region else []

        # D1(ADR-002): Hero 추천을 대화 세션의 단일 추천 목록으로 시드한다(채팅과 공유).
        # 채팅(/agent/converse)이 같은 session_id로 이 목록을 이어받아 "정책 N"을 해석한다.
        cards = [_policy_ref(rec, index + 1) for index, rec in enumerate(recommendations[:5])]
        session = conversation_store.get_or_create_session(request.session_id, request.user_id)
        session_id = session["session_id"]
        conversation_store.update_session(
            session_id,
            last_recommendations=cards,
            last_intent=RECOMMEND,
            clear_selection=True,
        )

        return {
            "user_condition": user_condition,
            "recommendations": recommendations,
            "centers": centers,
            "message": message,
            "session_id": session_id,
            "cards": cards,
        }
    except Exception as e:
        print(f"/recommend 처리 중 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"추천 처리 중 오류 발생: {str(e)}",
        )


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    try:
        messages = [
            {"role": message.role, "content": message.content}
            for message in request.messages
        ]
        return policy_chat_agent.answer(
            policy=request.policy,
            user_context=request.user_context,
            messages=messages,
        )
    except Exception as e:
        print(f"/chat 처리 중 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"챗봇 응답 생성 중 오류 발생: {str(e)}",
        )


@app.get("/chat/status")
def chat_status():
    return policy_chat_agent.status()


@app.post("/user", response_model=UserResponse)
def create_user(request: UserRequest):
    try:
        user_id = save_user(request.model_dump())
        user = get_user(user_id)
        if user is None:
            raise HTTPException(status_code=500, detail="저장된 사용자 정보를 다시 조회하지 못했습니다.")
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"사용자 저장 중 오류 발생: {str(e)}")


@app.get("/user/{user_id}", response_model=UserResponse)
def read_user(user_id: str):
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return user

# ── 신청 도우미 에이전트 (docs/AGENT_APPLY_DESIGN.md) ──────────────


@app.post("/agent/apply-plan", response_model=ApplicationResponse)
def create_apply_plan(request: ApplyPlanRequest):
    try:
        # 멱등: 동일 사용자+정책의 진행 중 신청 건이 있으면 그대로 반환
        doc_id = str(request.policy.get("doc_id") or "")
        if doc_id:
            existing = application_store.find_active_application(request.user_id, doc_id)
            if existing:
                return existing

        profile = get_user(request.user_id) if request.user_id else None
        plan = apply_agent.build_plan(request.policy, profile)
        if not plan.get("doc_id"):
            raise HTTPException(status_code=404, detail="정책을 찾을 수 없습니다. doc_id 또는 source 정보를 확인하세요.")
        plan["user_id"] = request.user_id
        application = application_store.create_application(plan, plan["checklist"])
        application["days_left"] = plan.get("days_left")
        application["next_action"] = plan.get("next_action")
        return application
    except HTTPException:
        raise
    except Exception as e:
        print(f"/agent/apply-plan 처리 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"신청 플랜 생성 중 오류 발생: {str(e)}")


@app.get("/agent/applications", response_model=list[ApplicationResponse])
def list_my_applications(user_id: str):
    return application_store.list_applications(user_id)


@app.get("/agent/applications/{application_id}", response_model=ApplicationResponse)
def read_application(application_id: str):
    application = application_store.get_application(application_id)
    if not application:
        raise HTTPException(status_code=404, detail="신청 건을 찾을 수 없습니다.")
    return application


@app.patch("/agent/applications/{application_id}", response_model=ApplicationResponse)
def update_application_status(application_id: str, request: ApplicationStatusRequest):
    try:
        application = application_store.update_status(application_id, request.status)
    except application_store.InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not application:
        raise HTTPException(status_code=404, detail="신청 건을 찾을 수 없습니다.")
    return application


@app.patch("/agent/applications/{application_id}/items/{item_id}", response_model=ApplicationResponse)
def update_application_item(application_id: str, item_id: str, request: ItemCheckRequest):
    try:
        application = application_store.set_item_checked(application_id, item_id, request.checked)
    except application_store.InvalidTransition as e:
        raise HTTPException(status_code=409, detail=str(e))
    if not application:
        raise HTTPException(status_code=404, detail="신청 건 또는 항목을 찾을 수 없습니다.")
    return application

# ── 대화형 신청 도우미 (docs/ADR-001-conversational-apply-flow.md) ──


@app.post("/agent/converse", response_model=ConverseResponse)
def converse(request: ConverseRequest):
    try:
        session = conversation_store.get_or_create_session(request.session_id, request.user_id)
        session_id = session["session_id"]

        # 선택 정책: 세션 복원값을 기본으로, 프론트가 카드 클릭으로 보낸 정책 ref/doc_id가 있으면 덮어쓴다
        selected = session.get("selected_policy")
        last_recommendations = session.get("last_recommendations", [])
        if request.policy:
            selected = _policy_ref(request.policy, 1)
            last_recommendations = _prepend_policy_ref(last_recommendations, selected)
            conversation_store.update_session(
                session_id,
                selected_policy=selected,
                last_recommendations=last_recommendations,
            )
        elif request.selected_doc_id:
            match = next(
                (card for card in last_recommendations
                 if card.get("doc_id") == request.selected_doc_id),
                None,
            )
            if match:
                selected = match

        profile = get_user(request.user_id) if request.user_id else None
        conversation_context = conversation_store.get_turns(session_id)
        conversation_store.add_turn(session_id, "user", request.message)

        if request.policy and not request.message.strip():
            result = converse_agent.select(selected)
        else:
            result = converse_agent.respond(
                message=request.message,
                selected_policy=selected,
                last_recommendations=last_recommendations,
                profile=profile,
                conversation_context=conversation_context,
            )

        # 상태 영속화: 추천 턴은 선택 해제+추천 목록 갱신, 그 외엔 선택 정책만 반영
        if result.get("intent") == RECOMMEND:
            conversation_store.update_session(
                session_id,
                last_recommendations=result.get("last_recommendations", []),
                last_intent=RECOMMEND,
                clear_selection=True,
            )
        elif result.get("selected_policy"):
            conversation_store.update_session(
                session_id,
                selected_policy=result["selected_policy"],
                last_intent=result.get("intent"),
            )
        else:
            conversation_store.update_session(session_id, last_intent=result.get("intent"))

        response_plan_meta = result.pop("_response_plan_meta", None)
        assistant_payload = {key: value for key, value in result.items() if key != "reply"}
        if response_plan_meta:
            assistant_payload["response_plan_meta"] = response_plan_meta
        conversation_store.add_turn(
            session_id, "assistant", result["reply"],
            intent=result.get("intent"),
            payload=assistant_payload,
        )

        result.setdefault("selected_policy", None)
        result["session_id"] = session_id
        return result
    except Exception as e:
        print(f"/agent/converse 처리 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"대화 처리 중 오류 발생: {str(e)}")


@app.get("/agent/converse/{session_id}")
def get_conversation(session_id: str):
    session = conversation_store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="대화 세션을 찾을 수 없습니다.")
    return {"session": session, "turns": conversation_store.get_turns(session_id)}
