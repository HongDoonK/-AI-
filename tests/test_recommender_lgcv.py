"""충북 전용(lgcv) 우선 추천 + 통합 DB fallback 테스트.

최신 구조(origin/main)에서 lgcv는 별도 파일이 아니라 search_documents 안에
source_table="lgcv", domain="welfare"로 통합되므로, 그 케이스를 핵심으로 검증한다.
welfare_central(전국)과 lgcv(충북)는 source_table로 구분된다.
"""
import os
import sqlite3
import tempfile
import unittest

from tests.util_fixture import ensure_lgcv_fixture_db, set_test_env


def _names(result: dict) -> list[str]:
    return [r.get("policy_name") for r in result.get("recommendations", [])]


def _sources(result: dict) -> list[str]:
    return [r.get("source_table") for r in result.get("recommendations", [])]


def _sigungus(result: dict) -> list[str]:
    return [r.get("region_sigungu") for r in result.get("recommendations", [])]


_SEARCH_DOCS_DDL = """
CREATE TABLE search_documents (
    doc_id TEXT PRIMARY KEY, source_table TEXT, source_id TEXT, domain TEXT,
    title TEXT, summary TEXT, region_name TEXT, region_sido TEXT, region_sigungu TEXT,
    target TEXT, min_age INTEGER, max_age INTEGER, employment_status TEXT, status TEXT,
    apply_start_date TEXT, apply_end_date TEXT, url TEXT, search_text TEXT, raw_ref TEXT, collected_at TEXT
)
"""
_SEARCH_DOCS_COLS = (
    "doc_id", "source_table", "source_id", "domain", "title", "summary", "region_name",
    "region_sido", "region_sigungu", "target", "min_age", "max_age", "employment_status",
    "status", "apply_start_date", "apply_end_date", "url", "search_text", "raw_ref", "collected_at",
)


def _doc(doc_id, source_table, domain, title, region_name, sido, sigungu, text):
    row = dict.fromkeys(_SEARCH_DOCS_COLS, "")
    row.update(
        doc_id=doc_id, source_table=source_table, source_id=doc_id.split(":")[-1], domain=domain,
        title=title, summary=title, region_name=region_name, region_sido=sido, region_sigungu=sigungu,
        target="청년", min_age=19, max_age=39, status="청년", search_text=text,
    )
    return tuple(row[col] for col in _SEARCH_DOCS_COLS)


def _build_search_docs_db(tmp_dir: str, rows: list[tuple]) -> str:
    path = os.path.join(tmp_dir, "youth_policy.db")
    conn = sqlite3.connect(path)
    conn.execute(_SEARCH_DOCS_DDL)
    placeholders = ",".join("?" * len(_SEARCH_DOCS_COLS))
    conn.executemany(
        f"INSERT INTO search_documents ({','.join(_SEARCH_DOCS_COLS)}) VALUES ({placeholders})",
        rows,
    )
    conn.commit()
    conn.close()
    return path


def _national_rent_docs(count: int) -> list[tuple]:
    return [
        _doc(
            f"policies_processed:NAT{i}", "policies_processed", "policy_housing",
            f"청년 월세 한시 특별지원 {i}", "전국", "전국", "",
            "청년 월세 임대료 주거 보증금 지원 전국",
        )
        for i in range(1, count + 1)
    ]


class RecommenderLgcvTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # LLM/FAISS off + 기본 youth_policy fixture(통합 search_documents에 lgcv/welfare_central 포함).
        set_test_env()

    def setUp(self):
        self._prev_lgcv = os.environ.get("LGCV_POLICY_DB_PATH")
        os.environ.pop("LGCV_POLICY_DB_PATH", None)

    def tearDown(self):
        if self._prev_lgcv is None:
            os.environ.pop("LGCV_POLICY_DB_PATH", None)
        else:
            os.environ["LGCV_POLICY_DB_PATH"] = self._prev_lgcv

    # 1) 충북 입력 → 통합 search_documents의 source_table="lgcv" 행이 먼저 추천된다.
    def test_chungbuk_uses_lgcv_from_search_documents(self):
        from ai.recommender import recommend_policy

        result = recommend_policy("충청북도 사는 28세 청년 복지 지원 정책 알려줘")

        self.assertEqual(result.get("recommendation_source"), "lgcv")
        self.assertGreater(len(result["recommendations"]), 0)
        self.assertIn("lgcv", _sources(result))
        self.assertTrue(any("충북" in name for name in _names(result)))
        # lgcv 우선 단계에서는 전국 welfare_central이 섞이지 않는다(lgcv df만 사용).
        self.assertNotIn("welfare_central", _sources(result))

    # 4) 충북 단축 별칭도 동작한다.
    def test_chungbuk_alias_short_form_works(self):
        from ai.recommender import recommend_policy

        result = recommend_policy("충북 사는 30세 청년 복지서비스 추천해줘")

        self.assertEqual(result.get("recommendation_source"), "lgcv")
        self.assertIn("lgcv", _sources(result))

    def test_chungbuk_uses_welfare_chungbuk_local_table(self):
        from ai.recommender import recommend_policy

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = os.path.join(tmp, "youth_policy.db")
            conn = sqlite3.connect(db_path)
            conn.execute(
                """
                CREATE TABLE welfare_chungbuk_local (
                    service_id TEXT PRIMARY KEY,
                    service_name TEXT,
                    region_sido TEXT,
                    region_sigungu TEXT,
                    department TEXT,
                    summary TEXT,
                    life_cycle TEXT,
                    target_group TEXT,
                    support_target TEXT,
                    selection_criteria TEXT,
                    support_content TEXT,
                    application_method TEXT,
                    homepage TEXT,
                    search_text TEXT,
                    imported_at TEXT
                )
                """
            )
            conn.execute(
                """
                INSERT INTO welfare_chungbuk_local VALUES (
                    'WLF-CB-001',
                    '충북 청년 복지서비스',
                    '충청북도',
                    '청주시',
                    '충청북도 청주시 복지정책과',
                    '청년 생활 안정을 위한 충북 지자체 복지서비스',
                    '청년',
                    '청년',
                    '충북 거주 청년',
                    '청주시 거주 청년',
                    '생활지원금 지원',
                    '행정복지센터 방문 신청',
                    'https://example.com/chungbuk',
                    '충청북도 청주시 청년 복지서비스 생활지원금 지자체',
                    '2026-06-23'
                )
                """
            )
            conn.commit()
            conn.close()

            previous_youth = os.environ.get("YOUTH_POLICY_DB_PATH")
            os.environ["YOUTH_POLICY_DB_PATH"] = db_path
            try:
                result = recommend_policy("충청북도 청주 사는 28세 청년 복지 서비스 추천해줘")
            finally:
                if previous_youth is None:
                    os.environ.pop("YOUTH_POLICY_DB_PATH", None)
                else:
                    os.environ["YOUTH_POLICY_DB_PATH"] = previous_youth

        self.assertEqual(result.get("recommendation_source"), "lgcv")
        self.assertEqual(_names(result), ["충북 청년 복지서비스"])
        self.assertEqual(_sources(result), ["lgcv"])

    # 2) lgcv 후보가 없으면 통합 DB로 fallback한다.
    def test_fallback_to_default_when_lgcv_empty(self):
        from ai.recommender import recommend_policy

        # 행이 없는 lgcv 테이블만 가진 별도 파일을 가리킨다 → load_lgcv_df None → fallback.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            empty_path = os.path.join(tmp, "lgcv.db")
            conn = sqlite3.connect(empty_path)
            conn.execute("CREATE TABLE lgcv (doc_id TEXT, search_text TEXT)")
            conn.commit()
            conn.close()

            os.environ["LGCV_POLICY_DB_PATH"] = empty_path
            result = recommend_policy("충청북도 사는 28세 청년 복지 지원 정책 알려줘")

        self.assertEqual(result.get("recommendation_source"), "default")
        self.assertIn("fallback_reason", result)
        self.assertGreater(len(result["recommendations"]), 0)

    # 3) fallback/default 추천에는 welfare_central 전국 복지서비스가 후보로 남는다.
    def test_fallback_keeps_welfare_central_national(self):
        from ai.recommender import recommend_policy

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            empty_path = os.path.join(tmp, "lgcv.db")
            conn = sqlite3.connect(empty_path)
            conn.execute("CREATE TABLE lgcv (doc_id TEXT, search_text TEXT)")
            conn.commit()
            conn.close()

            os.environ["LGCV_POLICY_DB_PATH"] = empty_path
            result = recommend_policy("충청북도 사는 28세 청년 복지 지원 정책 알려줘")

        self.assertEqual(result.get("recommendation_source"), "default")
        self.assertIn("welfare_central", _sources(result))

    # 5) 서울 등 비충북 입력은 lgcv를 사용하지 않는다.
    def test_non_chungbuk_keeps_default_flow(self):
        from ai.recommender import recommend_policy

        result = recommend_policy("서울 사는 24세 대학생인데 월세 지원 정책 알려줘")

        self.assertEqual(result.get("recommendation_source"), "default")
        self.assertNotIn("fallback_reason", result)
        self.assertNotIn("lgcv", _sources(result))

    # 6) 충북 세부 지역: 청주시 후보가 0개이고 충주/제천 lgcv만 있으면
    #    다른 충북 시군 lgcv 대신 전국 월세 후보로 채운다.
    def test_chungbuk_sigungu_excludes_other_sigungu_lgcv(self):
        from ai.recommender import recommend_policy

        rows = [
            _doc("lgcv:CHUNGJU1", "lgcv", "welfare", "충주 청년 월세 지원", "충북", "충북", "충주시",
                 "충주 청년 월세 주거 복지 지자체"),
            _doc("lgcv:JECHEON1", "lgcv", "welfare", "제천 청년 월세 지원", "충북", "충북", "제천시",
                 "제천 청년 월세 주거 복지 지자체"),
            *_national_rent_docs(6),
        ]
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = _build_search_docs_db(tmp, rows)
            previous = os.environ.get("YOUTH_POLICY_DB_PATH")
            os.environ["YOUTH_POLICY_DB_PATH"] = db_path
            try:
                result = recommend_policy("충북 청주시 24살 대학생 월세 지원")
            finally:
                if previous is None:
                    os.environ.pop("YOUTH_POLICY_DB_PATH", None)
                else:
                    os.environ["YOUTH_POLICY_DB_PATH"] = previous

        self.assertGreater(len(result["recommendations"]), 0)
        # 다른 충북 시군(충주/제천) lgcv 후보는 포함되지 않는다.
        self.assertNotIn("lgcv", _sources(result))
        # 전국 후보로 보충된다.
        self.assertTrue(any(r.get("region_name") == "전국" for r in result["recommendations"]))
        # 새 값을 추가하지 않고 default를 유지한다.
        self.assertIn(result.get("recommendation_source"), ("default", "mixed"))

    # 7) 충북 세부 지역: 청주시 후보 2개 + 전국 월세 보충으로 5개를 조합한다.
    def test_chungbuk_sigungu_combines_local_then_national(self):
        from ai.recommender import recommend_policy

        rows = [
            _doc("lgcv:CJ1", "lgcv", "welfare", "청주 청년 월세 지원 A", "충북 청주시", "충북", "청주시",
                 "청주 청년 월세 주거 임대료 복지 지자체"),
            _doc("lgcv:CJ2", "lgcv", "welfare", "청주 청년 월세 지원 B", "충북 청주시", "충북", "청주시",
                 "청주 청년 월세 주거 보증금 복지 지자체"),
            _doc("lgcv:CHUNGJU1", "lgcv", "welfare", "충주 청년 월세 지원", "충북", "충북", "충주시",
                 "충주 청년 월세 주거 복지 지자체"),
            _doc("lgcv:JECHEON1", "lgcv", "welfare", "제천 청년 월세 지원", "충북", "충북", "제천시",
                 "제천 청년 월세 주거 복지 지자체"),
            *_national_rent_docs(6),
        ]
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db_path = _build_search_docs_db(tmp, rows)
            previous = os.environ.get("YOUTH_POLICY_DB_PATH")
            os.environ["YOUTH_POLICY_DB_PATH"] = db_path
            try:
                result = recommend_policy("충북 청주시 24살 대학생 월세 지원")
            finally:
                if previous is None:
                    os.environ.pop("YOUTH_POLICY_DB_PATH", None)
                else:
                    os.environ["YOUTH_POLICY_DB_PATH"] = previous

        recs = result["recommendations"]
        self.assertEqual(len(recs), 5)
        # 앞쪽 2개는 청주시 정확 지역 후보다.
        self.assertEqual(_sigungus(result)[:2], ["청주시", "청주시"])
        # 충주/제천 lgcv 후보는 포함되지 않는다.
        self.assertNotIn("충주시", _sigungus(result))
        self.assertNotIn("제천시", _sigungus(result))
        # 나머지는 전국/기존 검색 후보로 채워진다.
        self.assertTrue(any(r.get("region_name") == "전국" for r in recs[2:]))

    # 8) 충북 광역(시군구 미지정) 입력은 기존처럼 lgcv 후보를 사용할 수 있다.
    def test_chungbuk_broad_still_uses_lgcv(self):
        from ai.recommender import recommend_policy

        result = recommend_policy("충북 사는 30세 청년 복지서비스 추천해줘")

        self.assertEqual(result.get("recommendation_source"), "lgcv")
        self.assertIn("lgcv", _sources(result))

    # 별도 lgcv.db 파일 경로(LGCV_POLICY_DB_PATH)도 동작한다.
    def test_separate_lgcv_file_path_works(self):
        from ai.recommender import recommend_policy

        os.environ["LGCV_POLICY_DB_PATH"] = str(ensure_lgcv_fixture_db())
        result = recommend_policy("충북 충주 사는 27세 청년 복지서비스 알려줘")

        self.assertEqual(result.get("recommendation_source"), "lgcv")
        self.assertIn("lgcv", _sources(result))


if __name__ == "__main__":
    unittest.main()
