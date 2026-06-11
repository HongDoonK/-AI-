# 설계: 신청 도우미 에이전트 (Apply Assistant Agent)

> 추천된 정책별로 개인화된 신청 체크리스트를 만들고, 클릭 한 번으로
> "신청 준비 → 신청 페이지 진입 → 진행 추적"까지 이어주는 에이전트 워크플로우.

## 0. 핵심 전제와 트레이드오프 (먼저 읽을 것)

**"클릭 한 번으로 신청 완료(자동 제출)"는 현재 불가능하다.**

| 이유 | 내용 |
|---|---|
| 인증 | 복지로/정부24/지자체 시스템은 공동인증서·간편인증 등 본인인증 필수 |
| API 부재 | 신청 제출용 공개 API가 없음 (조회용 API만 존재) |
| 법적 리스크 | 대리 제출·자동화 입력은 각 시스템 약관 위반 소지 |

따라서 목표를 **"클릭 한 번으로 신청 '준비'가 끝나는 에이전트"**로 정의한다.
사용자가 누르는 버튼은 하나지만, 그 뒤에서 에이전트가 적격성 검증 → 서류
체크리스트 생성 → 발급처 연결 → 신청 채널 결정 → 신청서 초안 작성을 모두
수행하고, 마지막 "제출"만 사용자가 인증 후 직접 한다. 완전 자동화는
Phase 3 연구 과제로 분리한다 (§7).

## 1. 요구사항

### 기능 요구사항
- F1. 추천 정책 카드의 **[신청 준비하기]** 버튼 1회 클릭 → 신청 플랜 자동 생성
- F2. 신청 플랜 구성: 적격성 판정, 제출 서류 체크리스트(발급처 링크 포함),
  자격 확인 항목, 신청 채널(온라인 URL/방문/우편/문의), 단계별 액션, D-day
- F3. (LLM 가용 시) 신청서 단골 항목(신청 사유 등) 초안 자동 작성
- F4. 체크리스트 체크 상태·신청 상태를 서버에 저장하고 재방문 시 복원
- F5. 신청 상태머신: `draft → preparing → ready → submitted → done/expired`
- F6. 마감 임박 정책 우선 정렬·배지 (기존 agentPlanner 로직 서버 연동)

### 비기능 요구사항
- N1. LLM/FAISS 없이도 규칙 기반으로 완전 동작 (기존 fallback 원칙 유지)
- N2. 플랜 생성 응답 p95 < 3초 (LLM 1회 호출 이내), 규칙 기반은 < 300ms
- N3. 개인정보(프로필, 신청 상태)는 user_data.db에만 저장 (정책 DB와 분리 유지)
- N4. LLM 비용: 플랜 1건당 호출 1회로 제한, 동일 (user, policy) 캐시
- N5. 1인 개발·기존 스택(FastAPI+SQLite+React) 내에서 구현

## 2. 전체 워크플로우

```
사용자                프론트엔드                  백엔드 (ApplyAgent)              데이터
  │  추천 결과 보기      │                            │                          │
  │ [신청 준비하기] 클릭 │                            │                          │
  ├────────────────────>│ POST /agent/apply-plan     │                          │
  │                     ├───────────────────────────>│                          │
  │                     │              ① Context Loader ──────────────────────> │ youth_policy.db
  │                     │                 (정책 원문/통합문서 로드,              │ (읽기 전용)
  │                     │                  PolicyChatAgent 컨텍스트 재사용)      │
  │                     │              ② Eligibility Checker <───────────────── │ user_data.db
  │                     │                 (프로필 vs 나이/지역/소득/상태)        │ (users)
  │                     │              ③ Checklist Builder                      │
  │                     │                 - submit_docs 파싱 → 서류 항목         │
  │                     │                 - document_registry로 발급처 매핑      │
  │                     │                 - 자격 확인 항목 생성                  │
  │                     │              ④ Channel Resolver                       │
  │                     │                 (application_url > ref_url > 문의처)   │
  │                     │              ⑤ Action Planner                         │
  │                     │                 (마감 D-day, 단계 순서, 우선순위)      │
  │                     │              ⑥ [LLM] Draft Writer (선택)              │
  │                     │                 (신청 사유 초안, 서류별 안내문)        │
  │                     │              ⑦ 저장 ─────────────────────────────────> │ user_data.db
  │                     │<───────────────────────────┤  ApplyPlan JSON           │ (applications)
  │  ApplyPanel 렌더    │                            │                          │
  │<────────────────────┤                            │                          │
  │  서류 체크 ✓        ├─ PATCH /items/{id} ───────>│ 체크 상태 저장 ──────────> │
  │ [신청 페이지 열기]  │  (새 탭으로 deep-link, 본인인증·제출은 사용자가 수행)   │
  │  제출 후 상태 변경  ├─ PATCH /applications/{id} ─> status=submitted ────────> │
```

