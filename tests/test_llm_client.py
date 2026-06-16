"""공급자 무관 LLM 클라이언트 테스트 (ADR-002 §D2).

네트워크/모델 없이 검증 가능한 부분만 다룬다: 공급자 선택, 비활성 fallback,
모델명 결정, JSON 추출/스키마 검증.
"""
import unittest
from unittest import mock

from ai import llm_client
from ai.llm_client import (
    DEFAULT_MODEL,
    LLMUnavailable,
    _extract_json,
    _provider,
    _validate_against_schema,
    create_chat_response,
    create_structured_output,
    get_model_name,
    llm_enabled,
)

_ENV_KEYS = ["LLM_PROVIDER", "LLM_MODEL", "USE_OPENAI_LLM", "OPENAI_API_KEY", "OPENAI_MODEL", "HF_TOKEN"]

_SCHEMA = {
    "type": "object",
    "properties": {"age": {"type": "integer"}, "region": {"type": "string"}},
    "required": ["age"],
    "additionalProperties": False,
}


class LLMClientTest(unittest.TestCase):
    def setUp(self):
        import os

        self._saved = {k: os.environ.get(k) for k in _ENV_KEYS}
        # load_dotenv(override=False)가 기존 값을 덮지 않도록 명시적으로 비운다
        for k in _ENV_KEYS:
            os.environ.pop(k, None)

    def tearDown(self):
        import os

        for k, v in self._saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def _set(self, **kwargs):
        import os

        for k, v in kwargs.items():
            os.environ[k] = v

    # ── 공급자 선택 ──────────────────────────────────────────────
    def test_provider_none_disables_llm(self):
        self._set(LLM_PROVIDER="none")
        self.assertEqual(_provider(), "none")
        self.assertFalse(llm_enabled())
        with self.assertRaises(LLMUnavailable):
            create_structured_output(
                system_prompt="s", user_prompt="u", schema_name="x", schema=_SCHEMA
            )
        with self.assertRaises(LLMUnavailable):
            create_chat_response(system_prompt="s", messages=[{"role": "user", "content": "u"}])

    def test_legacy_use_openai_zero_maps_to_none(self):
        self._set(USE_OPENAI_LLM="0")
        self.assertEqual(_provider(), "none")
        self.assertFalse(llm_enabled())

    def test_legacy_openai_key_maps_to_openai(self):
        self._set(USE_OPENAI_LLM="1", OPENAI_API_KEY="sk-test")
        self.assertEqual(_provider(), "openai")
        self.assertTrue(llm_enabled())

    def test_unknown_provider_raises_on_call(self):
        self._set(LLM_PROVIDER="bogus")
        self.assertTrue(llm_enabled())  # none이 아니므로 활성으로 간주
        with self.assertRaises(LLMUnavailable):
            create_chat_response(system_prompt="s", messages=[{"role": "user", "content": "u"}])

    # ── 모델명 ───────────────────────────────────────────────────
    def test_model_name_defaults_to_qwen(self):
        self._set(LLM_PROVIDER="hf")
        self.assertEqual(get_model_name(), DEFAULT_MODEL)
        self.assertTrue(DEFAULT_MODEL.startswith("Qwen/"))

    def test_model_name_respects_llm_model(self):
        self._set(LLM_PROVIDER="local", LLM_MODEL="Qwen/Qwen2.5-1.5B-Instruct")
        self.assertEqual(get_model_name(), "Qwen/Qwen2.5-1.5B-Instruct")

    def test_model_name_openai_uses_openai_model(self):
        self._set(LLM_PROVIDER="openai", OPENAI_MODEL="gpt-4o-mini")
        self.assertEqual(get_model_name(), "gpt-4o-mini")

    # ── JSON 추출 ────────────────────────────────────────────────
    def test_extract_json_plain(self):
        self.assertEqual(_extract_json('{"age": 24}'), {"age": 24})

    def test_extract_json_strips_code_fence(self):
        text = "다음과 같습니다:\n```json\n{\"age\": 24, \"region\": \"서울\"}\n```\n끝."
        self.assertEqual(_extract_json(text), {"age": 24, "region": "서울"})

    def test_extract_json_finds_object_in_prose(self):
        self.assertEqual(_extract_json('답: {"age": 30} 입니다'), {"age": 30})

    def test_extract_json_raises_on_garbage(self):
        with self.assertRaises(LLMUnavailable):
            _extract_json("JSON이 전혀 없는 문자열")

    # ── 스키마 검증 ──────────────────────────────────────────────
    def test_validate_accepts_valid(self):
        self.assertEqual(_validate_against_schema({"age": 24, "region": "서울"}, _SCHEMA), {"age": 24, "region": "서울"})

    def test_validate_rejects_missing_required(self):
        with self.assertRaises(LLMUnavailable):
            _validate_against_schema({"region": "서울"}, _SCHEMA)

    def test_validate_rejects_wrong_type(self):
        with self.assertRaises(LLMUnavailable):
            _validate_against_schema({"age": "스물넷"}, _SCHEMA)

    def test_validate_rejects_non_object(self):
        with self.assertRaises(LLMUnavailable):
            _validate_against_schema(["age"], _SCHEMA)

    # ── 공급자 실패 수렴 / 재시도 (codex CHANGES_REQUESTED 반영) ──
    def test_openai_structured_failure_wrapped(self):
        """OpenAI responses.create 예외도 LLMUnavailable로 수렴해야 함(P1)."""
        self._set(LLM_PROVIDER="openai", OPENAI_API_KEY="sk-test")
        fake = mock.MagicMock()
        fake.responses.create.side_effect = RuntimeError("boom")
        with mock.patch.object(llm_client, "_openai_client", return_value=fake):
            with self.assertRaises(LLMUnavailable):
                create_structured_output(
                    system_prompt="s", user_prompt="u", schema_name="x", schema=_SCHEMA
                )

    def test_structured_retry_succeeds_on_second_attempt(self):
        """hf 구조화 출력: 1차 실패(JSON 없음) 후 2차 성공이면 수용(P2)."""
        self._set(LLM_PROVIDER="hf")
        with mock.patch.object(
            llm_client, "_hf_chat_raw", side_effect=["설명만 있고 JSON 없음", '{"age": 24}']
        ) as m:
            out = create_structured_output(
                system_prompt="s", user_prompt="u", schema_name="x", schema=_SCHEMA
            )
        self.assertEqual(out, {"age": 24})
        self.assertEqual(m.call_count, 2)

    def test_structured_retry_exhausts_raises(self):
        """hf 구조화 출력: 2회 모두 실패하면 LLMUnavailable(P2)."""
        self._set(LLM_PROVIDER="hf")
        with mock.patch.object(
            llm_client, "_hf_chat_raw", side_effect=LLMUnavailable("net")
        ) as m:
            with self.assertRaises(LLMUnavailable):
                create_structured_output(
                    system_prompt="s", user_prompt="u", schema_name="x", schema=_SCHEMA
                )
        self.assertEqual(m.call_count, 2)


if __name__ == "__main__":
    unittest.main()
