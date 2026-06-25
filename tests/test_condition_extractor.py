"""규칙 기반 조건 추출 테스트 (LLM 비활성 상태)."""
import os
import unittest

os.environ["LLM_PROVIDER"] = "none"  # ADR-002 §D2
os.environ["USE_OPENAI_LLM"] = "0"   # 레거시 호환

from ai.condition_extractor import extract_user_condition, has_condition_signal


class ConditionExtractorTest(unittest.TestCase):
    def test_extracts_age_region_status_interest(self):
        condition = extract_user_condition("서울 관악구 사는 24세 대학생인데 주거 정책 추천해줘")
        self.assertEqual(condition.get("age"), 24)
        self.assertIn("서울", str(condition.get("region") or condition.get("region_sido")))
        self.assertEqual(condition.get("status"), "대학생")
        self.assertEqual(condition.get("interest"), "주거")

    def test_extracts_employment_status(self):
        condition = extract_user_condition("28살 직장인이고 적금 같은 금융 지원이 궁금해")
        self.assertEqual(condition.get("age"), 28)
        self.assertEqual(condition.get("employment_status"), "재직")
        self.assertEqual(condition.get("interest"), "금융")

    def test_culture_life_is_culture_interest_not_generic_welfare(self):
        condition = extract_user_condition("서울 사는 24세 청년인데 문화생활 지원 정책 없나?")
        self.assertEqual(condition.get("interest"), "문화")

    def test_living_expense_loan_is_finance_interest_not_welfare(self):
        condition = extract_user_condition("서울 사는 24세 청년인데 생활비 대출 필요해")
        self.assertEqual(condition.get("interest"), "금융")

    def test_extracts_chungbuk_cheongju_sigungu(self):
        # REGION_CODE_MAP의 충북에는 청주시가 구 단위로만 있어 보충 인식이 필요하다.
        condition = extract_user_condition("충북 청주시 24살 대학생 월세 지원 알려줘")
        self.assertEqual(condition.get("region_sido"), "충북")
        self.assertEqual(condition.get("region_sigungu"), "청주시")

    def test_has_condition_signal_true_for_specific_input(self):
        self.assertTrue(has_condition_signal("부산 사는 30세 예비창업자입니다"))

    def test_has_condition_signal_false_for_greeting(self):
        self.assertFalse(has_condition_signal("안녕"))


if __name__ == "__main__":
    unittest.main()
