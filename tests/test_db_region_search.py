"""get_policies_by_region 다중 코드 검색 테스트.

청주시 대표 코드(43110)가 DB에 없고 하위 구 코드(43111~43114)만 있어도
청주시 질의로 정책이 조회되는지 검증한다.
"""
import os
import sqlite3
import tempfile
import unittest

from backend import db


class GetPoliciesByRegionTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        path = os.path.join(self._tmp.name, "youth_policy.db")
        conn = sqlite3.connect(path)
        conn.execute(
            "CREATE TABLE policies_processed (policy_id TEXT PRIMARY KEY, policy_name TEXT, region TEXT)"
        )
        conn.executemany(
            "INSERT INTO policies_processed (policy_id, policy_name, region) VALUES (?, ?, ?)",
            [
                ("CJ_DISTRICT", "청주 상당구 청년 정책", "43111"),  # 청주시 하위 구 코드만 있음
                ("CHUNGJU", "충주 청년 정책", "43130"),            # 다른 시군(충주)
            ],
        )
        conn.commit()
        conn.close()

        self._prev = db.DB_PATH
        db.DB_PATH = path

    def tearDown(self):
        db.DB_PATH = self._prev
        self._tmp.cleanup()

    def test_cheongju_query_finds_district_code_rows(self):
        rows = db.get_policies_by_region("충북", "청주시")
        ids = {row["policy_id"] for row in rows}
        # 43110이 DB에 없어도 하위 구 코드(43111)로 청주시 정책을 찾는다.
        self.assertIn("CJ_DISTRICT", ids)
        # 다른 시군(충주, 43130)은 청주시 질의에 섞이지 않는다.
        self.assertNotIn("CHUNGJU", ids)

    def test_chungju_query_returns_only_chungju(self):
        rows = db.get_policies_by_region("충북", "충주시")
        ids = {row["policy_id"] for row in rows}
        self.assertEqual(ids, {"CHUNGJU"})


if __name__ == "__main__":
    unittest.main()
