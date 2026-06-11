"""recommend_policy() 통합 smoke test — fixture DB + 규칙 기반 fallback."""
import unittest

from tests.util_fixture import set_test_env

set_test_env()


class RecommenderSmokeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        set_test_env()

    def test_recommend_returns_results_for_housing_query(self):
        from ai.recommender import recommend_policy

        result = recommend_policy("서울 사는 24세 대학생인데 월세 지원 정책 알려줘")
        self.assertIn("user_condition", result)
        self.assertIn("recommendations", result)
        self.assertEqual(result.get("message", ""), "")
        self.assertGreater(len(result["recommendations"]), 0)
        first = result["recommendations"][0]
        for key in ["policy_name", "reason", "application_period", "checklist"]:
            self.assertIn(key, first)

    def test_recommend_rejects_input_without_condition(self):
        from ai.recommender import recommend_policy

        result = recommend_policy("안녕")
        self.assertEqual(result["recommendations"], [])
        self.assertTrue(result["message"])

    def test_age_filter_excludes_out_of_range_policy(self):
        from ai.recommender import recommend_policy

        result = recommend_policy("서울 사는 24세 청년 금융 정책 추천")
        names = [r["policy_name"] for r in result["recommendations"]]
        self.assertNotIn("고연령 제외 테스트 정책", names)


if __name__ == "__main__":
    unittest.main()
