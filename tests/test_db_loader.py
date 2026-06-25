"""ai.db_loader의 DB 경로 탐색/로딩 테스트 (fixture DB 기반)."""
import os
import sqlite3
import tempfile
import unittest

from tests.util_fixture import ensure_fixture_db, ensure_lgcv_fixture_db


class DbLoaderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_path = ensure_fixture_db()
        cls._prev_env = os.environ.get("YOUTH_POLICY_DB_PATH")
        os.environ["YOUTH_POLICY_DB_PATH"] = str(cls.fixture_path)

    @classmethod
    def tearDownClass(cls):
        if cls._prev_env is None:
            os.environ.pop("YOUTH_POLICY_DB_PATH", None)
        else:
            os.environ["YOUTH_POLICY_DB_PATH"] = cls._prev_env

    def test_find_db_path_uses_env_override(self):
        from ai.db_loader import find_db_path

        self.assertEqual(str(find_db_path()), str(self.fixture_path))

    def test_find_db_path_raises_when_env_points_to_missing_file(self):
        from ai.db_loader import find_db_path

        os.environ["YOUTH_POLICY_DB_PATH"] = "/nonexistent/no.db"
        try:
            with self.assertRaises(FileNotFoundError):
                find_db_path()
        finally:
            os.environ["YOUTH_POLICY_DB_PATH"] = str(self.fixture_path)

    def test_load_policy_df_returns_normalized_search_documents(self):
        from ai.db_loader import load_policy_df

        df = load_policy_df()
        self.assertFalse(df.empty)
        # search_documents 정규화 컬럼 확인
        for column in ["policy_id", "policy_name", "search_text", "domain"]:
            self.assertIn(column, df.columns)
        self.assertIn("청년 월세 지원", set(df["policy_name"]))


class LgcvLoaderTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lgcv_path = str(ensure_lgcv_fixture_db())
        cls.fixture_path = str(ensure_fixture_db())
        cls._prev_youth = os.environ.get("YOUTH_POLICY_DB_PATH")
        os.environ["YOUTH_POLICY_DB_PATH"] = cls.fixture_path

    @classmethod
    def tearDownClass(cls):
        if cls._prev_youth is None:
            os.environ.pop("YOUTH_POLICY_DB_PATH", None)
        else:
            os.environ["YOUTH_POLICY_DB_PATH"] = cls._prev_youth

    def setUp(self):
        self._prev = os.environ.get("LGCV_POLICY_DB_PATH")
        os.environ.pop("LGCV_POLICY_DB_PATH", None)

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("LGCV_POLICY_DB_PATH", None)
        else:
            os.environ["LGCV_POLICY_DB_PATH"] = self._prev

    def test_load_lgcv_df_reads_source_table_from_search_documents(self):
        from ai.db_loader import load_lgcv_df

        # 별도 파일 없이 통합 search_documents의 source_table='lgcv' 행만 읽어야 한다.
        os.environ.pop("LGCV_POLICY_DB_PATH", None)
        df = load_lgcv_df()
        self.assertIsNotNone(df)
        self.assertFalse(df.empty)
        self.assertTrue((df["source_table"] == "lgcv").all())
        self.assertIn("search_text", df.columns)
        # welfare_central(전국)은 lgcv로 읽히면 안 된다.
        self.assertFalse((df["source_table"] == "welfare_central").any())

    def test_load_lgcv_df_reads_welfare_chungbuk_local_table(self):
        from ai.db_loader import load_lgcv_df

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
                df = load_lgcv_df()
            finally:
                if previous_youth is None:
                    os.environ["YOUTH_POLICY_DB_PATH"] = self.fixture_path
                else:
                    os.environ["YOUTH_POLICY_DB_PATH"] = previous_youth

        self.assertIsNotNone(df)
        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertEqual(row["source_table"], "lgcv")
        self.assertEqual(row["domain"], "welfare")
        self.assertEqual(row["region_sido"], "충북")
        self.assertEqual(row["region_sigungu"], "청주시")
        self.assertEqual(row["policy_name"], "충북 청년 복지서비스")

    def test_find_lgcv_db_path_returns_none_when_no_file(self):
        from ai.db_loader import find_lgcv_db_path

        os.environ.pop("LGCV_POLICY_DB_PATH", None)
        # 로컬에 data/lgcv.db 등이 없으면 None을 반환해 fallback을 허용한다.
        self.assertIsNone(find_lgcv_db_path())

    def test_find_lgcv_db_path_raises_when_env_missing_file(self):
        from ai.db_loader import find_lgcv_db_path

        os.environ["LGCV_POLICY_DB_PATH"] = "/nonexistent/lgcv.db"
        with self.assertRaises(FileNotFoundError):
            find_lgcv_db_path()

    def test_load_lgcv_df_normalizes_standard_columns(self):
        from ai.db_loader import load_lgcv_df

        os.environ["LGCV_POLICY_DB_PATH"] = self.lgcv_path
        df = load_lgcv_df()
        self.assertIsNotNone(df)
        self.assertFalse(df.empty)
        for column in ["policy_id", "policy_name", "search_text", "domain"]:
            self.assertIn(column, df.columns)
        self.assertTrue((df["region_sido"] == "충북").any())


if __name__ == "__main__":
    unittest.main()
