from __future__ import annotations

import os
import re
from datetime import date, datetime
from functools import lru_cache
from typing import Any

import pandas as pd

from ai.db_loader import project_root


EMBEDDING_MODEL_NAME = "jhgan/ko-sroberta-multitask"

INTEREST_TERMS = {
    "주거": ["주거", "월세", "전세", "임대", "보증금", "무주택", "주택", "거주"],
    "취업": ["취업", "구직", "일자리", "면접", "채용", "자격증"],
    "창업": ["창업", "사업", "스타트업", "창업자", "예비창업"],
    "교육": ["교육", "훈련", "강의", "학습", "장학", "학비"],
    "복지": ["복지", "상담", "건강", "문화", "생활"],
    "금융": ["금융", "대출", "저축", "자산", "소득", "지원금"],
}

ALWAYS_OPEN_TERMS = ["상시", "수시", "연중", "예산 소진", "별도 문의", "문의", "미정"]


def _text_series(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    existing = [col for col in columns if col in df.columns]
    if not existing:
        return pd.Series([""] * len(df), index=df.index)
    return df[existing].fillna("").astype(str).agg(" ".join, axis=1)


def _contains(series: pd.Series, value: str | None) -> pd.Series:
    if not value:
        return pd.Series([True] * len(series), index=series.index)
    return series.str.contains(re.escape(str(value)), case=False, na=False)


def _parse_date_token(token: str) -> date | None:
    token = token.strip()
    patterns = [
        r"(\d{4})[.\-/년\s]*(\d{1,2})[.\-/월\s]*(\d{1,2})",
        r"(\d{8})",
    ]
    for pattern in patterns:
        match = re.search(pattern, token)
        if not match:
            continue
        try:
            if len(match.groups()) == 1:
                return datetime.strptime(match.group(1), "%Y%m%d").date()
            year, month, day = match.groups()
            return date(int(year), int(month), int(day))
        except ValueError:
            return None
    return None


def _extract_apply_end(value: Any) -> date | None:
    text = "" if value is None else str(value).strip()
    if not text or any(term in text for term in ALWAYS_OPEN_TERMS):
        return None

    date_tokens = re.findall(r"\d{4}[.\-/년\s]*\d{1,2}[.\-/월\s]*\d{1,2}|\d{8}", text)
    parsed = [_parse_date_token(token) for token in date_tokens]
    parsed = [item for item in parsed if item is not None]
    if not parsed:
        return None
    return max(parsed)


def _is_active_policy(row: pd.Series, today: date | None = None) -> bool:
    today = today or date.today()
    end_date = _extract_apply_end(row.get("apply_period"))
    if end_date is None:
        return True
    return end_date >= today


def _filter_active_policies(df: pd.DataFrame) -> pd.DataFrame:
    if "apply_period" not in df.columns:
        return df
    active_mask = df.apply(_is_active_policy, axis=1)
    return df[active_mask].copy()


def _apply_soft_filters(df: pd.DataFrame, condition: dict[str, Any]) -> pd.DataFrame:
    filtered = _filter_active_policies(df.copy())

    age = condition.get("age")
    if age is not None and {"min_age", "max_age"}.issubset(filtered.columns):
        min_age = pd.to_numeric(filtered["min_age"], errors="coerce").mask(lambda s: s == 0)
        max_age = pd.to_numeric(filtered["max_age"], errors="coerce").mask(lambda s: s == 0)
        age_mask = ((min_age.isna()) | (min_age <= age)) & ((max_age.isna()) | (max_age >= age))
        filtered = filtered[age_mask]

    searchable = _text_series(
        filtered,
        ["search_text", "policy_name", "description", "keyword", "support_content", "job_cd", "school_cd"],
    )

    employment = condition.get("employment_status")
    if employment:
        job_text = _text_series(filtered, ["job_cd", "search_text"])
        mask = _contains(job_text, employment)
        if mask.sum() > 0:
            filtered = filtered[mask]
            searchable = searchable[mask]

    status = condition.get("status")
    if status:
        school_text = _text_series(filtered, ["school_cd", "search_text"])
        mask = _contains(school_text, status)
        if mask.sum() > 0:
            filtered = filtered[mask]
            searchable = searchable[mask]

    interest = condition.get("interest")
    if interest:
        mask = _contains(searchable, interest)
        if mask.sum() > 0:
            filtered = filtered[mask]

    return filtered.reset_index(drop=False).rename(columns={"index": "_source_index"})


@lru_cache(maxsize=1)
def _load_faiss_resources():
    if os.getenv("USE_FAISS", "0").lower() not in {"1", "true", "yes"}:
        raise RuntimeError("FAISS is disabled. Set USE_FAISS=1 to enable embedding search.")
    try:
        import faiss
        import torch
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        raise RuntimeError(f"FAISS dependencies are not available: {exc}") from exc

    index_path = project_root() / "data" / "index" / "faiss_index.index"
    if not index_path.exists():
        raise FileNotFoundError(f"FAISS index not found at {index_path}")

    index = faiss.read_index(str(index_path))
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(EMBEDDING_MODEL_NAME, device=device)
    return faiss, model, index


def _faiss_rank(user_input: str, candidates: pd.DataFrame, top_k: int) -> pd.DataFrame:
    faiss, model, index = _load_faiss_resources()
    query_embedding = model.encode([user_input], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(query_embedding)

    search_k = min(max(top_k * 10, 30), index.ntotal)
    scores, indices = index.search(query_embedding, search_k)

    allowed = set(candidates["_source_index"].astype(int).tolist())
    rows = []
    for score, source_index in zip(scores[0], indices[0]):
        if int(source_index) in allowed:
            row = candidates[candidates["_source_index"] == int(source_index)].head(1).copy()
            if not row.empty:
                row["score"] = float(score)
                rows.append(row)
        if len(rows) >= top_k:
            break

    if not rows:
        raise RuntimeError("FAISS search returned no rows after filtering.")
    return pd.concat(rows, ignore_index=True)


def _keyword_rank(user_input: str, condition: dict[str, Any], candidates: pd.DataFrame, top_k: int) -> pd.DataFrame:
    query_terms = set(re.findall(r"[가-힣A-Za-z0-9]{2,}", user_input or ""))
    for key in ["region", "employment_status", "interest", "housing_status", "status", "income", "gender"]:
        value = condition.get(key)
        if value:
            query_terms.add(str(value))

    text = _text_series(
        candidates,
        ["search_text", "policy_name", "description", "keyword", "category_main", "category_sub", "support_content"],
    )

    if condition.get("housing_status") == "월세":
        rent_pattern = "월세|전월세|임대료|보증금|주택임차"
        rent_mask = text.str.contains(rent_pattern, case=False, na=False, regex=True)
        if rent_mask.sum() > 0:
            candidates = candidates[rent_mask].copy()
            text = text[rent_mask]

    ranked = candidates.copy()
    scores = []
    interest = condition.get("interest")
    interest_terms = INTEREST_TERMS.get(interest, [])

    for idx, value in text.items():
        haystack = value.lower()
        row = candidates.loc[idx]
        category_text = " ".join(
            str(row.get(col) or "")
            for col in ["category_main", "category_sub", "keyword", "policy_name"]
        )

        score = 0.0
        for term in query_terms:
            if term.lower() in haystack:
                score += 2.0 if term in [condition.get("interest"), condition.get("employment_status")] else 1.0

        if interest and interest in category_text:
            score += 8.0
        for term in interest_terms:
            if term in category_text:
                score += 4.0
            elif term in haystack:
                score += 1.5

        if condition.get("status") and condition["status"] in haystack:
            score += 3.0
        if condition.get("employment_status") and condition["employment_status"] in str(row.get("job_cd") or ""):
            score += 3.0

        housing_requested = interest == "주거" or condition.get("housing_status")
        if housing_requested:
            housing_terms = ["월세", "전세", "주거", "주택", "임대", "보증금"]
            rent_terms = ["월세", "전월세", "임대료", "보증금", "주택임차"]
            has_housing_signal = any(term in category_text for term in housing_terms)
            if has_housing_signal:
                score += 6.0
            if "창업" in category_text and not has_housing_signal:
                score -= 6.0
            if condition.get("housing_status") == "월세":
                has_rent_signal = any(term in haystack or term in category_text for term in rent_terms)
                score += 8.0 if has_rent_signal else -10.0

        region = condition.get("region")
        if region and region.lower() in haystack:
            score += 0.5
        scores.append(score)

    ranked["score"] = scores
    return ranked.sort_values(["score", "policy_id"], ascending=[False, True]).head(top_k).reset_index(drop=True)


def retrieve_top_k(user_input: str, user_condition: dict, df: pd.DataFrame, top_k: int = 5) -> list[dict]:
    candidates = _apply_soft_filters(df, user_condition)
    if candidates.empty:
        candidates = _filter_active_policies(df.copy()).reset_index(drop=False).rename(columns={"index": "_source_index"})

    try:
        ranked = _faiss_rank(user_input, candidates, top_k)
    except Exception as exc:
        print(f"[ai.retriever] FAISS unavailable, using keyword fallback: {exc}")
        ranked = _keyword_rank(user_input, user_condition, candidates, top_k)

    return ranked.drop(columns=["_source_index"], errors="ignore").head(top_k).to_dict("records")
