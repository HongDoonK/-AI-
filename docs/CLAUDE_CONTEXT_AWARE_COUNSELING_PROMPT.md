# Claude Code 전달 프롬프트

아래 작업을 현재 저장소에서 구현해줘.

먼저 다음 두 문서를 처음부터 끝까지 읽고, 설계와 구현 계획을 임의로 축소하거나 확장하지 마.

1. `docs/superpowers/specs/2026-06-22-context-aware-counseling-response-design.md`
2. `docs/superpowers/plans/2026-06-22-context-aware-counseling-response.md`

구현 목표는 추천 이후 상담 Agent의 답변을 맥락 기반으로 다양화하는 것이다.

- 적용 대상: 선택된 정책을 상담하는 `POST /chat`, 정책 선택 후 `POST /agent/converse`
- 제외 대상: `/recommend`, 검색, 필터링, 랭킹, 추천 카드 생성
- 정책 금액·기간·자격·서류·URL은 기존 DB·규칙 결과만 사용
- 무작위 답변이 아니라 질문, 사용자 조건, 이전 대화에 따른 결정론적 `ResponsePlan` 사용
- 같은 맥락에서는 계획과 규칙 답변이 안정적이어야 함
- 후속 질문이 구체화되면 초점, 섹션 순서, 설명 깊이, 다음 질문이 달라져야 함
- `LLM_PROVIDER=none`에서도 완전히 동작해야 함
- LLM sampling/temperature를 다양성의 해결책으로 변경하지 말 것
- 기존 공개 API 응답 스키마를 변경하지 말 것
- `documents`, `benefit`, `eligibility`, `eligibility_notes`, `apply_detail`의 구조화 사실을 변경하지 말 것
- 계획 메타는 `/agent/converse` 직접 응답에서 제거하고 세션의 assistant 턴 payload에만 저장할 것

작업 방식:

1. 현재 branch와 `git status`를 확인하고 기존 사용자 변경을 보존해.
2. `superpowers:subagent-driven-development`를 사용할 수 있으면 그 방식으로 계획의 Task 1부터 순서대로 실행해. 사용할 수 없으면 `superpowers:executing-plans` 방식으로 실행해.
3. 각 Task에서 반드시 테스트를 먼저 작성하고 실패를 확인한 다음 최소 구현으로 통과시켜.
4. 계획에 명시된 파일 경계와 함수 책임을 지켜. 추천 관련 파일은 수정하지 마.
5. 각 Task의 focused test가 통과한 뒤 계획에 적힌 단위로 커밋해.
6. 구현 중 계획과 실제 코드가 충돌하면 추측으로 범위를 넓히지 말고, 설계 원칙을 보존하는 가장 작은 수정안을 선택한 뒤 그 이유를 기록해.
7. 완료 전 다음을 반드시 새로 실행해.

```powershell
python -m pytest -q
Set-Location frontend
npm test
npm run build
Set-Location ..
git diff --check
git status --short
```

최종 보고에는 다음만 간결하게 포함해.

- 구현한 핵심 구조
- 변경 파일
- 정책 사실과 추천 경계를 보존한 방법
- 실행한 테스트와 실제 결과
- 남은 위험 또는 미완료 항목
- 생성한 커밋 목록

테스트가 실패하거나 요구사항을 충족하지 못한 상태에서는 완료했다고 말하지 마.
