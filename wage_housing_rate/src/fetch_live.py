#!/usr/bin/env python3
"""공식 원자료를 API로 받아 **실측 월별 CSV**를 생성한다.

생성물(있으면 build_charts.py 가 자동으로 월별 차트로 그림):
  data/base_rate_monthly.csv     month,base_rate_pct          ← ECOS(자동)
  data/hourly_wage_monthly.csv   month,hourly_wage_won        ← KOSIS
  data/seoul_apt_monthly.csv     month,seoul_apt_avg_price_100m(또는 지수)  ← KOSIS

주의: 실행 환경의 네트워크 정책에 따라 통계포털 접속이 막힐 수 있다. 접속이 되는 환경에서
실행하면 된다(필요 도메인: kosis.kr, ecos.bok.or.kr). 접속 확인:
  curl -sS -o /dev/null -w "%{http_code}\\n" https://kosis.kr

── 키/URL (환경변수) ───────────────────────────────────────────────
선택
  ECOS_API_KEY        한국은행 ECOS 인증키   https://ecos.bok.or.kr/api  (무료)
                      ※ 없어도 됨 — 정책금리 월별은 레포의 변경이력 기반 CSV로 이미 완성.
                        이 키를 주면 ECOS 공식값으로 덮어쓸 뿐이다.

집값·임금(월별)에 필요 — KOSIS는 표마다 분류코드가 달라, 포털이 만들어 주는 'OpenAPI URL'을 그대로 쓰는 게 가장 확실하다.
  KOSIS 통계표 → 우측 상단 [OpenAPI] → '조회 URL' 생성(주기=월, 기간 지정) → 그 URL을 아래에 넣는다.

  KOSIS_APT_URL       서울 아파트 실거래가격지수(월) 조회 URL
                      데이터 값은 Param/statisticsParameterData.do 엔드포인트가 반환한다:
                      예) https://kosis.kr/openapi/Param/statisticsParameterData.do?method=getList&apiKey=...&
                          orgId=408&tblId=DT_KAB_11672_S1&prdSe=M&startPrdDe=200601&endPrdDe=202612&
                          objL1=030&itmId=T1&objL2=&objL3=&objL4=&objL5=&objL6=&objL7=&objL8=&format=json&jsonVD=Y
                      (objL1=030=서울, itmId=T1=지수. 코드 확인: method=getMeta&type=ITM. README 참고)

  시간당 임금(사업체노동력조사, 월). 표가 '시간당 임금총액'을 직접 주면 하나만:
  KOSIS_WAGE_URL      시간당 임금총액(원) getList URL
  또는 월임금총액과 월근로시간을 나눠 계산하려면 두 개:
  KOSIS_WAGE_PAY_URL  월 임금총액(원) URL
  KOSIS_WAGE_HRS_URL  월 근로시간(시간) URL
────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import os
import sys

try:
    import requests
except ImportError:
    sys.exit("requests 필요:  pip install requests")

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, "data")


def _ym(prd_de: str) -> str:
    """'YYYYMM' → 'YYYY-MM'."""
    return f"{prd_de[:4]}-{prd_de[4:6]}"


def fetch_base_rate_ecos(key: str) -> dict:
    """ECOS 722Y001(기준금리) 월별. {'YYYY-MM': rate}."""
    url = (f"https://ecos.bok.or.kr/api/StatisticSearch/{key}"
           f"/json/kr/1/100000/722Y001/M/200501/202612/0101000")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    rows = r.json()["StatisticSearch"]["row"]
    return {_ym(x["TIME"]): float(x["DATA_VALUE"]) for x in rows}


def fetch_kosis(url: str) -> dict:
    """KOSIS getList URL → {'YYYY-MM': value}. PRD_DE(YYYYMM), DT(값)."""
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    data = r.json()
    if isinstance(data, dict) and data.get("err"):
        raise RuntimeError(f"KOSIS 오류: {data}")
    out = {}
    for x in data:
        prd = x.get("PRD_DE", "")
        if len(prd) == 6:  # 월 데이터
            try:
                out[_ym(prd)] = float(x["DT"])
            except (ValueError, KeyError):
                pass
    if not out:
        raise RuntimeError("KOSIS 응답에 월(YYYYMM) 데이터가 없음 — prdSe=M 인지 URL 확인")
    return out


def _write(path: str, header: str, comment: str, series: dict):
    months = sorted(series)
    with open(path, "w") as f:
        f.write(f"# {comment}\n{header}\n")
        for m in months:
            f.write(f"{m},{series[m]}\n")
    print(f"  → {os.path.relpath(path, HERE)}  ({len(months)}개월, 최신 {months[-1]}={series[months[-1]]})")


def main():
    os.makedirs(DATA, exist_ok=True)
    did = []

    # 1) 기준금리 — ECOS (자동)
    key = os.environ.get("ECOS_API_KEY")
    if key:
        try:
            _write(os.path.join(DATA, "base_rate_monthly.csv"),
                   "month,base_rate_pct", "한국은행 기준금리 월별 (ECOS 722Y001)",
                   fetch_base_rate_ecos(key))
            did.append("base_rate")
        except Exception as e:  # noqa: BLE001
            print(f"기준금리 수집 실패: {e}")
    else:
        print("ECOS_API_KEY 미설정 — 기준금리 건너뜀(레포의 변경이력 기반 월별 CSV 사용)")

    # 2) 서울 아파트 실거래가(지수) — KOSIS URL
    apt_url = os.environ.get("KOSIS_APT_URL")
    if apt_url:
        try:
            _write(os.path.join(DATA, "seoul_apt_monthly.csv"),
                   "month,seoul_apt_avg_price_100m",
                   "서울 아파트 실거래가(월) — KOSIS_APT_URL (지수/평균가는 URL에 따름)",
                   fetch_kosis(apt_url))
            did.append("seoul_apt")
        except Exception as e:  # noqa: BLE001
            print(f"아파트 수집 실패: {e}")
    else:
        print("KOSIS_APT_URL 미설정 — 서울 아파트 월별 건너뜀")

    # 3) 시간당 임금 — KOSIS URL(단일) 또는 임금총액/근로시간 두 URL
    wage_url = os.environ.get("KOSIS_WAGE_URL")
    pay_url = os.environ.get("KOSIS_WAGE_PAY_URL")
    hrs_url = os.environ.get("KOSIS_WAGE_HRS_URL")
    try:
        if wage_url:
            wage = fetch_kosis(wage_url)
        elif pay_url and hrs_url:
            pay, hrs = fetch_kosis(pay_url), fetch_kosis(hrs_url)
            wage = {m: round(pay[m] / hrs[m]) for m in (pay.keys() & hrs.keys()) if hrs[m]}
        else:
            wage = None
            print("KOSIS_WAGE_URL(또는 PAY/HRS URL) 미설정 — 시간당 임금 월별 건너뜀")
        if wage:
            _write(os.path.join(DATA, "hourly_wage_monthly.csv"),
                   "month,hourly_wage_won", "시간당 명목임금 월별 — KOSIS(사업체노동력조사)", wage)
            did.append("hourly_wage")
    except Exception as e:  # noqa: BLE001
        print(f"임금 수집 실패: {e}")

    print(f"\n완료: {', '.join(did) if did else '없음'} 수집. 이후 `python build_charts.py` 실행 시 월별로 그려집니다.")
    if not did:
        print("외부망이 막힌 환경에서는 실패가 정상입니다. 도메인 허용 + 키/URL 설정 후 재실행하세요.")


if __name__ == "__main__":
    main()
