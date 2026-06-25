"""충북 복지(lgcv=welfare_chungbuk_local)·전국 복지(welfare_central) 상담/신청 도우미 회귀 테스트.

운영 DB 구조를 모사한다: lgcv는 search_documents에 통합되지 않고 원천
welfare_chungbuk_local에만 있으며, 카드 ref만으로 상담에 들어와도 원본에서
지역/대상/서류/문의처가 보강돼야 한다(이전엔 모두 비어 있었음).
"""
import os
import sqlite3
import tempfile
import unittest


SEARCH_DOCS_DDL = """
CREATE TABLE search_documents (
    doc_id TEXT PRIMARY KEY, source_table TEXT, source_id TEXT, domain TEXT,
    title TEXT, summary TEXT, region_name TEXT, region_sido TEXT, region_sigungu TEXT,
    target TEXT, min_age INTEGER, max_age INTEGER, employment_status TEXT, status TEXT,
    apply_start_date TEXT, apply_end_date TEXT, url TEXT, search_text TEXT,
    raw_ref TEXT, collected_at TEXT
)
"""

WELFARE_CHUNGBUK_DDL = """
CREATE TABLE welfare_chungbuk_local (
    service_id TEXT PRIMARY KEY, service_name TEXT, region_sido TEXT, region_sigungu TEXT,
    department TEXT, summary TEXT, life_cycle TEXT, support_target TEXT,
    selection_criteria TEXT, support_content TEXT, application_method TEXT,
    contact TEXT, homepage TEXT, search_text TEXT
)
"""


def _build_db(path: str) -> None:
    conn = sqlite3.connect(path)
    conn.execute(SEARCH_DOCS_DDL)
    conn.execute(WELFARE_CHUNGBUK_DDL)
    # 운영과 동일하게 lgcv는 search_documents에 넣지 않는다.
    conn.execute(
        "INSERT INTO welfare_chungbuk_local VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "WLF-T1", "충북 청년 생활지원금", "충청북도", "청주시",
            "충청북도 청주시 복지정책과", "청년 생활 안정을 위한 충북 지자체 복지서비스",
            "청년", "충북 거주 만 19~39세 청년", "소득 기준 충족 시 선정",
            "월 10만원 생활지원금 지급", "행정복지센터 방문 신청",
            "청주시청 복지정책과(043-201-0000)", "https://example.com/chungbuk",
            "충북 청주 청년 생활지원금 복지서비스",
        ),
    )
    conn.commit()
    conn.close()


class WelfareChatApplyTest(unittest.TestCase):
    def setUp(self):
        os.environ["LLM_PROVIDER"] = "none"
        os.environ["USE_FAISS"] = "0"
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self._tmp.name, "youth_policy.db")
        _build_db(self.db_path)
        self._prev = os.environ.get("YOUTH_POLICY_DB_PATH")
        os.environ["YOUTH_POLICY_DB_PATH"] = self.db_path
        os.environ.pop("LGCV_POLICY_DB_PATH", None)
        # 카드 ref(프론트가 보내는 최소 정보)만으로 상담에 들어오는 상황을 모사.
        self.ref = {
            "doc_id": "lgcv:WLF-T1",
            "source_table": "lgcv",
            "source_id": "WLF-T1",
            "title": "충북 청년 생활지원금",
            "domain": "welfare",
        }

    def tearDown(self):
        if self._prev is None:
            os.environ.pop("YOUTH_POLICY_DB_PATH", None)
        else:
            os.environ["YOUTH_POLICY_DB_PATH"] = self._prev
        self._tmp.cleanup()

    def test_context_enriches_from_welfare_original(self):
        from ai.policy_chat_agent import PolicyChatAgent

        ctx = PolicyChatAgent().load_policy_context(self.ref)
        self.assertNotEqual(ctx["original"], {})
        self.assertEqual(ctx["source_label"], "충북 지자체 복지서비스")
        self.assertEqual(ctx["domain_label"], "복지서비스")
        # 시도는 충북으로 정규화, 시군구/대상/요약이 원본에서 보강된다.
        self.assertEqual(ctx["region_sido"], "충북")
        self.assertEqual(ctx["region_sigungu"], "청주시")
        self.assertTrue(ctx["target"])
        self.assertTrue(ctx["summary"])
        # 복지 facts가 채워진다.
        self.assertIn("contact", ctx["facts"])
        self.assertIn("benefit", ctx["facts"])

    def test_apply_plan_surfaces_real_documents_and_contact(self):
        from ai.apply_agent import ApplyAgent

        profile = {"age": 28, "region_sido": "충북", "region_sigungu": "청주시"}
        plan = ApplyAgent().build_plan(self.ref, profile)
        self.assertEqual(plan["eligibility"], "ok")
        docs = [item["label"] for item in plan["checklist"] if item["kind"] == "document"]
        # 더 이상 'public 공고문에서 제출 서류 확인' 한 줄짜리 generic이 아니어야 한다.
        self.assertGreaterEqual(len(docs), 3)
        self.assertIn("주민등록등본", docs)
        self.assertNotEqual(docs, ["신분증", "공고문에서 제출 서류 확인"])

    def test_apply_how_answer_includes_method_and_contact(self):
        from ai.converse_agent import ConverseAgent

        profile = {"age": 28, "region_sido": "충북", "region_sigungu": "청주시", "status": "청년"}
        out = ConverseAgent().respond(
            message="신청 방법 알려줘",
            selected_policy=self.ref,
            last_recommendations=[self.ref],
            profile=profile,
        )
        reply = out["reply"]
        self.assertIn("방문", reply)  # application_method = 행정복지센터 방문 신청
        self.assertIn("043-201-0000", reply)  # 원본 문의처가 노출된다


if __name__ == "__main__":
    unittest.main()
