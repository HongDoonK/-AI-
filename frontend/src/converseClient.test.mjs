import assert from 'node:assert/strict';
import test from 'node:test';

import { actionToMessage, sendConverse } from './converseClient.js';

test('actionToMessage maps ordinal selection', () => {
  assert.equal(actionToMessage({ label: '2번 선택', intent: 'select', ordinal: 2 }), '정책 2 선택할래');
});

test('actionToMessage maps policy intents to natural utterances', () => {
  assert.equal(actionToMessage({ label: '필요 서류 보기', intent: 'docs' }), '필요한 서류 알려줘');
  assert.equal(actionToMessage({ label: '얼마 받는지 보기', intent: 'benefit' }), '얼마나 받을 수 있어?');
  assert.equal(actionToMessage({ label: '신청 자격 확인', intent: 'eligibility' }), '신청 자격 확인해줘');
});

test('actionToMessage maps create_apply_plan action', () => {
  assert.equal(actionToMessage({ label: '신청 준비 시작', action: 'create_apply_plan' }), '신청 준비 시작할래');
});

test('actionToMessage falls back to label', () => {
  assert.equal(actionToMessage({ label: '기타' }), '기타');
  assert.equal(actionToMessage({}), '');
});

test('sendConverse serializes seeded policy refs', async () => {
  const originalFetch = globalThis.fetch;
  let requestBody;
  globalThis.fetch = async (_url, options) => {
    requestBody = JSON.parse(options.body);
    return {
      ok: true,
      json: async () => ({ session_id: 's1', intent: 'select', reply: 'ok' }),
    };
  };

  try {
    await sendConverse('http://example.test', {
      message: '',
      sessionId: 's1',
      userId: 'u1',
      policy: { doc_id: 'policies_processed:P001', policy_name: '청년 월세 지원' },
    });
  } finally {
    globalThis.fetch = originalFetch;
  }

  assert.deepEqual(requestBody, {
    message: '',
    session_id: 's1',
    user_id: 'u1',
    selected_doc_id: null,
    policy: { doc_id: 'policies_processed:P001', policy_name: '청년 월세 지원' },
  });
});
