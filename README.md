# 청년 맞춤 정책 안내 AI

통합청년 API와 SQLite DB를 기반으로 사용자의 나이, 성별, 지역, 상태, 관심 분야를 분석해 현재 신청 가능한 청년 정책과 가까운 청년센터를 추천하는 FastAPI + React 프로젝트입니다.

사용자가 자연어로 상황을 입력하면 AI 모듈이 조건을 추출하고, `search_documents` 통합 검색 테이블과 `policies_processed` fallback 테이블에서 정책 후보를 검색한 뒤 추천 사유, 지원 내용, 신청 기간, 신청 링크, 체크리스트를 반환합니다. OpenAI API 키가 있으면 LLM 기반 조건 추출/응답 생성을 사용하고, 없으면 규칙 기반 fallback으로 동작합니다.

이 프로젝트는 단순 질의응답 챗봇보다 "정책 추천 업무 흐름" 구현에 초점을 둡니다. 자연어 조건 추출, RAG 검색, 정책 필터링, 신청 가능성 판단, 소득/세금 계산, 정책별 후속 상담, 신청 준비 체크리스트 생성을 하나의 워크플로우로 연결합니다.

> AI 개발자 역할 분리(LLM / RAG / NLU / 생성 / 대화 / 오케스트레이션)와 협업 가이드는 [`docs/AI_ROLES.md`](docs/AI_ROLES.md)를 참고하세요.

## 주요 기능

- 자연어 입력 기반 청년 정책 Top 5 추천
- 나이, 지역, 상태, 관심 분야, 취업 상태, 소득, 주거 상태, 성별 조건 추출
- 로그인/프로필 입력값을 SQLite `users` 테이블에 저장
- 저장된 프로필을 추천 요청에 함께 반영
- 신청 종료 정책 제외 및 나이 조건 필터링
- FAISS + `jhgan/ko-sroberta-multitask` 임베딩 검색
- FAISS/임베딩 사용이 불가능할 때 키워드 검색으로 fallback
- 지역 기반 청년센터 목록 조회
- 정책별 후속 질문에 답하는 `/chat` 상담 에이전트
- 추천 정책의 마감일, 신청 우선순위, 준비 서류를 정리하는 신청 준비 리포트
- 저장된 프로필과 정책 조건을 비교하는 자동 적격성 1차 검증
- 2026년 기준 중위소득 환산 및 근로소득 실수령액 계산기
- Vite React 프론트엔드와 FastAPI 백엔드 연동

## 과제 기준 대응

### 다양한 도구를 활용한 AI 에이전트 프로토타입

프로젝트 안에서 여러 기능 모듈을 도구처럼 분리해 사용합니다.

- `condition_extractor.py`: 자연어에서 나이, 지역, 관심 분야, 취업 상태, 소득 조건 추출
- `retriever.py`: FAISS 임베딩 검색 또는 키워드 fallback 검색
- `generator.py`: 추천 사유, 지원 내용 요약, 신청 체크리스트 생성
- `policy_chat_agent.py`: 특정 정책을 기준으로 서류, 자격, 신청 방법, 혜택을 후속 상담
- `agentPlanner.js`: 추천 결과의 마감일과 우선순위를 분석해 신청 준비 리포트 생성
- `eligibilityCheck.js`: 저장된 프로필과 정책 조건을 비교해 신청이 어려운 정책 탐지
- `incomeTax.js`, `medianIncome.js`: 소득/중위소득 관련 계산 도구

OpenAI API가 설정된 경우 `llm_client.py`가 Responses API의 구조화 출력을 사용해 조건 추출과 추천 문장 생성을 수행합니다. API 키가 없거나 LLM 호출에 실패하면 규칙 기반 로직으로 fallback하여 시연 안정성을 유지합니다.

### 워크플로우 기반 복합 로직

전체 추천 흐름은 다음과 같은 업무형 워크플로우로 구성됩니다.

```text
사용자 프로필 저장/자연어 질문 입력
-> 조건 추출: 나이, 지역, 상태, 관심 분야, 소득, 주거 상태
-> DB 로드: search_documents 우선, 없으면 policies_processed fallback
-> RAG 검색: FAISS 임베딩 검색 또는 키워드/필터 검색
-> 정책 필터링: 신청 기간, 지역, 나이, 도메인, 관심 분야
-> 추천 생성: 지원 내용 요약, 신청 가능성, 체크리스트 생성
-> 후속 작업: 정책별 상담, 청년센터 조회, 신청 준비 리포트, 적격성 검증
```

직접 질문에 포함된 조건은 저장된 프로필보다 우선합니다. 예를 들어 프로필 관심 분야가 `주거`여도 질문에 `복지 정책 추천`이라고 쓰면 추천 관심 분야는 `복지`로 처리됩니다.

### RAG와 Tool Calling 관점

- RAG: `search_documents` 16,571건의 통합 검색 문서와 FAISS 임베딩을 이용해 사용자 조건에 맞는 정책 후보를 검색합니다.
- Tool Calling 관점: OpenAI의 명시적 function calling을 전면에 둔 구조는 아니지만, 추천 엔진이 내부 도구 모듈을 단계별로 호출하는 방식으로 구현되어 있습니다. 발표 시에는 `조건 추출 도구 -> 검색 도구 -> 생성 도구 -> 상담 도구 -> 신청 준비 도구`의 순서로 설명하면 좋습니다.
- 업무 로직: 정책 데이터의 도메인, 지역, 연령, 신청 기간, 소득 정보를 반영하므로 단순한 일반 Q&A보다 과제 주제에 맞는 정교한 추천 로직을 갖습니다.

## 프로젝트 구조

