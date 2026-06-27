function text(value) {
  return String(value || '').trim();
}

export function parsePolicyDeadline(period) {
  const matches = text(period).match(/\d{4}[-.]\d{1,2}[-.]\d{1,2}|\b\d{8}\b/g) || [];
  if (matches.length === 0) return null;
  const latest = matches[matches.length - 1];
  const normalized = latest.includes('-') || latest.includes('.')
    ? latest.replace(/\./g, '-').split('-')
    : [latest.slice(0, 4), latest.slice(4, 6), latest.slice(6, 8)];
  const [year, month, day] = normalized.map(Number);
  if (!year || !month || !day) return null;
  return new Date(Date.UTC(year, month - 1, day));
}

export function buildPolicyChecklist(policy) {
  const base = Array.isArray(policy?.checklist) ? policy.checklist.filter(Boolean) : [];
  if (base.length >= 3) return [...new Set(base)].slice(0, 6);

  const period = text(policy?.application_period);
  const url = text(policy?.application_url || policy?.url || policy?.ref_url);
  const policyName = text(policy?.policy_name);
  const regionMatch = text(policy?.region_match);
  const fillers = [
    period ? `신청 기간 확인: ${period}` : (policyName ? `'${policyName}' 신청 기간 확인` : '신청 기간 확인 필요'),
    regionMatch ? `지역 조건 확인: ${regionMatch}` : null,
    url ? '신청 링크에서 접수 절차 확인하기' : null,
  ].filter(Boolean);

  return [...new Set([...fillers, ...base])].slice(0, 6);
}

export function buildAgentReport(recommendations, today = new Date()) {
  const policies = Array.isArray(recommendations) ? recommendations.slice(0, 5) : [];
  const enriched = policies.map((policy, index) => {
    const deadline = parsePolicyDeadline(policy.application_period);
    const daysLeft = deadline ? Math.ceil((deadline - today) / (1000 * 60 * 60 * 24)) : null;
    const status = deadline === null ? 'needs_date_check' : daysLeft < 0 ? 'expired' : daysLeft <= 7 ? 'urgent' : 'open';
    return {
      index,
      policy,
      deadline,
      daysLeft,
      status,
      checklist: buildPolicyChecklist(policy),
    };
  });

  const priority = enriched
    .filter((item) => item.status !== 'expired')
    .sort((a, b) => {
      if (a.daysLeft === null && b.daysLeft === null) return a.index - b.index;
      if (a.daysLeft === null) return 1;
      if (b.daysLeft === null) return -1;
      return a.daysLeft - b.daysLeft;
    });

  return {
    total: policies.length,
    urgentCount: enriched.filter((item) => item.status === 'urgent').length,
    needsDateCheckCount: enriched.filter((item) => item.status === 'needs_date_check').length,
    priority,
    summary:
      policies.length === 0
        ? '추천 결과가 나오면 에이전트가 신청 우선순위와 준비 체크리스트를 생성합니다.'
        : `에이전트가 추천 정책 ${policies.length}개를 분석해 신청 우선순위와 준비 작업을 만들었습니다.`,
  };
}
