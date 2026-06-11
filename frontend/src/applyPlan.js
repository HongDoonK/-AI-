// 신청 도우미 에이전트 프론트 로직 (docs/AGENT_APPLY_DESIGN.md Phase 1)
// 순수 함수는 node --test로 검증 가능하도록 fetch와 분리한다.

export const APPLY_STATUS_LABELS = {
  draft: '준비 전',
  preparing: '준비 중',
  ready: '준비 완료',
  submitted: '제출 완료',
  done: '완료',
  expired: '마감 지남',
};

export const APPLY_CHANNEL_LABELS = {
  online: '온라인 신청',
  visit: '방문 신청',
  mail: '우편 접수',
  contact: '기관 문의',
};

const ELIGIBILITY_BADGES = {
  ok: { label: '조건 적합', className: 'badge green' },
  needs_info: { label: '정보 확인 필요', className: 'badge orange' },
  ineligible: { label: '조건 불일치', className: 'badge gray' },
};

export function getStatusLabel(status) {
  return APPLY_STATUS_LABELS[status] || status || '상태 확인';
}

export function getChannelLabel(channel) {
  return APPLY_CHANNEL_LABELS[channel] || '신청 방법 확인';
}

export function getEligibilityBadge(eligibility) {
  return ELIGIBILITY_BADGES[eligibility] || { label: '적격성 확인 필요', className: 'badge blue' };
}

export function getApplyProgress(plan) {
  const items = Array.isArray(plan?.checklist) ? plan.checklist : [];
  const total = items.length;
  const completed = items.filter((item) => item.checked).length;
  const percent = total > 0 ? Math.round((completed / total) * 100) : 0;
  return { total, completed, percent };
}

export function computeDaysLeft(deadline, today = new Date()) {
  if (!deadline || deadline === '상시') return null;
  const parsed = new Date(`${deadline}T00:00:00`);
  if (Number.isNaN(parsed.getTime())) return null;
  const base = new Date(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((parsed - base) / (1000 * 60 * 60 * 24));
}

export function formatDeadlineLabel(plan, today = new Date()) {
  const deadline = plan?.apply_deadline;
  if (!deadline || deadline === '상시') return '상시 접수';
  const daysLeft = plan?.days_left ?? computeDaysLeft(deadline, today);
  if (daysLeft == null) return deadline;
  if (daysLeft < 0) return `${deadline} (마감 지남)`;
  if (daysLeft === 0) return `${deadline} (오늘 마감)`;
  return `${deadline} (D-${daysLeft})`;
}

export function groupChecklist(plan) {
  const groups = { document: [], eligibility: [], action: [] };
  for (const item of Array.isArray(plan?.checklist) ? plan.checklist : []) {
    (groups[item.kind] || groups.action).push(item);
  }
  return groups;
}

export function getDeadlineUrgency(daysLeft) {
  if (daysLeft == null) return { label: '상시', className: 'badge' };
  if (daysLeft < 0) return { label: '마감 지남', className: 'badge gray' };
  if (daysLeft <= 7) return { label: `D-${daysLeft} 임박`, className: 'badge orange' };
  return { label: `D-${daysLeft}`, className: 'badge blue' };
}

export function isChecklistLocked(status) {
  return ['submitted', 'done', 'expired'].includes(status);
}

export function getNextStatusActions(plan) {
  const progress = getApplyProgress(plan);
  switch (plan?.status) {
    case 'preparing':
      return progress.total > 0 && progress.completed === progress.total
        ? [{ status: 'ready', label: '준비 완료로 표시' }]
        : [];
    case 'ready':
      return [
        { status: 'submitted', label: '제출 완료로 표시' },
        { status: 'preparing', label: '다시 준비 중으로' },
      ];
    case 'submitted':
      return [{ status: 'done', label: '최종 완료 처리' }];
    default:
      return [];
  }
}

// ── API 호출 (얇은 fetch 래퍼) ───────────────────────────────

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

export function createApplyPlan(baseUrl, policy, userId) {
  return requestJson(`${baseUrl}/agent/apply-plan`, {
    method: 'POST',
    body: JSON.stringify({
      policy: {
        doc_id: policy?.doc_id || '',
        source_table: policy?.source_table || '',
        source_id: policy?.source_id || '',
        policy_name: policy?.policy_name || '',
      },
      user_id: userId || null,
    }),
  });
}

export function toggleApplyItem(baseUrl, applicationId, itemId, checked) {
  return requestJson(`${baseUrl}/agent/applications/${applicationId}/items/${itemId}`, {
    method: 'PATCH',
    body: JSON.stringify({ checked }),
  });
}

export function updateApplyStatus(baseUrl, applicationId, status) {
  return requestJson(`${baseUrl}/agent/applications/${applicationId}`, {
    method: 'PATCH',
    body: JSON.stringify({ status }),
  });
}

export function fetchApplications(baseUrl, userId) {
  return requestJson(`${baseUrl}/agent/applications?user_id=${encodeURIComponent(userId)}`, { method: 'GET' });
}

export function fetchApplication(baseUrl, applicationId) {
  return requestJson(`${baseUrl}/agent/applications/${applicationId}`, { method: 'GET' });
}
