from __future__ import annotations

import json
import re
import sqlite3
from typing import Any

from ai.db_loader import find_db_path
from ai.llm_client import LLMUnavailable, create_chat_response, llm_enabled


SOURCE_KEY_COLUMNS = {
    "policies_processed": "policy_id",
    "hrd_trainings": "id",
    "kstartup_notices": "pbanc_sn",
    "smallloan_youth": "id",
    "myhome_notices": "id",
    "rental_houses": "id",
}

SOURCE_LABELS = {
    "policies_processed": "온통청년 정책",
    "hrd_trainings": "HRD-Net 훈련과정",
    "kstartup_notices": "K-Startup 창업지원공고",
    "smallloan_youth": "청년 금융상품",
    "myhome_notices": "마이홈 임대공고",
    "rental_houses": "청년 임대주택 단지",
}

DOMAIN_LABELS = {
    "policy": "일반 정책",
    "policy_housing": "주거 정책",
    "policy_finance": "금융/복지 정책",
    "policy_training": "교육/훈련 정책",
    "policy_job": "취업 정책",
    "policy_startup": "창업 정책",
    "housing_notice": "임대 공고",
    "rental_house": "임대주택 단지",
    "loan": "청년 금융상품",
    "training": "직업훈련",
    "startup": "창업 공고",
}

FIELD_LABELS = {
    # Common policy table
    "policy_name": "정책명",
    "description": "개요",
    "support_content": "지원 내용",
    "apply_period": "신청 기간",
    "apply_period_type": "신청 기간 유형",
    "apply_method": "신청 방법",
    "selection_method": "선정 방법",
    "application_url": "신청 URL",
    "submit_docs": "제출 서류",
    "apply_condition": "신청 자격",
    "excluded_target": "제외 대상",
    "institution": "주관 기관",
    "oper_inst": "운영 기관",
    "income_type": "소득 조건",
    "income_etc": "소득 기타 조건",
    "min_age": "최소 연령",
    "max_age": "최대 연령",
    "job_cd": "취업 상태 조건",
    "school_cd": "학력/상태 조건",
    "region_name": "지역",
    "ref_url1": "참고 링크",
    "ref_url2": "참고 링크 2",
    # Training
    "title": "과정명",
    "sub_title": "훈련기관",
    "address": "주소",
    "tel_no": "전화번호",
    "course_man": "훈련비",
    "real_man": "실제 훈련비",
    "train_target": "훈련 대상",
    "tra_start_date": "훈련 시작일",
    "tra_end_date": "훈련 종료일",
    "title_link": "상세 링크",
    "yard_man": "정원",
    "satisfaction_score": "만족도",
    # Startup
    "notice_name": "공고명",
    "category": "분야",
    "organization": "기관",
    "target": "대상",
    "target_detail": "상세 대상",
    "business_age": "업력",
    "target_age": "연령",
    "apply_start_date": "신청 시작일",
    "apply_end_date": "신청 종료일",
    "apply_url": "신청 URL",
    "detail_url": "상세 URL",
    "contact": "문의처",
    # Loan
    "finPrdNm": "상품명",
    "lnLmt": "대출 한도",
    "irt": "금리",
    "irtCtg": "금리 유형",
    "maxTotLnTrm": "최대 대출 기간",
    "rdptMthd": "상환 방법",
    "usge": "용도",
    "trgt": "대상",
    "ofrInstNm": "제공 기관",
    "suprTgtDtlCond": "상세 조건",
    "age": "연령",
    "incm": "소득",
    "crdtSc": "신용 조건",
    "grnInst": "보증 기관",
    "jnMthd": "가입 방법",
    "rfrcCnpl": "참고 문의처",
    "cnpl": "문의처",
    "rltSite": "관련 사이트",
    "mgmDln": "마감",
    # Housing
    "supply_inst": "공급 기관",
    "house_type": "주택 유형",
    "supply_type": "공급 유형",
    "status": "공고 상태",
    "house_name": "주택명",
    "supply_units": "공급 세대",
    "deposit": "보증금",
    "monthly_rent": "월 임대료",
    "begin_date": "신청 시작일",
    "end_date": "신청 종료일",
    "post_date": "공고일",
    "myhome_url": "마이홈 URL",
    "youth_keyword": "청년 키워드",
    # Rental house
    "insttNm": "기관",
    "brtcNm": "시도",
    "signguNm": "시군구",
    "hsmpNm": "단지명",
    "rnAdres": "도로명 주소",
    "hshldCo": "세대 수",
    "suplyTyNm": "공급 유형",
    "styleNm": "주택형",
    "suplyPrvuseAr": "전용면적",
    "suplyCmnuseAr": "공용면적",
    "houseTyNm": "주택 유형",
    "heatMthdDetailNm": "난방 방식",
    "buldStleNm": "건물 형태",
    "elvtrInstlAtNm": "승강기",
    "parkngCo": "주차 대수",
    "bassRentGtn": "기본 보증금",
    "bassMtRntchrg": "기본 월 임대료",
    "bassCnvrsGtnLmt": "전환 보증금 한도",
}

INTENT_KEYWORDS = {
    "docs": ["서류", "준비", "준비물", "제출", "필요한", "필요"],
    "eligibility": ["자격", "조건", "대상", "가능", "받을 수", "해당", "지원대상"],
    "apply": ["신청", "방법", "절차", "어디", "링크", "접수", "가입"],
    "period": ["기간", "마감", "언제", "날짜", "시작", "종료"],
    "benefit": ["혜택", "지원", "내용", "금액", "얼마", "한도", "금리", "월세", "보증금"],
    "contact": ["문의", "연락", "전화", "기관", "담당"],
}


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