```text
backend/
  main.py              FastAPI 서버 진입점, /recommend 및 /user API
  db.py                SQLite 연결, 테이블 생성, 사용자/센터 조회
  api_collector.py     통합청년 정책/청년센터 API 수집
  preprocessing.py     원본 정책 데이터 전처리 및 search_documents 생성
  models.py            Pydantic 요청/응답 모델
  config.py            API 필드와 DB 컬럼 매핑
  region_map.py        시도/시군구 코드 매핑

ai/
  condition_extractor.py  사용자 입력에서 추천 조건 추출
  db_loader.py            youth_policy.db의 search_documents/policies_processed 로드
  retriever.py            정책 후보 필터링, FAISS 검색, 키워드 fallback
  generator.py            추천 사유/체크리스트 생성
  policy_chat_agent.py    정책별 후속 상담 에이전트
  llm_client.py           OpenAI Responses API 구조화 출력 클라이언트
  recommender.py          recommend_policy() 통합 함수

frontend/
  src/App.jsx          React 화면, 프로필 저장, 추천 요청
  src/agentPlanner.js  신청 우선순위/마감 위험 분석
  src/prepTracker.js   신청 준비 체크리스트 상태 관리
  src/eligibilityCheck.js  프로필 기반 적격성 1차 검증
  src/incomeTax.js     연봉 실수령액 계산
  src/medianIncome.js  기준 중위소득 비율 계산
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

`backend.preprocessing`은 기존 `policies_processed`를 정리하고, 여러 출처의 데이터를 RAG 검색용 `search_documents` 통합 테이블로 재생성합니다. 시연 전에 이 명령을 실행해야 정책별 상담과 통합 검색 품질이 안정적으로 나옵니다.

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

### 정책별 상담

`POST /chat`

```json
{
  "policy": {
    "policy_name": "청년 매입임대주택 사업",
    "doc_id": "policies_processed:...",
    "source_table": "policies_processed",
    "source_id": "..."
  },
  "user_context": {
    "age": 24,
    "region": "서울 관악구"
  },
  "messages": [
    {
      "role": "user",
      "content": "이 정책 신청할 때 필요한 서류가 뭐야?"
    }
  ]
}
```

정책별 상담 에이전트는 DB 원문과 통합 검색 문서를 다시 조회해 제출 서류, 자격 조건, 신청 방법, 기간, 문의처를 답변합니다.

## 추천 흐름

```text
프론트엔드 입력/프로필
-> POST /recommend
-> ai.recommender.recommend_policy()
-> condition_extractor: 사용자 조건 추출
-> db_loader: data/youth_policy.db의 search_documents 로드
-> retriever: 신청 가능 정책 필터링 + FAISS/키워드 검색
-> generator: 추천 사유와 체크리스트 생성
-> main.py: 지역 기반 청년센터 조회
-> 추천 정책, 사용자 조건, 청년센터 JSON 반환
```

## DB 구조

추천 로직은 `search_documents`를 우선 사용하고, 해당 테이블이 비어 있거나 없으면 `policies_processed`를 fallback으로 사용합니다.

```text
policies
  API에서 수집한 원본 정책 데이터

policies_processed
  전처리된 정책 데이터
  search_text 컬럼을 포함하며 fallback 추천 검색에 사용

search_documents
  여러 원본 테이블을 통합한 RAG 검색 문서
  domain, source_table, source_id, doc_id, 지역, 대상, 기간, search_text 포함

hrd_trainings
  HRD-Net 직업훈련 데이터

kstartup_notices
  K-Startup 창업 공고 데이터

smallloan_youth
  청년 금융상품 데이터

myhome_notices
  마이홈 임대공고 데이터

rental_houses
  청년 임대주택 단지 데이터

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

## 검증 결과

현재 로컬 환경에서 다음 항목을 확인했습니다.

```text
python -m compileall backend ai tests
결과: 통과

python -m unittest discover -s tests
결과: 1개 테스트 통과

cd frontend
node --test src\*.test.mjs
결과: 2개 테스트 통과

cd frontend
npm run build
결과: Vite 프로덕션 빌드 성공
```

API 레벨 검증:

- `GET /`: 200 응답
- `GET /chat/status`: 200 응답
- `POST /recommend`: 200 응답, 추천 정책 5개 반환
- `POST /chat`: 200 응답, 정책별 후속 상담 정상 응답
- `USE_FAISS=1` 상태에서 `match_method`가 `FAISS 임베딩`인 추천 결과 반환 확인
- `backend.preprocessing` 실행 후 `search_documents` 16,571건 생성 확인

평가 기준 관점에서는 RAG와 워크플로우 기반 복합 로직은 강하게 구현되어 있습니다. 다만 OpenAI의 명시적 function calling을 직접 사용하기보다는 내부 모듈을 도구처럼 순차 호출하는 구조이므로, 발표에서는 이 부분을 "도구형 모듈 호출 기반 에이전트 워크플로우"로 설명하는 것이 적절합니다.

## 주의 사항

- `.env`에는 API 키가 들어가므로 공개 저장소에 올리지 않습니다.
- `data/youth_policy.db`를 삭제하면 정책/센터 데이터를 다시 수집하고 전처리해야 합니다.
- `search_documents`가 비어 있으면 `python -m backend.preprocessing`을 다시 실행합니다.
- `data/index/*.npy`는 FAISS 임베딩 캐시입니다. 정책 데이터가 바뀌면 새 캐시가 자동 생성될 수 있습니다.
- `frontend/node_modules`와 빌드 결과물은 `npm install`, `npm run build`로 다시 만들 수 있습니다.
- OpenAI 또는 FAISS 의존성이 없어도 fallback 로직으로 기본 추천은 동작하지만, 추천 품질은 달라질 수 있습니다.
