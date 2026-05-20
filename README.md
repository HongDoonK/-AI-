# 청년 맞춤 정책 안내 AI 서비스

온통청년 정책/센터 API와 SQLite DB를 기반으로 사용자의 나이, 지역, 상태, 관심 분야를 분석해 현재 신청 가능한 청년정책과 가까운 청년센터를 안내하는 FastAPI + React 프로젝트입니다.

## 현재 구조

```text
backend/
  main.py              FastAPI 서버 진입점, /recommend 및 /user API
  db.py                SQLite 연결, 테이블 생성, 사용자 정보 저장/조회
  api_collector.py     온통청년 청년정책/청년센터 API 수집
  preprocessing.py     코드값 변환, search_text 생성, policies_processed 저장
  models.py            Pydantic 요청/응답 모델
  config.py            API 필드와 DB 컬럼 매핑
  region_map.py        시도/시군구 선택용 지역 매핑

ai/
  db_loader.py         youth_policy.db 탐색 및 policies_processed 로드
  condition_extractor.py 사용자 입력과 로그인 프로필 조건 추출
  retriever.py         정책 후보 필터링 및 검색
  generator.py         추천 사유/checklist 응답 생성
  recommender.py       백엔드가 호출하는 recommend_policy()

frontend/
  src/App.jsx          React 화면 및 API 연결
  src/styles.css       화면 스타일
  vercel.json          Vercel 배포 설정
  package.json         프론트엔드 의존성/스크립트

data/
  youth_policy.db      SQLite DB

requirements.txt       백엔드 Python 의존성
.env                   API 키 등 로컬 환경 변수
```

## 삭제한 항목

이번 정리에서 현재 실행 흐름에 필요 없는 파일과 폴더를 제거했습니다.

- `src/`: 예전 CSV/FAISS/LLM 실험 코드입니다. 현재 `/recommend`는 `ai/recommender.py`를 사용합니다.
- `prompts/`: 예전 LLM 프롬프트 파일입니다. 현재 조건 추출과 응답 생성은 `ai/` 내부 로직으로 처리합니다.
- `tests/`: 이전 `src/` 구조 기준 테스트라 현재 코드와 맞지 않습니다.
- `app.py`: 예전 CLI 실행 파일이며 FastAPI 서버는 `backend/main.py`를 사용합니다.
- `backend/mock_ai.py`: 임시 추천 함수였고 현재는 `ai.recommender.recommend_policy`로 교체되었습니다.
- `data/raw/`, `data/processed/`: API 원본 텍스트와 CSV 산출물입니다. 현재 추천은 CSV가 아니라 `data/youth_policy.db`의 `policies_processed`를 읽습니다.
- `data/index/`: 예전 FAISS 산출물입니다. 현재 기본 검색은 안정적인 키워드/조건 기반 fallback으로 동작합니다.
- `frontend/dist/`: 빌드 결과물입니다. `npm run build`로 언제든 다시 생성됩니다.
- `frontend/node_modules/`: 설치 산출물입니다. `npm install`로 다시 생성됩니다.
- `backend/__pycache__/`, `ai/__pycache__/`: Python 캐시입니다. 실행 시 자동 생성됩니다.
- 루트 `package-lock.json`: 루트에는 `package.json`이 없어 불필요합니다. 프론트엔드용 `frontend/package-lock.json`은 유지했습니다.
- `RUN_BACKEND.md`: README와 내용이 중복되어 제거했습니다.

## DB 구조

추천은 반드시 `policies_processed` 테이블을 사용합니다.

```text
policies
  API 원본 정책 데이터입니다. 코드값이 그대로 있어 AI 검색에 직접 사용하지 않습니다.

policies_processed
  전처리 완료 정책 데이터입니다.
  search_text 컬럼이 있으며 추천 로직이 이 테이블을 읽습니다.

centers
  청년센터 데이터입니다.

users
  프론트엔드 로그인/프로필 입력값을 저장합니다.
```

## 추천 흐름

```text
프론트엔드 입력
-> POST /recommend
-> ai.recommender.recommend_policy()
-> 사용자 조건 추출
-> data/youth_policy.db 의 policies_processed 로드
-> 종료된 정책 제외
-> 나이/상태/관심분야/지역 보조 조건 기반 검색
-> 최대 5개 추천 JSON 반환
```

질문에 직접 적힌 조건을 로그인 프로필보다 우선합니다. 예를 들어 프로필 관심 분야가 `주거`여도 사용자가 `복지 정책 추천`이라고 입력하면 관심 분야는 `복지`로 처리합니다.

## 백엔드 실행

프로젝트 루트에서 실행합니다.

```bash
python -m venv venv
```

Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

macOS/Linux:

```bash
source venv/bin/activate
```

의존성 설치:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

DB 생성 및 데이터 갱신:

```bash
python -m backend.db
python -m backend.api_collector
python -m backend.preprocessing
```

서버 실행:

```bash
python -m uvicorn backend.main:app --reload
```

문서 확인:

```text
http://127.0.0.1:8000/docs
```

## 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
```

기본 주소:

```text
http://127.0.0.1:5173
```

## API 예시

`POST /recommend`

```json
{
  "user_input": "서울 관악구 사는 24살 대학생인데 복지 정책 추천해줘"
}
```

응답 형태:

```json
{
  "user_condition": {
    "age": 24,
    "region": "서울 관악구",
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

## Vercel 배포

Vercel에는 프론트엔드만 배포합니다.

```text
Root Directory: frontend
Framework Preset: Vite
Build Command: npm run build
Output Directory: dist
```

환경 변수:

```text
VITE_API_URL=https://배포된-백엔드-주소
```

백엔드를 Render/Railway/Fly.io 등에 배포하지 않는 경우에는 발표 PC에서 백엔드를 로컬로 실행하고, 프론트엔드가 `http://localhost:8000`을 바라보게 사용할 수 있습니다. 이 방식은 접속한 사람의 컴퓨터에서 `localhost:8000`을 찾기 때문에 공개 서비스용은 아니고 발표/시연용에 가깝습니다.

## 주의

- `data/youth_policy.db`는 삭제하면 안 됩니다.
- API 키는 `.env`에만 보관하고 Git/Vercel 공개 로그에 노출하지 않습니다.
- `frontend/node_modules`와 `frontend/dist`는 삭제되어 있어도 정상입니다. 각각 `npm install`, `npm run build`로 다시 생성됩니다.
- FAISS를 다시 쓰고 싶다면 `data/index`를 새로 생성하는 스크립트를 별도로 복구하거나 현재 `ai/retriever.py`에 맞춰 재구성해야 합니다.
