"""실데이터 검증에서 발견된 F2 회귀 버그 테스트.

발견 사례 (2026-06-12, 실제 youth_policy.db):
1. submit_docs에 URL이 섞이면 체크리스트가 URL 조각으로 깨짐
2. submit_docs가 없는 소스(loan/rental_house 등)는 무의미한 기본 서류만 표시
3. 추천기가 '상시'로 통과시킨 정책에서 과거 마감일이 추출되어
   플랜이 생성 즉시 expired 처리됨
"""
import unittest

from tests.util_fixture import set_test_env

set_test_env()


class SplitDocumentsTest(unittest.TestCase):
    def test_url_in_submit_docs_is_not_shredded(self):
        # 실데이터: 주거안정장학금 submit_docs 형태
        from ai.apply_agent import _split_documents

        text = "한국장학재단 홈페이지(https://www.kosaf.go.kr/ko/scholar.do?pg=a), 주민등록등본, 임대차계약서 사본"
        items = _split_documents(text)
        self.assertIn("주민등록등본", items)
        self.assertIn("임대차계약서 사본", items)
        for item in items:
            self.assertNotIn("www.", item)
            self.assertNotIn("http", item)
            self.assertNotEqual(item.lower(), "ko")

    def test_plain_docs_still_split(self):
        from ai.apply_agent import _split_documents

        items = _split_documents("주민등록등본 1부, 가족관계증명서, 통장사본")
        self.assertEqual(len(items), 3)


class DomainDefaultDocumentsTest(unittest.TestCase):
    def test_loan_without_submit_docs_gets_loan_documents(self):
        # 실데이터: smallloan_youth(월세자금보증 등)는 submit_docs 컬럼이 없음
        from ai.apply_agent import build_checklist

        context = {"domain": "loan", "original": {}, "target": ""}
        items = build_checklist(context, [], "online", "https://example.com", "상시")
        doc_labels = [i["label"] for i in items if i["kind"] == "document"]
        self.assertTrue(any("소득 증빙" in label for label in doc_labels))
        self.assertNotIn("공고문에서 제출 서류 확인", doc_labels)

    def test_rental_house_without_url_gets_portal_link(self):
        # 실데이터: rental_houses는 신청 URL이 없어 contact 채널이 됨
        from ai.apply_agent import build_checklist

        context = {"domain": "rental_house", "original": {}, "target": ""}
        items = build_checklist(context, [], "contact", "", "상시")
        contact_items = [i for i in items if i["kind"] == "action" and "문의" in i["label"]]
        self.assertTrue(contact_items)
        self.assertIn("myhome", contact_items[0].get("help_url") or "")

    def test_unknown_domain_keeps_generic_fallback(self):
        from ai.apply_agent import build_checklist

        context = {"domain": "policy", "original": {}, "target": ""}
        items = build_checklist(context, [], "online", "https://example.com", "상시")
        doc_labels = [i["label"] for i in items if i["kind"] == "document"]
        self.assertIn("신분증", doc_labels)


class StaleDeadlineTest(unittest.TestCase):
    def test_past_date_in_source_is_treated_as_open(self):
        # 실데이터: 추천기는 활성으로 판단했는데 원문 apply_period에 지난 기수
        # 날짜가 남아 있으면 과거 마감일이 추출되어 즉시 expired 되던 버그
        from ai.apply_agent import compute_deadline

        deadline, days_left = compute_deadline(
            {"search_document": {"apply_end_date": "2020-01-01"}, "original": {}}
        )
        self.assertEqual(deadline, "상시")
        self.assertIsNone(days_left)

    def test_future_date_still_returned(self):
        from ai.apply_agent import compute_deadline

        deadline, days_left = compute_deadline(
            {"search_document": {"apply_end_date": "2099-12-31"}, "original": {}}
        )
        self.assertEqual(deadline, "2099-12-31")
        self.assertGreater(days_left, 0)


if __name__ == "__main__":
    unittest.main()
