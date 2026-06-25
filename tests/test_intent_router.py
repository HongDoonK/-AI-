"""의도 라우터 단위 테스트 (규칙 기반, DB 불필요)."""
import unittest

from tests.util_fixture import set_test_env

set_test_env()

from ai.intent_router import (
    APPLY_HOW,
    BENEFIT,
    DOCS,
    ELIGIBILITY,
    NEED_RECOMMENDATION,
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
    def test_recommendation_request_routes_to_guidance(self):
        # 하드 분리: 채팅 추천 요청은 RECOMMEND가 아니라 NEED_RECOMMENDATION(Hero 안내)
        self.assertEqual(
            classify_intent("서울 26살 목돈 마련 정책 없나?", has_selected=False),
            NEED_RECOMMENDATION,
        )
        self.assertEqual(classify_intent("다른 정책 추천해줘", has_selected=True), NEED_RECOMMENDATION)

    def test_selected_policy_intent_beats_recommend_signal(self):
        # R1: 선택 정책이 있으면 '찾아줘'가 붙어도 상담 의도가 우선 (추천 안내로 새지 않음)
        self.assertEqual(classify_intent("지원금 찾아줘", has_selected=True), BENEFIT)
        self.assertEqual(classify_intent("서류 찾아줘", has_selected=True), DOCS)
        self.assertEqual(classify_intent("신청 방법 찾아줘", has_selected=True), APPLY_HOW)

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

    def test_strong_money_signal_is_benefit(self):
        self.assertEqual(classify_intent("얼마 받을 수 있어?", has_selected=True), BENEFIT)
        self.assertEqual(classify_intent("총액 알려줘", has_selected=True), BENEFIT)

    def test_eligibility_signal_beats_weak_support_word(self):
        # 'bare 지원'·'받을 수'만으로 무조건 benefit이 되면 안 됨 → 자격/대상/받을 수는 eligibility
        self.assertEqual(classify_intent("내가 지원 대상이야?", has_selected=True), ELIGIBILITY)
        self.assertEqual(classify_intent("이거 받을 수 있어?", has_selected=True), ELIGIBILITY)
        self.assertEqual(classify_intent("신청 가능해?", has_selected=True), ELIGIBILITY)

    def test_weak_support_word_without_eligibility_is_benefit(self):
        self.assertEqual(classify_intent("지원금 찾아줘", has_selected=True), BENEFIT)

    def test_explicit_apply_method_beats_weak_benefit_words(self):
        # 월세·보증금·지원이 붙어도 '신청 방법'은 apply_how
        self.assertEqual(classify_intent("월세 지원 신청 방법 알려줘", has_selected=True), APPLY_HOW)
        self.assertEqual(classify_intent("보증금 대출 신청 방법", has_selected=True), APPLY_HOW)
        self.assertEqual(classify_intent("지원 신청 방법 알려줘", has_selected=True), APPLY_HOW)

    def test_explicit_eligibility_beats_weak_benefit_words(self):
        # 월세·보증금은 단독 strong-money가 아님 → 자격/대상이면 eligibility
        self.assertEqual(classify_intent("월세 대상이야?", has_selected=True), ELIGIBILITY)
        self.assertEqual(classify_intent("보증금 자격 되나?", has_selected=True), ELIGIBILITY)
        self.assertEqual(classify_intent("이거 받을 수 있어?", has_selected=True), ELIGIBILITY)

    def test_money_context_makes_housing_word_benefit(self):
        # 월세·보증금 + 금액 문맥일 때만 benefit
        self.assertEqual(classify_intent("월세 얼마 지원돼?", has_selected=True), BENEFIT)
        self.assertEqual(classify_intent("보증금 한도가 얼마야?", has_selected=True), BENEFIT)
        self.assertEqual(classify_intent("총액 알려줘", has_selected=True), BENEFIT)

    def test_docs_request_is_docs(self):
        self.assertEqual(classify_intent("필요한 서류 알려줘", has_selected=True), DOCS)

    def test_unclear(self):
        self.assertEqual(classify_intent("음 그렇구나", has_selected=True), UNCLEAR)

    def test_empty(self):
        self.assertEqual(classify_intent("", has_selected=False), UNCLEAR)


if __name__ == "__main__":
    unittest.main()
