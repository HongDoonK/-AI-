# AI 개발자 역할 분리 가이드

청년 정책 추천 서비스의 AI 모듈(`ai/`)을 **도메인 단위**로 나눈 협업 가이드입니다.
지금까지는 "AI 담당"이 한 덩어리라 누가 어디까지 손대야 하는지 경계가 모호했습니다.
이 문서는 모듈을 LLM / RAG / NLU / 생성 / 대화 / 오케스트레이션 도메인으로 갈라서
**소유자(Owner)**, **책임 범위**, **다른 역할과의 인터페이스(계약)**, **겹치는 부분 처리 규칙**을 정의합니다.

> 핵심 원칙: 파일은 한 명이 소유한다. 두 역할이 만나는 지점은 "파일"이 아니라 "함수 시그니처(계약)"로 나눈다.
> 계약만 안 바뀌면 각자 내부 구현은 자유롭게 바꿔도 된다.

---

## 한눈에 보는 역할 ↔ 모듈 맵

| 역할 | 별칭 | 소유 모듈 | 한 줄 책임 |
| --- | --- | --- | --- |
| **R1. LLM 플랫폼** | LLM | `ai/llm_client.py` | OpenAI 호출/구조화 출력/fallback 스위치를 한 곳에서 관리 |
| **R2. RAG / 검색** | RAG | `ai/retriever.py`, `ai/db_loader.py`, `data/index/` | 정책 후보 로드 · FAISS 임베딩 검색 · 키워드 fallback · 필터링 |
| **R3. NLU / 조건 추출** | NLU | `ai/condition_extractor.py`, `backend/region_map.py` | 자연어 → 구조화된 사용자 조건(나이/지역/관심분야 등) |
| **R4. 생성 / 응답** | GEN | `ai/generator.py` | 추천 사유 · 지원 내용 요약 · 신청 체크리스트 생성 |
| **R5. 대화 에이전트** | AGENT | `ai/policy_chat_agent.py` | `/chat` 정책별 후속 상담 (서류/자격/신청방법) |
| **R6. 오케스트레이션** | FLOW | `ai/recommender.py`, `ai/__init__.py` | 위 단계를 묶어 `recommend_policy()` 워크플로우 구성 |

의존 방향(누가 누구를 부르는가):

```text
              ┌──────────────────────────────────────────┐
              │ R6 FLOW  recommender.py                  │
              │   recommend_policy(user_input)           │
              └───┬───────┬───────────┬───────────┬──────┘
                  │       │           │           │
          extract │  load │   retrieve│  generate │
                  ▼       ▼           ▼           ▼
            ┌───────┐ ┌────────┐ ┌─────────┐ ┌──────────┐
            │ R3 NLU│ │R2 load │ │R2 RAG   │ │ R4 GEN   │
            │cond_  │ │db_     │ │retriever│ │generator │
            │extract│ │loader  │ │         │ │          │
            └───┬───┘ └───┬────┘ └────┬────┘ └────┬─────┘
                │         │           │           │
                └─────────┴─────┬─────┴───────────┘
                                ▼
                        ┌───────────────┐
                        │ R1 LLM        │   ← R3, R4, R5가 공유
                        │ llm_client.py │
                        └───────────────┘

  R5 AGENT (policy_chat_agent.py) 는 /chat 전용 경로.
  R1(LLM) + R2(db_loader) 를 재사용하지만 recommend 흐름과는 분리됨.
```

---

## 역할별 상세

### R1. LLM 플랫폼 (LLM)
- **소유 모듈**: `ai/llm_client.py`
- **책임**
  - OpenAI Responses API 클라이언트, 모델 설정(`OPENAI_MODEL`), API 키/환경변수 처리
  - `create_structured_output()`, `create_chat_response()`, `llm_enabled()` 제공
  - LLM 미사용/실패 시 일관된 `LLMUnavailable` 예외 정책
  - 토큰/비용/속도 튜닝, 프롬프트 공통 유틸, 모델 교체(gpt-4o-mini ↔ 다른 모델)
- **제공 계약(다른 역할이 의존하는 함수)**
  - `create_structured_output(schema, prompt, ...) -> dict` — R3, R4가 사용
  - `create_chat_response(messages, ...) -> str` — R5가 사용
  - `llm_enabled() -> bool` — R5 등이 분기용으로 사용
