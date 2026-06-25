import unittest
from unittest import mock

from tests.util_fixture import set_test_env

set_test_env()

from ai.policy_chat_agent import PolicyChatAgent


P001 = {
    "doc_id": "policies_processed:P001",
    "source_table": "policies_processed",
    "source_id": "P001",
    "policy_name": "청년 월세 지원",
}

# fixture P002: 금액·기간·서류 정량 데이터가 없는 정책 (미기재 안내 검증용)
P002 = {
    "doc_id": "policies_processed:P002",
    "source_table": "policies_processed",
    "source_id": "P002",
    "policy_name": "청년 자산형성 적금",
}


def _user(message: str):
    return [{"role": "user", "content": message}]


class PolicyChatAgentTest(unittest.TestCase):
    def setUp(self):
        self.agent = PolicyChatAgent()

    def test_same_context_has_stable_rule_answer(self):
        messages = [{"role": "user", "content": "총 얼마 받을 수 있어?"}]
        first = self.agent.answer(policy=P001, user_context={}, messages=messages)
        second = self.agent.answer(policy=P001, user_context={}, messages=messages)
        self.assertEqual(first["answer"], second["answer"])
        self.assertEqual(first["suggested_questions"], second["suggested_questions"])

    def test_follow_up_context_changes_structure_but_keeps_policy_identity(self):
        broad = self.agent.answer(
            policy=P001,
            user_context={},
            messages=[{"role": "user", "content": "필요한 서류가 뭐야?"}],
        )
        specific = self.agent.answer(
            policy=P001,
            user_context={},
            messages=[
                {"role": "user", "content": "필요한 서류가 뭐야?"},
                {"role": "assistant", "content": broad["answer"]},
                {"role": "user", "content": "그 서류는 어디서 발급해?"},
            ],
        )
        self.assertNotEqual(broad["answer"], specific["answer"])
        self.assertEqual(broad["policy_context"]["doc_id"], specific["policy_context"]["doc_id"])
        self.assertIn("구체적으로", specific["answer"])

    def test_missing_profile_asks_for_user_conditions_first(self):
        result = self.agent.answer(
            policy=P001,
            user_context={},
            messages=[{"role": "user", "content": "내가 신청 가능해?"}],
        )
        self.assertIn("나이", result["answer"])
        self.assertIn("거주 지역", result["answer"])

    def test_llm_prompt_contains_response_plan(self):
        with mock.patch(
            "ai.policy_chat_agent.create_chat_response",
            return_value="계획에 따른 답변",
        ) as create:
            result = self.agent.answer(
                policy=P001,
                user_context={"age": 24, "region_sido": "서울"},
                messages=[{"role": "user", "content": "총 얼마 받을 수 있어?"}],
            )
        self.assertEqual(result["answer"], "계획에 따른 답변")
        self.assertIn("응답 계획", create.call_args.kwargs["system_prompt"])
        self.assertIn("total_amount", create.call_args.kwargs["system_prompt"])

    # ── 결함 1: /chat 섹션 순서 계약 ────────────────────────────────
    def test_total_amount_question_puts_money_section_first(self):
        result = self.agent.answer(policy=P001, user_context={}, messages=_user("총 얼마 받을 수 있어?"))
        body = result["answer"]
        money_pos = body.find("금액")
        docs_pos = body.find("서류")
        self.assertGreater(money_pos, -1, "금액 섹션이 있어야 함")
        # 금액 섹션이 서류 등 다른 핵심 섹션보다 먼저 나와야 한다
        if docs_pos > -1:
            self.assertLess(money_pos, docs_pos)
        self.assertIn("20만원", body)

    def test_missing_profile_eligibility_lists_user_info_first(self):
        result = self.agent.answer(policy=P001, user_context={}, messages=_user("내가 신청 가능해?"))
        body = result["answer"]
        info_pos = body.find("나이")
        docs_pos = body.find("필요한 서류")
        self.assertGreater(info_pos, -1)
        if docs_pos > -1:
            self.assertLess(info_pos, docs_pos)

    def test_deadline_question_period_section_leads(self):
        result = self.agent.answer(policy=P001, user_context={}, messages=_user("신청 마감이 언제야?"))
        body = result["answer"]
        self.assertIn("신청 기간", body)

    # ── 결함 3: LLM-on 사실 보존 ───────────────────────────────────
    def test_hallucinated_amount_and_duration_fall_back_to_rule(self):
        with mock.patch(
            "ai.policy_chat_agent.create_chat_response",
            return_value="이 정책은 매월 999만원씩 99개월 동안 지원합니다.",
        ):
            result = self.agent.answer(
                policy=P001,
                user_context={"age": 24, "region_sido": "서울"},
                messages=_user("총 얼마 받을 수 있어?"),
            )
        self.assertNotIn("999", result["answer"])
        self.assertNotIn("99개월", result["answer"])

    def test_hallucinated_url_and_date_fall_back_to_rule(self):
        with mock.patch(
            "ai.policy_chat_agent.create_chat_response",
            return_value="신청 마감은 2030년 12월 31일이며 https://evil.example/hack 에서 신청하세요.",
        ):
            result = self.agent.answer(
                policy=P001,
                user_context={"age": 24, "region_sido": "서울"},
                messages=_user("신청 방법 알려줘"),
            )
        self.assertNotIn("evil.example", result["answer"])
        self.assertNotIn("2030", result["answer"])

    def test_grounded_amount_and_duration_are_allowed(self):
        grounded = "이 정책은 매월 20만원씩 최대 12개월 동안 지원받을 수 있어요."
        with mock.patch("ai.policy_chat_agent.create_chat_response", return_value=grounded):
            result = self.agent.answer(
                policy=P001,
                user_context={"age": 24, "region_sido": "서울"},
                messages=_user("총 얼마 받을 수 있어?"),
            )
        self.assertEqual(result["answer"], grounded)

    def test_grounded_url_is_allowed(self):
        grounded = "신청은 https://example.com/p001 에서 진행하면 돼요."
        with mock.patch("ai.policy_chat_agent.create_chat_response", return_value=grounded):
            result = self.agent.answer(
                policy=P001,
                user_context={"age": 24, "region_sido": "서울"},
                messages=_user("신청 방법 알려줘"),
            )
        self.assertEqual(result["answer"], grounded)

    def test_list_numbers_do_not_trigger_false_positive(self):
        grounded = "필요한 서류는 다음과 같아요.\n1. 신분증\n2. 주민등록등본\n3. 소득 증빙"
        with mock.patch("ai.policy_chat_agent.create_chat_response", return_value=grounded):
            result = self.agent.answer(
                policy=P001,
                user_context={"age": 24, "region_sido": "서울"},
                messages=_user("필요한 서류가 뭐야?"),
            )
        self.assertEqual(result["answer"], grounded)

    def test_llm_exception_falls_back_to_rule(self):
        with mock.patch(
            "ai.policy_chat_agent.create_chat_response",
            side_effect=RuntimeError("boom"),
        ):
            result = self.agent.answer(
                policy=P001,
                user_context={"age": 24, "region_sido": "서울"},
                messages=_user("총 얼마 받을 수 있어?"),
            )
        self.assertTrue(result["answer"])
        self.assertNotIn("boom", result["answer"])
        self.assertIn("20만원", result["answer"])

    # ── 결함 4: DB 미기재 안내 복원 ────────────────────────────────
    def test_missing_period_shows_db_notice_and_link(self):
        result = self.agent.answer(policy=P001, user_context={}, messages=_user("신청 마감이 언제야?"))
        body = result["answer"]
        self.assertIn("신청 기간", body)
        self.assertIn("확인", body)
        self.assertIn("example.com/p001", body)

    def test_missing_docs_shows_db_notice(self):
        result = self.agent.answer(policy=P002, user_context={}, messages=_user("필요한 서류가 뭐야?"))
        self.assertIn("명시", result["answer"])

    def test_present_data_is_still_shown(self):
        result = self.agent.answer(policy=P001, user_context={}, messages=_user("총 얼마 받을 수 있어?"))
        self.assertIn("20만원", result["answer"])

    # ── 결함 2(재): grounding 우회 차단 (KRW/₩/한글수사/수집일) ──────
    def test_hallucinated_krw_unit_falls_back(self):
        with mock.patch(
            "ai.policy_chat_agent.create_chat_response",
            return_value="월 9,990,000 KRW를 12개월 지원합니다.",
        ):
            result = self.agent.answer(
                policy=P001, user_context={"age": 24, "region_sido": "서울"},
                messages=_user("총 얼마 받을 수 있어?"),
            )
        self.assertNotIn("9,990,000", result["answer"])

    def test_hallucinated_won_symbol_falls_back(self):
        with mock.patch(
            "ai.policy_chat_agent.create_chat_response",
            return_value="월 ₩9,990,000을 12개월 지원합니다.",
        ):
            result = self.agent.answer(
                policy=P001, user_context={"age": 24, "region_sido": "서울"},
                messages=_user("총 얼마 받을 수 있어?"),
            )
        self.assertNotIn("9,990,000", result["answer"])

    def test_hallucinated_korean_numeral_amount_falls_back(self):
        with mock.patch(
            "ai.policy_chat_agent.create_chat_response",
            return_value="월 구백구십구만원을 12개월 지원합니다.",
        ):
            result = self.agent.answer(
                policy=P001, user_context={"age": 24, "region_sido": "서울"},
                messages=_user("총 얼마 받을 수 있어?"),
            )
        self.assertNotIn("구백구십구만원", result["answer"])

    def test_collected_at_date_is_not_valid_deadline_ground(self):
        # 수집일(collected_at)만 같은 날짜는 신청 마감 근거가 될 수 없다 → fallback
        context = self.agent.load_policy_context(P001)
        context = dict(context)
        context["collected_at"] = "2026-06-22"
        context["search_document"] = {**context.get("search_document", {}), "collected_at": "2026-06-22"}
        self.assertFalse(
            self.agent._llm_answer_is_grounded("신청 마감은 6월 22일입니다.", context)
        )

    def test_grounded_won_with_comma_is_allowed(self):
        grounded = "매월 200,000원씩 1년 지원받을 수 있어요."
        with mock.patch("ai.policy_chat_agent.create_chat_response", return_value=grounded):
            result = self.agent.answer(
                policy=P001, user_context={"age": 24, "region_sido": "서울"},
                messages=_user("총 얼마 받을 수 있어?"),
            )
        self.assertEqual(result["answer"], grounded)

    # ── 결함(재): 날짜 연도 검증 ────────────────────────────────────
    def _end_2026_context(self):
        context = dict(self.agent.load_policy_context(P001))
        context["search_document"] = {
            **context.get("search_document", {}),
            "apply_start_date": "2026-01-01",
            "apply_end_date": "2026-12-31",
        }
        return context

    def _range_2026_context(self):
        context = dict(self.agent.load_policy_context(P001))
        context["search_document"] = {**context.get("search_document", {}),
                                      "apply_start_date": "", "apply_end_date": ""}
        context["original"] = {}
        context["facts"] = {}
        context["period"] = "2026-01-01 ~ 2026-12-31"
        return context

    def test_deadline_with_matching_end_year_is_allowed(self):
        context = self._end_2026_context()
        self.assertTrue(self.agent._llm_answer_is_grounded("신청 마감은 2026년 12월 31일입니다.", context))

    def test_deadline_without_year_matches_end_month_day(self):
        context = self._end_2026_context()
        self.assertTrue(self.agent._llm_answer_is_grounded("신청 마감은 12월 31일입니다.", context))

    def test_deadline_with_wrong_year_falls_back(self):
        context = self._end_2026_context()
        self.assertFalse(self.agent._llm_answer_is_grounded("신청 마감은 2030년 12월 31일입니다.", context))

    def test_deadline_equal_to_start_date_falls_back(self):
        context = self._end_2026_context()
        self.assertFalse(self.agent._llm_answer_is_grounded("신청 마감은 2026년 1월 1일입니다.", context))

    def test_range_string_end_is_valid_but_start_is_not(self):
        context = self._range_2026_context()
        self.assertTrue(self.agent._llm_answer_is_grounded("신청 마감은 2026년 12월 31일입니다.", context))
        self.assertFalse(self.agent._llm_answer_is_grounded("신청 마감은 2026년 1월 1일입니다.", context))

    # ── 결함(재): 한글 금액 fail-closed ─────────────────────────────
    def test_korean_magnitude_amount_answer_falls_back(self):
        for hallucination in ["월 천 원을 12개월 지원합니다.", "월 백 원을 12개월 지원합니다.",
                              "월 스무만원을 12개월 지원합니다."]:
            with mock.patch("ai.policy_chat_agent.create_chat_response", return_value=hallucination):
                result = self.agent.answer(
                    policy=P001, user_context={"age": 24, "region_sido": "서울"},
                    messages=_user("총 얼마 받을 수 있어?"),
                )
            self.assertNotEqual(result["answer"], hallucination, f"폴백되어야 함: {hallucination}")

    # ── P1-2(재): 자릿수 단위 없는 고유어/한자어 수사 금액 fail-closed ──
    def test_korean_numeral_without_magnitude_answer_falls_back(self):
        for hallucination in ["월 스무 원을 12개월 지원합니다.", "월 서른 원을 12개월 지원합니다.",
                              "월 아흔아홉 원을 12개월 지원합니다."]:
            with mock.patch("ai.policy_chat_agent.create_chat_response", return_value=hallucination):
                result = self.agent.answer(
                    policy=P001, user_context={"age": 24, "region_sido": "서울"},
                    messages=_user("총 얼마 받을 수 있어?"),
                )
            self.assertNotEqual(result["answer"], hallucination, f"폴백되어야 함: {hallucination}")

    # ── P1-1(재): 전체 신청 기간(범위) 답변 허용, 시작일 단독 마감은 거부 ──
    def test_full_period_range_answers_are_allowed(self):
        context = self._end_2026_context()
        for allowed in [
            "신청 기간은 2026년 1월 1일부터 2026년 12월 31일까지입니다.",
            "신청 기간은 2026년 1월 1일부터 12월 31일까지입니다.",
            "신청 기간은 2026-01-01 ~ 2026-12-31입니다.",
            "신청 마감은 2026년 12월 31일입니다.",
            "12월 31일까지 신청하세요.",
        ]:
            self.assertTrue(self.agent._llm_answer_is_grounded(allowed, context), allowed)

    def test_range_and_single_deadline_rejections(self):
        context = self._end_2026_context()
        for rejected in [
            "2026년 1월 1일까지 신청하세요.",                      # 시작일을 마감으로
            "신청 기간은 2026년 1월 1일부터 2030년 12월 31일까지입니다.",  # 잘못된 종료 연도
            "6월 30일까지 신청하세요.",                           # 종료일과 다른 날짜
        ]:
            self.assertFalse(self.agent._llm_answer_is_grounded(rejected, context), rejected)


