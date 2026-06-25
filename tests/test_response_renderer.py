import unittest

from ai.response_planner import ResponsePlan
from ai.response_renderer import (
    order_actions,
    ordered_section_keys,
    render_follow_up,
    render_opening,
    section_item_limit,
)


class ResponseRendererTest(unittest.TestCase):
    def _plan(self, **overrides):
        values = {
            "focus": "total_amount",
            "section_order": ("amount", "duration", "next_step"),
            "detail_level": "focused",
            "opening_variant": "direct",
            "repetition_mode": "fresh",
            "follow_up_kind": "eligibility",
            "suggested_action_order": ("eligibility", "docs", "create_apply_plan"),
        }
        values.update(overrides)
        return ResponsePlan(**values)

    def test_section_order_uses_plan_and_keeps_unknown_sections_last(self):
        plan = self._plan()
        keys = ordered_section_keys(plan, {"duration", "amount", "contact"})
        self.assertEqual(keys, ["amount", "duration", "contact"])

    def test_compact_repeat_limits_items(self):
        plan = self._plan(detail_level="compact", repetition_mode="confirm")
        self.assertEqual(section_item_limit(plan), 2)

    def test_opening_changes_for_confirm_mode(self):
        plan = self._plan(repetition_mode="confirm")
        opening = render_opening("청년 월세 지원", "benefit", plan)
        self.assertIn("다시 핵심만", opening)

    def test_follow_up_is_selected_from_plan(self):
        plan = self._plan(follow_up_kind="eligibility")
        self.assertIn("조건", render_follow_up(plan, "통합청년 정책"))

    def test_actions_follow_planned_order(self):
        plan = self._plan()
        actions = [
            {"label": "서류", "intent": "docs"},
            {"label": "준비", "action": "create_apply_plan"},
            {"label": "자격", "intent": "eligibility"},
        ]
        ordered = order_actions(actions, plan)
        self.assertEqual([item.get("intent") or item.get("action") for item in ordered],
                         ["eligibility", "docs", "create_apply_plan"])


if __name__ == "__main__":
    unittest.main()
