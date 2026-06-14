"""검색 랭킹 일반화 테스트.

특정 시연 문장 하나를 하드코딩하지 않고, 자산형성/저축 의도와 대출 의도를
분리해 금융 추천 품질이 여러 태스크에서 안정적으로 동작하는지 본다.
"""
import os
import unittest

import pandas as pd

os.environ["USE_FAISS"] = "0"

from ai.retriever import retrieve_top_k


def _row(doc_id: str, domain: str, title: str, text: str) -> dict:
    return {
        "doc_id": doc_id,
        "source_table": "test_source",
        "source_id": doc_id,
        "domain": domain,
        "title": title,
        "policy_name": title,
        "summary": text,
        "search_text": text,
        "region_name": "서울",
        "region_sido": "서울",
        "region_sigungu": "",
        "target": "청년",
        "min_age": 19,
        "max_age": 34,
        "apply_start_date": "",
        "apply_end_date": "",
    }


class RetrieverRankingTest(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame([
            _row("save", "policy_finance", "청년 자산형성 적금", "청년 자산형성 적금 저축 목돈 정부 매칭 서울"),
            _row("edu", "policy_finance", "청년 재테크 교육", "청년 재테크 투자 금융 교육 목돈 서울"),
            _row("account", "policy_finance", "청년 희망 통장", "청년 통장 저축 자산 목돈 서울"),
            _row("loan", "loan", "학자금 대출", "청년 학자금 대출 금융 서울"),
            _row("loan2", "loan", "생활비 대출", "청년 생활비 대출 금융 서울"),
        ])
        self.condition = {"age": 24, "region_sido": "서울", "interest": "금융"}

    def test_asset_building_query_ranks_savings_before_loans(self):
        results = retrieve_top_k("서울 24세 청년인데 목돈 마련하고 싶어", self.condition, self.df, top_k=5)
        doc_ids = [row["doc_id"] for row in results]
        self.assertLess(doc_ids.index("save"), doc_ids.index("loan"))
        self.assertLess(doc_ids.index("account"), doc_ids.index("loan"))

    def test_asset_building_query_prefers_savings_account_over_local_finance_education(self):
        local_education = _row("local_education", "policy_finance", "청년 재테크 교육", "서울 청년 재테크 금융교육 저축 습관 목돈 교육")
        national_savings = _row("national_savings", "policy_finance", "청년내일저축계좌", "청년 저축계좌 적금 매칭 목돈 자산형성 지원 전국")
        national_savings["region_name"] = "전국"
        national_savings["region_sido"] = "전국"
        df = pd.DataFrame([local_education, national_savings])

        results = retrieve_top_k("서울 24세 청년인데 목돈 마련하고 싶어", self.condition, df, top_k=2)

        self.assertEqual(results[0]["doc_id"], "national_savings")

    def test_loan_query_still_ranks_loans_first(self):
        results = retrieve_top_k("서울 24세 청년인데 생활비 대출 필요해", self.condition, self.df, top_k=5)
        self.assertEqual(results[0]["domain"], "loan")

    def test_explicit_loan_intent_beats_local_non_loan_finance(self):
        local_finance = _row("local_finance", "policy_finance", "청년 금융 상담", "서울 청년 금융 상담 지원")
        national_loan = _row("national_loan", "loan", "청년 생활비 대출", "청년 생활비 대출 금융 전국")
        national_loan["region_name"] = "전국"
        national_loan["region_sido"] = "전국"
        df = pd.DataFrame([local_finance, national_loan])

        results = retrieve_top_k("서울 24세 청년인데 생활비 대출 필요해", self.condition, df, top_k=2)

        self.assertEqual(results[0]["doc_id"], "national_loan")

    def test_culture_query_ranks_culture_policy_before_finance(self):
        df = pd.DataFrame([
            _row("culture", "policy", "청년 문화패스", "서울 청년 문화 공연 전시 관람비 지원 문화생활"),
            _row("finance", "policy_finance", "청년 금융교육", "서울 청년 재테크 금융 교육"),
            _row("startup", "startup", "청년 창업 캠프", "서울 청년 창업 사업화 지원"),
        ])
        results = retrieve_top_k(
            "서울 24세 청년인데 문화생활 지원 정책 없나?",
            {"age": 24, "region_sido": "서울", "interest": "문화"},
            df,
            top_k=3,
        )
        self.assertEqual(results[0]["doc_id"], "culture")

    def test_culture_intent_beats_local_generic_policy(self):
        national_culture = _row("national_culture", "policy", "청년 문화 관람비", "청년 문화생활 공연 전시 관람 지원 전국")
        national_culture["region_name"] = "전국"
        national_culture["region_sido"] = "전국"
        local_generic = _row("local_generic", "policy", "청년 정책네트워크", "서울 청년 정책 참여 상담 지원")
        df = pd.DataFrame([local_generic, national_culture])

        results = retrieve_top_k(
            "서울 24세 청년인데 문화생활 지원 정책 없나?",
            {"age": 24, "region_sido": "서울", "interest": "문화"},
            df,
            top_k=2,
        )

        self.assertEqual(results[0]["doc_id"], "national_culture")

    def test_culture_life_intent_prefers_arts_access_over_local_culture_exchange(self):
        national_arts = _row("national_arts", "policy", "청년 문화 관람비", "청년 문화생활 공연 전시 관람비 지원 전국")
        national_arts["region_name"] = "전국"
        national_arts["region_sido"] = "전국"
        local_exchange = _row("local_exchange", "policy", "청년 문화교류 봉사단", "서울 청년 해외 봉사 문화교류 체험 지원")
        df = pd.DataFrame([local_exchange, national_arts])

        results = retrieve_top_k(
            "서울 24세 청년인데 문화생활 지원 정책 없나?",
            {"age": 24, "region_sido": "서울", "interest": "문화"},
            df,
            top_k=2,
        )

        self.assertEqual(results[0]["doc_id"], "national_arts")

    def test_culture_life_intent_does_not_match_performance_inside_major_linkage(self):
        national_arts = _row("national_arts", "policy", "청년 문화 관람비", "청년 문화생활 공연 전시 관람비 지원 전국")
        national_arts["region_name"] = "전국"
        national_arts["region_sido"] = "전국"
        local_volunteer = _row("local_volunteer", "policy", "청년 봉사단", "서울 청년 해외 봉사 전공연계 문화교류 지원")
        df = pd.DataFrame([local_volunteer, national_arts])

        results = retrieve_top_k(
            "서울 24세 청년인데 문화생활 지원 정책 없나?",
            {"age": 24, "region_sido": "서울", "interest": "문화"},
            df,
            top_k=2,
        )

        self.assertEqual(results[0]["doc_id"], "national_arts")

    def test_culture_life_intent_prefers_culture_event_over_local_volunteering(self):
        national_event = _row("national_event", "policy", "청년 문화 행사", "청년 문화 행사 참여비 지원 전국")
        national_event["region_name"] = "전국"
        national_event["region_sido"] = "전국"
        local_volunteer = _row("local_volunteer", "policy", "청년 문화교류 봉사단", "서울 청년 해외 봉사 문화교류 체험 지원")
        df = pd.DataFrame([local_volunteer, national_event])

        results = retrieve_top_k(
            "서울 24세 청년인데 문화생활 지원 정책 없나?",
            {"age": 24, "region_sido": "서울", "interest": "문화"},
            df,
            top_k=2,
        )

        self.assertEqual(results[0]["doc_id"], "national_event")

    def test_housing_query_ranks_housing_before_startup(self):
        df = pd.DataFrame([
            _row("housing", "policy_housing", "청년 월세 지원", "서울 청년 월세 주거 임대료 지원"),
            _row("startup", "policy_startup", "청년 창업 지원금", "서울 청년 창업 사업화 지원금"),
            _row("finance", "policy_finance", "청년 저축 지원", "서울 청년 저축 금융 지원"),
        ])
        results = retrieve_top_k(
            "서울 24세 청년인데 월세 지원 주거 정책 찾아줘",
            {"age": 24, "region_sido": "서울", "interest": "주거", "housing_status": "월세"},
            df,
            top_k=3,
        )
        self.assertEqual(results[0]["doc_id"], "housing")

    def test_monthly_rent_support_intent_beats_local_unit_listing(self):
        local_listing = _row("local_listing", "rental_house", "청년 주택 공급", "서울 청년 주택 공급 입주 안내")
        national_rent_loan = _row("national_rent_loan", "loan", "청년 월세 대출", "청년 월세 임대료 대출 보증금 지원 전국")
        national_rent_loan["region_name"] = "전국"
        national_rent_loan["region_sido"] = "전국"
        df = pd.DataFrame([local_listing, national_rent_loan])

        results = retrieve_top_k(
            "서울 24세 청년인데 월세 지원 주거 정책 찾아줘",
            {"age": 24, "region_sido": "서울", "interest": "주거", "housing_status": "월세"},
            df,
            top_k=2,
        )

        self.assertEqual(results[0]["doc_id"], "national_rent_loan")

    def test_startup_query_ranks_startup_before_general_finance(self):
        df = pd.DataFrame([
            _row("startup", "startup", "청년 창업 사업화 지원", "서울 예비창업자 창업 사업화 자금 지원"),
            _row("finance", "policy_finance", "청년 금융 상담", "서울 청년 금융 상담 지원"),
            _row("culture", "policy", "청년 문화 행사", "서울 청년 문화 행사 지원"),
        ])
        results = retrieve_top_k(
            "서울 29세 예비창업자인데 창업 지원금 있어?",
            {"age": 29, "region_sido": "서울", "interest": "창업", "employment_status": "창업"},
            df,
            top_k=3,
        )
        self.assertEqual(results[0]["doc_id"], "startup")


if __name__ == "__main__":
    unittest.main()
