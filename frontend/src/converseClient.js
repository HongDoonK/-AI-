// 대화형 신청 도우미 클라이언트 (docs/ADR-001-conversational-apply-flow.md)
// 순수 함수(actionToMessage)는 node --test로 검증 가능하도록 fetch와 분리한다.

async function requestJson(url, options) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`요청 실패 ${response.status}: ${detail}`);
  }
  return response.json();
}

export function sendConverse(baseUrl, { message, sessionId, userId, selectedDocId, policy } = {}) {
  return requestJson(`${baseUrl}/agent/converse`, {
    method: 'POST',
    body: JSON.stringify({
      message,
      session_id: sessionId || null,
      user_id: userId || null,
      selected_doc_id: selectedDocId || null,
      policy: policy || null,
    }),
  });
}

// 액션칩 1개 → 백엔드로 보낼 자연어 발화. 백엔드 라우터가 이 문장을
// 다시 의도로 분류하므로, 칩 클릭이 곧 사용자가 그렇게 말한 것과 같다.
export function actionToMessage(action = {}) {
  if (action.ordinal) return `정책 ${action.ordinal} 선택할래`;
  switch (action.action || action.intent) {
    case 'docs':
      return '필요한 서류 알려줘';
    case 'benefit':
      return '얼마나 받을 수 있어?';
    case 'eligibility':
      return '신청 자격 확인해줘';
    case 'apply_how':
      return '신청 방법 알려줘';
    case 'create_apply_plan':
      return '신청 준비 시작할래';
    default:
      return action.label || '';
  }
}
