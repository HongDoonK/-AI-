# main.py
# ──────────────────────────────────────────────────────────────
# FastAPI 서버 진입점 (entry point)
# - /recommend 엔드포인트로 사용자 자연어 요청을 받음
# - AI 추천 모듈에 전달 → 정책 추천 + 청년센터 정보를 반환
#
# 실행 방법 (PowerShell, 프로젝트 루트에서):
#     uvicorn backend.main:app --reload
#
# 서버 주소     : http://localhost:8000
# Swagger 문서  : http://localhost:8000/docs
# ──────────────────────────────────────────────────────────────

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from dotenv import load_dotenv

# 우리가 만든 모듈
from backend.models import RecommendRequest, RecommendResponse
from backend.db import get_centers_by_region
from backend.db import save_user, get_user
from backend.models import UserRequest, UserResponse

# AI 모듈(ai/recommender.py)이 아직 비어있으므로 임시 mock 함수 사용
# 6단계에서 아래 한 줄만 수정하면 실제 AI 모듈로 교체됨
#     from ai.recommender import recommend_policy
from backend.mock_ai import recommend_policy


# ════════════════════════════════════════════════════════════════
# 1. 서버 시작/종료 시 실행할 작업 (lifespan)
# ════════════════════════════════════════════════════════════════
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    yield 이전 : 서버가 시작될 때 1회 실행
    yield 이후 : 서버가 종료될 때 1회 실행
    """
    # ── 시작 시 ───────────────────────────────────────────
    print("=" * 50)
    print("청년 맞춤 정책 안내 AI 서버 시작")
    load_dotenv()
    print("✅ .env 로드 완료")
    print("=" * 50)

    yield

    # ── 종료 시 ───────────────────────────────────────────
    print("서버 종료")


# ════════════════════════════════════════════════════════════════
# 2. FastAPI 앱 생성
# ════════════════════════════════════════════════════════════════
app = FastAPI(
    title="청년 맞춤 정책 안내 AI",
    description="온통청년 API 기반 정책 추천 서비스",
    version="0.1.0",
    lifespan=lifespan,
)


# ════════════════════════════════════════════════════════════════
# 3. 헬스 체크 엔드포인트 (서버 살아있는지 확인용)
# ════════════════════════════════════════════════════════════════
@app.get("/")
def root():
    return {
        "status": "ok",
        "message": "청년 맞춤 정책 안내 AI 서버 동작 중",
    }


# ════════════════════════════════════════════════════════════════
# 4. 메인 엔드포인트: /recommend
# ════════════════════════════════════════════════════════════════
@app.post("/recommend", response_model=RecommendResponse)
def recommend(request: RecommendRequest):
    """
    사용자 자연어 입력 → 맞춤 정책 Top 5 + 청년센터 반환

    요청 예시:
        {"user_input": "서울 사는 24살 대학생인데 월세 지원 받을 수 있어?"}
    """
    try:
        # ── 1) AI 추천 모듈 호출 ─────────────────────────
        # AI 담당자가 만든 recommend_policy() 함수에 사용자 입력 전달
        # 반환값: {'user_condition': {...}, 'recommendations': [...]}
        result = recommend_policy(request.user_input)

        user_condition  = result.get("user_condition", {})
        recommendations = result.get("recommendations", [])

        # ── 2) 사용자 지역 정보로 청년센터 조회 ──────────
        region  = user_condition.get("region", "")
        centers = get_centers_by_region(region) if region else []

        # ── 3) 최종 응답 반환 ────────────────────────────
        # CenterResult 필드명이 DB 컬럼명과 일치하므로 변환 불필요
        # (extra="ignore"로 잉여 컬럼은 자동 무시됨)
        return {
            "user_condition":  user_condition,
            "recommendations": recommendations,
            "centers":         centers,
        }

    except Exception as e:
        # 어떤 에러든 500 에러로 변환해서 반환
        print(f"❌ /recommend 처리 중 에러: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"추천 처리 중 오류 발생: {str(e)}",
        )
# ════════════════════════════════════════════════════════════════
# 5. USer
# ════════════════════════════════════════════════════════════════ 
@app.post("/user", response_model=UserResponse)
def create_user(request: UserRequest):
    try:
        user_id = save_user(request.model_dump())
        user = get_user(user_id)
        return user
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/user/{user_id}", response_model=UserResponse)
def read_user(user_id: str):
    user = get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다.")
    return user