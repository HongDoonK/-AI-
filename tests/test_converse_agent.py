"""ConverseAgent 오케스트레이션 테스트 (fixture DB, 규칙 기반)."""
import unittest

from tests.util_fixture import set_test_env

set_test_env()

from ai.converse_agent import ConverseAgent

# fixture search_documents/policies_processed에 존재하는 정책 (월 20만원 최대 12개월)
P001 = {
    "rank": 1,
    "doc_id": "policies_processed:P001",
    "source_table": "policies_processed",
    "source_id": "P001",
    "title": "청년 월세 지원",
    "domain": "policy_housing",
}


class ConverseAgentTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.agent = ConverseAgent()

    def test_recommend_returns_cards_and_resets_selection(self):
        result = self.agent.respond(
            message="서울 무주택 청년인데 월세 지원 정책 없나?",
            selected_policy=P001,
            last_recommendations=[],
            profile=None,
        )
        self.assertEqual(result["intent"], "recommend")
        self.assertTrue(result["cards"], "추천 카드가 비어 있으면 안 됨")
        self.assertIsNone(result["selected_policy"], "추천 시 이전 선택은 해제되어야 함")
        self.assertEqual(result["last_recommendations"], result["cards"])

    def test_select_by_ordinal_sets_policy(self):
        result = self.agent.respond(
            message="정책 1이 좋아",
            selected_policy=None,
            last_recommendations=[P001],
            profile=None,
        )
        self.assertEqual(result["intent"], "select")
        self.assertEqual(result["selected_policy"]["doc_id"], "policies_processed:P001")

    def test_select_direct_policy_ref_without_message(self):
        result = self.agent.select(P001)
        self.assertEqual(result["intent"], "select")
        self.assertEqual(result["selected_policy"]["doc_id"], "policies_processed:P001")
        self.assertIn("무엇을 먼저 볼까요", result["reply"])
        self.assertEqual(
            [action["intent"] for action in result["suggested_actions"]],
            ["docs", "benefit", "eligibility"],
        )

    def test_benefit_is_quantified(self):
        result = self.agent.respond(
            message="얼마나 받을 수 있어?",
            selected_policy=P001,
            last_recommendations=[P001],
            profile=None,
        )
        self.assertEqual(result["intent"], "benefit")
        self.assertEqual(result["benefit"]["kind"], "cash")
        self.assertEqual(result["benefit"]["monthly_won"], 200_000)
        self.assertEqual(result["benefit"]["months"], 12)
        self.assertIn("240만원", result["reply"])

    def test_docs_lists_documents(self):
        result = self.agent.respond(
            message="필요한 서류 뭐야?",
            selected_policy=P001,
            last_recommendations=[P001],
            profile={"age": 26, "region_sido": "서울"},
        )
        self.assertEqual(result["intent"], "docs")
        self.assertTrue(result["documents"])

    def test_need_select_when_no_policy(self):
        result = self.agent.respond(
            message="얼마 받아?",
            selected_policy=None,
            last_recommendations=[],
            profile=None,
        )
        self.assertEqual(result["intent"], "need_select")
        self.assertIsNone(result["selected_policy"])

    def test_select_with_docs_request_returns_documents(self):
        # 선택 정책 없이 '정책 N + 서류'를 물으면 선택과 서류 안내를 한 번에 처리
        result = self.agent.respond(
            message="정책 1 서류 보여줘",
            selected_policy=None,
            last_recommendations=[P001],
            profile=None,
        )
        self.assertEqual(result["intent"], "docs")
        self.assertEqual(result["selected_policy"]["doc_id"], "policies_processed:P001")
        self.assertTrue(result["documents"])

    def test_select_with_apply_intent_returns_application_documents(self):
        result = self.agent.respond(
            message="정책 1 이 마음에 드네 이걸로 신청해봐야겠어.",
            selected_policy=None,
            last_recommendations=[P001],
            profile={"age": 24, "region_sido": "서울"},
        )
        self.assertEqual(result["intent"], "docs")
        self.assertEqual(result["selected_policy"]["doc_id"], "policies_processed:P001")
        self.assertTrue(result["documents"])
        self.assertIn("신청 페이지", result["reply"])


if __name__ == "__main__":
    unittest.main()
