"""/agent/* 엔드포인트 smoke test."""
import os
import tempfile
import unittest

from tests.util_fixture import set_test_env

set_test_env()

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["USER_DB_PATH"] = _tmp.name

from fastapi.testclient import TestClient

from backend.main import app


class ApplyApiSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        set_test_env()
        cls.client = TestClient(app)

    def _create_plan(self, user_id=None):
        return self.client.post(
            "/agent/apply-plan",
            json={
                "policy": {
                    "doc_id": "policies_processed:P001",
                    "source_table": "policies_processed",
                    "source_id": "P001",
                },
                "user_id": user_id,
            },
        )

    def test_apply_plan_creates_application(self):
        response = self._create_plan()
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "preparing")
        self.assertEqual(body["doc_id"], "policies_processed:P001")
        self.assertGreater(len(body["checklist"]), 0)
        self.assertIn(body["eligibility"], {"ok", "needs_info", "ineligible"})

    def test_apply_plan_is_idempotent_for_same_user(self):
        # 저장된 사용자 생성
        user = self.client.post("/user", json={"age": 24, "region_sido": "서울"}).json()
        first = self._create_plan(user_id=user["user_id"]).json()
        second = self._create_plan(user_id=user["user_id"]).json()
        self.assertEqual(first["application_id"], second["application_id"])

    def test_item_toggle_and_status_flow(self):
        body = self._create_plan().json()
        aid = body["application_id"]
        item_id = body["checklist"][0]["item_id"]

        toggled = self.client.patch(
            f"/agent/applications/{aid}/items/{item_id}", json={"checked": True}
        )
        self.assertEqual(toggled.status_code, 200)
        self.assertEqual(toggled.json()["progress"]["completed"], 1)

        ready = self.client.patch(f"/agent/applications/{aid}", json={"status": "ready"})
        self.assertEqual(ready.status_code, 200)

        invalid = self.client.patch(f"/agent/applications/{aid}", json={"status": "done"})
        self.assertEqual(invalid.status_code, 409)

    def test_unknown_application_returns_404(self):
        response = self.client.get("/agent/applications/no-such-id")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
