"""공급자 무관 LLM 클라이언트 (ADR-002 §D2).

LLM은 비핵심·교체 가능한 "언어 계층"이다. 정책의 사실(금액/기간/자격/URL)은
RAG·규칙 엔진이 책임지고, 여기서는 ① 자유발화 조건 추출(JSON) ② 말투 다듬기(NLG)
만 담당한다. 어떤 공급자든 실패하면 LLMUnavailable을 던져 호출 측 규칙 fallback을 탄다.

공급자 선택: 환경변수 LLM_PROVIDER ∈ {none, openai, hf, local}
- none  : LLM 비활성 (기본). 즉시 LLMUnavailable → 규칙 fallback. 데모/CI 기본값.
- openai: 레거시 OpenAI Responses API (키 있을 때만). 점진 폐기 대상.
- hf    : HuggingFace Inference API (InferenceClient.chat_completion).
- local : 로컬 transformers 추론 (오프라인). 최초 1회 모델 다운로드.

레거시 호환: LLM_PROVIDER가 비어 있으면 USE_OPENAI_LLM/OPENAI_API_KEY로 추론한다
(USE_OPENAI_LLM=0 → none, 키 있으면 openai).

설계: docs/ADR-002-llm-provider-and-surface-consolidation.md
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - dotenv는 선택 의존성
    def load_dotenv(*args, **kwargs):
        return False


# 기본 오픈모델 (Apache-2.0). 저사양 폴백: Qwen/Qwen2.5-1.5B-Instruct
DEFAULT_MODEL = "Qwen/Qwen2.5-7B-Instruct"
_OPENAI_DEFAULT_MODEL = "gpt-4o-mini"
_DISABLED_PROVIDERS = {"", "none", "off", "disabled", "0", "false", "no"}

# 로컬 추론 모델/토크나이저 캐시 (재로딩 방지)
_LOCAL_CACHE: dict[str, Any] = {}


class LLMUnavailable(RuntimeError):
    """LLM 비활성·미설정·호출 실패 시 던져 규칙 fallback을 유도한다."""


# ── 공급자/모델 선택 ────────────────────────────────────────────────
def _provider() -> str:
    """LLM_PROVIDER 우선, 없으면 레거시 변수로 추론한다."""
    load_dotenv()
    explicit = os.getenv("LLM_PROVIDER", "").strip().lower()
    if explicit:
        return explicit
    # 레거시 호환
    if os.getenv("USE_OPENAI_LLM", "1").strip().lower() in {"0", "false", "no"}:
        return "none"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "none"


def llm_enabled() -> bool:
    return _provider() not in _DISABLED_PROVIDERS


def get_model_name() -> str:
    load_dotenv()
    if _provider() == "openai":
        return os.getenv("OPENAI_MODEL") or os.getenv("LLM_MODEL") or _OPENAI_DEFAULT_MODEL
    return os.getenv("LLM_MODEL", DEFAULT_MODEL)


# ── JSON 추출·검증 ──────────────────────────────────────────────────
def _extract_json(text: str) -> dict[str, Any]:
    """모델 출력에서 JSON 객체를 추출한다(코드펜스/잡설 방어)."""
    if not text:
        raise LLMUnavailable("LLM 응답이 비어 있습니다.")
    cleaned = text.strip()
    # ```json ... ``` 펜스 제거
    fence = re.search(r"```(?:json)?\s*(.+?)```", cleaned, re.DOTALL)
    if fence:
        cleaned = fence.group(1).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    # 첫 번째 균형 잡힌 중괄호 블록 시도
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError as exc:
            raise LLMUnavailable(f"LLM 응답이 유효한 JSON이 아닙니다: {exc}") from exc
    raise LLMUnavailable("LLM 응답에서 JSON 객체를 찾지 못했습니다.")


def _validate_against_schema(data: Any, schema: dict[str, Any]) -> dict[str, Any]:
    """json.loads 통과만으로 신뢰하지 않고 schema/type을 검증한다(ADR-002 codex 권고).

    jsonschema가 있으면 그것으로, 없으면 최소 required/type 검증으로 대체한다.
    검증 실패는 LLMUnavailable → 규칙 fallback.
    """
    if not isinstance(data, dict):
        raise LLMUnavailable("LLM 구조화 출력이 객체(JSON object)가 아닙니다.")
    try:
        import jsonschema  # type: ignore

        try:
            jsonschema.validate(instance=data, schema=schema)
        except jsonschema.ValidationError as exc:  # pragma: no cover - 메시지 경로
            raise LLMUnavailable(f"LLM 출력이 스키마를 위반했습니다: {exc.message}") from exc
        return data
    except ModuleNotFoundError:
        # 최소 검증: required 키 존재 + 최상위 type 일치
        for key in schema.get("required", []):
            if key not in data:
                raise LLMUnavailable(f"LLM 출력에 필수 필드 '{key}'가 없습니다.")
        props = schema.get("properties", {})
        for key, spec in props.items():
            if key in data and "type" in spec and not _type_ok(data[key], spec["type"]):
                raise LLMUnavailable(f"LLM 출력 필드 '{key}'의 타입이 스키마와 다릅니다.")
        return data


def _type_ok(value: Any, json_type: Any) -> bool:
    mapping = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
        "null": type(None),
    }
    types = json_type if isinstance(json_type, list) else [json_type]
    for t in types:
        py = mapping.get(t)
        if py and isinstance(value, py) and not (t in {"integer", "number"} and isinstance(value, bool)):
            return True
        if t == "null" and value is None:
            return True
    return False


# ── 공급자별 백엔드 ─────────────────────────────────────────────────
def _openai_client():
    if not os.getenv("OPENAI_API_KEY"):
        raise LLMUnavailable("OPENAI_API_KEY가 설정되지 않았습니다.")
    try:
        from openai import OpenAI
    except Exception as exc:  # pragma: no cover - openai 미설치 경로
        raise LLMUnavailable(f"OpenAI SDK를 불러올 수 없습니다: {exc}") from exc
    return OpenAI()


def _openai_structured(system_prompt, user_prompt, schema_name, schema, max_output_tokens):
    client = _openai_client()
    try:
        response = client.responses.create(
            model=get_model_name(),
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            text={"format": {"type": "json_schema", "name": schema_name, "schema": schema, "strict": True}},
            max_output_tokens=max_output_tokens,
        )
    except Exception as exc:  # 인증(401)/네트워크/레이트리밋 등 모두 LLMUnavailable로 수렴
        raise LLMUnavailable(f"OpenAI structured 응답 실패: {exc}") from exc
    output_text = getattr(response, "output_text", "")
    return _extract_json(output_text)


def _openai_chat(system_prompt, messages, max_output_tokens):
    client = _openai_client()
    try:
        response = client.responses.create(
            model=get_model_name(),
            input=[{"role": "system", "content": system_prompt}, *messages],
            max_output_tokens=max_output_tokens,
        )
    except Exception as exc:
        raise LLMUnavailable(f"OpenAI 응답 실패: {exc}") from exc
    text = getattr(response, "output_text", "").strip()
    if not text:
        raise LLMUnavailable("OpenAI 응답에 output_text가 없습니다.")
    return text


def _hf_client():
    try:
        from huggingface_hub import InferenceClient
    except Exception as exc:
        raise LLMUnavailable(f"huggingface_hub를 불러올 수 없습니다: {exc}") from exc
    return InferenceClient(model=get_model_name(), token=os.getenv("HF_TOKEN") or None)


def _hf_chat_raw(system_prompt: str, messages: list[dict[str, str]], max_tokens: int) -> str:
    client = _hf_client()
    try:
        resp = client.chat_completion(
            messages=[{"role": "system", "content": system_prompt}, *messages],
            max_tokens=max_tokens,
            temperature=0.0,
        )
    except Exception as exc:
        raise LLMUnavailable(f"HF Inference 호출 실패: {exc}") from exc
    try:
        text = resp.choices[0].message.content or ""
    except (AttributeError, IndexError, KeyError) as exc:
        raise LLMUnavailable(f"HF 응답 형식이 예상과 다릅니다: {exc}") from exc
    if not text.strip():
        raise LLMUnavailable("HF 응답이 비어 있습니다.")
    return text.strip()


def _local_generate(system_prompt: str, messages: list[dict[str, str]], max_new_tokens: int) -> str:
    try:
        import torch  # noqa: F401
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except Exception as exc:
        raise LLMUnavailable(f"transformers/torch를 불러올 수 없습니다: {exc}") from exc

    model_name = get_model_name()
    cache = _LOCAL_CACHE.get(model_name)
    if cache is None:
        try:
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype="auto", device_map="auto")
        except Exception as exc:
            raise LLMUnavailable(f"로컬 모델 로딩 실패({model_name}): {exc}") from exc
        cache = (tokenizer, model)
        _LOCAL_CACHE[model_name] = cache
    tokenizer, model = cache

    chat = [{"role": "system", "content": system_prompt}, *messages]
    try:
        inputs = tokenizer.apply_chat_template(chat, add_generation_prompt=True, return_tensors="pt")
        inputs = inputs.to(model.device)
        generated = model.generate(inputs, max_new_tokens=max_new_tokens, do_sample=False)
        new_tokens = generated[0][inputs.shape[-1]:]
        text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
    except Exception as exc:
        raise LLMUnavailable(f"로컬 추론 실패: {exc}") from exc
    if not text:
        raise LLMUnavailable("로컬 추론 결과가 비어 있습니다.")
    return text


_JSON_SUFFIX = (
    "\n\n반드시 추가 설명 없이 유효한 JSON 객체 하나만 출력하세요. "
    "제공된 context에 없는 수치·날짜·기관명은 만들지 마세요."
)


# ── 공개 API (시그니처 보존) ────────────────────────────────────────
def create_structured_output(
    *,
    system_prompt: str,
    user_prompt: str,
    schema_name: str,
    schema: dict[str, Any],
    max_output_tokens: int = 1200,
) -> dict[str, Any]:
    """공급자 무관 구조화(JSON) 출력. 실패·비활성 시 LLMUnavailable.

    hf/local은 JSON 추출 또는 schema 검증 실패 시 1회 재시도한 뒤 fallback한다
    (ADR-002 §D2: "값이 비거나 자유서술이면 ... 1회 재시도").
    """
    provider = _provider()
    if provider in _DISABLED_PROVIDERS:
        raise LLMUnavailable("LLM이 비활성화되어 있습니다 (LLM_PROVIDER=none).")

    if provider == "openai":
        data = _openai_structured(system_prompt, user_prompt, schema_name, schema, max_output_tokens)
        return _validate_against_schema(data, schema)

    if provider in {"hf", "local"}:
        generate = _hf_chat_raw if provider == "hf" else _local_generate
        sys_prompt = system_prompt + _JSON_SUFFIX
        messages = [{"role": "user", "content": user_prompt}]
        last_exc: LLMUnavailable | None = None
        for _attempt in range(2):  # 최초 + 1회 재시도
            try:
                raw = generate(sys_prompt, messages, max_output_tokens)
                data = _extract_json(raw)
                return _validate_against_schema(data, schema)
            except LLMUnavailable as exc:
                last_exc = exc
        raise last_exc if last_exc else LLMUnavailable("구조화 출력 생성에 실패했습니다.")

    raise LLMUnavailable(f"알 수 없는 LLM_PROVIDER: {provider}")


def create_chat_response(
    *,
    system_prompt: str,
    messages: list[dict[str, str]],
    max_output_tokens: int = 900,
) -> str:
    """공급자 무관 자유 텍스트(NLG) 출력. 실패·비활성 시 LLMUnavailable."""
    provider = _provider()
    if provider in _DISABLED_PROVIDERS:
        raise LLMUnavailable("LLM이 비활성화되어 있습니다 (LLM_PROVIDER=none).")

    if provider == "openai":
        return _openai_chat(system_prompt, messages, max_output_tokens)
    if provider == "hf":
        return _hf_chat_raw(system_prompt, messages, max_output_tokens)
    if provider == "local":
        return _local_generate(system_prompt, messages, max_output_tokens)
    raise LLMUnavailable(f"알 수 없는 LLM_PROVIDER: {provider}")
