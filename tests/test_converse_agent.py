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

    def test_chat_recommendation_attempt_returns_guidance_with_existing_cards(self):
        # 하드 분리: 채팅 추천 요청은 새 추천을 생성하지 않고, Hero로 안내 + 기존 시드 카드 재노출
        result = self.agent.respond(
            message="다른 정책도 추천해줘",
            selected_policy=None,
            last_recommendations=[P001],
            profile=None,
        )
        self.assertEqual(result["intent"], "need_recommendation")
        self.assertIn("나의 상황 입력", result["reply"])
        self.assertEqual(result["cards"], [P001], "새 목록이 아니라 기존 시드 그대로여야 함")

    def test_chat_recommendation_attempt_without_cards_points_to_hero(self):
        result = self.agent.respond(
            message="정책 찾아줘",
            selected_policy=None,
            last_recommendations=[],
            profile=None,
        )
        self.assertEqual(result["intent"], "need_recommendation")
        self.assertIn("나의 상황 입력", result["reply"])
        self.assertEqual(result["cards"], [])

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

    def test_apply_how_returns_apply_detail(self):
        """APPLY_HOW 의도 — 신청 방법·기간·링크·문의처 반환."""
        result = self.agent.respond(
            message="신청 방법 알려줘",
            selected_policy=P001,
            last_recommendations=[P001],
            profile=None,
        )
        self.assertEqual(result["intent"], "apply_how")
        self.assertIn("apply_detail", result)
        detail = result["apply_detail"]
        self.assertIsInstance(detail, dict, "apply_detail은 딕셔너리여야 함")
        self.assertIn("신청 방법", result["reply"])

    def test_eligibility_without_profile_returns_needs_info(self):
        """프로필 없이 적격성 요청 시 프로필 입력 안내를 반환해야 함."""
        result = self.agent.respond(
            message="내가 신청 자격 되는지 확인해줘",
            selected_policy=P001,
            last_recommendations=[P001],
            profile=None,
        )
        self.assertEqual(result["intent"], "eligibility")
        self.assertEqual(result["eligibility"], "needs_info")
        self.assertIn("프로필", result["reply"])
        self.assertTrue(result["eligibility_notes"])


if __name__ == "__main__":
    unittest.main()
