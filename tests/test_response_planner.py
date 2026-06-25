import unittest

from ai.response_planner import ResponsePlan, ResponsePlanner


POLICY = {
    "doc_id": "policies_processed:P001",
    "source_table": "policies_processed",
    "source_id": "P001",
    "domain": "policy_housing",
}


class ResponsePlannerTest(unittest.TestCase):
    def setUp(self):
        self.planner = ResponsePlanner()

    def test_same_context_returns_same_plan(self):
        kwargs = {
            "policy_context": POLICY,
            "intent": "benefit",
            "question": "그래서 총 얼마 받을 수 있어?",
            "user_context": {"age": 24, "region_sido": "서울"},
            "conversation_context": [],
        }
        self.assertEqual(self.planner.plan(**kwargs), self.planner.plan(**kwargs))

    def test_specific_benefit_question_focuses_total_amount(self):
        plan = self.planner.plan(
            policy_context=POLICY,
            intent="benefit",
            question="총 얼마 받을 수 있어?",
            user_context={},
            conversation_context=[],
        )
        self.assertEqual(plan.focus, "total_amount")
        self.assertEqual(plan.section_order[0], "amount")
        self.assertEqual(plan.detail_level, "focused")

    def test_missing_profile_focuses_required_user_information(self):
        plan = self.planner.plan(
            policy_context=POLICY,
            intent="eligibility",
            question="내가 신청 가능해?",
            user_context={},
            conversation_context=[],
        )
        self.assertEqual(plan.focus, "missing_user_condition")
        self.assertEqual(plan.follow_up_kind, "missing_user_condition")
        self.assertEqual(plan.section_order[0], "missing_info")

    def test_exact_repeat_becomes_confirm(self):
        history = [
            {"role": "user", "content": "필요한 서류가 뭐야?"},
            {
                "role": "assistant",
                "intent": "docs",
                "content": "서류 안내",
                "payload": {
                    "response_plan_meta": {
                        "focus": "document_preparation",
                        "repetition_mode": "fresh",
                    }
                },
            },
        ]
        plan = self.planner.plan(
            policy_context=POLICY,
            intent="docs",
            question="필요한 서류가 뭐야?",
            user_context={},
            conversation_context=history,
        )
        self.assertEqual(plan.repetition_mode, "confirm")
        self.assertEqual(plan.detail_level, "compact")

    def test_more_specific_repeat_becomes_clarify(self):
        history = [
            {"role": "user", "content": "필요한 서류가 뭐야?"},
            {"role": "assistant", "intent": "docs", "content": "서류 안내", "payload": None},
        ]
        plan = self.planner.plan(
            policy_context=POLICY,
            intent="docs",
            question="주민등록등본은 어디서 발급해?",
            user_context={},
            conversation_context=history,
        )
        self.assertEqual(plan.repetition_mode, "clarify")
        self.assertEqual(plan.focus, "issuance")
        self.assertEqual(plan.section_order[0], "issuance")

    def test_previous_follow_up_kind_is_not_reused_when_alternative_exists(self):
        history = [
            {
                "role": "assistant",
                "intent": "docs",
                "content": "서류 안내",
                "payload": {
                    "response_plan_meta": {
                        "follow_up_kind": "eligibility",
                    }
                },
            }
        ]
        plan = self.planner.plan(
            policy_context=POLICY,
            intent="docs",
            question="서류 알려줘",
            user_context={"age": 24, "region_sido": "서울"},
            conversation_context=history,
        )
        self.assertNotEqual(plan.follow_up_kind, "eligibility")

    def test_apply_deadline_question_puts_period_first(self):
        plan = self.planner.plan(
            policy_context=POLICY,
            intent="apply_how",
            question="신청 마감이 언제야?",
            user_context={},
            conversation_context=[],
        )
        self.assertEqual(plan.focus, "deadline_risk")
        self.assertEqual(plan.section_order[0], "period")


if __name__ == "__main__":
    unittest.main()