class PolicyChatAgent:
    def __init__(self):
        self.db_path = find_db_path()
        self._context_cache: dict[str, dict[str, Any]] = {}

    def status(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "db_path": str(self.db_path),
            "llm_enabled": llm_enabled(),
            "supported_sources": list(SOURCE_KEY_COLUMNS),
        }

    def answer(
        self,
        *,
        policy: dict[str, Any],
        user_context: dict[str, Any] | None = None,
        messages: list[dict[str, str]],
    ) -> dict[str, Any]:
        normalized_messages = _normalize_messages(messages)
        question = _latest_user_message(normalized_messages)
        policy_context = self._load_policy_context(policy)
        suggested_questions = self._suggest_questions(policy_context)

        if not question:
            return {
                "answer": "궁금한 점을 한 문장으로 물어봐 주세요. 예: 이 정책 신청할 때 필요한 서류가 뭐야?",
                "suggested_questions": suggested_questions,
                "policy_context": policy_context,
            }

        try:
            answer = self._llm_answer(
                policy_context=policy_context,
                user_context=user_context or {},
                messages=normalized_messages,
            )
        except Exception as exc:
            if not isinstance(exc, LLMUnavailable):
                print(f"[ai.policy_chat_agent] LLM chat failed, using rule fallback: {exc}")
            answer = self._rule_answer(question, policy_context, user_context or {})

        return {
            "answer": answer,
            "suggested_questions": suggested_questions,
            "policy_context": {
                "doc_id": policy_context.get("doc_id"),
                "source_table": policy_context.get("source_table"),
                "source_id": policy_context.get("source_id"),
                "title": policy_context.get("title"),
                "domain": policy_context.get("domain"),
                "source_label": policy_context.get("source_label"),
            },
        }

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _policy_cache_key(self, policy: dict[str, Any]) -> str:
        doc_id = _clean(policy.get("doc_id") or policy.get("policy_id"))
        if doc_id:
            return f"doc:{doc_id}"
        source_table = _clean(policy.get("source_table"))
        source_id = _clean(policy.get("source_id"))
        if source_table and source_id:
            return f"source:{source_table}:{source_id}"
        title = _clean(policy.get("policy_name") or policy.get("title"))
        return f"title:{title}" if title else ""

    def _context_cache_key(self, policy_context: dict[str, Any]) -> str:
        doc_id = _clean(policy_context.get("doc_id"))
        if doc_id:
            return f"doc:{doc_id}"
        source_table = _clean(policy_context.get("source_table"))
        source_id = _clean(policy_context.get("source_id"))
        if source_table and source_id:
            return f"source:{source_table}:{source_id}"
        title = _clean(policy_context.get("title"))
        return f"title:{title}" if title else ""

    def _load_policy_context(self, policy: dict[str, Any]) -> dict[str, Any]:
        requested_cache_key = self._policy_cache_key(policy)
        if requested_cache_key and requested_cache_key in self._context_cache:
            return self._context_cache[requested_cache_key]

        with self._connect() as conn:
            search_doc = self._find_search_document(conn, policy)
            source_table = _clean(search_doc.get("source_table") if search_doc else policy.get("source_table"))
            source_id = _clean(search_doc.get("source_id") if search_doc else policy.get("source_id"))
            original = self._find_original_row(conn, source_table, source_id, search_doc)

        title = (
            _clean(search_doc.get("title") if search_doc else "")
            or _clean(policy.get("policy_name"))
            or _clean(policy.get("title"))
            or self._title_from_original(source_table, original)
            or "정책명 확인 필요"
        )
        domain = _clean(search_doc.get("domain") if search_doc else policy.get("domain"))
        context = {
            "doc_id": _clean(search_doc.get("doc_id") if search_doc else policy.get("doc_id")),
            "source_table": source_table,
            "source_id": source_id,
            "domain": domain,
            "domain_label": DOMAIN_LABELS.get(domain, domain or "분야 확인"),
            "source_label": SOURCE_LABELS.get(source_table, source_table or "출처 확인"),
            "title": title,
            "summary": _clean(search_doc.get("summary") if search_doc else policy.get("summary") or policy.get("support_content")),
            "region_name": _clean(search_doc.get("region_name") if search_doc else policy.get("region_name")),
            "region_sido": _clean(search_doc.get("region_sido") if search_doc else policy.get("region_sido")),
            "region_sigungu": _clean(search_doc.get("region_sigungu") if search_doc else policy.get("region_sigungu")),
            "target": _clean(search_doc.get("target") if search_doc else policy.get("target")),
            "status": _clean(search_doc.get("status") if search_doc else policy.get("status")),
            "employment_status": _clean(search_doc.get("employment_status") if search_doc else policy.get("employment_status")),
            "min_age": _clean(search_doc.get("min_age") if search_doc else policy.get("min_age")),
            "max_age": _clean(search_doc.get("max_age") if search_doc else policy.get("max_age")),
            "period": self._period_from_search_doc(search_doc),
            "url": _clean(search_doc.get("url") if search_doc else policy.get("application_url") or policy.get("url")),
            "search_document": dict(search_doc) if search_doc else {},
            "original": original,
            "facts": self._facts_for_source(source_table, search_doc, original),
        }
        context["policy_profile"] = self._build_user_summary(context)

        for cache_key in _dedupe([requested_cache_key, self._context_cache_key(context)]):
            self._context_cache[cache_key] = context
        return context

    def _find_search_document(self, conn: sqlite3.Connection, policy: dict[str, Any]) -> dict[str, Any] | None:
        cursor = conn.cursor()
        doc_id = _clean(policy.get("doc_id") or policy.get("policy_id"))
        if ":" in doc_id:
            cursor.execute("SELECT * FROM search_documents WHERE doc_id = ?", (doc_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)

        source_table = _clean(policy.get("source_table"))
        source_id = _clean(policy.get("source_id"))
        if source_table and source_id:
            cursor.execute(
                "SELECT * FROM search_documents WHERE source_table = ? AND source_id = ? LIMIT 1",
                (source_table, source_id),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)

        title = _clean(policy.get("policy_name") or policy.get("title"))
        if title:
            cursor.execute(
                "SELECT * FROM search_documents WHERE title = ? ORDER BY doc_id LIMIT 1",
                (title,),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            cursor.execute(
                "SELECT * FROM search_documents WHERE title LIKE ? ORDER BY doc_id LIMIT 1",
                (f"%{title[:24]}%",),
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def _find_original_row(
        self,
        conn: sqlite3.Connection,
        source_table: str,
        source_id: str,
        search_doc: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if source_table not in SOURCE_KEY_COLUMNS:
            return {}
        key_column = SOURCE_KEY_COLUMNS[source_table]
        cursor = conn.cursor()
        candidates = [source_id, _clean(search_doc.get("raw_ref") if search_doc else "")]
        for candidate in candidates:
            if not candidate:
                continue
            cursor.execute(f"SELECT * FROM {source_table} WHERE {key_column} = ? LIMIT 1", (candidate,))
            row = cursor.fetchone()
            if row:
                return dict(row)

        if source_table == "hrd_trainings" and search_doc:
            raw_ref = _clean(search_doc.get("raw_ref"))
            if raw_ref:
                cursor.execute("SELECT * FROM hrd_trainings WHERE trpr_id = ? LIMIT 1", (raw_ref,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
        if source_table == "smallloan_youth" and search_doc:
            raw_ref = _clean(search_doc.get("raw_ref"))
            if raw_ref:
                cursor.execute("SELECT * FROM smallloan_youth WHERE snq = ? LIMIT 1", (raw_ref,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
        if source_table == "myhome_notices" and search_doc:
            raw_ref = _clean(search_doc.get("raw_ref"))
            if raw_ref:
                cursor.execute("SELECT * FROM myhome_notices WHERE notice_id = ? LIMIT 1", (raw_ref,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
        if source_table == "rental_houses" and search_doc:
            raw_ref = _clean(search_doc.get("raw_ref"))
            if raw_ref:
                cursor.execute("SELECT * FROM rental_houses WHERE hsmpSn = ? LIMIT 1", (raw_ref,))
                row = cursor.fetchone()
                if row:
                    return dict(row)
        return {}

    def _period_from_search_doc(self, search_doc: dict[str, Any] | None) -> str:
        if not search_doc:
            return ""
        start = _date(search_doc.get("apply_start_date"))
        end = _date(search_doc.get("apply_end_date"))
        if start and end:
            return f"{start} ~ {end}"
        return start or end

    def _title_from_original(self, source_table: str, original: dict[str, Any]) -> str:
        title_keys = {
            "policies_processed": "policy_name",
            "hrd_trainings": "title",
            "kstartup_notices": "notice_name",
            "smallloan_youth": "finPrdNm",
            "myhome_notices": "notice_name",
            "rental_houses": "hsmpNm",
        }
        return _clean(original.get(title_keys.get(source_table, "")))

    def _facts_for_source(
        self,
        source_table: str,
        search_doc: dict[str, Any] | None,
        original: dict[str, Any],
    ) -> dict[str, list[str]]:
        facts = {
            "overview": [],
            "eligibility": [],
            "benefit": [],
            "period": [],
            "apply": [],
            "docs": [],
            "contact": [],
        }
        if search_doc:
            _append(facts["overview"], "요약", search_doc.get("summary"))
            _append(facts["overview"], "지역", search_doc.get("region_name"))
            _append(facts["eligibility"], "대상", search_doc.get("target"))
            if self._period_from_search_doc(search_doc):
                facts["period"].append(f"- 신청/운영 기간: {self._period_from_search_doc(search_doc)}")
            _append(facts["apply"], "링크", search_doc.get("url"))

        if source_table == "policies_processed":
            _append(facts["benefit"], "지원 내용", original.get("support_content"))
            _append(facts["eligibility"], "신청 자격", original.get("apply_condition"))
            _append(facts["eligibility"], "취업 상태", original.get("job_cd"))
            _append(facts["eligibility"], "학력/상태", original.get("school_cd"))
            _append(facts["eligibility"], "소득", original.get("income_etc") or original.get("income_type"))
            _append(facts["apply"], "신청 방법", original.get("apply_method"))
            _append(facts["apply"], "선정 방법", original.get("selection_method"))
            _append(facts["apply"], "신청 URL", original.get("application_url") or original.get("ref_url1") or original.get("ref_url2"))
            _append(facts["docs"], "제출 서류", original.get("submit_docs"))
            _append(facts["contact"], "주관 기관", original.get("institution"))
            _append(facts["contact"], "운영 기관", original.get("oper_inst"))
            _append(facts["period"], "신청 기간", original.get("apply_period") or original.get("apply_period_type"))
        elif source_table == "hrd_trainings":
            _append(facts["benefit"], "훈련 과정", original.get("title"))
            _append(facts["benefit"], "훈련 기관", original.get("sub_title"))
            _append(facts["benefit"], "훈련비", original.get("real_man") or original.get("course_man"))
            _append(facts["benefit"], "정원", original.get("yard_man"))
            _append(facts["eligibility"], "훈련 대상", original.get("train_target"))
            _append_date(facts["period"], "훈련 시작일", original.get("tra_start_date"))
            _append_date(facts["period"], "훈련 종료일", original.get("tra_end_date"))
            _append(facts["apply"], "상세/신청 링크", original.get("title_link"))
            _append(facts["docs"], "준비할 것", "국민내일배움카드 대상 여부와 본인 인증 정보를 먼저 확인하세요.")
            _append(facts["contact"], "전화번호", original.get("tel_no"))
            _append(facts["contact"], "주소", original.get("address"))
        elif source_table == "kstartup_notices":
            _append(facts["benefit"], "지원 내용", original.get("description"))
            _append(facts["eligibility"], "대상", original.get("target"))
            _append(facts["eligibility"], "상세 대상", original.get("target_detail"))
            _append(facts["eligibility"], "업력", original.get("business_age"))
            _append(facts["eligibility"], "연령", original.get("target_age"))
            _append_date(facts["period"], "신청 시작일", original.get("apply_start_date"))
            _append_date(facts["period"], "신청 종료일", original.get("apply_end_date"))
            _append(facts["apply"], "신청 URL", original.get("apply_url"))
            _append(facts["apply"], "상세 URL", original.get("detail_url"))
            _append(facts["docs"], "제출 서류", self._raw_json_value(original, "sbmsn_file") or "공고문에서 사업계획서, 증빙서류 등 제출 서류를 확인해야 합니다.")
            _append(facts["contact"], "기관", original.get("organization"))
            _append(facts["contact"], "문의처", original.get("contact"))
        elif source_table == "smallloan_youth":
            _append(facts["benefit"], "대출 한도", original.get("lnLmt"))
            _append(facts["benefit"], "금리", original.get("irt"))
            _append(facts["benefit"], "상환 방법", original.get("rdptMthd"))
            _append(facts["benefit"], "최대 기간", original.get("maxTotLnTrm"))
            _append(facts["eligibility"], "대상", original.get("trgt"))
            _append(facts["eligibility"], "상세 조건", original.get("suprTgtDtlCond"))
            _append(facts["eligibility"], "연령", original.get("age"))
            _append(facts["eligibility"], "소득", original.get("incm"))
            _append(facts["eligibility"], "신용 조건", original.get("crdtSc"))
            _append(facts["period"], "마감", original.get("mgmDln"))
            _append(facts["apply"], "가입 방법", original.get("jnMthd"))
            _append(facts["apply"], "관련 사이트", original.get("rltSite"))
            _append(facts["docs"], "준비할 것", "신분증, 소득 증빙, 무주택/세대주 관련 증빙, 임대차계약 관련 서류는 취급 기관에서 확인하세요.")
            _append(facts["contact"], "제공 기관", original.get("ofrInstNm"))
            _append(facts["contact"], "문의처", original.get("cnpl") or original.get("rfrcCnpl"))
        elif source_table == "myhome_notices":
            _append(facts["benefit"], "공급 유형", original.get("supply_type"))
            _append(facts["benefit"], "주택명", original.get("house_name"))
            _append(facts["benefit"], "공급 세대", original.get("supply_units"))
            _append_money(facts["benefit"], "보증금", original.get("deposit"))
            _append_money(facts["benefit"], "월 임대료", original.get("monthly_rent"))
            _append(facts["eligibility"], "청년 관련 키워드", original.get("youth_keyword"))
            _append_date(facts["period"], "신청 시작일", original.get("begin_date"))
            _append_date(facts["period"], "신청 종료일", original.get("end_date"))
            _append(facts["apply"], "상세 URL", original.get("detail_url") or original.get("myhome_url"))
            _append(facts["docs"], "준비할 것", "공고문에서 주민등록등본, 가족관계증명서, 소득/자산 증빙, 임대주택 신청서류를 확인하세요.")
            _append(facts["contact"], "공급 기관", original.get("supply_inst"))
        elif source_table == "rental_houses":
            _append(facts["benefit"], "공급 유형", original.get("suplyTyNm"))
            _append(facts["benefit"], "주택 유형", original.get("houseTyNm"))
            _append(facts["benefit"], "주택형", original.get("styleNm"))
            _append(facts["benefit"], "전용면적", original.get("suplyPrvuseAr"))
            _append_money(facts["benefit"], "기본 보증금", original.get("bassRentGtn"))
            _append_money(facts["benefit"], "기본 월 임대료", original.get("bassMtRntchrg"))
            _append(facts["benefit"], "세대 수", original.get("hshldCo"))
            _append(facts["eligibility"], "청년 관련 키워드", original.get("youth_filter_keyword"))
            _append(facts["apply"], "주소", original.get("rnAdres"))
            _append(facts["docs"], "준비할 것", "이 항목은 단지 정보라 실제 모집공고에서 신청 기간, 자격, 제출 서류를 별도로 확인해야 합니다.")
            _append(facts["contact"], "기관", original.get("insttNm"))

        return {key: values for key, values in facts.items() if values}

    def _raw_json_value(self, original: dict[str, Any], key: str) -> str:
        raw_json = _clean(original.get("raw_json"))
        if not raw_json:
            return ""
        try:
            data = json.loads(raw_json)
        except json.JSONDecodeError:
            return ""
        return _clean(data.get(key))

    def _suggest_questions(self, policy_context: dict[str, Any]) -> list[str]:
        source = policy_context.get("source_table")
        common = ["이 정책에서 필요한 건 뭐야?", "내가 신청 가능할까?", "신청은 어떻게 해?"]
        if source == "smallloan_youth":
            return ["대출 조건이 뭐야?", "금리랑 한도 알려줘", "신청할 때 뭘 준비해야 해?"]
        if source in {"myhome_notices", "rental_houses"}:
            return ["보증금이랑 월세가 얼마야?", "입주 신청에 필요한 서류는?", "신청 기간이 언제야?"]
        if source == "hrd_trainings":
            return ["훈련 기간이 언제야?", "수강하려면 뭘 준비해야 해?", "훈련기관 연락처 알려줘"]
        if source == "kstartup_notices":
            return ["창업 지원 대상이 누구야?", "신청 마감이 언제야?", "사업계획서가 필요할까?"]
        return common

    def _llm_answer(
        self,
        *,
        policy_context: dict[str, Any],
        user_context: dict[str, Any],
        messages: list[dict[str, str]],
    ) -> str:
        policy_profile = policy_context.get("policy_profile") or self._build_user_summary(policy_context)
        personal_fit = self._build_personal_fit(policy_context, user_context, policy_profile)
        apply_detail = self._build_apply_detail(policy_context, policy_profile)
        compact_context = {
            "doc_id": policy_context.get("doc_id"),
            "source_table": policy_context.get("source_table"),
            "source_id": policy_context.get("source_id"),
            "title": policy_context.get("title"),
            "domain": policy_context.get("domain"),
            "source_label": policy_context.get("source_label"),
            "region_name": policy_context.get("region_name"),
            "region_sido": policy_context.get("region_sido"),
            "region_sigungu": policy_context.get("region_sigungu"),
            "period": policy_context.get("period"),
            "url": policy_context.get("url"),
            "policy_profile": policy_profile,
            "apply_detail": apply_detail,
            "user_condition_check": personal_fit,
            "facts": policy_context.get("facts", {}),
        }
        system_prompt = (
            "너는 한국 청년 정책 상담 챗봇이다. 사용자는 이미 특정 정책 카드에서 질문하고 있다. "
            "반드시 제공된 DB 정책 정보 안에서만 답하고, 없는 정보는 'DB에는 없다'고 말한 뒤 확인 경로를 알려라. "
            "정책 프로필은 DB 원본을 미리 구조화한 내용이므로 이 프로필을 우선 근거로 사용한다. "
            "사용자 조건이 있으면 정책 조건과 비교해서 맞는 부분, 애매한 부분, 추가 확인이 필요한 부분을 먼저 설명한다. "
            "대화형으로 답하되 정책 원문을 길게 복사하지 말고, 사용자가 이해하기 쉬운 짧은 항목으로 재구성한다. "
            "조건이나 필요한 것을 묻는 질문에는 반드시 다음 형식을 우선 사용한다: "
            "내 조건 기준 체크, 1. 필요한 서류, 2. 조건, 3. 지원 받을 수 있는 내용(금액), 4. 신청 방법/기간. "
            "신청 방법을 묻는 질문에는 apply_detail의 신청 경로, 기간, 링크, 준비물, 문의처를 우선 확인해서 리스트로 정리한다. "
            "각 항목은 '- 주민등록등본'처럼 짧은 bullet로 쓰고, DB에 없는 내용은 추정하지 말고 확인 필요라고 쓴다. "
            "마지막에는 사용자가 이어서 물어볼 만한 한 가지 확인 질문을 던진다."
        )
        context_message = {
            "role": "user",
            "content": (
                "선택된 정책 DB 구조화 프로필:\n"
                f"{json.dumps(compact_context, ensure_ascii=False)[:12000]}\n\n"
                "사용자 조건:\n"
                f"{json.dumps(user_context, ensure_ascii=False)}"
            ),
        }
        return create_chat_response(
            system_prompt=system_prompt,
            messages=[context_message, *messages],
            max_output_tokens=900,
        )

    def _rule_answer(self, question: str, policy_context: dict[str, Any], user_context: dict[str, Any]) -> str:
        intents = self._detect_intents(question)
        if not intents:
            intents = ["overview", "eligibility", "apply"]

        title = policy_context.get("title", "이 정책")
        source_label = policy_context.get("source_label", "정책 DB")
        if self._wants_apply_detail(question, intents):
            return self._apply_detail_answer(title, policy_context, source_label, intents)
        if self._wants_structured_summary(question, intents):
            return self._structured_answer(title, policy_context, source_label, intents, user_context)

        facts = policy_context.get("facts", {})
        lines = [f"**{title}** 기준으로 확인해봤어요."]
        summary = policy_context.get("policy_profile") or self._build_user_summary(policy_context)
        personal_fit = self._build_personal_fit(policy_context, user_context, summary)
        if personal_fit:
            lines.append("\n내 조건 기준 체크")
            for item in personal_fit[:5]:
                lines.append(f"- {item}")

        for intent in intents[:3]:
            section = self._section_for_intent(intent, facts, policy_context)
            if section:
                lines.extend(section)

        if not any(line.startswith("- ") for line in lines):
            lines.append("- DB에 세부 정보가 부족해서, 상세 공고 링크나 담당 기관 확인이 필요합니다.")

        url = policy_context.get("url")
        if url and not any("링크" in line or "URL" in line for line in lines):
            lines.append(f"- 확인 링크: {url}")

        follow_up = self._follow_up_question(intents[0], source_label)
        lines.append(f"\n{follow_up}")
        return "\n".join(lines)

    def _detect_intents(self, question: str) -> list[str]:
        intents = []
        for intent, keywords in INTENT_KEYWORDS.items():
            if any(keyword in question for keyword in keywords):
                intents.append(intent)
        if "필요" in question and "서류" not in question:
            intents = ["docs", "eligibility", "apply"]
        return intents

    def _wants_structured_summary(self, question: str, intents: list[str]) -> bool:
        broad_words = ["조건", "필요", "뭐야", "무엇", "정리", "알려", "받을 수", "신청 가능"]
        return (
            any(word in question for word in broad_words)
            or {"docs", "eligibility"}.issubset(set(intents))
            or question.strip() in {"이 정책 설명해줘", "자세히 알려줘"}
        )

    def _wants_apply_detail(self, question: str, intents: list[str]) -> bool:
        if "apply" not in intents:
            return False
        direct_apply_words = ["신청 방법", "신청은", "신청하려면", "어떻게", "절차", "접수", "어디", "링크", "가입 방법", "가입은"]
        if not any(word in question for word in direct_apply_words):
            return False
        if "신청 가능" in question or "가능할" in question:
            return False
        return True

    def _apply_detail_answer(
        self,
        title: str,
        policy_context: dict[str, Any],
        source_label: str,
        intents: list[str],
    ) -> str:
        summary = policy_context.get("policy_profile") or self._build_user_summary(policy_context)
        detail = self._build_apply_detail(policy_context, summary)
        sections = [
            ("1. 신청 경로/방법", detail["method"]),
            ("2. 신청 기간/마감", detail["period"]),
            ("3. 신청 링크/확인 페이지", detail["links"]),
            ("4. 준비물/서류", detail["docs"]),
            ("5. 문의처/담당 기관", detail["contact"]),
        ]

        lines = [f"**{title}** 신청 방법은 DB에서 찾은 내용 기준으로 이렇게 정리할 수 있어요."]
        for heading, items in sections:
            lines.append(f"\n{heading}")
            if items:
                for item in items[:6]:
                    lines.append(f"- {item}")
            else:
                lines.append("- DB에 직접 명시된 내용이 없어 공고 링크나 담당 기관 확인이 필요해요.")

        if detail["notes"]:
            lines.append("\n확인 필요")
            for item in detail["notes"][:4]:
                lines.append(f"- {item}")

        lines.append(f"\n{self._follow_up_question(intents[0] if intents else 'apply', source_label)}")
        return "\n".join(lines)

    def _structured_answer(
        self,
        title: str,
        policy_context: dict[str, Any],
        source_label: str,
        intents: list[str],
        user_context: dict[str, Any],
    ) -> str:
        summary = policy_context.get("policy_profile") or self._build_user_summary(policy_context)
        personal_fit = self._build_personal_fit(policy_context, user_context, summary)
        sections = [
            ("1. 필요한 서류", summary["docs"]),
            ("2. 조건", summary["eligibility"]),
            ("3. 지원 받을 수 있는 내용(금액)", summary["benefit"]),
            ("4. 신청 방법/기간", summary["apply"]),
        ]

        lines = [f"**{title}**은 내 조건과 연결해서 보면 이렇게 이해하기 쉬워요."]
        if personal_fit:
            lines.append("\n내 조건 기준 체크")
            for item in personal_fit[:6]:
                lines.append(f"- {item}")
        for heading, items in sections:
            lines.append(f"\n{heading}")
            for item in items[:6]:
                lines.append(f"- {item}")

        if summary["notice"]:
            lines.append("\n확인 필요")
            for item in summary["notice"][:3]:
                lines.append(f"- {item}")

        lines.append(f"\n{self._follow_up_question(intents[0] if intents else 'overview', source_label)}")
        return "\n".join(lines)

    def _build_user_summary(self, policy_context: dict[str, Any]) -> dict[str, list[str]]:
        source_table = policy_context.get("source_table")
        original = policy_context.get("original", {})
        facts = policy_context.get("facts", {})
        summary_text = " ".join(
            _strip_label(item)
            for item in [*facts.get("overview", []), *facts.get("benefit", []), *facts.get("eligibility", [])]
        )

        if source_table == "policies_processed":
            return self._summary_for_policy(original, facts, summary_text)
        if source_table == "smallloan_youth":
            return self._summary_for_loan(original)
        if source_table == "myhome_notices":
            return self._summary_for_myhome(original)
        if source_table == "rental_houses":
            return self._summary_for_rental_house(original)
        if source_table == "hrd_trainings":
            return self._summary_for_training(original)
        if source_table == "kstartup_notices":
            return self._summary_for_startup(original, summary_text)
        return self._summary_from_facts(facts)

    def _normalize_user_context(self, user_context: dict[str, Any]) -> dict[str, Any]:
        user_context = user_context or {}

        def first_text(*keys: str) -> str:
            for key in keys:
                value = _clean(user_context.get(key))
                if value:
                    return value
            return ""

        region = first_text("region", "address", "location")
        sido = first_text("region_sido", "sido", "ctpv")
        sigungu = first_text("region_sigungu", "sigungu", "sgg")
        if region and (not sido or not sigungu):
            tokens = [token for token in re.split(r"\s+", region) if token]
            if tokens and not sido:
                sido = tokens[0]
            if len(tokens) >= 2 and not sigungu:
                sigungu = tokens[1]

        return {
            "age": self._to_int(user_context.get("age")),
            "gender": first_text("gender"),
            "region": region,
            "region_sido": sido,
            "region_sigungu": sigungu,
            "status": first_text("status"),
            "employment_status": first_text("employment_status", "job_status", "work_status"),
            "interest": first_text("interest", "domain"),
            "income": first_text("income"),
            "housing_status": first_text("housing_status", "housing"),
        }

    def _to_int(self, value: Any) -> int | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            number = int(value)
            return number if number > 0 else None
        match = re.search(r"\d+", _clean(value).replace(",", ""))
        return int(match.group()) if match else None

    def _build_personal_fit(
        self,
        policy_context: dict[str, Any],
        user_context: dict[str, Any],
        summary: dict[str, list[str]],
    ) -> list[str]:
        user = self._normalize_user_context(user_context)
        if not any(user.get(key) for key in ["age", "gender", "region", "region_sido", "region_sigungu", "status", "employment_status", "interest", "income", "housing_status"]):
            return []
        checks = [
            self._age_fit_line(user, policy_context, summary),
            self._region_fit_line(user, policy_context),
            self._interest_fit_line(user, policy_context, summary),
            self._housing_fit_line(user, policy_context, summary),
            self._employment_fit_line(user, policy_context, summary),
            self._income_fit_line(user, summary),
        ]
        return _dedupe([line for line in checks if line])

    def _age_fit_line(
        self,
        user: dict[str, Any],
        policy_context: dict[str, Any],
        summary: dict[str, list[str]],
    ) -> str:
        age = user.get("age")
        if not age:
            return ""
        min_age, max_age = self._policy_age_bounds(policy_context, summary)
        if min_age or max_age:
            parts = []
            if min_age:
                parts.append(f"만 {min_age}세 이상")
            if max_age:
                parts.append(f"만 {max_age}세 이하")
            condition = ", ".join(parts)
            if min_age and age < min_age:
                return f"나이: {age}세라서 정책 연령 조건({condition})보다 어려요. 예외 가능 여부 확인이 필요해요."
            if max_age and age > max_age:
                return f"나이: {age}세라서 정책 연령 조건({condition})을 넘어요. 신청 가능성은 낮아 보여요."
            return f"나이: {age}세는 정책 연령 조건({condition})에 맞아요."

        profile_text = self._policy_profile_text(policy_context, summary)
        if "청년" in profile_text:
            return f"나이: {age}세로 청년 대상에는 들어갈 가능성이 있지만, DB에 정확한 연령 범위가 없어 공고 확인이 필요해요."
        return f"나이: {age}세를 입력했지만, 이 정책 프로필에는 연령 제한이 뚜렷하게 보이지 않아요."

    def _policy_age_bounds(
        self,
        policy_context: dict[str, Any],
        summary: dict[str, list[str]],
    ) -> tuple[int | None, int | None]:
        original = policy_context.get("original", {})
        min_age = self._to_int(policy_context.get("min_age") or original.get("min_age"))
        max_age = self._to_int(policy_context.get("max_age") or original.get("max_age"))
        text = self._policy_profile_text(policy_context, summary)

        range_matches = [
            re.search(
                r"(?:만\s*)?(\d{1,2})\s*세\s*(?:이상|부터)?\s*(?:~|-|부터)\s*(?:만\s*)?(\d{1,2})\s*세\s*(?:이하|까지)?",
                text,
            ),
            re.search(
                r"(?:만\s*)?(\d{1,2})\s*(?:~|-)\s*(?:만\s*)?(\d{1,2})\s*세",
                text,
            ),
        ]
        range_match = next((match for match in range_matches if match), None)
        if range_match:
            low = int(range_match.group(1))
            high = int(range_match.group(2))
            min_age = min_age or min(low, high)
            max_age = max_age or max(low, high)

        if min_age is None:
            match = re.search(r"(?:만\s*)?(\d{1,2})\s*세\s*(?:이상|초과|부터)", text)
            if match:
                min_age = int(match.group(1))
        if max_age is None:
            match = re.search(r"(?:만\s*)?(\d{1,2})\s*세\s*(?:이하|미만|까지)", text)
            if match:
                max_age = int(match.group(1))
        return min_age, max_age

    def _region_fit_line(self, user: dict[str, Any], policy_context: dict[str, Any]) -> str:
        user_sido = user.get("region_sido") or ""
        user_sigungu = user.get("region_sigungu") or ""
        user_region = self._format_region(user_sido, user_sigungu, user.get("region") or "")
        policy_sido, policy_sigungu, policy_region = self._policy_region(policy_context)
        policy_display = self._format_region(policy_sido, policy_sigungu, policy_region)

        if self._is_national_region(policy_display):
            return f"지역: {user_region or '입력 지역'} 기준으로 봐도, 이 정책은 전국/공통 성격이라 지역 불일치 위험이 낮아요."
        if not user_region:
            return f"지역: 이 정책은 {policy_display or '지역 조건 확인 필요'} 기준이라, 내 시도/시군구를 입력하면 더 정확히 판단할 수 있어요."
        if not policy_display:
            return f"지역: 내 지역은 {user_region}이고, 정책에는 별도 지역 제한이 뚜렷하지 않아요."
        if policy_sigungu:
            if user_sigungu and user_sigungu == policy_sigungu and (not policy_sido or not user_sido or user_sido == policy_sido):
                return f"지역: {user_region}와 정책 지역({policy_display})이 시군구까지 맞아요."
            return f"지역: 내 지역({user_region})과 정책 지역({policy_display})이 달라 신청 가능성 확인이 필요해요."
        if policy_sido:
            if user_sido and user_sido == policy_sido:
                return f"지역: {user_region}가 정책 지역({policy_display})의 시도 조건에 맞아요."
            return f"지역: 내 지역({user_region})과 정책 시도({policy_display})가 달라 우선순위는 낮아 보여요."
        if user_sido and user_sido in policy_display:
            return f"지역: {user_region}가 정책 지역({policy_display})에 포함될 가능성이 있어요."
        if user_sigungu and user_sigungu in policy_display:
            return f"지역: {user_region}가 정책 지역({policy_display})에 포함될 가능성이 있어요."
        return f"지역: 내 지역({user_region})과 정책 지역({policy_display})은 직접 일치하지 않아 확인이 필요해요."

    def _policy_region(self, policy_context: dict[str, Any]) -> tuple[str, str, str]:
        original = policy_context.get("original", {})
        search_doc = policy_context.get("search_document", {})
        sido = (
            _clean(policy_context.get("region_sido"))
            or _clean(search_doc.get("region_sido"))
            or _clean(original.get("brtcNm"))
        )
        sigungu = (
            _clean(policy_context.get("region_sigungu"))
            or _clean(search_doc.get("region_sigungu"))
            or _clean(original.get("signguNm"))
        )
        region = _clean(policy_context.get("region_name")) or " ".join(item for item in [sido, sigungu] if item)
        return sido, sigungu, region

    def _format_region(self, sido: str, sigungu: str, fallback: str = "") -> str:
        parts = [part for part in [sido, sigungu] if part]
        return " ".join(parts) or _clean(fallback)

    def _is_national_region(self, region_text: str) -> bool:
        text = _clean(region_text)
        if not text:
            return True
        return any(word in text for word in ["전국", "전체", "공통", "중앙부처", "대한민국"])

    def _interest_fit_line(
        self,
        user: dict[str, Any],
        policy_context: dict[str, Any],
        summary: dict[str, list[str]],
    ) -> str:
        interest = user.get("interest") or ""
        if not interest:
            return ""
        text = self._policy_profile_text(policy_context, summary)
        keywords = self._interest_keywords(interest)
        if interest in text or any(keyword in text for keyword in keywords):
            return f"관심분야: 입력한 '{interest}'와 이 정책 내용이 잘 연결돼요."
        return f"관심분야: 입력한 '{interest}'와 직접 연결되는 문구는 적어서, 정책 목적을 한 번 더 확인하는 게 좋아요."

    def _interest_keywords(self, interest: str) -> list[str]:
        keyword_map = {
            "주거": ["주거", "임대", "주택", "전세", "월세", "보증금", "housing", "rental"],
            "금융": ["금융", "대출", "금리", "저축", "자산", "loan", "finance"],
            "복지": ["복지", "지원금", "수당", "자립", "소득", "policy_finance"],
            "취업": ["취업", "구직", "일자리", "재직", "근로", "job"],
            "교육": ["교육", "훈련", "수강", "HRD", "training"],
            "창업": ["창업", "사업", "스타트업", "startup"],
        }
        return keyword_map.get(interest, [interest])

    def _housing_fit_line(
        self,
        user: dict[str, Any],
        policy_context: dict[str, Any],
        summary: dict[str, list[str]],
    ) -> str:
        housing_status = user.get("housing_status") or ""
        if not housing_status:
            return ""
        text = self._policy_profile_text(policy_context, summary)
        aliases = [housing_status]
        if "전세" in housing_status or "월세" in housing_status:
            aliases.extend(["전세", "월세", "전월세", "임대차", "보증금"])
        if "무주택" in housing_status:
            aliases.extend(["무주택", "세대주"])
        if any(alias and alias in text for alias in aliases):
            return f"주거상황: 입력한 '{housing_status}'와 정책의 주거 조건/혜택이 연결돼요."
        if any(word in text for word in ["주거", "임대", "주택", "전세", "월세"]):
            return f"주거상황: 주거 관련 정책이지만 '{housing_status}'가 직접 조건으로 명시됐는지는 확인이 필요해요."
        return f"주거상황: 입력한 '{housing_status}'와 직접 연결되는 주거 조건은 이 정책 프로필에서 뚜렷하지 않아요."

    def _employment_fit_line(
        self,
        user: dict[str, Any],
        policy_context: dict[str, Any],
        summary: dict[str, list[str]],
    ) -> str:
        employment = user.get("employment_status") or ""
        if not employment:
            return ""
        policy_employment = _clean(policy_context.get("employment_status"))
        text = self._policy_profile_text(policy_context, summary)
        if policy_employment and (employment in policy_employment or policy_employment in employment):
            return f"재직 여부: 입력값은 '{employment}'이고, 정책의 재직 조건({policy_employment})과 맞아 보여요."
        if employment in text:
            return f"재직 여부: 입력값 '{employment}'이 정책 조건에 직접 언급돼요."
        employment_words = ["미취업", "재직", "근로", "구직", "창업", "자영업", "프리랜서"]
        mentioned = [word for word in employment_words if word in text]
        if mentioned:
            return f"재직 여부: 정책에 {', '.join(mentioned[:3])} 조건이 있어 입력값({employment})과 비교 확인이 필요해요."
        return f"재직 여부: 입력값 '{employment}' 기준으로 볼 때, 이 정책에는 별도 재직 조건이 뚜렷하지 않아요."

    def _income_fit_line(self, user: dict[str, Any], summary: dict[str, list[str]]) -> str:
        income = user.get("income") or ""
        income_items = [
            item
            for item in summary.get("eligibility", [])
            if any(word in item for word in ["소득", "중위", "연소득", "합산", "만원 이하", "원 이하"])
        ]
        if income and income_items:
            return f"소득: 입력값은 '{income}'이고, 정책 조건은 '{_short_item(income_items[0], 70)}'라서 이 기준과 비교해야 해요."
        if income:
            return f"소득: '{income}'을 입력했지만, 이 정책 프로필에는 소득 조건이 뚜렷하게 보이지 않아요."
        if income_items:
            return f"소득: 정책에 '{_short_item(income_items[0], 70)}' 조건이 있어 본인 소득 구간 확인이 필요해요."
        return ""

    def _policy_profile_text(self, policy_context: dict[str, Any], summary: dict[str, list[str]]) -> str:
        return " ".join(
            _clean(item)
            for item in [
                policy_context.get("title"),
                policy_context.get("summary"),
                policy_context.get("target"),
                policy_context.get("domain"),
                policy_context.get("domain_label"),
                policy_context.get("source_label"),
                *summary.get("docs", []),
                *summary.get("eligibility", []),
                *summary.get("benefit", []),
                *summary.get("apply", []),
                *summary.get("notice", []),
            ]
        )

    def _build_apply_detail(
        self,
        policy_context: dict[str, Any],
        summary: dict[str, list[str]],
    ) -> dict[str, list[str]]:
        original = policy_context.get("original", {})
        search_doc = policy_context.get("search_document", {})
        facts = policy_context.get("facts", {})
        buckets = {
            "method": [],
            "period": [],
            "links": [],
            "docs": [],
            "contact": [],
            "notes": [],
        }

        def add(bucket: str, label: str, value: Any, *, as_date: bool = False, split: bool = False):
            text = _date(value) if as_date else _clean(value)
            if not text:
                return
            items = _split_items(text) if split else [text]
            for item in items:
                item_text = _short_item(item, 150)
                if item_text:
                    buckets[bucket].append(f"{label}: {item_text}" if label else item_text)

        def add_period_range(label: str, start: Any, end: Any):
            start_text = _date(start)
            end_text = _date(end)
            if start_text or end_text:
                buckets["period"].append(f"{label}: {start_text or '확인 필요'} ~ {end_text or '확인 필요'}")

        source_table = policy_context.get("source_table")

        add("method", "신청 방법", original.get("apply_method"))
        add("method", "가입 방법", original.get("jnMthd"))
        add("method", "선정 방법", original.get("selection_method"))
        add("period", "신청 기간", original.get("apply_period") or original.get("apply_period_type"))
        add_period_range("신청 기간", original.get("apply_start_date"), original.get("apply_end_date"))
        add_period_range("신청 기간", original.get("begin_date"), original.get("end_date"))
        add_period_range("훈련 기간", original.get("tra_start_date"), original.get("tra_end_date"))
        add("period", "마감", original.get("mgmDln"))
        add("period", "통합 문서 기간", policy_context.get("period"))

        add("links", "신청 URL", original.get("application_url"))
        add("links", "참고 링크", original.get("ref_url1"))
        add("links", "참고 링크 2", original.get("ref_url2"))
        add("links", "신청 URL", original.get("apply_url"))
        add("links", "상세 URL", original.get("detail_url"))
        add("links", "상세/신청 링크", original.get("title_link"))
        add("links", "관련 사이트", original.get("rltSite"))
        add("links", "마이홈 URL", original.get("myhome_url"))
        add("links", "통합 검색 링크", search_doc.get("url") or policy_context.get("url"))

        add("docs", "제출 서류", original.get("submit_docs"), split=True)
        add("docs", "공고 제출 서류", self._raw_json_value(original, "sbmsn_file"), split=True)
        for item in summary.get("docs", []):
            add("docs", "", item)

        add("contact", "주관 기관", original.get("institution"))
        add("contact", "운영 기관", original.get("oper_inst"))
        add("contact", "기관", original.get("organization") or original.get("insttNm"))
        add("contact", "제공 기관", original.get("ofrInstNm"))
        add("contact", "공급 기관", original.get("supply_inst"))
        add("contact", "문의처", original.get("contact") or original.get("cnpl") or original.get("rfrcCnpl"))
        add("contact", "전화번호", original.get("tel_no"))
        add("contact", "주소", original.get("address") or original.get("rnAdres"))

        for line in [*facts.get("apply", []), *summary.get("apply", [])]:
            item = _clean(line).lstrip("-").strip()
            if any(word in item for word in ["문의", "기관", "전화", "주소"]):
                add("contact", "", item)
            elif any(word in item for word in ["URL", "링크", "사이트", "http"]):
                add("links", "", item)
            elif any(word in item for word in ["기간", "시작", "종료", "마감"]):
                add("period", "", item)
            else:
                add("method", "", item)
        for line in facts.get("period", []):
            add("period", "", _clean(line).lstrip("-").strip())
        for line in facts.get("docs", []):
            add("docs", "", _clean(line).lstrip("-").strip())
        for line in facts.get("contact", []):
            add("contact", "", _clean(line).lstrip("-").strip())

        if source_table == "rental_houses":
            if not buckets["method"]:
                buckets["method"].append("실제 모집공고에서 신청 기간과 접수처 확인")
            buckets["notes"].append("이 항목은 단지 정보라 실제 모집공고에서 접수 기간과 신청 페이지를 반드시 다시 확인해야 해요.")
        if source_table == "smallloan_youth":
            buckets["notes"].append("금융상품은 은행/보증기관 심사 결과에 따라 가입이 제한될 수 있어요.")
        if source_table == "myhome_notices":
            if not buckets["method"]:
                buckets["method"].append("마이홈/LH 공고 페이지에서 신청 절차 확인")
            buckets["notes"].append("임대공고는 모집 상태와 접수 일정이 바뀔 수 있어 공고 링크에서 최신 내용을 확인해야 해요.")
        if source_table == "hrd_trainings" and not buckets["method"]:
            buckets["method"].append("HRD-Net 상세 페이지에서 수강 신청 절차 확인")
        if source_table == "kstartup_notices" and not buckets["method"]:
            buckets["method"].append("K-Startup 공고 페이지에서 신청 절차 확인")

        for key, values in buckets.items():
            buckets[key] = self._dedupe_apply_items(key, values)
        return buckets

    def _dedupe_apply_items(self, bucket: str, values: list[str]) -> list[str]:
        seen = set()
        result = []
        for value in values:
            text = _clean(value)
            if not text:
                continue
            key = text
            if bucket == "links":
                match = re.search(r"https?://\S+", text)
                if match:
                    key = match.group(0).rstrip(".,)")
                    key = key.replace("...", "")[:120]
            elif bucket in {"method", "period", "contact"} and ":" in text:
                key = text.split(":", 1)[1].strip()
            if key in seen:
                continue
            seen.add(key)
            result.append(text)
        return result

    def _summary_for_policy(self, original: dict[str, Any], facts: dict[str, list[str]], summary_text: str) -> dict[str, list[str]]:
        docs = _split_items(original.get("submit_docs"))
        if not docs:
            docs = ["DB에 제출 서류가 명시되어 있지 않음", "신청 링크 또는 담당 기관에서 최종 서류 확인"]

        eligibility = []
        min_age = _clean(original.get("min_age"))
        max_age = _clean(original.get("max_age"))
        if min_age and min_age != "0":
            eligibility.append(f"만 {min_age}세 이상")
        if max_age and max_age != "0":
            eligibility.append(f"만 {max_age}세 이하")
        for value in [original.get("job_cd"), original.get("school_cd"), original.get("income_etc"), original.get("income_type"), original.get("apply_condition")]:
            eligibility.extend(_extract_condition_bullets(_clean(value)) or _split_items(value))
        if not eligibility:
            eligibility = _extract_condition_bullets(summary_text) or ["나이, 거주지, 소득 등 세부 자격은 공고문 확인"]

        support_only = _support_content_only(original.get("support_content") or summary_text)
        benefit = _dash_bullets_from_text(support_only) or _extract_benefit_bullets(support_only)
        if not benefit and original.get("support_content"):
            benefit = [_short_item(support_only or original.get("support_content"))]
        if not benefit:
            benefit = ["지원 금액/내용은 공고문에서 확인 필요"]

        apply_items = []
        if _clean(original.get("apply_period") or original.get("apply_period_type")):
            apply_items.append(f"신청 기간: {_clean(original.get('apply_period') or original.get('apply_period_type'))}")
        if _clean(original.get("apply_method")):
            apply_items.append(f"신청 방법: {_short_item(original.get('apply_method'))}")
        url = _clean(original.get("application_url") or original.get("ref_url1") or original.get("ref_url2"))
        if url:
            apply_items.append(f"신청/확인 링크: {url}")
        if not apply_items:
            apply_items = ["신청 방법과 기간은 담당 기관 또는 공고 링크에서 확인"]

        return {
            "docs": _dedupe(docs),
            "eligibility": _dedupe([_short_item(item) for item in eligibility]),
            "benefit": _dedupe(benefit),
            "apply": apply_items,
            "notice": [],
        }

    def _summary_for_loan(self, original: dict[str, Any]) -> dict[str, list[str]]:
        docs = ["신분증", "소득 증빙 서류", "무주택/세대주 확인 서류", "임대차계약 관련 서류"]
        eligibility = []
        if _clean(original.get("age")):
            eligibility.append(_clean(original.get("age")))
        if _clean(original.get("incm")):
            eligibility.append(_clean(original.get("incm")))
        detail = _clean(original.get("suprTgtDtlCond"))
        if "무주택" in detail and "세대주" in detail:
            eligibility.append("무주택 세대주")
        elif "무주택" in detail:
            eligibility.append("무주택 요건 확인")
        if _clean(original.get("crdtSc")) and _clean(original.get("crdtSc")) != "없음":
            eligibility.append(f"신용 조건: {_clean(original.get('crdtSc'))}")
        benefit = []
        if _clean(original.get("lnLmt")):
            benefit.append(f"대출 한도: {_clean(original.get('lnLmt'))}")
        if _clean(original.get("irt")):
            benefit.append(f"금리: {_clean(original.get('irt'))}")
        if _clean(original.get("maxTotLnTrm")):
            benefit.append(f"대출 기간: {_clean(original.get('maxTotLnTrm'))}")
        if _clean(original.get("rdptMthd")):
            benefit.append(f"상환 방법: {_clean(original.get('rdptMthd'))}")
        apply_items = []
        if _clean(original.get("jnMthd")):
            apply_items.append(f"신청 방법: {_clean(original.get('jnMthd'))}")
        if _clean(original.get("mgmDln")):
            apply_items.append(f"마감: {_clean(original.get('mgmDln'))}")
        if _clean(original.get("rltSite")):
            apply_items.append(f"확인 링크: {_clean(original.get('rltSite'))}")
        return {
            "docs": docs,
            "eligibility": _dedupe([_short_item(item) for item in eligibility]) or ["취급 기관 심사 기준 충족 필요"],
            "benefit": benefit or ["대출 한도와 금리는 취급 기관 확인 필요"],
            "apply": apply_items or ["취급 금융기관에서 신청 절차 확인"],
            "notice": ["은행/보증기관 심사 결과에 따라 가입이 제한될 수 있음"],
        }

    def _summary_for_myhome(self, original: dict[str, Any]) -> dict[str, list[str]]:
        docs = ["주민등록등본", "가족관계증명서", "소득/자산 증빙 서류", "임대주택 신청서류"]
        eligibility = _split_items(original.get("youth_keyword")) or ["공고문상 입주 자격 확인"]
        benefit = []
        for label, key in [("공급 유형", "supply_type"), ("공급 세대", "supply_units"), ("보증금", "deposit"), ("월 임대료", "monthly_rent")]:
            value = _money(original.get(key)) if key in {"deposit", "monthly_rent"} else _clean(original.get(key))
            if value:
                benefit.append(f"{label}: {value}")
        apply_items = []
        if _date(original.get("begin_date")) or _date(original.get("end_date")):
            apply_items.append(f"신청 기간: {_date(original.get('begin_date')) or '확인 필요'} ~ {_date(original.get('end_date')) or '확인 필요'}")
        if _clean(original.get("detail_url") or original.get("myhome_url")):
            apply_items.append(f"공고 링크: {_clean(original.get('detail_url') or original.get('myhome_url'))}")
        return {
            "docs": docs,
            "eligibility": eligibility,
            "benefit": benefit or ["공급 금액/세대 정보는 공고문 확인 필요"],
            "apply": apply_items or ["마이홈/LH 공고에서 신청 기간 확인"],
            "notice": [],
        }

    def _summary_for_rental_house(self, original: dict[str, Any]) -> dict[str, list[str]]:
        docs = ["이 항목은 단지 정보라 제출 서류는 실제 모집공고에서 확인 필요"]
        eligibility = _split_items(original.get("youth_filter_keyword")) or ["해당 공급유형의 모집공고 자격 확인"]
        benefit = []
        for label, key in [("공급 유형", "suplyTyNm"), ("주택 유형", "houseTyNm"), ("전용면적", "suplyPrvuseAr"), ("기본 보증금", "bassRentGtn"), ("기본 월 임대료", "bassMtRntchrg")]:
            value = _money(original.get(key)) if key in {"bassRentGtn", "bassMtRntchrg"} else _clean(original.get(key))
            if value:
                benefit.append(f"{label}: {value}")
        apply_items = []
        if _clean(original.get("rnAdres")):
            apply_items.append(f"주소: {_clean(original.get('rnAdres'))}")
        apply_items.append("실제 모집공고에서 신청 기간과 접수처 확인")
        return {
            "docs": docs,
            "eligibility": eligibility,
            "benefit": benefit or ["단지 세부 정보는 모집공고 확인 필요"],
            "apply": apply_items,
            "notice": ["단지 정보와 모집공고는 다를 수 있으므로 최신 공고 확인 필요"],
        }

    def _summary_for_training(self, original: dict[str, Any]) -> dict[str, list[str]]:
        docs = ["국민내일배움카드 대상 여부 확인", "본인 인증 정보", "수강 신청에 필요한 HRD-Net 계정"]
        eligibility = _split_items(original.get("train_target")) or ["훈련 대상 확인 필요"]
        benefit = []
        for label, key in [("훈련기관", "sub_title"), ("훈련비", "real_man"), ("훈련 기간", "tra_start_date")]:
            value = _date(original.get(key)) if key == "tra_start_date" else _clean(original.get(key))
            if value:
                benefit.append(f"{label}: {value}")
        if _date(original.get("tra_end_date")):
            benefit.append(f"종료일: {_date(original.get('tra_end_date'))}")
        apply_items = []
        if _clean(original.get("title_link")):
            apply_items.append(f"신청/상세 링크: {_clean(original.get('title_link'))}")
        if _clean(original.get("tel_no")):
            apply_items.append(f"문의: {_clean(original.get('tel_no'))}")
        return {
            "docs": docs,
            "eligibility": eligibility,
            "benefit": benefit or ["훈련비/기간은 상세 페이지 확인 필요"],
            "apply": apply_items or ["HRD-Net에서 수강 신청 절차 확인"],
            "notice": [],
        }

    def _summary_for_startup(self, original: dict[str, Any], summary_text: str) -> dict[str, list[str]]:
        docs = _split_items(self._raw_json_value(original, "sbmsn_file"))
        if not docs:
            docs = ["사업계획서", "대표자/기업 증빙 서류", "공고문에 명시된 증빙자료"]
        eligibility = []
        for value in [original.get("target"), original.get("target_detail"), original.get("business_age"), original.get("target_age")]:
            eligibility.extend(_extract_condition_bullets(_clean(value)) or _split_items(value))
        benefit = _extract_benefit_bullets(original.get("description") or summary_text)
        if not benefit and original.get("description"):
            benefit = [_short_item(original.get("description"))]
        apply_items = []
        if _date(original.get("apply_start_date")) or _date(original.get("apply_end_date")):
            apply_items.append(f"신청 기간: {_date(original.get('apply_start_date')) or '확인 필요'} ~ {_date(original.get('apply_end_date')) or '확인 필요'}")
        if _clean(original.get("apply_url") or original.get("detail_url")):
            apply_items.append(f"신청/공고 링크: {_clean(original.get('apply_url') or original.get('detail_url'))}")
        return {
            "docs": docs,
            "eligibility": _dedupe([_short_item(item) for item in eligibility]) or ["공고문상 창업기업 자격 확인"],
            "benefit": benefit or ["사업화/글로벌/교육 등 지원 내용은 공고문 확인 필요"],
            "apply": apply_items or ["K-Startup 공고 페이지에서 신청 절차 확인"],
            "notice": [],
        }

    def _summary_from_facts(self, facts: dict[str, list[str]]) -> dict[str, list[str]]:
        return {
            "docs": [_strip_label(item) for item in facts.get("docs", [])] or ["공고문에서 제출 서류 확인"],
            "eligibility": [_strip_label(item) for item in facts.get("eligibility", [])] or ["세부 자격 확인 필요"],
            "benefit": [_strip_label(item) for item in facts.get("benefit", [])] or ["지원 내용 확인 필요"],
            "apply": [_strip_label(item) for item in facts.get("apply", [])] or ["신청 방법 확인 필요"],
            "notice": [],
        }

    def _section_for_intent(
        self,
        intent: str,
        facts: dict[str, list[str]],
        policy_context: dict[str, Any],
    ) -> list[str]:
        if intent == "docs":
            docs = facts.get("docs", [])
            if docs:
                return ["\n필요한 준비물/서류는 이렇게 보면 돼요.", *docs]
            return [
                "\nDB에 명시된 제출 서류는 없습니다.",
                "- 공고문에서 제출 서류 항목을 확인하세요.",
                "- 기본적으로 신분증, 주민등록등본, 소득 증빙, 자격 증빙이 요구될 수 있습니다.",
            ]
        if intent == "eligibility":
            values = facts.get("eligibility", [])
            if values:
                return ["\n신청 자격은 이 부분을 확인해야 해요.", *values]
        if intent == "apply":
            values = facts.get("apply", [])
            if values:
                return ["\n신청 방법은 다음과 같아요.", *values]
        if intent == "period":
            values = facts.get("period", [])
            if values:
                return ["\n기간 정보는 이렇습니다.", *values]
        if intent == "benefit":
            values = facts.get("benefit", [])
            if values:
                return ["\n지원/혜택 정보는 이렇습니다.", *values]
        if intent == "contact":
            values = facts.get("contact", [])
            if values:
                return ["\n문의할 곳은 다음과 같아요.", *values]
        if intent == "overview":
            values = facts.get("overview", [])
            if values:
                return ["\n정책 요약은 이렇습니다.", *values]
        return []

    def _follow_up_question(self, intent: str, source_label: str) -> str:
        if intent == "docs":
            return "원하면 제가 다음으로 신청 자격부터 같이 체크해볼게요."
        if intent == "eligibility":
            return "나이, 지역, 소득 조건을 알려주면 해당 가능성을 더 좁혀서 볼 수 있어요."
        if intent == "apply":
            return "신청 전에 필요한 서류도 바로 정리해드릴까요?"
        if intent == "period":
            return "마감 전 준비 순서까지 체크리스트로 정리해드릴까요?"
        if intent == "benefit":
            return "이 혜택이 본인 상황에 맞는지 조건도 같이 볼까요?"
        if intent == "contact":
            return "문의 전에 물어볼 질문 목록도 만들어드릴 수 있어요."
        return f"{source_label} 기준으로 더 궁금한 항목을 이어서 물어봐 주세요."
