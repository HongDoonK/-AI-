# ADR-001: 대화형 신청 절차 도우미 (Conversational Apply Flow)

**Status:** Proposed
**Date:** 2026-06-14
**Deciders:** 프로젝트 오너(1인 개발), 지도/평가 기준
**관련 문서:** [AGENT_APPLY_DESIGN.md](AGENT_APPLY_DESIGN.md), [REFACTORING_PLAN.md](REFACTORING_PLAN.md)

## Context

현재 모델은 두 단계로 나뉜다: **정책 추천 → 정책별 신청 절차 도움**. 후자를
아래와 같은 *자연스러운 멀티턴 대화*로 자동화하려 한다.

```
사용자: 요즘 주거 비용이 너무 많이 드는데 청년 정책 없나?
신청 Agent: 회원님 정보 기준으로 신청 가능한 청년 주거 정책 5개입니다. (①~⑤)
사용자: 그럼 <정책3>을 신청해야겠다.
신청 Agent: <정책3> 신청에는 서류1·2·3이 필요합니다.
            서류1은 정부24, 서류2는 동네 행정복지센터, 서류3은 임대차계약서.
            (각 서류 발급 방법을 접근성 좋게 안내)
사용자: 그럼 <정책3> 신청하면 나는 얼마나 받을 수 있어?
정보 Agent: <정책3>은 12개월간 매월 20만원씩 지원됩니다.
            (현금성=총액/월/기간, 주택=보증금/월세/거주기간으로 정량화)
```

### 이미 있는 자산 (재사용 대상)

| 능력 | 위치 | 비고 |
|---|---|---|
| 조건 추출 + 추천 | `ai/recommender.py`, `ai/condition_extractor.py` | `/recommend` |
| 정책 컨텍스트 로딩 | `PolicyChatAgent.load_policy_context` | 6개 소스 테이블 정규화, 캐시 |
| 서류 → 발급처 매핑 | `ai/document_registry.py` | 정부24·홈택스·대법원 등 정적 URL |
| 적격성/채널/D-day/LLM 초안 | `ai/apply_agent.py` | `/agent/apply-plan` |
| 4분류 요약(docs·자격·혜택·신청) | `PolicyChatAgent._build_user_summary` | 소스별 분기 |
| 의도 키워드 | `INTENT_KEYWORDS` (`ai/chat_labels.py`) | docs/eligibility/apply/period/benefit/contact |
| 혜택 텍스트 추출 | `_extract_benefit_bullets`, `_support_content_only` | **정량화 안 됨** |

### 빠진 것 (이번 ADR이 해결)

1. **대화 오케스트레이션 부재.** `/recommend`·`/chat`·`/agent/apply-plan`이
   각자 독립 엔드포인트라, "선택된 정책"을 턴 간 유지하거나 자유 발화를
   올바른 능력으로 라우팅하는 주체가 없다.
2. **정량화된 지원금(정보 Agent) 부재.** "12개월간 매월 20만원"·"보증금 500/
   월 20·24개월"처럼 **금액·주기·기간**을 구조화해 답하는 컴포넌트가 없다.
   현재 benefit은 `support_content`에서 뽑은 텍스트 bullet뿐이다.

### 제약(기존 설계 원칙 계승)

- N1. LLM/FAISS 없이도 규칙 기반으로 완전 동작 (recommender·apply_agent의 fallback 원칙)
- N2. 개인정보는 `user_data.db`에만, 정책 DB(`youth_policy.db`)는 읽기 전용
- N3. 1인 개발·기존 스택(FastAPI+SQLite+React) 내, 데모 신뢰성 최우선
- N4. LLM 비용: 한 턴당 호출 1회 이내, `(user, policy)` 캐시 재사용

## Decision

**백엔드에 결정론적 의도 라우터를 백본으로 하는 대화 오케스트레이터
`ConverseAgent`를 신설하고, 단일 엔드포인트 `POST /agent/converse`로
멀티턴 대화를 처리한다.** 각 턴에서 오케스트레이터는 (1) 대화 상태(선택된
정책 등)를 복원하고, (2) 사용자 발화의 의도를 분류해 기존 능력
—추천기 · 서류 안내(apply_agent) · **신설 BenefitEstimator**— 중 하나로
디스패치한 뒤, (3) 결과를 대화체로 직렬화해 응답한다. 의도 분류·인자 추출은
**LLM 우선, 규칙 fallback**으로 두어 LLM 없이도 동작시킨다.