①~⑤는 순수 규칙 기반이라 LLM 없이 항상 동작하고, ⑥만 LLM 의존(실패 시 생략).
이는 기존 recommender의 "LLM 우선, 규칙 fallback" 패턴과 동일하다.

## 3. 데이터 모델 (user_data.db)

정책 DB(youth_policy.db)는 계속 읽기 전용으로 두고, 신청 상태는 전부
사용자 런타임 DB에 둔다 (이번 정리에서 확립한 분리 원칙 유지).

```sql
CREATE TABLE applications (
    application_id  TEXT PRIMARY KEY,          -- uuid4
    user_id         TEXT,                      -- users.user_id (nullable: 비로그인)
    doc_id          TEXT NOT NULL,             -- search_documents.doc_id 참조
    source_table    TEXT, source_id TEXT,      -- 정책 원문 재조회용
    policy_name     TEXT,
    status          TEXT NOT NULL DEFAULT 'draft',
    eligibility     TEXT,                      -- ok | needs_info | ineligible
    eligibility_notes TEXT,                    -- 부족/불일치 항목 JSON
    apply_channel   TEXT,                      -- online | visit | mail | contact
    apply_url       TEXT,
    apply_deadline  TEXT,                      -- ISO date 또는 '상시'
    draft_answers   TEXT,                      -- LLM 초안 JSON (선택)
    created_at      TEXT DEFAULT (datetime('now','localtime')),
    updated_at      TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE application_items (
    item_id         TEXT PRIMARY KEY,
    application_id  TEXT NOT NULL REFERENCES applications(application_id),
    kind            TEXT NOT NULL,             -- document | eligibility | action
    label           TEXT NOT NULL,
    help_label      TEXT, help_url TEXT,       -- 발급처 (예: 정부24 등본 발급)
    checked         INTEGER NOT NULL DEFAULT 0,
    sort_order      INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX idx_applications_user ON applications(user_id, status);
```

상태머신 (서버에서 전이 검증):

```
draft → preparing → ready → submitted → done
  └────────────┴───────┴──> expired (마감 경과 시 배치/조회 시점 판정)
허용 외 전이는 409 반환. submitted 이후 체크리스트는 읽기 전용.
```

## 4. API 설계

| 메서드/경로 | 설명 | 비고 |
|---|---|---|
| `POST /agent/apply-plan` | 플랜 생성(멱등: 동일 user+doc_id 진행건 있으면 그것을 반환) | body: `{policy:{doc_id,source_table,source_id}, user_id?}` |
| `GET /agent/applications?user_id=` | 내 신청 목록 + 진행률/D-day | 정렬: 마감 임박순 |
| `GET /agent/applications/{id}` | 단건 상세 (체크리스트 포함) | |
| `PATCH /agent/applications/{id}` | 상태 전이 | body: `{status}` |
| `PATCH /agent/applications/{id}/items/{item_id}` | 체크 토글 | body: `{checked}` |

`POST /agent/apply-plan` 응답 예시:

```json
{
  "application_id": "…",
  "status": "preparing",
  "eligibility": "needs_info",
  "eligibility_notes": [{"field": "income", "reason": "소득 정보 미입력"}],
  "apply_channel": "online",
  "apply_url": "https://…",
  "apply_deadline": "2026-07-31",
  "days_left": 50,
  "checklist": [
    {"item_id": "…", "kind": "document", "label": "주민등록등본 1부",
     "help_label": "정부24에서 발급", "help_url": "https://www.gov.kr/…", "checked": false},
    {"item_id": "…", "kind": "eligibility", "label": "무주택 여부 확인", "checked": false},
    {"item_id": "…", "kind": "action", "label": "온라인 신청서 제출", "checked": false}
  ],
  "draft_answers": {"신청 사유": "…(LLM 초안, 없으면 null)…"},
  "next_action": "서류 2건을 준비한 뒤 신청 페이지에서 본인인증 후 제출하세요."
}
```

## 5. 모듈 배치 (기존 구조 존중)

```
ai/
  apply_agent.py        ApplyAgent: ①~⑥ 오케스트레이션 (recommender와 동급의 진입점)
  document_registry.py  서류명 → 발급처/URL 정적 매핑 (prepTracker의 정부24 링크를
                        서버로 승격·확장: 등본/초본, 가족관계증명서, 소득금액증명 등)
backend/
  application_store.py  user_data.db CRUD + 상태머신 검증
  models.py             ApplyPlanRequest/Response 등 Pydantic 모델 추가
  main.py               /agent/* 라우트 (얇게 유지)
frontend/src/
  applyPlan.js          API 클라이언트 + 진행률 계산 (순수 함수, node --test 가능)
  components/ApplyPanel.jsx  플랜 패널 (REFACTORING_PLAN의 컴포넌트 분리와 합류)
```

