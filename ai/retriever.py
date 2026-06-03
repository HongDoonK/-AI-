from __future__ import annotations

import hashlib
import os
import re
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


EMBEDDING_MODEL_NAME = "jhgan/ko-sroberta-multitask"
INDEX_DIR = Path(__file__).resolve().parent.parent / "data" / "index"

INTEREST_TERMS = {
    "주거": ["주거", "월세", "전세", "임대", "보증금", "무주택", "주택", "거주"],
    "취업": ["취업", "구직", "일자리", "면접", "채용", "자격증"],
    "창업": ["창업", "사업", "스타트업", "창업자", "예비창업"],
    "교육": ["교육", "훈련", "강의", "학습", "장학", "학비"],
    "복지": ["복지", "상담", "건강", "문화", "생활"],
    "금융": ["금융", "대출", "저축", "자산", "소득", "지원금"],
}

ALWAYS_OPEN_TERMS = ["상시", "수시", "연중", "예산 소진", "별도 문의", "문의", "미정"]

INTEREST_DOMAINS = {
    "주거": ["policy_housing", "housing_notice", "rental_house", "loan"],
    "금융": ["policy_finance", "loan"],
    "교육": ["policy_training", "training"],
    "취업": ["policy_job", "training"],
    "창업": ["policy_startup", "startup"],
    "복지": ["policy", "policy_finance"],
}

DOMAIN_QUOTAS = {
    "주거": {"policy_housing": 2, "housing_notice": 2, "rental_house": 1, "loan": 1},
    "금융": {"policy_finance": 3, "loan": 2},
    "교육": {"policy_training": 2, "training": 3},
    "취업": {"policy_job": 2, "training": 3},
    "창업": {"policy_startup": 2, "startup": 3},
}

REGION_ALIASES = {
    "서울특별시": "서울",
    "부산광역시": "부산",
    "대구광역시": "대구",
    "인천광역시": "인천",
    "광주광역시": "광주",
    "대전광역시": "대전",
    "울산광역시": "울산",
    "세종특별자치시": "세종",
    "경기도": "경기",
    "강원특별자치도": "강원",
    "강원도": "강원",
    "충청북도": "충북",
    "충청남도": "충남",
    "전북특별자치도": "전북",
    "전라북도": "전북",
    "전라남도": "전남",
    "경상북도": "경북",
    "경상남도": "경남",
    "제주특별자치도": "제주",
}


def _text_series(df: pd.DataFrame, columns: list[str]) -> pd.Series:
    existing = [col for col in columns if col in df.columns]
    if not existing:
        return pd.Series([""] * len(df), index=df.index)
    return df[existing].fillna("").astype(str).agg(" ".join, axis=1)


def _contains(series: pd.Series, value: str | None) -> pd.Series:
    if not value:
        return pd.Series([True] * len(series), index=series.index)
    return series.str.contains(re.escape(str(value)), case=False, na=False)


def _normalize_region(value: str | None) -> str:
    text = "" if value is None else str(value).strip()
    for long_name, short_name in REGION_ALIASES.items():
        text = text.replace(long_name, short_name)
    return text


