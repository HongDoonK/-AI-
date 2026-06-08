import assert from 'node:assert/strict';
import {
  buildPreparationItems,
  getPreparationLink,
  getCompletionStats,
  togglePreparationItem,
} from './prepTracker.js';

const policy = {
  application_period: '20260101 ~ 20261231',
  application_url: 'https://example.com/apply',
  checklist: ['소득 증빙 확인하기', '자격 조건 확인: 제한없음 제한없음', '소득 증빙 확인하기'],
};

const items = buildPreparationItems(policy);
assert.ok(items.includes('신청 기간 확인: 20260101 ~ 20261231'));
assert.ok(items.includes('신청 링크에서 접수 절차 확인하기'));
assert.ok(items.includes('소득 증빙 확인하기'));
assert.equal(items.some((item) => item.includes('자격 조건')), false);
assert.equal(items.length, new Set(items).size);

const documentLink = getPreparationLink('주민등록등본, 신분증, 소득 증빙 등 기본 서류 준비하기', policy);
assert.equal(documentLink.label, '정부24 등본 발급');
assert.equal(documentLink.href, 'https://www.gov.kr/main?CappBizCD=13100000015&HighCtgCD=A01010&a=AA020InfoCappViewApp');

const applyLink = getPreparationLink('신청 링크에서 접수 절차 확인하기', policy);
assert.equal(applyLink.label, '신청 링크 열기');
assert.equal(applyLink.href, 'https://example.com/apply');

let checkedByPolicy = {};
checkedByPolicy = togglePreparationItem(checkedByPolicy, 'policy-1', items[0], true);

let stats = getCompletionStats(items, checkedByPolicy['policy-1']);
assert.equal(stats.completed, 1);
assert.equal(stats.total, items.length);
assert.equal(stats.percent, Math.round((1 / items.length) * 100));

checkedByPolicy = togglePreparationItem(checkedByPolicy, 'policy-1', items[0], false);
stats = getCompletionStats(items, checkedByPolicy['policy-1']);
assert.equal(stats.completed, 0);
