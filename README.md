# 청년 맞춤 정책 안내 AI

통합청년 API와 SQLite DB를 기반으로 사용자의 나이, 성별, 지역, 상태, 관심 분야를 분석해 현재 신청 가능한 청년 정책과 가까운 청년센터를 추천하는 FastAPI + React 프로젝트입니다.

사용자가 자연어로 상황을 입력하면 AI 모듈이 조건을 추출하고, `policies_processed` 테이블에서 정책 후보를 검색한 뒤 추천 사유, 지원 내용, 신청 기간, 신청 링크, 체크리스트를 반환합니다. OpenAI API 키가 있으면 LLM 기반 조건 추출/응답 생성을 사용하고, 없으면 규칙 기반 fallback으로 동작합니다.

## 주요 기능

- 자연어 입력 기반 청년 정책 Top 5 추천
- 나이, 지역, 상태, 관심 분야, 취업 상태, 소득, 주거 상태, 성별 조건 추출
- 로그인/프로필 입력값을 SQLite `users` 테이블에 저장
- 저장된 프로필을 추천 요청에 함께 반영
- 신청 종료 정책 제외 및 나이 조건 필터링
- FAISS + `jhgan/ko-sroberta-multitask` 임베딩 검색
- FAISS/임베딩 사용이 불가능할 때 키워드 검색으로 fallback
- 지역 기반 청년센터 목록 조회
- Vite React 프론트엔드와 FastAPI 백엔드 연동

## 프로젝트 구조

```text
backend/
  main.py              FastAPI 서버 진입점, /recommend 및 /user API
  db.py                SQLite 연결, 테이블 생성, 사용자/센터 조회
  api_collector.py     통합청년 정책/청년센터 API 수집
  preprocessing.py     원본 정책 데이터 전처리 및 search_text 생성
  models.py            Pydantic 요청/응답 모델
  config.py            API 필드와 DB 컬럼 매핑
  region_map.py        시도/시군구 코드 매핑

ai/
  condition_extractor.py  사용자 입력에서 추천 조건 추출
  db_loader.py            youth_policy.db의 policies_processed 로드
  retriever.py            정책 후보 필터링, FAISS 검색, 키워드 fallback
  generator.py            추천 사유/체크리스트 생성
  llm_client.py           OpenAI Responses API 구조화 출력 클라이언트
  recommender.py          recommend_policy() 통합 함수

frontend/
  src/App.jsx          React 화면, 프로필 저장, 추천 요청
  src/styles.css       화면 스타일
  vercel.json          Vercel 배포 설정
  package.json         프론트엔드 의존성 및 스크립트

data/
  youth_policy.db      SQLite DB
  index/               정책 임베딩 캐시(.npy)

requirements.txt       백엔드 Python 의존성
.env.example           환경변수 예시
```

## 환경변수

프로젝트 루트에 `.env` 파일을 만들고 필요한 값을 설정합니다.

