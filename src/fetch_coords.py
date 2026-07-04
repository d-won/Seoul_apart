"""rt.molit.go.kr GIS 단지목록에서 아파트 단지별 좌표(위경도) 수집.

거리 분석은 아파트 좌표가 있어야 가능하다(국토부 실거래엔 위경도가 없음).
실거래가 공개시스템의 지도검색이 쓰는 내부 엔드포인트로 단지별 좌표를 모은다:
  · /pt/gis/ptDanjiList.do : 법정동(LED코드) → 단지목록(단지명·위도 la·경도 lo), 페이징

법정동(읍면동) 코드는 시군구코드(5) + 읍면동코드(5)로 이뤄진다. 별도 목록 API 없이
읍면동코드 후보(10100~13900)를 순회하며 결과가 있는 법정동만 채택한다(견고한 방식).

결과를 config/apartment_coords.yaml 형식(apartments: [{lawd_cd, apt_name, lat, lon}])
으로 저장하면 geo/pipeline 이 그대로 사용한다.
"""
from __future__ import annotations

import time

import requests

BASE = "https://rt.molit.go.kr"

# 읍면동 코드 후보(5자리). 서울 법정동은 대체로 10100~13900 범위.
EMD_CANDIDATES = [f"{n:05d}" for n in range(10100, 14000, 100)]


class CoordClient:
    def __init__(self, sleep_sec: float = 0.2):
        self.sleep_sec = sleep_sec
        self.s = requests.Session()
        self.s.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Referer": f"{BASE}/pt/gis/gis.do?srhThingSecd=A",
            }
        )
        self.s.get(f"{BASE}/pt/gis/gis.do?srhThingSecd=A&mobileAt=", timeout=30)

    def emd_codes(self, sgg_cd: str) -> list[str]:
        """시군구에서 실제 단지가 있는 읍면동(5자리) 코드 목록을 탐지."""
        found = []
        for emd in EMD_CANDIDATES:
            j = self._danji_page(sgg_cd + emd, page=1)
            if j.get("totCnt", 0):
                found.append(emd)
            time.sleep(self.sleep_sec)
        return found

    def _danji_page(self, led_cd: str, page: int, year: str = "2025") -> dict:
        form = {
            "srhThingSecd": "A", "srhYear": year, "srhLadSecd": "1",
            "srhLedCd": led_cd, "srhRoadCd": "", "srhBldgNm": "",
            "pageIndex": str(page), "mobileAt": "",
        }
        try:
            return self.s.post(f"{BASE}/pt/gis/ptDanjiList.do", data=form, timeout=30).json()
        except Exception:
            return {}

    def danji_list(self, led_cd: str, year: str = "2025") -> list[dict]:
        """법정동(10자리 LED코드)의 아파트 단지목록을 페이징으로 모두 수집."""
        out: list[dict] = []
        page = 1
        seen = set()
        while True:
            j = self._danji_page(led_cd, page, year)
            lst = j.get("danjiList", [])
            if not lst:
                break
            new = 0
            for d in lst:
                code = d.get("aprpnHsmpCode")
                if code in seen:
                    continue
                seen.add(code)
                out.append(d)
                new += 1
            tot = j.get("totCnt", 0)
            if new == 0 or len(out) >= tot or page > 60:
                break
            page += 1
            time.sleep(self.sleep_sec)
        return out


def collect_coords(codes: list[str], sido_cd: str = "11000", progress: bool = True) -> list[dict]:
    """지정 시군구들의 모든 아파트 단지 좌표를 수집.

    반환: [{lawd_cd, apt_name, lat, lon, dong}]
    """
    c = CoordClient()
    rows: list[dict] = []
    for sgg in codes:
        emds = c.emd_codes(sgg)
        got = 0
        for emd in emds:
            led = sgg + emd
            danji = c.danji_list(led)
            for d in danji:
                la, lo = d.get("la"), d.get("lo")
                nm = d.get("aprpnHsmpNm")
                if not nm or not la or not lo:
                    continue
                rows.append(
                    {
                        "lawd_cd": sgg,
                        "apt_name": nm,
                        "lat": round(float(la), 6),
                        "lon": round(float(lo), 6),
                        "dong": d.get("ledNm", ""),
                    }
                )
                got += 1
            time.sleep(c.sleep_sec)
        if progress:
            print(f"[{sgg}] 단지 {got:,}개 (법정동 {len(emds)}개)")
    return rows
