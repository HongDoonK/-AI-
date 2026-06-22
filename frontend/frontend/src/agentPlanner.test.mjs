import assert from 'node:assert/strict';
import { buildAgentReport, buildPolicyChecklist, parsePolicyDeadline } from './agentPlanner.js';

const deadline = parsePolicyDeadline('2026-06-01 ~ 2026-06-30');
assert.equal(deadline.toISOString().slice(0, 10), '2026-06-30');

const compactDeadline = parsePolicyDeadline('20260101 ~ 20261231');
assert.equal(compactDeadline.toISOString().slice(0, 10), '2026-12-31');

const checklist = buildPolicyChecklist({
  application_period: '2026-06-01 ~ 2026-06-30',
  application_url: 'https://example.com/apply',
  checklist: ['소득 증빙 확인하기'],
});
assert.ok(checklist.includes('신청 기간 확인: 2026-06-01 ~ 2026-06-30'));
assert.ok(checklist.includes('신청 링크에서 접수 절차 확인하기'));
assert.ok(checklist.includes('소득 증빙 확인하기'));

const report = buildAgentReport(
  [
    { policy_name: 'Later policy', application_period: '2026-06-01 ~ 2026-07-20' },
    { policy_name: 'Soon policy', application_period: '2026-06-01 ~ 2026-06-12' },
    { policy_name: 'Unknown date policy', application_period: '확인 필요' },
  ],
  new Date(Date.UTC(2026, 5, 8)),
);
assert.equal(report.total, 3);
assert.equal(report.urgentCount, 1);
assert.equal(report.needsDateCheckCount, 1);
assert.equal(report.priority[0].policy.policy_name, 'Soon policy');
assert.equal(report.priority[0].status, 'urgent');
