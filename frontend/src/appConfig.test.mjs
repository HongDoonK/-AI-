import test from 'node:test';
import assert from 'node:assert/strict';
import { REGION_OPTIONS } from './appConfig.js';

test('서울 시군구 옵션은 25개 자치구와 성북구를 포함한다', () => {
  assert.equal(REGION_OPTIONS.서울.length, 25);
  assert.ok(REGION_OPTIONS.서울.includes('성북구'));
});

test('시군구 옵션은 중복 없이 제공된다', () => {
  for (const [sido, sigunguList] of Object.entries(REGION_OPTIONS)) {
    assert.equal(new Set(sigunguList).size, sigunguList.length, `${sido} has duplicate options`);
  }
});
