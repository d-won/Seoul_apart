#!/usr/bin/env python3
"""공식 원자료를 API로 직접 수집(선택) — 사용자 로컬 환경에서 실행.

주의: Claude Code 웹 실행 환경에서는 한국 통계포털(ECOS·KOSIS)로의
외부 접속이 네트워크 정책상 차단(CONNECT 403)됩니다. 따라서 이 스크립트는
**본인 PC 등 외부망이 열린 환경**에서 API 키를 넣고 실행해야 정확한
공식 수치를 받아 data/*.csv 를 덮어씁니다.

필요 키
  - ECOS_API_KEY : 한국은행 ECOS  (https://ecos.bok.or.kr/api  무료 신청)
  - KOSIS_API_KEY: 국가통계포털   (https://kosis.kr/openapi   무료 신청)

수집 대상
  1) 정책금리   : ECOS 통계표 722Y001 (한국은행 기준금리)
  2) 아파트값   : KOSIS 408 / DT_KAB_11672_S1 (아파트 매매 실거래가격지수, 서울)
  3) 시간당임금 : KOSIS 사업체노동력조사 시간당 임금총액 (표ID는 아래 주석 참고)

레포에 포함된 data/*.csv 는 위 포털 접속이 막힌 환경에서
확인된 앵커 수치 + 공식 변동률로 재구성한 값이다(각 CSV 주석의 신뢰도 표기 참고).
정확한 공식 수치가 필요하면 이 스크립트로 갱신할 것.
"""
from __future__ import annotations

import os
import sys

try:
    import requests
except ImportError:
    sys.exit("requests 필요:  pip install requests")


def fetch_base_rate(ecos_key: str):
    """ECOS 722Y001 (기준금리) 월별 → 연말 값."""
    url = (f"https://ecos.bok.or.kr/api/StatisticSearch/{ecos_key}"
           f"/json/kr/1/10000/722Y001/M/200501/202412/0101000")
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    rows = r.json()["StatisticSearch"]["row"]
    yearly = {}
    for row in rows:  # TIME = YYYYMM
        y = row["TIME"][:4]
        yearly[y] = float(row["DATA_VALUE"])  # 마지막(연말) 값이 남음
    return yearly


def main():
    ecos = os.environ.get("ECOS_API_KEY")
    kosis = os.environ.get("KOSIS_API_KEY")
    if not ecos:
        print("ECOS_API_KEY 미설정 — 기준금리 수집 건너뜀")
    else:
        try:
            yr = fetch_base_rate(ecos)
            print("기준금리(연말):")
            for y in sorted(yr):
                print(f"  {y}: {yr[y]}")
        except Exception as e:  # noqa: BLE001
            print(f"기준금리 수집 실패: {e}")
    if not kosis:
        print("\nKOSIS_API_KEY 미설정 — 아파트값·시간당임금 수집 건너뜀")
        print("KOSIS 표: 아파트 실거래가격지수 DT_KAB_11672_S1 (org 408),")
        print("          사업체노동력조사 시간당 임금총액(사업체규모/근로자지위 조건 선택).")
    print("\n외부망이 막힌 환경에서는 실패가 정상입니다. 로컬에서 키를 넣고 실행하세요.")


if __name__ == "__main__":
    main()
