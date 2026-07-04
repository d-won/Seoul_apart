"""국토교통부 실거래가 공개시스템(rt.molit.go.kr) '자료제공' CSV 수집.

배경:
  공공데이터포털 오픈API(apis.data.go.kr)는 인증키가 필요하고, 방화벽/정책에 따라
  접근이 막히는 환경이 있다. 반면 국토부 실거래가 공개시스템(rt.molit.go.kr)의
  '자료제공' 화면은 인증키 없이(웹 세션만으로) 시군구·기간 단위 CSV를 내려받을 수 있다.
  같은 국토부 원천 데이터이므로, 인증키 없이 실거래를 수집하는 대체 경로로 사용한다.

흐름:
  1) /pt/xls/xls.do 를 GET 하여 세션 쿠키(JSESSIONID) 확보
  2) /pt/xls/ptXlsDownDataCheck.do 로 조건에 맞는 건수 확인(선택)
  3) /pt/xls/ptXlsCSVDown.do 에 검색조건 POST → EUC-KR CSV 수신
     · 시군구 지정 시 계약일자 범위는 최대 1년 → 연 단위로 분할 요청

반환 스키마는 fetch.to_dataframe 와 동일 컬럼을 갖도록 맞춰, pipeline.run_analysis
가 그대로 동작한다.
"""
from __future__ import annotations

import csv
import io
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

BASE = "https://rt.molit.go.kr"
PAGE_URL = f"{BASE}/pt/xls/xls.do?mobileAt="
CHECK_URL = f"{BASE}/pt/xls/ptXlsDownDataCheck.do"
CSV_URL = f"{BASE}/pt/xls/ptXlsCSVDown.do"

# CSV 헤더(한글) → 우리 컬럼명
CSV_FIELD_MAP = {
    "단지명": "apt_name",
    "전용면적(㎡)": "area_m2",
    "계약년월": "deal_ym",
    "계약일": "day",
    "거래금액(만원)": "price_manwon",
    "층": "floor",
    "건축년도": "build_year",
    "시군구": "sigungu_full",
    "도로명": "road_name",
    "해제사유발생일": "cancel_day",
    "거래유형": "deal_type",
    "번지": "jibun",
}


@dataclass
class RtClient:
    """rt.molit.go.kr 자료제공 CSV 클라이언트."""

    sleep_sec: float = 0.6

    def __post_init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Referer": PAGE_URL,
            }
        )
        # 세션 쿠키 확보
        self.session.get(PAGE_URL, timeout=30)

    def _form(self, sido_cd: str, sgg_cd: str, from_dt: str, to_dt: str) -> dict:
        return {
            "srhThingNo": "A",       # 아파트
            "srhDelngSecd": "1",     # 매매
            "srhAddrGbn": "1",       # 지번주소
            "srhLfstsSecd": "1",
            "sidoNm": "", "sggNm": "", "emdNm": "", "loadNm": "",
            "areaNm": "", "hsmpNm": "", "mobileAt": "",
            "srhFromDt": from_dt, "srhToDt": to_dt,
            "srhNewRonSecd": "",
            "srhSidoCd": sido_cd, "srhSggCd": sgg_cd,
            "srhEmdCd": "", "srhRoadNm": "", "srhLoadCd": "",
            "srhHsmpCd": "", "srhArea": "",
            "srhFromAmount": "", "srhToAmount": "", "srhLrArea": "",
        }

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=16))
    def _post(self, url: str, form: dict) -> requests.Response:
        resp = self.session.post(url, data=form, timeout=90)
        resp.raise_for_status()
        return resp

    def count(self, sido_cd: str, sgg_cd: str, from_dt: str, to_dt: str) -> int:
        r = self._post(CHECK_URL, self._form(sido_cd, sgg_cd, from_dt, to_dt))
        try:
            return int(r.json().get("cnt", 0))
        except Exception:
            return -1

    def fetch_csv_rows(self, sido_cd: str, sgg_cd: str, from_dt: str, to_dt: str) -> list[dict]:
        """한 시군구·기간(<=1년)의 CSV를 받아 매핑된 dict 리스트로 반환."""
        r = self._post(CSV_URL, self._form(sido_cd, sgg_cd, from_dt, to_dt))
        text = r.content.decode("euc-kr", errors="replace")
        return _parse_csv(text, sgg_cd)