추가로 **`ai/benefit_estimator.py`(정보 Agent)** 를 신설해 지원금을 정량화한다.

핵심: *새 도메인 로직을 거의 만들지 않는다.* 추천·서류·발급처·적격성·채널은
전부 기존 모듈을 호출만 한다. 신규 코드는 ① 라우팅/상태 관리 ② 지원금 정량화
③ 대화 직렬화에 집중한다.

## Options Considered

### Option A: 프론트엔드 상태머신 (엔드포인트 그대로, React가 오케스트레이션)

기존 3개 엔드포인트를 React에서 순차 호출하고, 선택 정책/대화 단계는
프론트 상태로 관리.

| Dimension | Assessment |
|---|---|
| Complexity | Low (백엔드 무변경) |
| Cost | 낮음 |
| Scalability | 낮음 (대화 로직이 클라이언트에 분산) |
| Team familiarity | 높음 |

**Pros:** 가장 빠른 착수, 백엔드 회귀 위험 0.
**Cons:** "자유 발화 → 의도 라우팅"을 프론트에서 하기 어렵다(=결국 버튼 UI로
회귀). 대화 상태·LLM 키가 클라이언트에 노출. 정량화 지원금 로직이 갈 곳이 없음.
재사용/테스트 불가능한 JS에 핵심 로직이 쌓임.

### Option B: 백엔드 결정론적 오케스트레이터 + 규칙/LLM 하이브리드 라우터 (선택)

`/agent/converse` 단일 엔드포인트. 의도 라우터(규칙 백본 + LLM 보강)가
recommend / docs / benefit / eligibility / smalltalk로 디스패치.

| Dimension | Assessment |
|---|---|
| Complexity | Medium |
| Cost | LLM 턴당 0~1회 |
| Scalability | 높음 (능력 추가 = 라우트 1개 추가) |
| Team familiarity | 높음 (기존 agent 패턴과 동일) |

**Pros:** 기존 모듈 재사용 극대화. 규칙 fallback으로 LLM 없이 데모 가능.
서버 단일 책임(상태·키 보호). 능력별 단위 테스트 용이.
**Cons:** 상태 저장소·라우터·직렬화 신규 코드 필요. 의도 오분류 시 엉뚱한
능력 호출 → 라우터 정확도가 UX 좌우.

### Option C: LLM 함수호출(tool-calling) 자율 에이전트

LLM에 `recommend()`·`get_documents()`·`estimate_benefit()` 도구를 주고
모델이 호출 순서를 스스로 결정.

| Dimension | Assessment |
|---|---|
| Complexity | High |
| Cost | 턴당 LLM 2~4회 (도구 호출 왕복) |
| Scalability | 높음 (도구 추가만) |
| Team familiarity | 낮음 |

**Pros:** 가장 유연한 자연어 처리. 복합 의도("서류랑 받는 금액 다 알려줘")
한 번에 처리.
**Cons:** LLM 필수 → N1(규칙 fallback) 위반, 데모 중 키/쿼터 장애에 취약.
비용·지연 최고. 비결정성으로 평가/재현 어려움. 1인 개발 범위 초과.

## Trade-off Analysis

핵심 트레이드오프는 **유연성 vs. 결정성/재현성**이다. C(tool-calling)는
자연어 유연성이 최고지만 LLM 없이는 0% 동작이라 본 프로젝트의 fallback 원칙과
데모 신뢰성에 정면 충돌한다. A(프론트)는 회귀 위험이 가장 낮지만, "자유 발화
라우팅"이라는 요구의 본질을 클라이언트에서 풀 수 없어 결국 버튼 UI로 후퇴하고
정량화 지원금 로직이 갈 곳을 잃는다.

B는 **결정론적 규칙 라우터를 백본으로, LLM을 직렬화·인자추출 보강재로** 둬서
양쪽의 장점을 취한다. 기존 `apply_agent`가 이미 "①~⑤ 규칙 + ⑥만 LLM"으로
검증한 패턴과 동일하므로 코드/인지 부하가 낮다. 라우터 오분류 리스크는
(1) 명시적 선택 버튼(추천 카드의 "이거 신청"), (2) 직전 의도 컨텍스트 유지,
(3) 모호 시 되묻기로 완화한다.