def _region_fields(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    sido_text = _text_series(df, ["region_sido"]).map(_normalize_region)
    sigungu_text = _text_series(df, ["region_sigungu"]).map(_normalize_region)
    region_name_text = _text_series(df, ["region_name", "region"]).map(_normalize_region)
    return sido_text, sigungu_text, region_name_text


def _region_priority(
    df: pd.DataFrame,
    region: str | None = None,
    region_sido: str | None = None,
    region_sigungu: str | None = None,
) -> pd.Series:
    wanted_sigungu = _normalize_region(region_sigungu)
    wanted_sido = _normalize_region(region_sido or region)
    if not wanted_sido and not wanted_sigungu:
        return pd.Series([1] * len(df), index=df.index)

    sido_text, sigungu_text, region_name_text = _region_fields(df)
    nationwide = (
        sido_text.str.strip().eq("전국")
        | region_name_text.str.strip().eq("전국")
        | region_name_text.str.contains(r"(?:^|[, ]+)전국(?:$|[, ]+)", regex=True, na=False)
    )

    priority = pd.Series([0] * len(df), index=df.index)
    priority[nationwide] = 1

    if wanted_sido:
        same_sido = (
            sido_text.str.contains(re.escape(wanted_sido), case=False, na=False)
            | region_name_text.str.contains(re.escape(wanted_sido), case=False, na=False)
        )
        broad_sido = same_sido & sigungu_text.str.strip().isin(["", "전국"])
        priority[broad_sido] = priority[broad_sido].clip(lower=2)

    if wanted_sigungu:
        same_sigungu = sigungu_text.str.contains(re.escape(wanted_sigungu), case=False, na=False)
        priority[same_sigungu] = priority[same_sigungu].clip(lower=3)
    elif wanted_sido:
        same_sido = (
            sido_text.str.contains(re.escape(wanted_sido), case=False, na=False)
            | region_name_text.str.contains(re.escape(wanted_sido), case=False, na=False)
        )
        priority[same_sido] = priority[same_sido].clip(lower=3)

    return priority


def _region_mask(
    df: pd.DataFrame,
    region: str | None = None,
    region_sido: str | None = None,
    region_sigungu: str | None = None,
) -> pd.Series:
    return _region_priority(df, region, region_sido, region_sigungu) > 0


def _condition_region_mask(df: pd.DataFrame, condition: dict[str, Any]) -> pd.Series:
    return _region_mask(
        df,
        region=condition.get("region"),
        region_sido=condition.get("region_sido"),
        region_sigungu=condition.get("region_sigungu"),
    )


def _condition_region_priority(df: pd.DataFrame, condition: dict[str, Any]) -> pd.Series:
    return _region_priority(
        df,
        region=condition.get("region"),
        region_sido=condition.get("region_sido"),
        region_sigungu=condition.get("region_sigungu"),
    )


def _domain_hint(condition: dict[str, Any]) -> list[str]:
    interest = condition.get("interest")
    if interest in INTEREST_DOMAINS:
        return INTEREST_DOMAINS[interest]
    housing = condition.get("housing_status")
    if housing:
        return INTEREST_DOMAINS["주거"]
    return []


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
    end_date = _extract_apply_end(row.get("apply_end_date")) or _extract_apply_end(row.get("apply_period"))
    if end_date is None:
        return True
    return end_date >= today


def _filter_active_policies(df: pd.DataFrame) -> pd.DataFrame:
    if "apply_period" not in df.columns and "apply_end_date" not in df.columns:
        return df
    active_mask = df.apply(_is_active_policy, axis=1)
    return df[active_mask].copy()


def _apply_soft_filters(df: pd.DataFrame, condition: dict[str, Any]) -> pd.DataFrame:
    filtered = _filter_active_policies(df.copy())

    domains = _domain_hint(condition)
    if domains and "domain" in filtered.columns:
        domain_mask = filtered["domain"].isin(domains)
        if domain_mask.sum() > 0:
            filtered = filtered[domain_mask]

    if condition.get("region") or condition.get("region_sido") or condition.get("region_sigungu"):
        filtered = filtered[_condition_region_mask(filtered, condition)]

    age = condition.get("age")
    if age is not None and {"min_age", "max_age"}.issubset(filtered.columns):
        min_age = pd.to_numeric(filtered["min_age"], errors="coerce").mask(lambda s: s == 0)
        max_age = pd.to_numeric(filtered["max_age"], errors="coerce").mask(lambda s: s == 0)
        age_mask = ((min_age.isna()) | (min_age <= age)) & ((max_age.isna()) | (max_age >= age))
        filtered = filtered[age_mask]

    searchable = _text_series(
        filtered,
        [
            "search_text", "policy_name", "title", "description", "summary", "keyword",
            "support_content", "target", "job_cd", "school_cd", "employment_status", "status",
        ],
    )

    # In the unified table, domain/region/age are reliable hard filters.
    # Status and employment labels differ by source, so keep them as ranking
    # signals unless we are using the legacy policies_processed-only table.
    if "domain" not in filtered.columns:
        employment = condition.get("employment_status")
        if employment:
            job_text = _text_series(filtered, ["employment_status", "job_cd", "target", "search_text"])
            mask = _contains(job_text, employment)
            if mask.sum() > 0:
                filtered = filtered[mask]
                searchable = searchable[mask]

        status = condition.get("status")
        if status:
            school_text = _text_series(filtered, ["status", "school_cd", "target", "search_text"])
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


def _faiss_enabled() -> bool:
    return os.getenv("USE_FAISS", "1").lower() not in {"0", "false", "no"}


@lru_cache(maxsize=1)
def _load_faiss_resources():
    if not _faiss_enabled():
        raise RuntimeError("FAISS is disabled. Set USE_FAISS=1 to enable embedding search.")
    try:
        import faiss
        import torch
        from sentence_transformers import SentenceTransformer
    except Exception as exc:
        raise RuntimeError(f"FAISS dependencies are not available: {exc}") from exc

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = SentenceTransformer(EMBEDDING_MODEL_NAME, device=device)
    return faiss, model


def _embedding_query(user_input: str, condition: dict[str, Any]) -> str:
    condition_text = " ".join(
        str(value)
        for key in [
            "age", "region", "region_sido", "region_sigungu", "status", "interest",
            "employment_status", "income", "housing_status", "gender",
        ]
        if (value := condition.get(key)) not in (None, "")
    )
    return f"{user_input or ''} {condition_text}".strip()


def _embedding_texts(candidates: pd.DataFrame) -> pd.Series:
    return _text_series(
        candidates,
        [
            "search_text",
            "title",
            "summary",
            "domain",
            "source_table",
            "region_name",
            "region_sido",
            "region_sigungu",
            "target",
            "policy_name",
            "description",
            "keyword",
            "category_main",
            "category_sub",
            "support_content",
            "apply_condition",
            "job_cd",
            "school_cd",
            "income_type",
            "income_etc",
        ],
    ).str.strip().replace("", "정책 정보")


def _corpus_signature(corpus: pd.DataFrame) -> str:
    pieces = []
    for _, row in corpus.iterrows():
        pieces.append(
            "|".join(
                [
                    str(row.get("doc_id") or ""),
                    str(row.get("source_table") or ""),
                    str(row.get("source_id") or ""),
                    str(row.get("domain") or ""),
                    str(row.get("region_sido") or ""),
                    str(row.get("region_sigungu") or ""),
                    str(row.get("policy_id") or ""),
                    str(row.get("last_mod_date") or ""),
                    str(row.get("collected_at") or ""),
                    str(row.get("policy_name") or ""),
                    str(row.get("title") or ""),
                ]
            )
        )
    raw = f"{EMBEDDING_MODEL_NAME}\n" + "\n".join(pieces)
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]


