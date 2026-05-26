from __future__ import annotations

import json
import os
from typing import Any

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*args, **kwargs):
        return False


DEFAULT_MODEL = "gpt-4o-mini"


class LLMUnavailable(RuntimeError):
    pass


def _client():
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise LLMUnavailable("OPENAI_API_KEY is not set.")

    try:
        from openai import OpenAI
    except Exception as exc:
        raise LLMUnavailable(f"OpenAI SDK is not available: {exc}") from exc

    return OpenAI()


def llm_enabled() -> bool:
    load_dotenv()
    if os.getenv("USE_OPENAI_LLM", "1").lower() in {"0", "false", "no"}:
        return False
    return bool(os.getenv("OPENAI_API_KEY"))


def get_model_name() -> str:
    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL)


def create_structured_output(
    *,
    system_prompt: str,
    user_prompt: str,
    schema_name: str,
    schema: dict[str, Any],
    max_output_tokens: int = 1200,
) -> dict[str, Any]:
    if not llm_enabled():
        raise LLMUnavailable("LLM is disabled or OPENAI_API_KEY is missing.")

    client = _client()
    response = client.responses.create(
        model=get_model_name(),
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": schema_name,
                "schema": schema,
                "strict": True,
            }
        },
        max_output_tokens=max_output_tokens,
    )

    output_text = getattr(response, "output_text", "")
    if not output_text:
        raise LLMUnavailable("OpenAI response did not include output_text.")

    try:
        return json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise LLMUnavailable(f"OpenAI response was not valid JSON: {exc}") from exc
