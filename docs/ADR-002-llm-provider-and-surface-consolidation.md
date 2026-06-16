# ADR-002: LLM 공급자 교체(OpenAI→오픈모델)와 입력 Surface 통합

**Status:** Proposed
**Date:** 2026-06-16
**Deciders:** 프로젝트 오너(1인 개발), 지도/평가 기준
**관련 문서:** [ADR-001](ADR-001-conversational-apply-flow.md), [AGENT_APPLY_DESIGN.md](AGENT_APPLY_DESIGN.md),
[GENERALIZATION_EVALUATION_WORKFLOW.md](GENERALIZATION_EVALUATION_WORKFLOW.md), [AI_HANDOFF.md](AI_HANDOFF.md)
**검증자:** codex (이 문서 하단 §검증 체크리스트 기준)

## Context

세 가지 문제가 얽혀 있다.

1. **입력 Surface 역할 중복.** 화면에는 추천을 시작하는 입구가 둘이다.
   - "나의 상황 입력"(Hero 폼) → `POST /recommend` → 우측 컬럼에 카드 Top 5.
   - "대화형 신청 도우미"(ChatFlowPanel) → `POST /agent/converse`의 `recommend` 의도 →
     **같은** `ai.recommender.recommend_policy()`를 호출해 채팅 말풍선에 카드.
   두 입구가 동일 추천 엔진을 부르지만 **세션 상태를 공유하지 않아**, 사용자는 서로 다른
   두 카드 목록(우측 컬럼 vs 채팅)을 보게 되고 "정책 3" 같은 지시가 어느 목록을 가리키는지
   모호해진다(병렬 중복).

2. **"그냥 LLM에 청년 정책을 넣으면 우리 agent 없이도 되지 않나?"** 라는 정당성 질문.
   이 의심을 정면으로 다루지 않으면 프로젝트의 존재 이유가 약해 보인다.

3. **OpenAI 종속·키 만료.** `.env`의 `OPENAI_API_KEY`가 401(만료). 현재 LLM 경로는
   `ai/llm_client.py`가 OpenAI Responses API에 직접 묶여 있다(`create_structured_output`,
   `create_chat_response`). 유료·외부 종속이며 데모 신뢰성을 해친다.

### 현재 코드 사실 (근거)

| 사실 | 위치 |
|---|---|
| LLM 호출은 2개 함수로 추상화, 실패 시 `LLMUnavailable` | `ai/llm_client.py` |
| LLM 사용처(모두 실패 시 규칙 fallback 보유) | `condition_extractor`, `generator`, `benefit_estimator`, `apply_agent`, `policy_chat_agent` |
| Hero와 채팅이 같은 추천 엔진 호출 | `recommender.recommend_policy` ← `/recommend`, `converse_agent._handle_recommend` |
| 두 Surface가 세션/추천목록을 공유하지 않음 | `App.jsx`의 `result` state vs `conversations.last_recommendations` |
| 키워드/규칙 fallback이 LLM 없이 완전 동작 | `USE_OPENAI_LLM=0`, `USE_FAISS=0`로 112개 테스트 통과 |

### 핵심 통찰 (이 ADR의 논지)

> **정책의 "사실"(금액·기간·자격·지역·신청 URL)은 결정론적 RAG/규칙 엔진이 책임지고,
> LLM은 사실을 만들지 않는 "교체 가능한 언어 계층"으로 격하한다.**

이 논지가 세 문제를 한 번에 푼다. 사실 생성을 LLM에서 떼어내면 (a) raw LLM 대비 우위가
분명해지고(문제 2), (b) 공급자 교체가 저비용·저위험이 되며(문제 3), (c) Surface 통합 시
"단일 추천 결과(진실의 출처)"를 세션에 두는 설계가 자연스러워진다(문제 1).

## Decision

두 가지를 함께 결정한다.

- **D1. 입력 Surface 역할 재정의 + 단일 추천 세션.** Hero 폼은 "구조화된 1-shot 탐색"
  (프로필 필드 → 근거 있는 Top 5), 채팅은 "선택 정책에 대한 멀티턴 상담·실행"으로 분리한다.
  추천 결과는 **하나의 대화 세션 상태(last_recommendations)** 를 단일 출처로 공유한다.
  Hero 추천이 세션을 시드하고, 채팅은 그 결과를 이어받아 선택/서류/지원금/신청준비로 진행한다.

