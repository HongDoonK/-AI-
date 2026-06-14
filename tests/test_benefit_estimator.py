"""BenefitEstimator(정보 Agent) 단위 테스트.

context dict를 직접 입력하므로 DB는 불필요하다. set_test_env()로 LLM을 꺼서
규칙 기반 경로만 검증한다 (LLM 보강 경로는 비활성 시 _unknown으로 떨어짐).
"""
import unittest

from tests.util_fixture import set_test_env

set_test_env()

from ai.benefit_estimator import estimate_benefit, format_won


def _cash(text: str) -> dict:
    return {"source_table": "policies_processed", "original": {"support_content": text}}


class FormatWonTest(unittest.TestCase):
    def test_man_unit(self):
        self.assertEqual(format_won(500_000), "50만원")
        self.assertEqual(format_won(10_800_000), "1,080만원")

    def test_eok_unit(self):
        self.assertEqual(format_won(200_000_000), "2억원")
        self.assertEqual(format_won(120_000_000), "1억2,000만원")

    def test_non_round_falls_back_to_won(self):
        self.assertEqual(format_won(330_600), "330,600원")

    def test_zero_and_none(self):
        self.assertEqual(format_won(0), "")
        self.assertEqual(format_won(None), "")


class CashBenefitTest(unittest.TestCase):
    def test_monthly_times_months(self):
        result = estimate_benefit(_cash("(금전적 지원) 매월 50만원×최대 6개월간 지급 ※ 생애 1회"))
        self.assertEqual(result["kind"], "cash")
        self.assertEqual(result["monthly_won"], 500_000)
        self.assertEqual(result["months"], 6)
        self.assertEqual(result["total_won"], 3_000_000)
        self.assertEqual(result["confidence"], "exact")
        self.assertIn("300만원", result["summary_line"])

    def test_years_converted_to_months_with_explicit_total(self):
        result = estimate_benefit(_cash("월 30만원씩 지역화폐로 최대 3년간 지급(1인당 최대 1,080만원)"))
        self.assertEqual(result["months"], 36)
        self.assertEqual(result["monthly_won"], 300_000)
        self.assertEqual(result["total_won"], 10_800_000)

    def test_monthly_without_period_is_estimated(self):
        result = estimate_benefit(_cash("매월 20만원 지원"))
        self.assertEqual(result["kind"], "cash")
        self.assertEqual(result["monthly_won"], 200_000)
        self.assertIsNone(result["months"])
        self.assertEqual(result["confidence"], "estimated")
        self.assertIn("공고", result["summary_line"])


class LoanBenefitTest(unittest.TestCase):
    def test_loan_from_text(self):
        text = "1. 대출한도: 최대 5백만원\n2. 대출금리: 연 4.5% 이내\n3. 대출기간: 최대 11년(거치 6년)"
        result = estimate_benefit(_cash(text))
        self.assertEqual(result["kind"], "loan")
        self.assertEqual(result["limit_won"], 5_000_000)
        self.assertIn("4.5", result["rate_text"])
        self.assertEqual(result["term_months"], 132)

    def test_loan_from_smallloan_fields(self):
        ctx = {"source_table": "smallloan_youth",
               "original": {"lnLmt": "20000만원", "irt": "3.052~3.72%", "maxTotLnTrm": "3년"}}
        result = estimate_benefit(ctx)
        self.assertEqual(result["kind"], "loan")
        self.assertEqual(result["limit_won"], 200_000_000)
        self.assertIn("2억원", result["summary_line"])

    def test_loan_missing_fields_check_notice(self):
        ctx = {"source_table": "smallloan_youth", "original": {"lnLmt": "-", "irt": "-", "maxTotLnTrm": "-"}}
        result = estimate_benefit(ctx)
        self.assertEqual(result["kind"], "loan")
        self.assertEqual(result["confidence"], "check_notice")


class HousingBenefitTest(unittest.TestCase):
    def test_myhome_deposit_and_rent(self):
        ctx = {"source_table": "myhome_notices", "original": {"deposit": 69_600_000, "monthly_rent": 330_600}}
        result = estimate_benefit(ctx)
        self.assertEqual(result["kind"], "housing")
        self.assertEqual(result["deposit_won"], 69_600_000)
        self.assertEqual(result["monthly_rent_won"], 330_600)
        self.assertIn("보증금", result["summary_line"])

    def test_rental_house_zero_values_check_notice(self):
        ctx = {"source_table": "rental_houses", "original": {"bassRentGtn": 0, "bassMtRntchrg": 0}}
        result = estimate_benefit(ctx)
        self.assertEqual(result["confidence"], "check_notice")


class TrainingBenefitTest(unittest.TestCase):
    def test_training_bare_integer_won(self):
        ctx = {"source_table": "hrd_trainings", "original": {"real_man": "1000000", "course_man": "1000000"}}
        result = estimate_benefit(ctx)
        self.assertEqual(result["kind"], "training")
        self.assertEqual(result["course_won"], 1_000_000)
        self.assertIn("100만원", result["summary_line"])


class UnknownBenefitTest(unittest.TestCase):
    def test_no_amount_falls_to_check_notice(self):
        result = estimate_benefit(_cash("재무상담 및 자산관리 교육 운영"))
        self.assertEqual(result["kind"], "unknown")
        self.assertEqual(result["confidence"], "check_notice")

    def test_empty_context(self):
        result = estimate_benefit({"source_table": "policies_processed", "original": {}})
        self.assertEqual(result["kind"], "unknown")


if __name__ == "__main__":
    unittest.main()
