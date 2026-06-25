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
        # 턴 1: 추천은 Hero(/recommend)가 전담 — 대화 세션을 시드 (하드 분리)
        rec = self.client.post(
            "/recommend", json={"user_input": "서울 무주택 청년인데 월세 지원 정책 없나?"}
        )
        self.assertEqual(rec.status_code, 200)
        rec_body = rec.json()
        session_id = rec_body["session_id"]
        self.assertTrue(rec_body["cards"])

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

        # 세션 히스토리 복원 (converse 2턴 = user/assistant × 2)
        history = self.client.get(f"/agent/converse/{session_id}")
        self.assertEqual(history.status_code, 200)
        self.assertGreaterEqual(len(history.json()["turns"]), 4)

    def test_chat_recommendation_request_does_not_create_or_overwrite_list(self):
        # 하드 분리: 채팅 추천 요청은 새 목록을 만들지 않고 세션 추천 목록도 덮어쓰지 않는다
        rec = self.client.post("/recommend", json={"user_input": "서울 무주택 청년 월세 지원"})
        session_id = rec.json()["session_id"]
        seeded = rec.json()["cards"]
        self.assertTrue(seeded)

        chat = self._say("다른 정책 추천해줘", session_id=session_id)
        self.assertEqual(chat.status_code, 200)
        self.assertEqual(chat.json()["intent"], "need_recommendation")

        session = self.client.get(f"/agent/converse/{session_id}").json()["session"]
        self.assertEqual(
            [c["doc_id"] for c in session["last_recommendations"]],
            [c["doc_id"] for c in seeded],
            "채팅 추천 요청 후에도 Hero가 시드한 목록이 보존되어야 함",
        )

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

    def test_recommend_seeds_shared_session_for_chat(self):
        # D1: /recommend가 session_id+cards를 내려주고, 채팅이 같은 세션의 추천을 이어받는다
        rec = self.client.post("/recommend", json={"user_input": "서울 무주택 청년 월세 지원 정책"})
        self.assertEqual(rec.status_code, 200)
        rec_body = rec.json()
        self.assertIn("session_id", rec_body)
        self.assertTrue(rec_body["session_id"])
        self.assertTrue(rec_body["cards"], "추천 카드가 세션 시드용으로 반환되어야 함")
        # 기존 shape 보존 확인
        self.assertIn("recommendations", rec_body)
        self.assertIn("user_condition", rec_body)

        session_id = rec_body["session_id"]
        first_doc_id = rec_body["cards"][0]["doc_id"]

        # 같은 세션에서 "정책 1 신청할래" → Hero가 시드한 목록의 1번이 선택돼야 함
        chat = self._say("정책 1 신청할래", session_id=session_id)
        self.assertEqual(chat.status_code, 200)
        chat_body = chat.json()
        self.assertIsNotNone(chat_body["selected_policy"])
        self.assertEqual(chat_body["selected_policy"]["doc_id"], first_doc_id)

    def test_response_plan_meta_is_stored_in_history_but_not_returned_publicly(self):
        selected = self.client.post(
            "/agent/converse",
            json={"message": "", "policy": SEEDED_POLICY},
        ).json()
        session_id = selected["session_id"]

        response = self._say("필요한 서류가 뭐야?", session_id=session_id)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_response_plan_meta", response.json())
        self.assertNotIn("response_plan_meta", response.json())

        turns = self.client.get(f"/agent/converse/{session_id}").json()["turns"]
        assistant_turn = next(
            turn for turn in reversed(turns)
            if turn["role"] == "assistant" and turn["intent"] == "docs"
        )
        self.assertIn("response_plan_meta", assistant_turn["payload"])

    def test_multiturn_follow_up_changes_focus_without_changing_selected_policy(self):
        selected = self.client.post(
            "/agent/converse",
            json={"message": "", "policy": SEEDED_POLICY},
        ).json()
        session_id = selected["session_id"]
        first = self._say("필요한 서류가 뭐야?", session_id=session_id).json()
        second = self._say("그 서류는 어디서 발급해?", session_id=session_id).json()
        self.assertEqual(first["selected_policy"]["doc_id"], second["selected_policy"]["doc_id"])
        self.assertEqual(first["documents"], second["documents"])
        self.assertNotEqual(first["reply"], second["reply"])

    def test_unknown_session_returns_404(self):
        self.assertEqual(self.client.get("/agent/converse/no-such-session").status_code, 404)


if __name__ == "__main__":
    unittest.main()
