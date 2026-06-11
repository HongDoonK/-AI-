import assert from 'node:assert/strict';
import test from 'node:test';

import {
  computeDaysLeft,
  formatDeadlineLabel,
  getApplyProgress,
  getEligibilityBadge,
  getNextStatusActions,
  getStatusLabel,
  groupChecklist,
  isChecklistLocked,
} from './applyPlan.js';

test('getApplyProgress counts checked items', () => {
  const plan = {
    checklist: [
      { kind: 'document', label: 'a', checked: true },
      { kind: 'action', label: 'b', checked: false },
    ],
  };
  assert.deepEqual(getApplyProgress(plan), { total: 2, completed: 1, percent: 50 });
  assert.deepEqual(getApplyProgress({}), { total: 0, completed: 0, percent: 0 });
});

test('computeDaysLeft handles 상시 and dates', () => {
  assert.equal(computeDaysLeft('상시'), null);
  assert.equal(computeDaysLeft(null), null);
  const today = new Date(2026, 5, 12);
  assert.equal(computeDaysLeft('2026-06-22', today), 10);
  assert.equal(computeDaysLeft('2026-06-12', today), 0);
  assert.equal(computeDaysLeft('2026-06-10', today), -2);
});

test('formatDeadlineLabel renders D-day', () => {
  const today = new Date(2026, 5, 12);
  assert.equal(formatDeadlineLabel({ apply_deadline: '상시' }), '상시 접수');
  assert.equal(formatDeadlineLabel({ apply_deadline: '2026-06-22' }, today), '2026-06-22 (D-10)');
  assert.equal(formatDeadlineLabel({ apply_deadline: '2026-06-12' }, today), '2026-06-12 (오늘 마감)');
  assert.equal(formatDeadlineLabel({ apply_deadline: '2026-06-01' }, today), '2026-06-01 (마감 지남)');
});

test('groupChecklist groups by kind with action fallback', () => {
  const groups = groupChecklist({
    checklist: [
      { kind: 'document', label: 'doc' },
      { kind: 'eligibility', label: 'eli' },
      { kind: 'action', label: 'act' },
      { kind: 'unknown', label: 'x' },
    ],
  });
  assert.equal(groups.document.length, 1);
  assert.equal(groups.eligibility.length, 1);
  assert.equal(groups.action.length, 2);
});

test('status helpers', () => {
  assert.equal(getStatusLabel('preparing'), '준비 중');
  assert.equal(getEligibilityBadge('ok').className, 'badge green');
  assert.equal(isChecklistLocked('submitted'), true);
  assert.equal(isChecklistLocked('preparing'), false);
});

test('getNextStatusActions follows state machine', () => {
  const incomplete = {
    status: 'preparing',
    checklist: [{ kind: 'action', label: 'a', checked: false }],
  };
  assert.deepEqual(getNextStatusActions(incomplete), []);

  const complete = {
    status: 'preparing',
    checklist: [{ kind: 'action', label: 'a', checked: true }],
  };
  assert.equal(getNextStatusActions(complete)[0].status, 'ready');

  assert.equal(getNextStatusActions({ status: 'ready', checklist: [] })[0].status, 'submitted');
  assert.equal(getNextStatusActions({ status: 'submitted', checklist: [] })[0].status, 'done');
  assert.deepEqual(getNextStatusActions({ status: 'done', checklist: [] }), []);
});
