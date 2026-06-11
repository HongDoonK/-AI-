"""ai.db_loader의 DB 경로 탐색/로딩 테스트 (fixture DB 기반)."""
import os
import unittest

from tests.util_fixture import ensure_fixture_db


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


if __name__ == "__main__":
    unittest.main()
