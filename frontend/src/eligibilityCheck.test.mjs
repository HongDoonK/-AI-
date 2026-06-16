import assert from 'node:assert/strict';
import test from 'node:test';

import { checkEligibility, findIneligiblePolicies } from './eligibilityCheck.js';

test('checkEligibility accepts profile sigungu contained in comma-separated policy regions', () => {
  const profile = { age: 24, region_sido: '서울', region_sigungu: '성북구' };
  const policy = {
    policy_name: '서울 전체 청년 정책',
    min_age: 19,
    max_age: 39,
    region_sido: '서울',
    region_sigungu: '종로구,중구,용산구,성동구,광진구,동대문구,중랑구,성북구,강북구',
  };

  assert.deepEqual(checkEligibility(policy, profile), { eligible: true, gaps: [] });
});

test('findIneligiblePolicies does not flag matching multi-sigungu policy as ineligible', () => {
  const profile = { age: 24, region_sido: '서울', region_sigungu: '성북구' };
  const policies = [
    {
      policy_name: '서울 전체 청년 정책',
      min_age: 19,
      max_age: 39,
      region_sido: '서울',
      region_sigungu: '종로구,중구,용산구,성동구,광진구,동대문구,중랑구,성북구,강북구',
    },
  ];

  assert.deepEqual(findIneligiblePolicies(policies, profile), []);
});
