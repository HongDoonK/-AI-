"""ApplyAgent 단위 테스트 (fixture DB, 규칙 기반)."""
import unittest

from tests.util_fixture import set_test_env

set_test_env()


class ApplyAgentUnitTest(unittest.TestCase):
    def test_check_eligibility_ok(self):
        from ai.apply_agent import check_eligibility

        context = {"min_age": "19", "max_age": "34", "region_sido": "서울", "region_name": "서울"}
        profile = {"age": 24, "region_sido": "서울"}
        eligibility, notes = check_eligibility(context, profile)
        self.assertEqual(eligibility, "ok")
        self.assertEqual(notes, [])

    def test_check_eligibility_age_out_of_range(self):
        from ai.apply_agent import check_eligibility

        context = {"min_age": "19", "max_age": "34", "region_sido": "전국"}
        eligibility, notes = check_eligibility(context, {"age": 40})
        self.assertEqual(eligibility, "ineligible")
        self.assertTrue(any(n["field"] == "age" for n in notes))

    def test_check_eligibility_region_mismatch(self):
        from ai.apply_agent import check_eligibility

        context = {"region_sido": "부산", "region_name": "부산"}
        eligibility, notes = check_eligibility(context, {"age": 24, "region_sido": "서울"})
        self.assertEqual(eligibility, "ineligible")

    def test_check_eligibility_needs_info_when_profile_empty(self):
        from ai.apply_agent import check_eligibility

        context = {"min_age": "19", "max_age": "34", "region_sido": "서울"}
        eligibility, notes = check_eligibility(context, None)
        self.assertEqual(eligibility, "needs_info")
        self.assertEqual(len(notes), 2)

    def test_nationwide_policy_ignores_region(self):
        from ai.apply_agent import check_eligibility

        context = {"region_sido": "전국"}
        eligibility, _ = check_eligibility(context, {"age": 24, "region_sido": "서울"})
        self.assertEqual(eligibility, "ok")

    def test_resolve_channel_online(self):
        from ai.apply_agent import resolve_channel

        channel, url = resolve_channel({"url": "https://example.com/apply", "original": {}})
        self.assertEqual(channel, "online")
        self.assertTrue(url.startswith("https://"))

    def test_resolve_channel_contact_when_no_url(self):
        from ai.apply_agent import resolve_channel

        channel, url = resolve_channel({"url": "", "original": {}})
        self.assertEqual(channel, "contact")
        self.assertEqual(url, "")

    def test_compute_deadline_open_ended(self):
        from ai.apply_agent import compute_deadline

        deadline, days_left = compute_deadline({"search_document": {}, "original": {}, "period": ""})
        self.assertEqual(deadline, "상시")
        self.assertIsNone(days_left)

    def test_compute_deadline_parses_date(self):
        from ai.apply_agent import compute_deadline

        deadline, days_left = compute_deadline(
            {"search_document": {"apply_end_date": "2099-12-31"}, "original": {}}
        )
        self.assertEqual(deadline, "2099-12-31")
        self.assertGreater(days_left, 0)

    def test_build_checklist_includes_documents_and_issuer(self):
        from ai.apply_agent import build_checklist

        context = {
            "original": {"submit_docs": "주민등록등본 1부, 통장사본"},
            "target": "무주택 청년",
        }
        items = build_checklist(context, [], "online", "https://example.com", "2099-12-31")
        kinds = [item["kind"] for item in items]
        self.assertIn("document", kinds)
        self.assertIn("action", kinds)
        register_item = next(item for item in items if "주민등록등본" in item["label"])
        self.assertIn("정부24", register_item["help_label"])
        self.assertTrue(any("무주택" in item["label"] for item in items if item["kind"] == "eligibility"))

    def test_build_plan_end_to_end_with_fixture(self):
        from ai.apply_agent import ApplyAgent

        agent = ApplyAgent()
        plan = agent.build_plan(
            {"doc_id": "policies_processed:P001", "source_table": "policies_processed", "source_id": "P001"},
            {"age": 24, "region_sido": "서울"},
        )
        self.assertEqual(plan["doc_id"], "policies_processed:P001")
        self.assertEqual(plan["eligibility"], "ok")
        self.assertGreater(len(plan["checklist"]), 0)
        self.assertTrue(plan["next_action"])


class DocumentRegistryTest(unittest.TestCase):
    def test_known_documents_have_issuers(self):
        from ai.document_registry import find_issuer

        self.assertIn("정부24", find_issuer("주민등록등본 1부")["help_label"])
        self.assertIn("홈택스", find_issuer("소득금액증명원")["help_label"])
        self.assertIsNone(find_issuer("알 수 없는 서류"))


if __name__ == "__main__":
    unittest.main()