- **건드리면 안 되는 것**: 각 역할의 프롬프트 "내용"과 스키마(그건 R3/R4/R5 소유). R1은 호출 메커니즘만.

### R2. RAG / 검색 (RAG)
- **소유 모듈**: `ai/retriever.py`, `ai/db_loader.py`, `data/index/`(임베딩 캐시)
- **책임**
  - `youth_policy.db`에서 `search_documents`(우선) / `policies_processed`(fallback) 로드
  - FAISS + `jhgan/ko-sroberta-multitask` 임베딩 검색, 임베딩 캐시 관리
  - FAISS 불가 시 키워드/필터 fallback, `INTEREST_TERMS` 동의어 사전
  - 신청 기간/지역/나이/도메인/관심분야 **필터링**, Top-K 랭킹, `match_method` 표기
- **제공 계약**
  - `load_policy_df() -> DataFrame` — R6가 사용
  - `retrieve_top_k(df, condition, k) -> list[dict]` — R6가 사용
- **입력 계약**: R3가 만든 `condition` dict를 받는다(아래 공용 스키마 참조).
- **건드리면 안 되는 것**: `condition`의 "추출 방식"(R3 소유), 추천 "문장 생성"(R4 소유).

### R3. NLU / 조건 추출 (NLU)
- **소유 모듈**: `ai/condition_extractor.py`, `backend/region_map.py`
- **책임**
  - 자연어 입력 → `condition` dict(나이·성별·지역·상태·관심분야·취업상태·소득·주거상태)
  - LLM 구조화 추출 + 규칙 기반 fallback(`EMPLOYMENT_KEYWORDS`, `STATUS_KEYWORDS`, `REGIONS`)
  - 지역명 → 법정동 코드 매핑(`REGION_CODE_MAP`)
  - `has_condition_signal()` 등 "조건이 충분한가" 판단
- **제공 계약**
  - `extract_user_condition(user_input) -> condition(dict)` — R6가 사용
  - `has_condition_signal(...)` — R6가 사용
- **건드리면 안 되는 것**: 검색/필터 로직(R2). R3는 "무엇을 원하는가"만 만들고, "어떻게 찾는가"는 R2.

### R4. 생성 / 응답 (GEN)
- **소유 모듈**: `ai/generator.py`
- **책임**
  - 검색된 정책 후보 → 추천 사유, 지원 내용 요약, 신청 가능성(`높음/확인 필요/낮음`), 체크리스트
  - 도메인 라벨링(`DOMAIN_LABELS`), 출력 JSON 형식(README "응답 형식" 계약과 일치 유지)
  - LLM 생성 + 규칙 기반 fallback
- **제공 계약**
  - `generate_recommendations(condition, candidates) -> list[recommendation(dict)]` — R6가 사용
- **건드리면 안 되는 것**: 후보를 "고르는" 일(R2). R4는 받은 후보를 "설명/포장"만 한다.

### R5. 대화 에이전트 (AGENT)
- **소유 모듈**: `ai/policy_chat_agent.py`
- **책임**
  - `/chat` 정책별 후속 상담: 제출 서류·자격·신청 방법·기간·문의처
  - 원본 테이블(`SOURCE_KEY_COLUMNS`/`SOURCE_LABELS`) 재조회로 근거 있는 답변
  - 멀티턴 메시지 처리, LLM 미사용 시 안내 응답
- **재사용(소유 아님)**: R1 `create_chat_response`, R2 `find_db_path`
- **분리 포인트**: 추천(`/recommend`) 흐름과 **독립**. 추천 결과를 입력으로 받되 추천 로직은 모른다.

### R6. 오케스트레이션 (FLOW)
- **소유 모듈**: `ai/recommender.py`, `ai/__init__.py`
- **책임**
  - `recommend_policy(user_input)` 한 함수로 R3 → R2 → R4 순서 연결
  - 조건 부족 시 `NO_CONDITION_MESSAGE` 처리, 직접 입력 vs 저장 프로필 우선순위
  - 최종 응답 JSON 조립(`backend/main.py`가 그대로 반환)
- **건드리면 안 되는 것**: 각 단계 내부 구현. R6는 "순서와 연결"만 책임진다.