→ **Option B 채택.**

## 워크플로우 설계

```
사용자                프론트              백엔드 ConverseAgent                     데이터/모듈
  │  자유 발화          │  POST /agent/converse                                  │
  ├────────────────────>│  {session_id?, user_id?, message, selected_doc_id?}    │
  │                     ├──────────────>│ ① 세션 상태 복원 (conversations)        │ user_data.db
  │                     │               │ ② 의도 분류 (Router)                    │
  │                     │               │    규칙(INTENT_KEYWORDS) → 모호하면 LLM  │
  │                     │               │ ┌── intent = recommend ──────────────┐  │
  │                     │               │ │   recommend_policy(message)        │──┤ youth_policy.db
  │                     │               │ │   → 상위 5개, 카드 + "신청" 액션     │  │ (recommender)
  │                     │               │ ├── intent = select(정책N) ─────────┤  │
  │                     │               │ │   state.selected = doc_id          │  │
  │                     │               │ ├── intent = docs ──────────────────┤  │
  │                     │               │ │   apply_agent.build_plan(policy)   │──┤ document_registry
  │                     │               │ │   → 서류[발급처·URL] + 채널 + D-day  │  │ (apply_agent)
  │                     │               │ ├── intent = benefit (정보 Agent) ──┤  │
  │                     │               │ │   BenefitEstimator.estimate(ctx)   │──┤ policy_chat_agent
  │                     │               │ │   → {kind, total, monthly, months, │  │ .load_policy_context
  │                     │               │ │      deposit, rent, lease_months}  │  │
  │                     │               │ ├── intent = eligibility ───────────┤  │
  │                     │               │ │   check_eligibility(ctx, profile)  │──┤ (apply_agent)
  │                     │               │ └── intent = unclear → 되묻기 ───────┘  │
  │                     │               │ ③ 대화체 직렬화 (LLM NLG, 규칙 fallback)│
  │                     │<──────────────┤ ④ 상태 저장 + 응답                      │ user_data.db
  │  말풍선 + 액션칩     │  {reply, intent, cards?, documents?, benefit?,         │
  │<────────────────────┤   suggested_actions[], session_id}                    │
```

①·②(규칙 분기)·각 능력 호출·④는 LLM 없이 동작한다. ②의 모호 분류 보강과
③의 자연스러운 말투만 LLM에 의존하며, 실패 시 템플릿 직렬화로 대체한다
(`apply_agent`의 ⑥ 패턴과 동일).

### 의도 라우팅 규칙 (백본)

기존 `INTENT_KEYWORDS`를 그대로 쓰되 대화 레벨 의도를 더한다.

| 의도 | 트리거(규칙) | 디스패치 |
|---|---|---|
| `recommend` | 선택 정책 없음 + 고민/분야 발화("주거 비용", "없나") | `recommend_policy` |
| `select` | "정책3", "이거", 카드 클릭, 서수/번호 | `state.selected_doc_id` 설정 |
| `docs` | `INTENT_KEYWORDS["docs"]` + 선택 정책 있음 | `apply_agent.build_plan` 의 checklist |
| `benefit` | `INTENT_KEYWORDS["benefit"]`("얼마", "받을 수") | `BenefitEstimator` |
| `eligibility` | `INTENT_KEYWORDS["eligibility"]` | `check_eligibility` |
| `apply_how` | `INTENT_KEYWORDS["apply"]` | `PolicyChatAgent` apply_detail |
| `unclear` | 매칭 없음 | 되묻기 + suggested_actions |

선택 정책이 없는데 `docs`/`benefit` 의도가 오면 → "어떤 정책 기준으로
알려드릴까요?"로 되묻고 최근 추천 카드를 다시 제시(상태머신으로 강제).

### 정보 Agent: BenefitEstimator (`ai/benefit_estimator.py`)

`load_policy_context`의 `original`/`facts`를 입력받아 **구조화 지원금**을 낸다.
소스 테이블별로 이미 정규화된 필드를 정량화에 재사용한다.