- **D2. LLM 공급자 추상화 + 오픈모델(Qwen 계열) 기본화 + LLM 격하.** `llm_client.py`를
  공급자 무관 인터페이스로 바꾸고 OpenAI 직접 종속을 제거한다. 기본 공급자는 HuggingFace의
  **Qwen2.5-7B-Instruct**(Apache-2.0). LLM은 ① 자유발화 의도 분류 보강 ② 자연어 조건 추출
  ③ 말투 다듬기(NLG) 에만 쓰고, **사실 수치/날짜/자격은 절대 LLM이 생성하지 않는다**
  (grounded-only 계약, §D2-3).

핵심: 두 결정 모두 **신규 도메인 로직을 거의 만들지 않는다.** D1은 상태 공유 배선,
D2는 어댑터 교체다. 규칙 fallback 원칙(ADR-001 N1)은 그대로 유지된다.

---

## D1. 입력 Surface 통합

### 역할 재정의

| Surface | 역할 | 입력 | 출력 | 추천 재실행? |
|---|---|---|---|---|
| Hero "나의 상황 입력" | **탐색(browse)**: 구조화 1-shot | 프로필 필드 + 자유문장 | 우측 Top 5 카드(근거·적격성·에이전트 리포트) | 예(세션 시드) |
| 채팅 "대화형 신청 도우미" | **상담·실행(act)**: 멀티턴 | 자유발화 | 말풍선 + 액션칩 + (필요 시) 같은 세션 카드 | 기본 아니오, 재탐색 요청 시만 |

### Options Considered

#### Option A: 채팅 단일화 (Hero 제거)
| Dimension | Assessment |
|---|---|
| Complexity | Medium (Hero 폼 자산 폐기) |
| Cost | 낮음 |
| Scalability | 높음 |
| Team familiarity | 중간 |

**Pros:** 입구가 하나라 중복이 원천 제거. 대화 UX 일관.
**Cons:** 프로필 필드(나이/지역/소득)의 구조화 입력 affordance 상실 → 자유발화로 모든 조건을
받아야 해 추출 부담↑. 적격성 패널·소득 계산기 등 Hero 좌측 자산과의 연결이 어색해짐.

#### Option B: 역할 분리 + 단일 추천 세션 (선택)
| Dimension | Assessment |
|---|---|
| Complexity | Medium (세션 공유 배선) |
| Cost | 낮음 |
| Scalability | 높음 |
| Team familiarity | 높음 |

Hero = 탐색, 채팅 = 상담/실행. 추천 결과는 대화 세션의 `last_recommendations`를 **단일
출처**로 공유. Hero가 추천을 만들면 그 카드 목록과 `session_id`를 채팅에 시드하고, 채팅의
"정책 N"은 그 목록을 가리킨다. 채팅의 `recommend` 의도는 **재탐색/세분화**("더 주거 쪽으로")
용도로만 남기되, 결과는 새 평행 목록이 아니라 **같은 세션 목록을 갱신**한다.

**Pros:** 중복 제거(진실의 출처 1개). 두 자산 모두 보존. ADR-001 세션 모델 재사용.
"정책 N" 모호성 해소.
**Cons:** Hero→채팅 세션 시드 배선 필요. 프론트 상태(현재 `App.result`)와 세션의 일원화 작업.

#### Option C: 현행 유지(둘 독립)
| Dimension | Assessment |
|---|---|
| Complexity | Low |
| Cost | 0 |
| Scalability | 낮음 |
| Team familiarity | 높음 |

**Pros:** 작업 없음.
**Cons:** 문제 1(중복·모호) 그대로. 평가자에게 "왜 입구가 둘이냐" 지적 여지.

→ **Option B 채택.**