```env
YOUTH_POLICY_API_KEY=your_youth_policy_api_key
YOUTH_CENTER_API_KEY=your_youth_center_api_key

OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-4o-mini
USE_OPENAI_LLM=1

USE_FAISS=1
FRONTEND_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

OpenAI를 사용하지 않으려면 `USE_OPENAI_LLM=0`으로 설정하거나 `OPENAI_API_KEY`를 비워두면 됩니다. FAISS 임베딩 검색을 끄고 키워드 검색만 사용하려면 `USE_FAISS=0`으로 설정합니다.

## 백엔드 실행

프로젝트 루트에서 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

DB 테이블 생성 및 API 데이터 수집/전처리:

```powershell
python -m backend.db
python -m backend.api_collector
python -m backend.preprocessing
```

서버 실행:

```powershell
python -m uvicorn backend.main:app --reload
```

기본 주소:

```text
http://127.0.0.1:8000
http://127.0.0.1:8000/docs
```

## 프론트엔드 실행

```powershell
cd frontend
npm install
npm run dev
```

기본 주소:

```text
http://127.0.0.1:5173
```

백엔드 주소를 바꾸려면 프론트엔드 환경변수로 설정합니다.

```env
VITE_API_URL=http://127.0.0.1:8000
```

`VITE_API_URL`에 `/recommend`까지 넣어도 프론트엔드에서 자동으로 기본 API 주소로 정리합니다.

## API 사용 예시

### 정책 추천

`POST /recommend`

```json
{
  "user_input": "서울 관악구 사는 24세 대학생인데 복지 정책 추천해줘"
}
```

응답 형식:

```json
{
  "user_condition": {
    "age": 24,
    "region": "서울",
    "status": "대학생",
    "interest": "복지",
    "employment_status": null,
    "income": null,
    "housing_status": null,
    "gender": null
  },
  "recommendations": [
    {
      "policy_name": "...",
      "apply_possibility": "높음",
      "reason": "...",
      "support_content": "...",
      "application_period": "...",
      "application_url": "...",
      "checklist": ["...", "...", "..."]
    }
  ],
  "centers": []
}
```

### 사용자 프로필 저장

`POST /user`

```json
{
  "age": 24,
  "gender": "여성",
  "region_sido": "서울",
  "region_sigungu": "관악구",
  "status": "대학생",
  "interest": "주거",
  "employment_status": null,
  "income": "중위소득 100%",
  "housing_status": "월세"
}
```

저장된 사용자는 `GET /user/{user_id}`로 다시 조회할 수 있습니다. 프론트엔드는 저장된 프로필을 `localStorage`에도 보관하고 추천 요청 시 자연어 입력에 함께 붙여 보냅니다.

## 추천 흐름

```text
프론트엔드 입력/프로필
-> POST /recommend
-> ai.recommender.recommend_policy()
-> condition_extractor: 사용자 조건 추출
-> db_loader: data/youth_policy.db의 policies_processed 로드
-> retriever: 신청 가능 정책 필터링 + FAISS/키워드 검색
-> generator: 추천 사유와 체크리스트 생성
-> main.py: 지역 기반 청년센터 조회
-> 추천 정책, 사용자 조건, 청년센터 JSON 반환
```

직접 질문에 들어간 조건이 저장된 프로필보다 우선됩니다. 예를 들어 프로필 관심 분야가 `주거`여도 질문에 `복지 정책 추천`이라고 쓰면 관심 분야는 `복지`로 처리됩니다.

## DB 구조

추천 로직은 주로 `policies_processed`를 사용합니다.

```text
policies
  API에서 수집한 원본 정책 데이터

policies_processed
  전처리된 정책 데이터
  search_text 컬럼을 포함하며 추천 검색에 사용

centers
  청년센터 데이터

users
  프론트엔드에서 저장한 사용자 프로필
```

DB 파일 탐색 순서는 다음과 같습니다.

```text
youth_policy.db
data/youth_policy.db
backend/youth_policy.db
```

## Vercel 배포

Vercel에는 프론트엔드만 배포합니다.

```text
Root Directory: frontend
Framework Preset: Vite
Build Command: npm run build
Output Directory: dist
```

Vercel 환경변수:

```text
VITE_API_URL=https://배포된-백엔드-주소
```

백엔드는 Render, Railway, Fly.io 같은 별도 서비스에 배포하거나 발표/시연 환경에서는 로컬에서 실행할 수 있습니다. 로컬 백엔드를 사용하는 경우 프론트엔드가 접근할 수 있도록 `FRONTEND_ORIGINS`와 `VITE_API_URL`을 함께 확인해야 합니다.

## 주의 사항

- `.env`에는 API 키가 들어가므로 공개 저장소에 올리지 않습니다.
- `data/youth_policy.db`를 삭제하면 정책/센터 데이터를 다시 수집하고 전처리해야 합니다.
- `data/index/*.npy`는 FAISS 임베딩 캐시입니다. 정책 데이터가 바뀌면 새 캐시가 자동 생성될 수 있습니다.
- `frontend/node_modules`와 빌드 결과물은 `npm install`, `npm run build`로 다시 만들 수 있습니다.
- OpenAI 또는 FAISS 의존성이 없어도 fallback 로직으로 기본 추천은 동작하지만, 추천 품질은 달라질 수 있습니다.
