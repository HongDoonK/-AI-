"""정책 상담 에이전트용 순수 텍스트 정제/추출 유틸리티."""
from __future__ import annotations

import re
from typing import Any


def _clean(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "none", "null"}:
        return ""
    if text in {"-", "0", "0원"}:
        return ""
    return re.sub(r"\s+", " ", text)


def _date(value: Any) -> str:
    text = _clean(value)
    if re.fullmatch(r"\d{8}", text):
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text


def _money(value: Any) -> str:
    text = _clean(value)
    if not text:
        return ""
    try:
        number = int(float(text))
    except ValueError:
        return text
    return f"{number:,}원"


def _append(lines: list[str], label: str, value: Any):
    text = _clean(value)
    if text:
        lines.append(f"- {label}: {text}")


def _append_date(lines: list[str], label: str, value: Any):
    text = _date(value)
    if text:
        lines.append(f"- {label}: {text}")


def _append_money(lines: list[str], label: str, value: Any):
    text = _money(value)
    if text:
        lines.append(f"- {label}: {text}")


def _strip_label(line: str) -> str:
    text = _clean(line).lstrip("-").strip()
    if ":" in text:
        return text.split(":", 1)[1].strip()
    return text


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        text = _clean(item)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _split_items(value: Any) -> list[str]:
    text = _clean(value)
    if not text:
        return []
    text = re.sub(r"[○ㆍ•]", "\n", text)
    text = re.sub(r"\s*[-–]\s+(?=[가-힣A-Za-z0-9(])", "\n", text)
    pieces = re.split(r"\n+|,\s*|/\s*|·", text)
    cleaned = []
    for piece in pieces:
        item = _clean(piece).strip("-:; ")
        if item and item not in {"제한없음", "무관", "없음"}:
            cleaned.append(item)
    return _dedupe(cleaned)


def _short_item(value: Any, limit: int = 82) -> str:
    text = _clean(value).strip("- ")
    if len(text) <= limit:
        return text
    separators = ["다.", "요.", ". ", "  "]
    for separator in separators:
        cut = text.find(separator)
        if 10 < cut < limit:
            return text[: cut + len(separator)].strip()
    return text[: limit - 1].rstrip() + "..."


def _extract_condition_bullets(text: str) -> list[str]:
    source = _clean(text)
    bullets = []
    age_matches = re.findall(r"만\s*\d+\s*세(?:\s*(?:이상|이하|미만|초과))?(?:\s*~\s*만?\s*\d+\s*세(?:\s*(?:이상|이하|미만|초과))?)?", source)
    bullets.extend(age_matches)
    income_matches = re.findall(r"(?:중위소득|합산 소득|가구소득|개인.*?소득|소득)[^,.。;\n]{0,45}(?:이하|미만|이상|초과|충족)", source)
    bullets.extend(income_matches)
    if "무주택" in source:
        bullets.append("무주택 요건 확인")
    if "세대주" in source:
        bullets.append("세대주 요건 확인")
    if "재직" in source or "근로" in source:
        bullets.append("근로/재직 여부 확인")
    if "청년" in source:
        bullets.append("청년 대상")
    if "창업" in source:
        bullets.append("창업 상태 또는 업력 조건 확인")
    return [_short_item(item, 72) for item in _dedupe(bullets)]


def _extract_benefit_bullets(text: str) -> list[str]:
    source = _clean(text)
    bullets = []
    money_patterns = re.findall(r"(?:월\s*)?\d[\d,]*(?:\.\d+)?\s*(?:만원|원|%)\s*(?:[~∼-]\s*\d[\d,]*(?:\.\d+)?\s*(?:만원|원|%))?(?:\s*(?:지원|지급|대출|적립|한도|금리|이하|이내))?", source)
    bullets.extend(money_patterns)
    duration_patterns = re.findall(r"\d+\s*(?:개월|년|년간)[^,.。;\n]{0,30}", source)
    bullets.extend(duration_patterns)
    for phrase in ["월세 지원", "임대료 지원", "보증금 지원", "금융교육", "재무상담", "사업화 지원", "훈련비 지원"]:
        if phrase in source:
            bullets.append(phrase)
    return [_short_item(item, 72) for item in _dedupe(bullets)]


def _support_content_only(text: Any) -> str:
    source = str(text or "").strip()
    if not source:
        return ""
    for marker in ["지원내용", "지원 내용", "지원혜택", "혜택"]:
        if marker in source:
            source = source.split(marker, 1)[1]
            break
    for marker in ["지원조건", "지원 조건", "신청자격", "신청 자격", "지원대상", "지원 대상"]:
        if marker in source:
            source = source.split(marker, 1)[0]
    return source


def _dash_bullets_from_text(text: Any) -> list[str]:
    source = str(text or "")
    bullets = []
    for line in source.splitlines():
        item = _clean(line).strip("-–* ")
        if item and line.strip().startswith(("-", "–", "*")):
            bullets.append(_short_item(item, 96))
    return _dedupe(bullets)


def _latest_user_message(messages: list[dict[str, str]]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            return _clean(message.get("content"))
    return ""


def _normalize_messages(messages: list[dict[str, str]]) -> list[dict[str, str]]:
    normalized = []
    for message in messages[-10:]:
        role = message.get("role", "user")
        if role == "model":
            role = "assistant"
        if role not in {"user", "assistant"}:
            continue
        content = _clean(message.get("content"))
        if content:
            normalized.append({"role": role, "content": content})
    return normalized