### D1 구현 스케치 (최소 변경)
1. Hero `handleSubmit` 성공 시 `/agent/converse`와 같은 `session_id`를 확보하고
   추천 결과를 그 세션의 `last_recommendations`로 기록한다. `/recommend` 응답을
   확장하더라도 기존 `user_condition`/`recommendations`/`centers` shape는 유지하고,
   `session_id` 같은 필드는 선택적 additive 필드로만 추가한다.
2. `ChatFlowPanel`은 별도 추천 목록을 만들지 않고 세션의 `last_recommendations`를 카드로 렌더.
3. 채팅 `recommend` 의도는 결과를 **세션 목록 갱신**으로 반영(평행 목록 금지).
4. 문구 정리: Hero는 "정책 찾기/탐색", 채팅은 "고른 정책 상담·신청 준비"로 라벨 차별화.
5. 회귀 범위: `App.result` 기반 추천 카드, 적격성 패널, 신청 준비 리포트, `seededPolicy`
   선택 상담, `/agent/apply-plan` 연결이 그대로 동작해야 한다.

---

## D2. LLM 공급자 교체 + 격하

### LLM의 안전한 역할 경계 (격하)

| 작업 | LLM 사용? | 사실 출처 | 실패 시 |
|---|---|---|---|
| 의도 분류 | 보강만(규칙이 백본) | — | 규칙 분류 |
| 자연어 조건 추출(나이/지역/관심) | 예(JSON) | 추출은 힌트일 뿐, 검색이 검증 | 규칙 추출 |
| 말투 다듬기(NLG) | 예 | **제공된 context만** 인용 | 템플릿 직렬화 |
| 금액·기간·자격·URL | **아니오(금지)** | DB 필드/BenefitEstimator | — |
| 랭킹/적격성 판정 | 아니오 | retriever/apply_agent 규칙 | — |

### D2-3. Grounded-only 계약 (raw LLM 대비 우위의 핵심)
NLG 단계는 "검색된 context에 없는 수치/날짜/기관명을 생성하지 않는다"를 계약으로 강제한다.
- 프롬프트에 "context에 없으면 '공고 확인 필요'라고 답하라" 지시.
- (옵션) 생성 후 **검증 패스**: 응답에 등장한 숫자/날짜가 context에 존재하는지 정규식 대조,
  불일치 시 템플릿 직렬화로 대체. 단, `20만원`/`200,000원`처럼 표현 단위가 다른 정상 수치가
  false-positive로 막히지 않도록 원 단위 정규화와 날짜 포맷 정규화를 먼저 적용한다.
  이는 GENERALIZATION_WORKFLOW의 "수치 환각 방지"와 합류.

### "왜 raw LLM(Qwen 직접 질의)으로 충분하지 않은가" — 문제 2에 대한 답

| 위험 | raw LLM 단독 | 본 프로젝트(grounded agent) |
|---|---|---|
| 사실 환각 | 마감일·금액·자격을 자신 있게 지어냄(신청 실패=실질 피해) | 모든 수치를 DB 필드에 grounding, 없으면 "확인 필요" |
| 지식 신선도 | 파라미터 지식이 과거·연도별 변동 미반영 | 통합청년 API → `search_documents` 16,571건 최신 |
| 롱테일 커버리지 | 유명 정책만 앎(구/군 단위·임대단지 누락) | RAG가 지역 소규모 공고까지 검색 |
| 재현성/평가 | 비결정적 → 회귀 테스트 불가 | 규칙 라우터+grounded → 112 테스트로 고정 |
| 비용/지연/오프라인 | 매 턴 호출 필수 | LLM off에서도 완전 동작(데모 신뢰성) |
| 실행(actionability) | Q&A에 그침 | 적격성·체크리스트·발급처·상태머신·D-day 워크플로우 |

결론: 본 프로젝트의 해자는 "한국어 문장 생성"이 아니라 **검색 기반 사실 grounding +
구조화된 신청 워크플로우/상태**다. 그래서 LLM 공급자는 부품처럼 갈아끼울 수 있다.

### 모델 추천 (HuggingFace)

요구: 한국어 양호 · JSON 구조화 출력 · 로컬/서버 양쪽 가능 · 관대한 라이선스.

