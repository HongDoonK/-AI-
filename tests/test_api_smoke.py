"""FastAPI 엔드포인트 smoke test — TestClient + fixture DB."""
import unittest

from tests.util_fixture import set_test_env

set_test_env()

import os
import tempfile

# 사용자 DB도 임시 경로로 격리
_tmp_user_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["USER_DB_PATH"] = _tmp_user_db.name

from fastapi.testclient import TestClient

from backend.main import app


class ApiSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        set_test_env()
        cls.client = TestClient(app)

    def test_root_returns_ok(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("status"), "ok")

    def test_chat_status_returns_200(self):
        response = self.client.get("/chat/status")
        self.assertEqual(response.status_code, 200)

    def test_recommend_returns_recommendations(self):
        response = self.client.post(
            "/recommend",
            json={"user_input": "서울 사는 24세 대학생인데 월세 지원 정책 알려줘"},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("recommendations", body)
        self.assertGreater(len(body["recommendations"]), 0)

    def test_user_save_and_fetch_roundtrip(self):
        response = self.client.post(
            "/user",
            json={
                "age": 24,
                "gender": "여성",
                "region_sido": "서울",
                "region_sigungu": "관악구",
                "status": "대학생",
                "interest": "주거",
                "employment_status": None,
                "income": None,
                "housing_status": "월세",
            },
        )
        self.assertEqual(response.status_code, 200)
        user_id = response.json()["user_id"]
        fetched = self.client.get(f"/user/{user_id}")
        self.assertEqual(fetched.status_code, 200)
        self.assertEqual(fetched.json()["region_sigungu"], "관악구")


if __name__ == "__main__":
    unittest.main()