def _load_or_create_embeddings(model, corpus: pd.DataFrame) -> np.ndarray:
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = INDEX_DIR / f"search_embeddings_{_corpus_signature(corpus)}.npy"
    if cache_path.exists():
        return np.load(cache_path).astype("float32")

    texts = _embedding_texts(corpus).tolist()
    embeddings = model.encode(
        texts,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
    ).astype("float32")
    np.save(cache_path, embeddings)
    return embeddings


def _faiss_rank(
    user_input: str,
    condition: dict[str, Any],
    corpus: pd.DataFrame,
    candidates: pd.DataFrame,
    top_k: int,
) -> pd.DataFrame:
    if corpus.empty or candidates.empty:
        raise RuntimeError("No candidates available for FAISS search.")

    allowed = set(candidates["_source_index"].astype(int).tolist()) if "_source_index" in candidates.columns else set()
    search_corpus = corpus
    if allowed and "_source_index" in corpus.columns:
        search_corpus = corpus[corpus["_source_index"].astype(int).isin(allowed)].copy()
    if search_corpus.empty:
        search_corpus = candidates.copy()

    faiss, model = _load_faiss_resources()
    doc_embeddings = _load_or_create_embeddings(model, search_corpus)
    faiss.normalize_L2(doc_embeddings)

    index = faiss.IndexFlatIP(doc_embeddings.shape[1])
    index.add(doc_embeddings)

    query_text = _embedding_query(user_input, condition)
    query_embedding = model.encode(
        [query_text],
        show_progress_bar=False,
        convert_to_numpy=True,
    ).astype("float32")
    faiss.normalize_L2(query_embedding)

    search_k = index.ntotal
    scores, indices = index.search(query_embedding, search_k)

    rows = []
    for score, search_index in zip(scores[0], indices[0]):
        if int(search_index) < 0:
            continue
        row = search_corpus.iloc[[int(search_index)]].copy()
        if allowed and "_source_index" in row.columns and int(row["_source_index"].iloc[0]) not in allowed:
            continue
        row["score"] = float(score)
        rows.append(row)
        if len(rows) >= top_k:
            break

    if not rows:
        raise RuntimeError("FAISS search returned no rows after filtering.")
    ranked = pd.concat(rows, ignore_index=True)
    ranked["match_method"] = "FAISS 임베딩"
    return ranked


