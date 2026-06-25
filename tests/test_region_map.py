"""region_map 정합성 테스트.

청주시가 통합 시명으로 등록되고(대표 코드 43110), 검색용 코드 조회 시
하위 구 코드(43111~43114)까지 함께 반환되는지 검증한다.
"""
import unittest

from backend.region_map import (
    CODE_TO_SIGUNGU,
    get_region_code,
    get_region_codes,
    get_sigungu_list,
)


class RegionMapTest(unittest.TestCase):
    def test_cheongju_city_code_is_registered(self):
        self.assertEqual(get_region_code("충북", "청주시"), "43110")
        self.assertIn("청주시", get_sigungu_list("충북"))
        self.assertEqual(CODE_TO_SIGUNGU["43110"], "청주시")

    def test_cheongju_city_search_codes_include_district_codes(self):
        self.assertEqual(
            get_region_codes("충북", "청주시"),
            ["43110", "43111", "43112", "43113", "43114"],
        )

    def test_district_reverse_mapping_preserved(self):
        # 청주시 추가 후에도 하위 구 코드의 역매핑은 그대로 유지되어야 한다.
        self.assertEqual(CODE_TO_SIGUNGU["43111"], "상당구")
        self.assertEqual(CODE_TO_SIGUNGU["43112"], "서원구")
        self.assertEqual(CODE_TO_SIGUNGU["43113"], "흥덕구")
        self.assertEqual(CODE_TO_SIGUNGU["43114"], "청원구")

    def test_non_aggregate_region_codes_return_single_code(self):
        self.assertEqual(get_region_codes("충북", "충주시"), ["43130"])

    def test_unknown_region_returns_empty(self):
        self.assertEqual(get_region_codes("충북", "없는시"), [])


if __name__ == "__main__":
    unittest.main()
