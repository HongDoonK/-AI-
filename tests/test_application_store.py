"""application_store 상태머신/CRUD 테스트 (임시 user DB)."""
import os
import tempfile
import unittest

from tests.util_fixture import set_test_env

set_test_env()

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["USER_DB_PATH"] = _tmp.name

from backend import application_store


def _sample_plan(doc_id="policies_processed:P001", user_id=None):
    return {
        "user_id": user_id,
        "doc_id": doc_id,
        "source_table": "policies_processed",
        "source_id": "P001",
        "policy_name": "청년 월세 지원",
        "eligibility": "ok",
        "eligibility_notes": [],
        "apply_channel": "online",
        "apply_url": "https://example.com/p001",
        "apply_deadline": "상시",
        "draft_answers": None,
    }


_CHECKLIST = [
    {"kind": "document", "label": "주민등록등본 1부", "help_label": "정부24에서 발급", "help_url": "https://gov.kr"},
    {"kind": "action", "label": "신청서 제출"},
]


class ApplicationStoreTest(unittest.TestCase):
    def test_create_and_get_roundtrip(self):
        app = application_store.create_application(_sample_plan(), _CHECKLIST)
        self.assertEqual(app["status"], "preparing")
        self.assertEqual(len(app["checklist"]), 2)
        self.assertEqual(app["progress"], {"total": 2, "completed": 0})

    def test_item_check_updates_progress(self):
        app = application_store.create_application(_sample_plan(), _CHECKLIST)
        item_id = app["checklist"][0]["item_id"]
        updated = application_store.set_item_checked(app["application_id"], item_id, True)
        self.assertEqual(updated["progress"]["completed"], 1)
        self.assertTrue(updated["checklist"][0]["checked"])

    def test_valid_transitions(self):
        app = application_store.create_application(_sample_plan(), _CHECKLIST)
        aid = app["application_id"]
        self.assertEqual(application_store.update_status(aid, "ready")["status"], "ready")
        self.assertEqual(application_store.update_status(aid, "submitted")["status"], "submitted")
        self.assertEqual(application_store.update_status(aid, "done")["status"], "done")

    def test_invalid_transition_raises(self):
        app = application_store.create_application(_sample_plan(), _CHECKLIST)
        with self.assertRaises(application_store.InvalidTransition):
            application_store.update_status(app["application_id"], "done")

    def test_checklist_locked_after_submit(self):
        app = application_store.create_application(_sample_plan(), _CHECKLIST)
        aid = app["application_id"]
        application_store.update_status(aid, "ready")
        application_store.update_status(aid, "submitted")
        with self.assertRaises(application_store.InvalidTransition):
            application_store.set_item_checked(aid, app["checklist"][0]["item_id"], True)

    def test_find_active_application_idempotency(self):
        plan = _sample_plan(doc_id="policies_processed:P002", user_id="user-x")
        created = application_store.create_application(plan, _CHECKLIST)
        found = application_store.find_active_application("user-x", "policies_processed:P002")
        self.assertEqual(found["application_id"], created["application_id"])
        # done 처리 후에는 활성 건이 아님
        application_store.update_status(created["application_id"], "ready")
        application_store.update_status(created["application_id"], "submitted")
        application_store.update_status(created["application_id"], "done")
        self.assertIsNone(application_store.find_active_application("user-x", "policies_processed:P002"))


if __name__ == "__main__":
    unittest.main()
