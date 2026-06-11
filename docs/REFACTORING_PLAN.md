# 책임 분리 리팩터링 계획

## 완료된 분리 (동작 불변, import 경로만 변경)

| 원본 | 분리 결과 | 내용 |
|---|---|---|
| `ai/policy_chat_agent.py` (1,543줄) | `ai/chat_labels.py` (149줄) | 소스/도메인/필드 라벨, 의도 키워드 상수 |
| | `ai/chat_text_utils.py` (176줄) | 순수 텍스트 정제/추출 유틸 17개 |
| | `ai/policy_chat_agent.py` (1,250줄) | PolicyChatAgent 클래스만 유지 |
| `frontend/src/App.jsx` (896줄) | `frontend/src/appConfig.js` | REGION_OPTIONS, 스토리지 키, 순수 헬퍼 4개 |
| | `frontend/src/App.jsx` (856줄) | React 컴포넌트만 유지 |

## 남은 분리 계획 (다음 단계, 테스트 선행 필요)

### ai/policy_chat_agent.py (1,250줄)
PolicyChatAgent 클래스가 여전히 세 가지 책임을 가짐:
1. **DB 컨텍스트 로딩** (`_load_policy_context`, `_find_search_document`, `_connect` 등)
   → `ai/chat_context_loader.py`로 분리 (클래스 또는 함수군)
2. **의도 분류와 규칙 기반 답변 생성** (`_classify_intent`, 의도별 `_answer_*`)
   → `ai/chat_rule_answers.py`
3. **LLM 호출 조립** (프롬프트 구성, fallback 제어)
   → 클래스 본체에 유지
- 선행 조건: `/chat` 응답 형식 고정 테스트 (의도별 golden test) 추가 후 진행

### frontend/src/App.jsx (856줄)
1. 프로필 폼 → `components/ProfileForm.jsx`
2. 추천 결과 카드 → `components/PolicyCard.jsx`
3. 정책 상담 패널 → `components/ChatPanel.jsx`
4. 계산기 → `components/IncomeCalculator.jsx`
- 선행 조건: 컴포넌트 단위 렌더 테스트 도구(vitest + testing-library) 도입 검토
- props 경계는 현재 함수형 분리에 따라 자연스럽게 정해짐

### backend/preprocessing.py (629줄)
`rebuild_search_documents()` 하나가 6개 소스 테이블 변환을 모두 포함:
1. 소스별 변환 함수를 `backend/preprocess_sources/` 패키지로 분리
   (`policies.py`, `hrd.py`, `kstartup.py`, `smallloan.py`, `myhome.py`, `rental.py`)
2. 공용 유틸(`_clean`, `_date_yyyymmdd`, 지역 파싱)은 `backend/preprocess_common.py`
- 선행 조건: fixture 원본 테이블 → search_documents 결과 스냅샷 테스트
- 위험: 실데이터 재전처리 검증이 필요하므로 API 키 보유 환경에서 실행 확인 후 머지

## 원칙
- 한 커밋에 한 파일 분리만
- 분리 전 해당 경로를 지나는 테스트 먼저 추가
- public 이름(외부 import 대상)은 기존 모듈에서 re-export 유지