| 모델 | 한국어 | 라이선스 | JSON | 메모리(대략, 4bit) | 적합 |
|---|---|---|---|---|---|
| **Qwen2.5-7B-Instruct** ★기본 | 우수 | Apache-2.0 | 좋음 | ~5–6GB | 기본값. 균형 최상 |
| Qwen2.5-1.5B-Instruct | 보통+ | Apache-2.0 | 보통 | ~1.5GB | CPU/저사양 데모 |
| Qwen2.5-14B-Instruct | 우수+ | Apache-2.0 | 우수 | ~9–10GB | GPU 있으면 추출 품질↑ |
| Qwen3-8B 계열 | 우수 | 모델카드 확인 | 좋음 | ~6GB | 최신 대안. 라이선스 재확인 전 기본값 금지 |
| EXAONE-3.5-7.8B-Instruct | 매우 우수(한국어 특화) | EXAONE 라이선스(연구/제약) | 좋음 | ~6GB | 한국어 최강 후보, **상업·배포 라이선스 확인 필수** |
| Llama-3.1-8B-Instruct | 보통 | Llama 커뮤니티 | 좋음 | ~6GB | 생태계 넓으나 한국어 약함 |
| Gemma-2-9B-it | 보통+ | Gemma 약관 | 보통 | ~7GB | 무난한 대안 |

주의: Qwen2.5의 **3B/72B는 Apache-2.0이 아님**(Qwen 라이선스) → 3B는 피하고 7B 권장.
정확한 라이선스·한국어 벤치는 각 HF 모델 카드에서 재확인.

**권장:** 기본 `Qwen2.5-7B-Instruct`(Apache-2.0), 저사양 폴백 `Qwen2.5-1.5B-Instruct`.
한국어 품질을 최우선하고 라이선스가 허용되면 `EXAONE-3.5-7.8B`를 대안으로.

### 배포(실행) 옵션

#### Option A: HF Inference(서버리스/Endpoint) + Qwen2.5-7B
| Dimension | Assessment |
|---|---|
| Complexity | Low (HF 토큰만) |
| Cost | 사용량 과금/무료 한도 |
| Scalability | 높음 |
| Offline | 불가(네트워크 의존) |

**Pros:** 인프라 0, 빠른 착수. **Cons:** 네트워크·쿼터 의존(데모 위험), 토큰 필요.

#### Option B: 로컬 추론 (llama.cpp GGUF / transformers / vLLM) (선택, 데모 기본)
| Dimension | Assessment |
|---|---|
| Complexity | Medium (런타임 설치) |
| Cost | 0(자기 하드웨어) |
| Scalability | 단일 노드 |
| Offline | 가능 |

**Pros:** 오프라인·무료·데모 신뢰성(ADR-001 N1 철학과 정합). 7B-4bit는 소비자 GPU/CPU 가능.
**Cons:** 최초 모델 다운로드(수 GB), 추론 지연(CPU면 느림) → 그래서 LLM은 비핵심으로 격하.

#### Option C: LLM 완전 제거(규칙 전용)
**Pros:** 가장 단순·재현. **Cons:** 자유발화 추출/말투가 딱딱해짐. 단, **항상 fallback으로 유지**.

→ **채택: 공급자 무관 어댑터.** `LLM_PROVIDER ∈ {none, hf, local}`. 데모 기본은
`local`(Qwen2.5-7B) 또는 `none`(규칙). `hf`는 옵션. 어떤 경우든 실패 시 규칙 fallback.

### D2 구현 스케치 (최소 변경, 인터페이스 보존)
1. `ai/llm_client.py`를 공급자 어댑터로 리팩터:
   - `create_structured_output(...)`, `create_chat_response(...)` **시그니처 유지**(호출처 무변경).
   - 내부 분기: `none`→즉시 `LLMUnavailable`; `hf`→HF Inference; `local`→transformers/llama.cpp.
   - JSON 강제: OpenAI `json_schema` strict가 없으므로 (a) 엄격 프롬프트 + `json.loads`,
     (b) `jsonschema` 또는 Pydantic으로 required/type/enum 검증, (c) 실패 시 1회 재시도,
     (d) 그래도 실패면 `LLMUnavailable`(→규칙 fallback). 선택적으로 `outlines`/문법제약
     디코딩으로 JSON을 보장한다.
