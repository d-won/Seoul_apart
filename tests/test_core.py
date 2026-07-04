"""핵심 순수 함수 단위 테스트. 실행: pytest -q  (또는 python -m pytest)"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import fetch, geo  # noqa: E402


def test_haversine_known_distance():
    # 서울시청(37.5665,126.9780) ~ 강남역(37.4979,126.9276) 약 8.4km
    d = geo.haversine_m(37.5665, 126.9780, 37.4979, 126.9276)
    assert 8000 < d < 9000


def test_haversine_zero():
    assert geo.haversine_m(37.5, 127.0, 37.5, 127.0) == 0.0


def test_distance_band():
    bands = [500, 1000, 2000]
    assert geo.distance_band(300, bands) == "0-500m"
    assert geo.distance_band(500, bands) == "0-500m"
    assert geo.distance_band(700, bands) == "500-1000m"
    assert geo.distance_band(1500, bands) == "1000-2000m"
    assert geo.distance_band(5000, bands) == "2000m+"


def test_month_range():
    months = fetch.month_range("202411", "202502")
    assert months == ["202411", "202412", "202501", "202502"]


def test_month_range_single():
    assert fetch.month_range("202001", "202001") == ["202001"]


def test_parse_xml_minimal():
    xml = """<response><body><items>
      <item>
        <aptNm>테스트아파트</aptNm>
        <excluUseAr>84.9</excluUseAr>
        <dealYear>2023</dealYear><dealMonth>5</dealMonth><dealDay>10</dealDay>
        <dealAmount>120,000</dealAmount>
        <buildYear>1998</buildYear>
        <umdNm>둔촌동</umdNm>
        <sggCd>11740</sggCd>
      </item>
    </items><totalCount>1</totalCount></body></response>"""
    rows, total = fetch._parse_xml(xml)
    assert total == 1
    assert rows[0]["apt_name"] == "테스트아파트"
    assert rows[0]["price_manwon"] == "120,000"


def test_to_dataframe_derives_price_per_pyeong():
    results = [fetch.MonthResult("11740", "202305", [{
        "apt_name": "테스트", "area_m2": "84.9", "year": "2023", "month": "5",
        "day": "10", "price_manwon": "120,000", "build_year": "1998", "sgg_cd": "11740",
    }])]
    df = fetch.to_dataframe(results)
    assert len(df) == 1
    assert df.loc[0, "price_manwon"] == 120000
    assert math.isclose(df.loc[0, "price_per_m2"], 120000 / 84.9, rel_tol=1e-6)
    assert df.loc[0, "ym"] == "2023-05"
