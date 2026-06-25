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

    # 별도 lgcv.db 파일 경로(LGCV_POLICY_DB_PATH)도 동작한다.
    def test_separate_lgcv_file_path_works(self):
        from ai.recommender import recommend_policy

        os.environ["LGCV_POLICY_DB_PATH"] = str(ensure_lgcv_fixture_db())
        result = recommend_policy("충북 충주 사는 27세 청년 복지서비스 알려줘")

        self.assertEqual(result.get("recommendation_source"), "lgcv")
        self.assertIn("lgcv", _sources(result))


if __name__ == "__main__":
    unittest.main()