2. 환경변수 정리: `OPENAI_API_KEY`/`OPENAI_MODEL`/`USE_OPENAI_LLM` →
   `LLM_PROVIDER`, `LLM_MODEL`(예: `Qwen/Qwen2.5-7B-Instruct`), `HF_TOKEN`(hf일 때만).
   하위호환: 과거 변수는 무시하되 문서/`.env.example` 갱신.
3. `requirements.txt`: `openai` 제거(또는 옵션), `transformers`/`accelerate`(local) 또는
   `huggingface_hub`(hf) 추가. CI(`requirements-ci.txt`)는 LLM 없이 규칙 경로만 테스트.
4. 테스트: 기존 `LLMUnavailable` fallback 테스트가 그대로 통과해야 함(공급자 무관 회귀).
   `tests/util_fixture.py`의 LLM 비활성 설정을 `LLM_PROVIDER=none`로 갱신.

---

## Trade-off Analysis

- **유연성 vs 재현성:** raw-LLM(유연)과 규칙(재현)의 대립을, "사실=규칙/RAG, 문장=LLM" 분리로
  해소한다. LLM이 죽어도 사실은 정확하고 데모는 산다.
- **온라인 vs 오프라인:** HF Inference(간편·네트워크 의존) vs 로컬(설치 비용·오프라인). 데모
  신뢰성을 위해 로컬/none을 기본, hf는 선택지로.
- **한국어 품질 vs 라이선스:** EXAONE(한국어 최고, 제약 라이선스) vs Qwen2.5-7B(우수, Apache-2.0).
  배포·평가 안전성을 위해 Apache-2.0 기본, EXAONE은 라이선스 확인 후 대안.
- **Surface 통합 비용:** 세션 일원화 배선이 약간 필요하나, ADR-001 세션 모델을 재사용하므로 낮음.

## Consequences

**쉬워지는 것**
- "왜 LLM이 아니라 agent인가"에 명확히 답(사실 grounding + 워크플로우 = 해자).
- 공급자 교체가 어댑터 1개로 끝남(OpenAI 종속·키 만료 문제 제거).
- 추천 결과가 단일 출처가 되어 "정책 N" 모호성·중복 카드 해소.
- 오프라인 데모 가능(로컬 Qwen / 규칙).

**어려워지는 것**
- 로컬 추론 런타임·모델 다운로드 운영 부담(최초 1회).
- JSON 강제를 OpenAI strict 없이 직접 보장해야 함(프롬프트+검증/문법제약).
- Hero↔채팅 세션 일원화로 프론트 상태 흐름이 약간 바뀜(회귀 테스트 필요).

**다시 볼 것**
- 사용자 증가 시 로컬 추론 → vLLM/TGI 서버 분리.
- 한국어 품질이 부족하면 14B 또는 EXAONE으로 승급(라이선스 확인).
- grounded 검증 패스의 false-positive(정상 수치를 환각으로 오판) 빈도 모니터링.

## Action Items
1. [ ] `ai/llm_client.py` 공급자 어댑터화(시그니처 보존, `LLM_PROVIDER` 분기)
2. [ ] `none`/`hf`/`local` 3경로 + JSON 검증/재시도 + 실패 시 `LLMUnavailable`
3. [ ] 환경변수 마이그레이션(`OPENAI_*`→`LLM_*`), `.env.example`·README 갱신
4. [ ] `requirements.txt`/`requirements-ci.txt` 의존성 정리(openai 제거, transformers/hf 추가)
5. [ ] grounded-only NLG 계약 + (옵션) 수치 검증 패스 추가, 단위 테스트
6. [ ] D1: `/recommend`↔`/agent/converse` 세션 일원화(단일 `last_recommendations`)
7. [ ] D1: `ChatFlowPanel`이 세션 추천목록을 단일 출처로 렌더, 평행 목록 제거
8. [ ] 회귀: `USE`→`LLM_PROVIDER=none`에서 112 py / 17 frontend 테스트 그대로 통과
9. [ ] (옵션) raw-LLM vs grounded 응답의 환각률 비교 평가(LLM-judge, GENERALIZATION_WORKFLOW 연계)

