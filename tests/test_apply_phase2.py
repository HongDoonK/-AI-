"""Phase 2: LLM 초안 fallback, 적격성 확장, 마감 만료/정렬 테스트."""
import os
import tempfile
import unittest

from tests.util_fixture import set_test_env

set_test_env()

_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["USER_DB_PATH"] = _tmp.name

from backend import application_store


class DraftFallbackTest(unittest.TestCase):
    def test_draft_is_none_when_llm_disabled(self):
        from ai.apply_agent import generate_draft_answers

        self.assertIsNone(generate_draft_answers({"title": "테스트 정책"}, {"age": 24}))

    def test_build_plan_includes_no_draft_without_llm(self):
        from ai.apply_agent import ApplyAgent

        plan = ApplyAgent().build_plan(
            {"doc_id": "policies_processed:P001", "source_table": "policies_processed", "source_id": "P001"},
            {"age": 24, "region_sido": "서울"},
        )
        self.assertIsNone(plan["draft_answers"])


class EligibilityPhase2Test(unittest.TestCase):
    def test_employment_condition_adds_note(self):
        from ai.apply_agent import check_eligibility

        context = {"region_sido": "전국", "employment_status": "미취업"}
        eligibility, notes = check_eligibility(context, {"age": 24, "region_sido": "서울", "employment_status": "재직"})
        self.assertEqual(eligibility, "needs_info")
        self.assertTrue(any(n["field"] == "employment_status" for n in notes))

    def test_matching_employment_adds_no_note(self):
        from ai.apply_agent import check_eligibility

        context = {"region_sido": "전국", "employment_status": "미취업"}
        eligibility, notes = check_eligibility(context, {"age": 24, "employment_status": "미취업"})
        self.assertEqual(eligibility, "ok")

    def test_income_condition_without_profile_income(self):
        from ai.apply_agent import check_eligibility

        context = {"region_sido": "전국", "original": {"income_type": "중위소득 150% 이하"}}
        eligibility, notes = check_eligibility(context, {"age": 24})
        self.assertEqual(eligibility, "needs_info")
        self.assertTrue(any(n["field"] == "income" for n in notes))


class DeadlineLifecycleTest(unittest.TestCase):
    @staticmethod
    def _plan(doc_id, deadline, user_id="user-p2"):
        return {
            "user_id": user_id,
            "doc_id": doc_id,
            "source_table": "policies_processed",
            "source_id": "P001",
            "policy_name": "테스트",
            "eligibility": "ok",
            "eligibility_notes": [],
            "apply_channel": "online",
            "apply_url": "https://example.com",
            "apply_deadline": deadline,
            "draft_answers": None,
        }

    _ITEMS = [{"kind": "action", "label": "신청"}]

    def test_days_left_of(self):
        from datetime import date, timedelta

        self.assertIsNone(application_store.days_left_of("상시"))
        self.assertIsNone(application_store.days_left_of(None))
        self.assertIsNone(application_store.days_left_of("이상한값"))
        tomorrow = (date.today() + timedelta(days=1)).isoformat()
        self.assertEqual(application_store.days_left_of(tomorrow), 1)

    def test_overdue_application_expires_on_read(self):
        app = application_store.create_application(self._plan("doc:overdue", "2020-01-01"), self._ITEMS)
        fetched = application_store.get_application(app["application_id"])
        self.assertEqual(fetched["status"], "expired")

    def test_submitted_application_does_not_expire(self):
        app = application_store.create_application(self._plan("doc:submitted", "2020-01-01"), self._ITEMS)
        aid = app["application_id"]
        # 만료 전이가 일어나기 전에 제출 상태로 이동
        conn = application_store._connect()
        conn.execute("UPDATE applications SET status='submitted' WHERE application_id=?", (aid,))
        conn.commit()
        conn.close()
        fetched = application_store.get_application(aid)
        self.assertEqual(fetched["status"], "submitted")

    def test_list_sorted_by_urgency_active_first(self):
        from datetime import date, timedelta

        user = "user-sort"
        soon = (date.today() + timedelta(days=2)).isoformat()
        later = (date.today() + timedelta(days=30)).isoformat()
        application_store.create_application(self._plan("doc:later", later, user), self._ITEMS)
        application_store.create_application(self._plan("doc:open", "상시", user), self._ITEMS)
        application_store.create_application(self._plan("doc:soon", soon, user), self._ITEMS)
        application_store.create_application(self._plan("doc:past", "2020-01-01", user), self._ITEMS)

        listed = application_store.list_applications(user)
        doc_ids = [item["doc_id"] for item in listed]
        self.assertEqual(doc_ids[0], "doc:soon")      # 마감 임박 우선
        self.assertEqual(doc_ids[1], "doc:later")
        self.assertEqual(doc_ids[2], "doc:open")      # 상시는 뒤
        self.assertEqual(doc_ids[3], "doc:past")      # expired는 마지막
        self.assertEqual(listed[3]["status"], "expired")
        self.assertEqual(listed[0]["days_left"], 2)


if __name__ == "__main__":
    unittest.main()