def _keyword_rank(user_input: str, condition: dict[str, Any], candidates: pd.DataFrame, top_k: int) -> pd.DataFrame:
    query_terms = set(re.findall(r"[가-힣A-Za-z0-9]{2,}", user_input or ""))
    for key in [
        "region", "region_sido", "region_sigungu", "employment_status",
        "interest", "housing_status", "status", "income", "gender",
    ]:
        value = condition.get(key)
        if value:
            query_terms.add(str(value))

    text = _text_series(
        candidates,
        [
            "search_text", "title", "summary", "region_name", "region_sido", "region_sigungu", "target", "domain", "source_table",
            "policy_name", "description", "keyword", "category_main", "category_sub", "support_content",
        ],
    )

    if condition.get("housing_status") == "월세":
        rent_pattern = "월세|전월세|임대료|보증금|주택임차"
        rent_mask = text.str.contains(rent_pattern, case=False, na=False, regex=True)
        if rent_mask.sum() > 0:
            candidates = candidates[rent_mask].copy()
            text = text[rent_mask]
    elif condition.get("housing_status") == "전세":
        lease_pattern = "전세|전월세|전세금|전세자금"
        lease_mask = text.str.contains(lease_pattern, case=False, na=False, regex=True)
        if lease_mask.sum() > 0:
            candidates = candidates[lease_mask].copy()
            text = text[lease_mask]

    ranked = candidates.copy()
    scores = []
    interest = condition.get("interest")
    interest_terms = INTEREST_TERMS.get(interest, [])

    for idx, value in text.items():
        haystack = value.lower()
        row = candidates.loc[idx]
        category_text = " ".join(
            str(row.get(col) or "")
            for col in ["domain", "source_table", "category_main", "category_sub", "keyword", "policy_name", "title"]
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
            elif condition.get("housing_status") == "전세":
                lease_terms = ["전세", "전월세", "전세금", "전세자금", "보증금", "주택임차"]
                has_lease_signal = any(term in haystack or term in category_text for term in lease_terms)
                score += 8.0 if has_lease_signal else -10.0

        if (condition.get("region") or condition.get("region_sido") or condition.get("region_sigungu")) and _condition_region_mask(pd.DataFrame([row]), condition).iloc[0]:
            score += 2.0
        scores.append(score)

    ranked["score"] = scores
    ranked["match_method"] = "키워드/필터"
    ranked["_region_priority"] = _condition_region_priority(ranked, condition)
    sort_id = "doc_id" if "doc_id" in ranked.columns else "policy_id"
    return ranked.sort_values(
        ["_region_priority", "score", sort_id],
        ascending=[False, False, True],
    ).head(top_k).reset_index(drop=True)


def _apply_region_order(ranked: pd.DataFrame, condition: dict[str, Any], top_k: int) -> pd.DataFrame:
    if ranked.empty:
        return ranked
    if not (condition.get("region") or condition.get("region_sido") or condition.get("region_sigungu")):
        return ranked.head(top_k).reset_index(drop=True)

    ordered = ranked.copy()
    ordered["_region_priority"] = _condition_region_priority(ordered, condition)
    sort_columns = ["_region_priority"]
    ascending = [False]
    if "score" in ordered.columns:
        sort_columns.append("score")
        ascending.append(False)
    sort_id = "doc_id" if "doc_id" in ordered.columns else "policy_id"
    if sort_id in ordered.columns:
        sort_columns.append(sort_id)
        ascending.append(True)
    ordered = ordered.sort_values(sort_columns, ascending=ascending)
    dedupe_columns = [col for col in ["domain", "policy_name", "region_name"] if col in ordered.columns]
    if dedupe_columns:
        ordered = ordered.drop_duplicates(subset=dedupe_columns, keep="first")
    return ordered.head(top_k).reset_index(drop=True)


def _rank_with_fallback(
    user_input: str,
    condition: dict[str, Any],
    corpus: pd.DataFrame,
    candidates: pd.DataFrame,
    top_k: int,
) -> pd.DataFrame:
    try:
        return _apply_region_order(_faiss_rank(user_input, condition, corpus, candidates, top_k), condition, top_k)
    except Exception as exc:
        print(f"[ai.retriever] FAISS unavailable, using keyword fallback: {exc}")
        return _apply_region_order(_keyword_rank(user_input, condition, candidates, top_k), condition, top_k)


def _rank_by_domain_quotas(
    user_input: str,
    condition: dict[str, Any],
    corpus: pd.DataFrame,
    candidates: pd.DataFrame,
    top_k: int,
) -> pd.DataFrame | None:
    if "domain" not in candidates.columns:
        return None

    quotas = DOMAIN_QUOTAS.get(condition.get("interest"))
    if not quotas and condition.get("housing_status"):
        quotas = DOMAIN_QUOTAS.get("주거")
    if not quotas:
        return None
    if "대출" in (user_input or "") and "loan" in quotas:
        quotas = {**quotas, "loan": max(quotas["loan"], min(3, top_k))}
        quotas = {"loan": quotas["loan"], **{domain: quota for domain, quota in quotas.items() if domain != "loan"}}

    ranked_parts = []
    for domain, quota in quotas.items():
        domain_candidates = candidates[candidates["domain"] == domain]
        if domain_candidates.empty:
            continue
        domain_corpus = corpus[corpus["domain"] == domain] if "domain" in corpus.columns else corpus
        ranked_parts.append(
            _rank_with_fallback(user_input, condition, domain_corpus, domain_candidates, min(quota, top_k))
        )

    if not ranked_parts:
        return None

    merged = pd.concat(ranked_parts, ignore_index=True)
    id_col = "doc_id" if "doc_id" in merged.columns else "policy_id"
    merged = merged.drop_duplicates(subset=[id_col], keep="first")

    if len(merged) < top_k:
        fill = _rank_with_fallback(user_input, condition, corpus, candidates, top_k)
        merged = pd.concat([merged, fill], ignore_index=True).drop_duplicates(subset=[id_col], keep="first")

    return _apply_region_order(merged, condition, top_k)


def retrieve_top_k(user_input: str, user_condition: dict, df: pd.DataFrame, top_k: int = 5) -> list[dict]:
    corpus = _filter_active_policies(df.copy()).reset_index(drop=False).rename(columns={"index": "_source_index"})
    candidates = _apply_soft_filters(df, user_condition)
    if candidates.empty:
        return []

    ranked = _rank_by_domain_quotas(user_input, user_condition, corpus, candidates, top_k)
    if ranked is None:
        if "domain" in candidates.columns and not _domain_hint(user_condition):
            ranked = _apply_region_order(_keyword_rank(user_input, user_condition, candidates, top_k), user_condition, top_k)
        else:
            ranked = _rank_with_fallback(user_input, user_condition, corpus, candidates, top_k)

    return ranked.drop(columns=["_source_index", "_region_priority"], errors="ignore").head(top_k).to_dict("records")