## Codex 검증 메모 (2026-06-16)

- 코드 정합성: `ai/llm_client.py`는 `create_structured_output`/`create_chat_response`
  2개 호출면과 `LLMUnavailable` 예외를 중심으로 구성되어 있다. LLM 사용처 5개
  (`condition_extractor`, `generator`, `benefit_estimator`, `apply_agent`, `policy_chat_agent`)는
  실패 시 규칙/템플릿 fallback 경로를 가진다.
- Surface 정합성: `/recommend`와 `converse_agent._handle_recommend`는 모두
  `ai.recommender.recommend_policy()`를 호출한다. 현재 프론트의 `App.result`와
  대화 세션의 `last_recommendations`는 서로 공유되지 않아 D1의 중복/모호성 문제 제기는 타당하다.
- 모델 라이선스: Hugging Face 모델 카드 기준 Qwen2.5-1.5B/7B/14B Instruct는 Apache-2.0,
  Qwen2.5-3B는 `qwen-research`, Qwen2.5-72B는 `qwen`, EXAONE-3.5-7.8B-Instruct는
  `EXAONE AI Model License Agreement 1.1 - NC`로 확인했다. 따라서 기본값을
  Qwen2.5-7B-Instruct로 두고 EXAONE은 라이선스 확인 후 대안으로만 두는 결정은 유지한다.
- 보강 사항: OpenAI strict JSON 부재 대응은 단순 `json.loads`가 아니라 schema/type 검증까지
  포함하도록 본문을 보강했다. D1은 기존 `/recommend` 응답 shape를 유지하는 additive 확장
  조건과 `App.result` 주변 회귀 범위를 명시했다.

## 트레이드오프 기록
| 결정 | 대안 | 선택 이유 |
|---|---|---|
| 사실=RAG/규칙, 문장=LLM(격하) | raw LLM에 전적 위임 | 환각·신선도·재현성·실행성. 해자 명료화 |
| 공급자 무관 어댑터, 기본 Qwen2.5-7B | OpenAI 유지 / 단일 공급자 하드코딩 | 키 만료·비용·오프라인. Apache-2.0 |
| 로컬/none 기본, hf 옵션 | hf 전용 | 데모 신뢰성(네트워크/쿼터 비의존) |
| Surface 분리 + 단일 세션 | 채팅 단일화 / 현행 유지 | 자산 보존 + 중복 제거의 균형 |

---

## 검증 체크리스트 (codex 용)

이 ADR은 **제안(Proposed)** 이며 아직 코드 미반영이다. codex는 아래를 확인하라.

1. **사실 정합성** — 본문 "현재 코드 사실" 표가 실제와 일치하는가?
   - `ai/llm_client.py`가 `create_structured_output`/`create_chat_response` 2함수 + `LLMUnavailable` 구조인지.
   - LLM 사용처 5개 파일이 모두 실패 시 규칙 fallback을 갖는지.
   - `/recommend`와 `converse_agent._handle_recommend`가 같은 `recommend_policy`를 호출하는지.
   - Hero와 채팅이 추천 세션을 공유하지 않는지(병렬 중복 주장의 근거).
2. **모델 권고 타당성** — Qwen2.5-7B-Instruct Apache-2.0 / 3B·72B 비-Apache 주장, EXAONE
   라이선스 제약 주장이 맞는지(각 HF 모델 카드 기준). 틀리면 `CHANGES_REQUESTED`로 정정.
3. **설계 위험** — JSON strict 부재에 대한 대응(프롬프트+검증/문법제약)이 충분한지,
   grounded 검증 패스의 false-positive 위험을 과소평가하지 않았는지.
4. **D1 영향 범위** — 세션 일원화가 기존 `/recommend` 응답 형식·프론트 `App.result`
   흐름에 주는 회귀 위험을 빠뜨리지 않았는지.
5. **fallback 원칙(ADR-001 N1) 보존** — 모든 변경안이 LLM-off 완전 동작을 깨지 않는지.

판정은 `docs/AI_HANDOFF.md`에 새 항목으로 회신(`VERIFIED` 또는 `CHANGES_REQUESTED`).
