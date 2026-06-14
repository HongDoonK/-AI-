"""의도 라우터 단위 테스트 (규칙 기반, DB 불필요)."""
import unittest

from tests.util_fixture import set_test_env

set_test_env()

from ai.intent_router import (
    APPLY_HOW,
    BENEFIT,
    DOCS,
    ELIGIBILITY,
    RECOMMEND,
    SELECT,
    UNCLEAR,
    classify_intent,
    detect_selection,
)


class DetectSelectionTest(unittest.TestCase):
    def test_policy_number(self):
        self.assertEqual(detect_selection("정책 3 신청할래"), 3)
        self.assertEqual(detect_selection("정책3"), 3)

    def test_nth_form(self):
        self.assertEqual(detect_selection("2번 할래"), 2)
        self.assertEqual(detect_selection("1번째 정책"), 1)

    def test_korean_ordinal(self):
        self.assertEqual(detect_selection("세번째 거"), 3)

    def test_none(self):
        self.assertIsNone(detect_selection("얼마 받을 수 있어?"))


class ClassifyIntentTest(unittest.TestCase):
    def test_recommend_without_selection(self):
        self.assertEqual(classify_intent("서울 26살 목돈 마련 정책 없나?", has_selected=False), RECOMMEND)

    def test_select_takes_priority(self):
        self.assertEqual(classify_intent("정책 2 신청할래", has_selected=True), SELECT)

    def test_benefit_beats_eligibility_for_how_much(self):
        # '받을 수'가 eligibility 키워드와 겹쳐도 '얼마'가 있으면 benefit
        self.assertEqual(classify_intent("얼마나 받을 수 있어?", has_selected=True), BENEFIT)

    def test_docs(self):
        self.assertEqual(classify_intent("필요한 서류 뭐야?", has_selected=True), DOCS)

    def test_eligibility(self):
        self.assertEqual(classify_intent("내가 신청 자격 되나?", has_selected=True), ELIGIBILITY)

    def test_apply_how(self):
        self.assertEqual(classify_intent("이거 신청 방법 알려줘", has_selected=True), APPLY_HOW)

    def test_unclear(self):
        self.assertEqual(classify_intent("음 그렇구나", has_selected=True), UNCLEAR)

    def test_empty(self):
        self.assertEqual(classify_intent("", has_selected=False), UNCLEAR)


if __name__ == "__main__":
    unittest.main()