```python
def estimate_benefit(context: dict) -> dict:
    """반환: {
      kind: 'cash' | 'housing' | 'loan' | 'training' | 'unknown',
      # cash:    total_won, monthly_won, months, formula_text
      # housing: deposit_won, monthly_rent_won, lease_months, area
      # loan:    limit_won, rate_text, term_months
      summary_line: '12개월간 매월 20만원씩 지원됩니다.',  # 대화체 한 줄
      confidence: 'exact' | 'estimated' | 'check_notice',
      sources: ['support_content', ...]                     # 근거 필드
    }"""
```

| 소스 | 정량화 근거 필드 | 산출 |
|---|---|---|
| `policies_processed` | `support_content` 파싱(금액·"개월"·"매월") | cash: 월액·개월·총액 |
| `myhome_notices` | `deposit`, `monthly_rent`, 기간 | housing |
| `rental_houses` | `bassRentGtn`, `bassMtRntchrg` | housing |
| `smallloan_youth` | `lnLmt`, `irt`, `maxTotLnTrm` | loan |
| `hrd_trainings` | `real_man`/`course_man`, 기간 | training(훈련비) |

규칙 파서(정규식: `매월\s*\d+만원`, `\d+개월`, `보증금\s*[\d,]+`)로 1차 추출하고,
값이 비거나 자유서술이면 LLM 구조화 출력으로 보강(스키마 강제), 그래도 없으면
`confidence='check_notice'` + 공고 확인 안내. `_extract_benefit_bullets`·`_money`를
재사용한다. **수치를 지어내지 않는다**(없으면 비움 + 확인 경로).

### 대화 상태 모델 (user_data.db)

```sql
CREATE TABLE conversations (
    session_id     TEXT PRIMARY KEY,        -- uuid4
    user_id        TEXT,                    -- nullable(비로그인)
    selected_doc_id TEXT,                   -- 현재 선택 정책
    last_intent    TEXT,
    last_recommendations TEXT,              -- 최근 추천 doc_id 목록 JSON(선택 재현용)
    created_at     TEXT DEFAULT (datetime('now','localtime')),
    updated_at     TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE conversation_turns (
    turn_id        TEXT PRIMARY KEY,
    session_id     TEXT NOT NULL REFERENCES conversations(session_id),
    role           TEXT NOT NULL,           -- user | assistant
    intent         TEXT,
    content        TEXT NOT NULL,
    payload        TEXT,                    -- 직렬화된 cards/benefit 등 JSON
    created_at     TEXT DEFAULT (datetime('now','localtime'))
);
```

`applications`(기존)와는 분리: 대화는 휘발성 컨텍스트, 신청은 영속 진행 상태.
사용자가 대화 중 "신청 준비"를 누르면 기존 `/agent/apply-plan`으로 연결된다
(대화 ↔ 신청 플랜의 경계 유지).

### API

| 메서드/경로 | 설명 |
|---|---|
| `POST /agent/converse` | 한 턴 처리. body: `{session_id?, user_id?, message, selected_doc_id?}` |
| `GET /agent/converse/{session_id}` | 대화 히스토리 복원 |

`POST /agent/converse` 응답 예시(benefit 턴):

```json
{
  "session_id": "…",
  "intent": "benefit",
  "reply": "선택하신 청년월세지원은 12개월간 매월 20만원씩, 최대 240만원을 지원받을 수 있어요.",
  "benefit": {
    "kind": "cash", "monthly_won": 200000, "months": 12, "total_won": 2400000,
    "summary_line": "12개월간 매월 20만원씩 지원됩니다.", "confidence": "exact"
  },
  "selected_policy": {"doc_id": "…", "title": "청년월세지원"},
  "suggested_actions": [
    {"label": "신청 서류 보기", "intent": "docs"},
    {"label": "신청 준비 시작", "action": "create_apply_plan"}
  ]
}
```

## 모듈 배치 (기존 구조 존중)