재사용: 정책 컨텍스트 로딩은 `PolicyChatAgent._load_policy_context`를 분리 예정인
`ai/chat_context_loader.py`(REFACTORING_PLAN §남은 분리)로 추출해 양쪽이 공유.
체크리스트 시드는 `generator._checklist`의 규칙을 분리해 재사용. 기존
`prepTracker.js`의 localStorage 상태는 마이그레이션: 로그인 사용자는 서버 저장,
비로그인은 localStorage 유지(점진 전환, 기능 회귀 없음).

## 6. 오류 처리·신뢰성

| 상황 | 처리 |
|---|---|
| LLM 실패/비활성 | ⑥ 생략, 규칙 기반 플랜만 반환 (`draft_answers: null`) |
| 신청 URL 없음 | channel=contact, 문의처·주관기관 표시, action에 "전화 문의" 항목 |
| 마감일 파싱 실패 | '상시'로 표시하되 "공고문에서 기한 확인" 항목 추가 (현 retriever 규칙 재사용) |
| 정책 원문 조회 실패 | 404 + 추천 캐시에 있는 요약으로 최소 플랜 제안 |
| 동시 체크 토글 | 마지막 쓰기 승리 (단일 사용자 데이터라 충돌 영향 미미) |
| SQLite 동시성 | user_data.db `PRAGMA journal_mode=WAL` 적용 |

관측성: 플랜 생성 시 `eligibility 분포`, `LLM 사용 여부`, `생성 소요시간`을
로그로 남겨 데모/리포트에 활용.

## 7. 단계별 구현 계획

| Phase | 범위 | 산출물 | 예상 규모 |
|---|---|---|---|
| **1 (MVP)** | 규칙 기반 ①~⑤ + applications 저장 + ApplyPanel + deep-link | `/agent/apply-plan`, 목록/상태 API, 테스트 | 백 ~400줄, 프론트 ~250줄 |
| **2** | LLM 초안(⑥), 적격성 서버 통합(eligibilityCheck.js 이관), 마감 임박 정렬/배지 | draft_answers, needs_info UX | +200줄 |
| **3 (연구)** | 폼 프리필 보조: 신청 페이지에서 붙여넣을 답변 묶음 "복사" 버튼 → 북마클릿/확장 검토. 정부 시스템 연동 API 출현 시 재평가 | 스파이크 문서 | 별도 |

Phase 1 테스트 계획 (fixture DB 기반, 기존 15개 테스트에 추가):
- ApplyAgent 단위: submit_docs 파싱, 채널 결정, D-day 계산, 적격성 3분기
- 상태머신: 허용/비허용 전이
- API smoke: plan 생성 → 체크 → 상태 전이 왕복, 멱등성
- 회귀: `/recommend` 응답 형식 불변 확인

## 8. 트레이드오프 기록

| 결정 | 대안 | 선택 이유 |
|---|---|---|
| 자동 제출 대신 "준비 완료 + deep-link" | 브라우저 자동화로 대리 제출 | 인증 장벽·약관 리스크·유지보수 비용. 데모 신뢰성 우선 |
| 신청 상태를 서버(user_data.db) 저장 | localStorage 유지 | 다기기 복원·진행률 집계 가능. 비로그인은 localStorage fallback으로 회귀 방지 |
| 발급처 정적 매핑(document_registry) | LLM이 매번 발급처 추론 | 정확성·비용. 정부 발급처 URL은 변동이 적어 정적이 안전. LLM은 미등록 서류만 보강 |
| 멱등 plan 생성 | 클릭마다 새 플랜 | 중복 행 방지, "클릭 한 번" UX와 일치 |
| SQLite 유지 | Postgres 도입 | 현 규모(단일 서버, 저트래픽)에 충분. 분리된 DB 파일이라 추후 이전 용이 |

## 9. 규모가 커지면 다시 볼 것
- 사용자 증가 시: user_data.db → Postgres, 세션/인증 도입 (현재 user_id가 비밀값 역할이므로 추측 불가 UUID 전제 유지)
- 알림(마감 D-3 푸시/메일): 스케줄러 작업 추가 — 현 설계의 apply_deadline 컬럼으로 바로 가능
- 정책 데이터 갱신 주기와 플랜의 정합성: doc_id 스냅샷 저장으로 이미 대비, 갱신 시 "정보 변경됨" 배지 검토
