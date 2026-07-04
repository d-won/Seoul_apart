"""국토교통부 아파트 매매 실거래가 상세 자료 수집.

공공데이터포털 오픈API:
  아파트 매매 실거래가 상세 자료 (RTMSDataSvcAptTradeDev)
  https://www.data.go.kr/data/15126469/openapi.do

요청 파라미터:
  serviceKey : 인증키
  LAWD_CD    : 지역코드(법정동 시군구코드 5자리)
  DEAL_YMD   : 계약년월 (YYYYMM)
  pageNo, numOfRows : 페이징

주의: API는 '월 단위'로만 조회된다. 10년치를 받으려면 (구 × 개월) 만큼 반복 호출한다.
"""
from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from tenacity import retry, stop_after_attempt, wait_exponential

API_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"

# API XML 태그 -> 우리 컬럼명. (신규 상세 API 기준. 응답 태그가 다를 수 있어 별칭도 함께 처리)
FIELD_MAP = {
    "aptNm": "apt_name",
    "aptDong": "apt_dong",
    "excluUseAr": "area_m2",
    "dealYear": "year",
    "dealMonth": "month",
    "dealDay": "day",
    "dealAmount": "price_manwon",   # 만원 단위, 콤마 포함 문자열
    "floor": "floor",
    "buildYear": "build_year",
    "umdNm": "legal_dong",
    "jibun": "jibun",
    "sggCd": "sgg_cd",
    "cdealType": "cancel_type",     # 해제여부 (O이면 계약해제)
    "cdealDay": "cancel_day",
    "roadNm": "road_name",
    "landLeaseholdGbn": "land_lease",
}


@dataclass
class MonthResult:
    lawd_cd: str
    deal_ymd: str
    rows: list[dict]


class MolitClient:
    def __init__(self, service_key: str, sleep_sec: float = 0.12):
        self.service_key = service_key
        self.sleep_sec = sleep_sec
        self.session = requests.Session()

    @retry(stop=stop_after_attempt(4), wait=wait_exponential(multiplier=1, min=2, max=16))
    def _request(self, lawd_cd: str, deal_ymd: str, page_no: int, num_rows: int) -> str:
        params = {
            "serviceKey": self.service_key,
            "LAWD_CD": lawd_cd,
            "DEAL_YMD": deal_ymd,
            "pageNo": page_no,
            "numOfRows": num_rows,
        }
        resp = self.session.get(API_URL, params=params, timeout=30)
        resp.raise_for_status()
        text = resp.text
        # 공공데이터포털은 정상 응답도 200으로 오지만, 에러는 본문에 담긴다.
        if "<errMsg>" in text or "SERVICE ERROR" in text or "SERVICE_KEY" in text:
            head = text[:300]
            if "NORMAL SERVICE" not in head and "resultCode>00" not in text:
                raise RuntimeError(f"API 오류 응답: {head}")
        return text

    def fetch_month(self, lawd_cd: str, deal_ymd: str, num_rows: int = 1000) -> MonthResult:
        """한 개 구(區)의 한 개 월(月) 전체 거래를 페이징으로 모두 수집."""
        all_rows: list[dict] = []
        page = 1
        while True:
            xml_text = self._request(lawd_cd, deal_ymd, page, num_rows)
            rows, total = _parse_xml(xml_text)
            all_rows.extend(rows)
            if page * num_rows >= total or not rows:
                break
            page += 1
            time.sleep(self.sleep_sec)
        return MonthResult(lawd_cd=lawd_cd, deal_ymd=deal_ymd, rows=all_rows)


def _parse_xml(xml_text: str) -> tuple[list[dict], int]:
    """상세 API XML을 파싱해 dict 리스트와 totalCount를 반환."""
    root = ET.fromstring(xml_text)

    total_el = root.find(".//totalCount")
    total = int(total_el.text) if total_el is not None and total_el.text else 0

    rows: list[dict] = []
    for item in root.findall(".//item"):
        rec: dict[str, str] = {}
        for child in item:
            tag = child.tag
            if tag in FIELD_MAP:
                rec[FIELD_MAP[tag]] = (child.text or "").strip()
        rows.append(rec)
    return rows, total


def month_range(start_ym: str, end_ym: str) -> list[str]:
    """'YYYYMM' 구간을 월 리스트로 확장."""
    sy, sm = int(start_ym[:4]), int(start_ym[4:])
    ey, em = int(end_ym[:4]), int(end_ym[4:])
    out = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}{m:02d}")
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


def to_dataframe(results: list[MonthResult]) -> pd.DataFrame:
    """수집 결과를 정제된 DataFrame으로 변환."""
    records = []
    for r in results:
        for row in r.rows:
            records.append(row)
    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)

    # 숫자 정제
    if "price_manwon" in df:
        df["price_manwon"] = (
            df["price_manwon"].str.replace(",", "", regex=False).str.strip()
        )
        df["price_manwon"] = pd.to_numeric(df["price_manwon"], errors="coerce")
    for col in ("area_m2", "floor", "build_year", "year", "month", "day"):
        if col in df:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # 계약일자
    if {"year", "month", "day"}.issubset(df.columns):
        df["deal_date"] = pd.to_datetime(
            dict(year=df["year"], month=df["month"], day=df["day"]),
            errors="coerce",
        )
        df["ym"] = df["deal_date"].dt.to_period("M").astype(str)

    # 계약 해제 건 제외 플래그
    if "cancel_type" in df:
        df["is_cancelled"] = df["cancel_type"].fillna("").str.upper().eq("O")
    else:
        df["is_cancelled"] = False

    # 파생: 평단가(만원/3.3㎡), ㎡당가(만원/㎡)
    if {"price_manwon", "area_m2"}.issubset(df.columns):
        df["price_per_m2"] = df["price_manwon"] / df["area_m2"]
        df["price_per_pyeong"] = df["price_per_m2"] * 3.3058

    return df


def save_raw(df: pd.DataFrame, lawd_cd: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"trades_{lawd_cd}.parquet"
    df.to_parquet(path, index=False)
    return path