def _parse_csv(text: str, sgg_cd: str) -> list[dict]:
    """rt.molit CSV(상단 안내문 + 헤더 + 데이터)를 파싱."""
    lines = text.splitlines()
    # 헤더 행: '단지명' 을 포함하는 첫 행
    hidx = next((i for i, l in enumerate(lines) if "단지명" in l and "전용면적" in l), None)
    if hidx is None:
        return []
    reader = csv.reader(io.StringIO("\n".join(lines[hidx:])))
    header = next(reader)
    idx = {h: i for i, h in enumerate(header)}
    rows = []
    for parts in reader:
        if not parts or len(parts) < len(header):
            continue
        rec: dict[str, str] = {}
        for kor, col in CSV_FIELD_MAP.items():
            if kor in idx:
                rec[col] = parts[idx[kor]].strip()
        rec["sgg_cd"] = sgg_cd
        rows.append(rec)
    return rows


def _year_windows(start_ym: str, end_ym: str) -> list[tuple[str, str]]:
    """연 단위(달력연도) 구간 리스트로 분할. 각 구간은 시군구 검색 1년 제한 이내."""
    sy, sm = int(start_ym[:4]), int(start_ym[4:])
    ey, em = int(end_ym[:4]), int(end_ym[4:])
    out = []
    y = sy
    while y <= ey:
        f_m = sm if y == sy else 1
        t_m = em if y == ey else 12
        f = f"{y:04d}-{f_m:02d}-01"
        # 종료일: 해당 월 말일
        last_day = _last_day(y, t_m)
        t = f"{y:04d}-{t_m:02d}-{last_day:02d}"
        out.append((f, t))
        y += 1
    return out


def _last_day(y: int, m: int) -> int:
    if m == 12:
        return 31
    import datetime
    return (datetime.date(y, m + 1, 1) - datetime.date(y, m, 1)).days


def collect_rt(start_ym: str, end_ym: str, codes: list[str], sido_cd: str = "11000",
               progress: bool = True) -> pd.DataFrame:
    """지정 시군구·기간의 아파트 매매 실거래를 rt.molit CSV로 수집해 정제 DataFrame 반환."""
    client = RtClient()
    windows = _year_windows(start_ym, end_ym)
    all_rows: list[dict] = []
    for code in codes:
        got = 0
        for (f, t) in windows:
            rows = client.fetch_csv_rows(sido_cd, code, f, t)
            all_rows.extend(rows)
            got += len(rows)
            if progress:
                print(f"  [{code}] {f}~{t}: {len(rows):,}건")
            time.sleep(client.sleep_sec)
        if progress:
            print(f"[{code}] 합계 {got:,}건")
    return to_dataframe(all_rows)


def to_dataframe(rows: list[dict]) -> pd.DataFrame:
    """수집 rows → fetch.to_dataframe 와 동일 스키마의 정제 DataFrame."""
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)

    # 금액(만원): 콤마 제거 후 숫자
    df["price_manwon"] = pd.to_numeric(
        df["price_manwon"].astype(str).str.replace(",", "", regex=False).str.strip(),
        errors="coerce",
    )
    df["area_m2"] = pd.to_numeric(df["area_m2"], errors="coerce")
    df["build_year"] = pd.to_numeric(df["build_year"], errors="coerce")
    df["floor"] = pd.to_numeric(df["floor"], errors="coerce")
    df["day"] = pd.to_numeric(df["day"], errors="coerce")

    # 계약년월(YYYYMM) → year, month
    ym = df["deal_ym"].astype(str).str.strip()
    df["year"] = pd.to_numeric(ym.str.slice(0, 4), errors="coerce")
    df["month"] = pd.to_numeric(ym.str.slice(4, 6), errors="coerce")

    # 법정동: '서울특별시 강동구 성내동' → 성내동 (세 번째 토큰)
    def _dong(s: str) -> str:
        parts = str(s).split()
        return parts[2] if len(parts) >= 3 else ""
    df["legal_dong"] = df["sigungu_full"].map(_dong)

    # 계약일자
    df["deal_date"] = pd.to_datetime(
        dict(year=df["year"], month=df["month"], day=df["day"]), errors="coerce"
    )
    df["ym"] = df["deal_date"].dt.to_period("M").astype(str)

    # 해제(취소) 거래: 해제사유발생일이 '-' 가 아니면 해제건
    if "cancel_day" in df:
        cd = df["cancel_day"].astype(str).str.strip()
        df["is_cancelled"] = ~cd.isin(["-", "", "nan"])
        df["cancel_type"] = df["is_cancelled"].map({True: "O", False: ""})
    else:
        df["is_cancelled"] = False
        df["cancel_type"] = ""

    # 파생: ㎡당가, 평단가
    df["price_per_m2"] = df["price_manwon"] / df["area_m2"]
    df["price_per_pyeong"] = df["price_per_m2"] * 3.3058

    return df
