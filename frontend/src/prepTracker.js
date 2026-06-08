import { buildPolicyChecklist } from './agentPlanner.js';

export const GOVERNMENT24_RESIDENT_REGISTER_URL =
  'https://www.gov.kr/main?CappBizCD=13100000015&HighCtgCD=A01010&a=AA020InfoCappViewApp';

export function buildPreparationItems(policy) {
  return buildPolicyChecklist(policy).filter((item) => !item.includes('자격 조건'));
}

export function getPreparationLink(item, policy = {}) {
  if (item.includes('주민등록등본')) {
    return {
      label: '정부24 등본 발급',
      href: GOVERNMENT24_RESIDENT_REGISTER_URL,
    };
  }
  if (item.includes('신청 링크')) {
    const href = policy.application_url || policy.url || policy.ref_url;
    return href ? { label: '신청 링크 열기', href } : null;
  }
  return null;
}

export function getCompletionStats(items, checkedItems = {}) {
  const total = Array.isArray(items) ? items.length : 0;
  const completed = Array.isArray(items)
    ? items.filter((item) => Boolean(checkedItems?.[item])).length
    : 0;
  return {
    total,
    completed,
    percent: total === 0 ? 0 : Math.round((completed / total) * 100),
  };
}

export function togglePreparationItem(checkedByPolicy, policyId, item, checked) {
  const currentPolicyItems = checkedByPolicy?.[policyId] || {};
  return {
    ...(checkedByPolicy || {}),
    [policyId]: {
      ...currentPolicyItems,
      [item]: Boolean(checked),
    },
  };
}
