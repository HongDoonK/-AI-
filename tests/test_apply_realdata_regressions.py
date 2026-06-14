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
    def test_non_http_application_site_is_treated_as_online(self):
        # 실데이터: smallloan_youth의 신청 경로가 "www.kosaf.go.kr"처럼
        # http scheme 없이 들어와도 온라인 신청 채널로 안내해야 한다.
        from ai.apply_agent import resolve_channel

        channel, url = resolve_channel({
            "url": "재단 홈페이지(www.kosaf.go.kr) > 학자금대출 > 학자금대출 신청",
            "original": {
                "jnMthd": "한국장학재단 홈페이지(www.kosaf.go.kr) 또는 모바일 앱에서 신청",
                "rltSite": "재단 홈페이지(www.kosaf.go.kr) > 학자금대출 > 학자금대출 신청",
            },
        })
        self.assertEqual(channel, "online")
        self.assertTrue(url.startswith("https://"))
        self.assertIn("kosaf.go.kr", url)

    def test_loan_without_submit_docs_gets_loan_documents(self):
        # 실데이터: smallloan_youth(월세자금보증 등)는 submit_docs 컬럼이 없음
        from ai.apply_agent import build_checklist

        context = {"domain": "loan", "original": {}, "target": ""}
        items = build_checklist(context, [], "online", "https://example.com", "상시")
        doc_labels = [i["label"] for i in items if i["kind"] == "document"]
        self.assertTrue(any("소득 증빙" in label for label in doc_labels))
        self.assertNotIn("공고문에서 제출 서류 확인", doc_labels)

    def test_student_loan_uses_student_documents_not_rental_documents(self):
        from ai.apply_agent import build_checklist

        context = {
            "domain": "loan",
            "source_table": "smallloan_youth",
            "title": "취업 후 상환 학자금대출(등록금)",
            "summary": "한국장학재단 학자금대출",
            "original": {},
            "target": "국내 고등교육기관 학부생 및 대학원생",
        }
        items = build_checklist(context, [], "online", "https://www.kosaf.go.kr/", "상시")
        doc_labels = [i["label"] for i in items if i["kind"] == "document"]
        self.assertFalse(any("임대차계약서" in label for label in doc_labels))
        self.assertTrue(any("재학" in label or "학자금" in label for label in doc_labels))

    def test_vague_finance_submit_docs_are_supplemented(self):
        # 실데이터: 청년내일저축계좌처럼 submit_docs가 "첨부파일 참고" 수준이면
        # 사용자가 바로 준비할 수 있는 기본 금융/자산형성 서류를 보강한다.
        from ai.apply_agent import build_checklist

        context = {
            "domain": "policy_finance",
            "title": "청년내일저축계좌",
            "original": {"submit_docs": "※첨부파일 참고"},
            "target": "근로 청년",
        }
        items = build_checklist(context, [], "online", "https://example.com", "상시")
        doc_labels = [i["label"] for i in items if i["kind"] == "document"]
        self.assertGreaterEqual(len(doc_labels), 3)
        self.assertTrue(any("소득" in label or "근로" in label for label in doc_labels))

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
