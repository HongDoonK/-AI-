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

    def test_loan_query_still_ranks_loans_first(self):
        results = retrieve_top_k("서울 24세 청년인데 생활비 대출 필요해", self.condition, self.df, top_k=5)
        self.assertEqual(results[0]["domain"], "loan")


if __name__ == "__main__":
    unittest.main()