class GroundingPureFunctionTest(unittest.TestCase):
    def test_extract_money_korean_and_won_and_symbol_and_krw(self):
        from ai.policy_chat_agent import extract_money

        self.assertEqual(extract_money("20만원")[0], {200_000})
        self.assertEqual(extract_money("200,000원")[0], {200_000})
        self.assertEqual(extract_money("₩200,000")[0], {200_000})
        self.assertIn(200_000, extract_money("200,000 KRW")[0])
        self.assertIn(200_000, extract_money("KRW 200,000")[0])

    def test_extract_money_flags_korean_numeral_as_suspicious(self):
        from ai.policy_chat_agent import extract_money

        self.assertTrue(extract_money("구백구십구만원")[1])
        self.assertFalse(extract_money("20만원")[1])
        # 금액이 아닌 '원'(지원/병원/공원/사원)에 false positive가 없어야 함
        self.assertFalse(extract_money("지원 병원 공원 사원")[1])

    def test_extract_duration_normalizes_years(self):
        from ai.policy_chat_agent import extract_duration_months

        self.assertEqual(extract_duration_months("12개월"), {12})
        self.assertEqual(extract_duration_months("1년"), {12})

    def test_extract_dates_preserve_year_when_present(self):
        from ai.policy_chat_agent import extract_dates

        self.assertEqual(extract_dates("2030년 12월 31일"), {(2030, 12, 31)})
        self.assertEqual(extract_dates("6월 22일"), {(None, 6, 22)})
        self.assertEqual(extract_dates("2026-12-31"), {(2026, 12, 31)})

    def test_extract_money_native_and_magnitude_units_are_suspicious(self):
        from ai.policy_chat_agent import extract_money

        for text in ["백 원", "천 원", "오천 원", "일만원", "이백만 원",
                     "스무만원", "오십만원", "백오십만원", "구백구십구만원"]:
            self.assertTrue(extract_money(text)[1], f"{text} 는 의심 처리되어야 함")

    def test_extract_money_common_words_are_not_money(self):
        from ai.policy_chat_agent import extract_money

        for word in ["지원", "병원", "공원", "사원", "구원", "위원", "공무원", "회원"]:
            values, suspicious = extract_money(word)
            self.assertEqual(values, set(), f"{word} 는 금액이 아님")
            self.assertFalse(suspicious, f"{word} 는 의심이 아님")

    def test_extract_money_bare_numeral_words_with_space_are_suspicious(self):
        from ai.policy_chat_agent import extract_money

        # 자릿수 단위(만/억 등) 없이 수사 + 띄어쓰기 + 원
        for text in ["일 원", "오 원", "열 원", "스무 원", "서른 원", "아흔아홉 원", "오십 원", "삼백 원"]:
            self.assertTrue(extract_money(text)[1], f"{text} 는 의심 처리되어야 함")

    def test_extract_money_arabic_amounts_still_parse(self):
        from ai.policy_chat_agent import extract_money

        for text in ["20만원", "200,000원", "₩200,000", "200,000 KRW", "KRW 200,000"]:
            values, suspicious = extract_money(text)
            self.assertIn(200_000, values, text)
            self.assertFalse(suspicious, text)

    def test_list_numbers_and_age_are_not_money(self):
        from ai.policy_chat_agent import extract_money

        self.assertEqual(extract_money("1. 신분증\n2. 주민등록등본")[0], set())
        self.assertFalse(extract_money("1. 신분증\n2. 주민등록등본")[1])
        self.assertEqual(extract_money("만 19세 이상")[0], set())
        self.assertFalse(extract_money("만 19세 이상")[1])


if __name__ == "__main__":
    unittest.main()