```
ai/
  converse_agent.py     ConverseAgent: 세션 복원→라우팅→디스패치→직렬화 (신규)
  intent_router.py      규칙 백본 + LLM 보강 의도 분류 (신규, 얇게)
  benefit_estimator.py  정보 Agent: 지원금 정량화 (신규)
  apply_agent.py        (재사용) build_plan / check_eligibility / build_checklist
  policy_chat_agent.py  (재사용) load_policy_context / _build_apply_detail
  recommender.py        (재사용) recommend_policy
  document_registry.py  (재사용) 서류→발급처
backend/
  conversation_store.py conversations/turns CRUD (신규, application_store와 동형)
  models.py             ConverseRequest/Response 추가
  main.py               /agent/converse 라우트(얇게)
frontend/src/
  components/ChatFlowPanel.jsx  말풍선 + 액션칩 UI (신규; 기존 ApplyPanel과 연동)
  converseClient.js             API 클라이언트 (순수 함수, 테스트 가능)
```

## 오류 처리·신뢰성

| 상황 | 처리 |
|---|---|
| LLM 실패/비활성 | 의도=규칙 분류, 응답=템플릿 직렬화 (대화는 계속) |
| 의도 모호 | `unclear` → 되묻기 + 최근 추천/액션칩 제시 |
| 선택 정책 없이 docs/benefit | 되묻기로 정책 선택 유도(상태머신 강제) |
| 지원금 수치 없음 | `confidence=check_notice`, "공고에서 금액 확인" + 링크 |
| 추천 0건 | 조건 부족 메시지(`NO_CONDITION_MESSAGE`) 재사용 + 입력 유도 |
| 세션 유실/만료 | 새 session_id 발급, selected_doc_id는 프론트가 재전송 |

관측성: 턴별 `intent`, `llm_used`, `benefit.confidence`, 소요시간 로깅
→ 데모/리포트에서 라우터 정확도·정량화 성공률 집계.

## Consequences

**쉬워지는 것**
- 한 대화창에서 추천→서류→지원금이 자연스럽게 이어짐(요구 시나리오 그대로).
- 능력 추가가 라우트 한 줄(새 intent + 디스패치)로 끝남.
- "얼마 받아?"에 정량 답변 가능(BenefitEstimator).

**어려워지는 것**
- 대화 상태 관리·세션 수명주기 신규 부담.
- 의도 라우터 정확도가 UX 품질을 좌우 → 키워드/테스트 지속 보강 필요.

**다시 볼 것**
- 복합 의도("서류랑 금액 한 번에") 빈도가 높아지면 Option C(tool-calling)
  부분 도입 재평가.
- 사용자 증가 시 `user_data.db` → Postgres, 세션 인증 도입.

## Action Items

1. [ ] `backend/conversation_store.py` + 테이블 2개 (application_store 패턴 복제)
2. [ ] `ai/benefit_estimator.py` — 소스별 정량화 + 규칙/LLM 하이브리드, 단위 테스트
3. [ ] `ai/intent_router.py` — `INTENT_KEYWORDS` 기반 규칙 분류 + 대화 의도
4. [ ] `ai/converse_agent.py` — 오케스트레이션(복원→라우팅→디스패치→직렬화)
5. [ ] `POST /agent/converse` 라우트 + `ConverseRequest/Response` 모델
6. [ ] `ChatFlowPanel.jsx` + `converseClient.js` (액션칩 → docs/benefit/신청준비)
7. [ ] 테스트: 라우터 의도 분기, BenefitEstimator 소스별 정량화, /converse smoke
       (추천→선택→서류→지원금 왕복), 기존 `/recommend`·`/chat` 회귀 불변

## 트레이드오프 기록

| 결정 | 대안 | 선택 이유 |
|---|---|---|
| 결정론 라우터 백본 + LLM 보강 | 순수 LLM tool-calling | N1(규칙 fallback)·데모 신뢰성·재현성 |
| 백엔드 오케스트레이션 | 프론트 상태머신 | 자유발화 라우팅·키 보호·로직 재사용/테스트 |
| 대화 상태 별도 테이블 | applications에 합침 | 휘발성 대화 vs 영속 신청 분리, 관심사 분리 |
| BenefitEstimator 규칙 우선 | 매번 LLM 정량화 | 비용·정확성, 정규화 필드 재사용. 수치 환각 방지 |
| 단일 `/converse` 엔드포인트 | 엔드포인트 다수 유지 | 멀티턴 상태 일원화, "한 대화창" UX와 일치 |