---

## 공용 데이터 계약 (역할 경계의 핵심)

겹침을 막는 가장 중요한 장치는 **모듈 사이를 오가는 dict 스키마**를 고정하는 것입니다.
아래 두 개만 합의되어 있으면 R2/R3/R4는 서로의 내부를 몰라도 됩니다.

### `condition` (R3 생산 → R2·R4 소비)
```python
{
  "age": int | None,
  "gender": str | None,
  "region": str | None,            # 시도 단위
  "region_sigungu": str | None,
  "status": str | None,            # 대학생/직장인 등
  "interest": str | None,          # 주거/취업/창업/교육/복지/금융
  "employment_status": str | None,
  "income": str | None,
  "housing_status": str | None,
}
```

### `recommendation` (R4 생산 → R6 소비 → 프론트엔드)
```python
{
  "policy_name": str,
  "apply_possibility": "높음" | "확인 필요" | "낮음",
  "reason": str,
  "support_content": str,
  "application_period": str,
  "application_url": str,
  "checklist": [str, ...],
}
```

> 이 스키마를 바꿔야 하면 **혼자 바꾸지 말 것.** 생산자와 소비자 역할이 같이 합의하고
> README의 "응답 형식" 섹션도 함께 업데이트한다.

---

## 겹치는 부분 처리 규칙 (자주 부딪히는 지점)

| 상황 | 누가 소유? | 규칙 |
| --- | --- | --- |
| "관심분야 키워드"가 추출(NLU)에도 검색(RAG)에도 필요 | R3가 추출, R2가 검색 사전 소유 | `condition["interest"]`는 R3. `INTEREST_TERMS` 동의어 확장은 R2. 새 분야 추가 시 둘이 같이 PR. |
| 프롬프트 수정 | 프롬프트 소유 역할 | 프롬프트 "문구/스키마"는 R3·R4·R5 각자. 호출 함수는 R1. |
| 모델 교체 / 비용 이슈 | R1 | R1이 `llm_client.py`에서 단독 처리. 다른 역할은 영향 없음. |
| 새 데이터 소스 테이블 추가 | R2 + R5 | 스키마/로드는 R2, `/chat` 원문 조회 매핑은 R5. |
| 응답 JSON 필드 추가 | R4 + R6 | R4가 필드 생성, R6·README 계약 동기화, 프론트엔드에 공지. |
| fallback(LLM 없이 동작) 동작 | 각 역할 | 각자 자기 모듈의 규칙 기반 fallback을 직접 책임진다. |

**한 PR이 두 역할의 소유 모듈을 동시에 건드리면** → 두 소유자 모두 리뷰어로 지정.

---

## 팀 규모별 배정 예시

역할은 6개지만 사람 수에 맞춰 묶으면 됩니다.

- **2명**: ① RAG+NLU+FLOW(데이터/검색 파이프라인) · ② LLM+GEN+AGENT(LLM/생성/대화)
- **3명**: ① RAG+FLOW · ② NLU+LLM · ③ GEN+AGENT
- **4명**: ① RAG · ② NLU · ③ GEN+FLOW · ④ LLM+AGENT
- **5~6명**: 표의 R1~R6 1:1 배정

> 묶더라도 "파일 단위 소유"는 유지하세요. 사람이 늘면 묶음만 쪼개면 되도록.

---

## 브랜치 / 커밋 컨벤션 제안

코드 충돌을 줄이려면 역할 약칭을 브랜치·커밋에 붙이는 걸 권장합니다.

```text
feat(rag): FAISS 캐시 무효화 로직 추가
fix(nlu): "취준생" 조건 추출 누락 수정
feat(gen): 체크리스트 항목 우선순위 정렬
```

역할 약칭: `llm` / `rag` / `nlu` / `gen` / `agent` / `flow`

---

## 체크리스트 (PR 올리기 전)

- [ ] 내 PR이 **내 소유 모듈** 안에서 끝나는가? 아니면 다른 소유자를 리뷰어로 넣었는가?
- [ ] `condition` / `recommendation` 스키마를 바꿨다면 소비자 역할과 합의했는가?
- [ ] LLM 없이도(fallback) 동작하는가?
- [ ] README의 모듈 설명/응답 형식과 어긋나지 않는가?
