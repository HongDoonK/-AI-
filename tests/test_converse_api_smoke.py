"""/agent/converse 엔드포인트 smoke test (멀티턴 세션 왕복)."""
import os
import tempfile
import unittest

from tests.util_fixture import set_test_env

set_test_env()

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["USER_DB_PATH"] = _tmp.name

from fastapi.testclient import TestClient

from backend.main import app

SEEDED_POLICY = {
    "doc_id": "policies_processed:P001",
    "source_table": "policies_processed",
    "source_id": "P001",
    "policy_name": "청년 월세 지원",
    "category_main": "policy_housing",
}


class ConverseApiSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        set_test_env()
        cls.client = TestClient(app)

    def _say(self, message, session_id=None):
        body = {"message": message}
        if session_id:
            body["session_id"] = session_id
        return self.client.post("/agent/converse", json=body)

    def test_full_recommend_select_benefit_roundtrip(self):
        # 턴 1: 추천
        r1 = self._say("서울 무주택 청년인데 월세 지원 정책 없나?")
        self.assertEqual(r1.status_code, 200)
        body1 = r1.json()
        session_id = body1["session_id"]
        self.assertEqual(body1["intent"], "recommend")
        self.assertTrue(body1["cards"])

        # 턴 2: 같은 세션에서 1번 신청 의사 → 서류 안내와 선택 정책 영속화
        r2 = self._say("정책 1 신청할래", session_id=session_id)
        body2 = r2.json()
        self.assertEqual(body2["intent"], "docs")
        self.assertIsNotNone(body2["selected_policy"])
        self.assertTrue(body2["documents"])

        # 턴 3: 지원금 — 선택 정책이 세션에서 복원되어 정량화 응답
        r3 = self._say("그럼 얼마나 받을 수 있어?", session_id=session_id)
        body3 = r3.json()
        self.assertEqual(body3["intent"], "benefit")
        self.assertIn("benefit", body3)

        # 세션 히스토리 복원
        history = self.client.get(f"/agent/converse/{session_id}")
        self.assertEqual(history.status_code, 200)
        self.assertGreaterEqual(len(history.json()["turns"]), 6)  # user/assistant × 3턴

    def test_seeded_policy_empty_message_selects_and_persists_session(self):
        response = self.client.post(
            "/agent/converse",
            json={"message": "", "policy": SEEDED_POLICY},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["intent"], "select")
        self.assertEqual(body["selected_policy"]["doc_id"], "policies_processed:P001")
        self.assertIn("무엇을 먼저 볼까요", body["reply"])

        history = self.client.get(f"/agent/converse/{body['session_id']}")
        self.assertEqual(history.status_code, 200)
        session = history.json()["session"]
        self.assertEqual(session["selected_policy"]["doc_id"], "policies_processed:P001")
        self.assertEqual(session["last_recommendations"][0]["doc_id"], "policies_processed:P001")

    def test_unknown_session_returns_404(self):
        self.assertEqual(self.client.get("/agent/converse/no-such-session").status_code, 404)


if __name__ == "__main__":
    unittest.main()
