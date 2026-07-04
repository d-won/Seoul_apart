#!/usr/bin/env python3
"""서울 재개발 인근 구축 아파트 가격 분석 — CLI 진입점.

사용 예:
  # 1) 데이터 수집 (관심 구 전체, 2015-01 ~ 2025-06)
  python run.py collect --start 201501 --end 202506

  # 특정 구만 수집
  python run.py collect --start 201501 --end 202506 --lawd 11740 11680

  # 2) 수집된 데이터로 분석 + 차트 생성 (outputs/ 에 저장)
  python run.py analyze

  # 3) 수집 + 분석 한 번에
  python run.py all --start 201501 --end 202506

  # 파이프라인 자체 점검(합성 데이터, API 불필요)
  python run.py selftest
"""
from __future__ import annotations

import argparse
import sys


def cmd_collect(args):
    from src import pipeline
    df = pipeline.collect(args.start, args.end, args.lawd)
    print(f"수집 완료: {len(df):,} 건  → data/raw/ 저장")


def cmd_analyze(args):
    from src import pipeline
    from src.config import Settings
    df = pipeline.load_collected()
    out = pipeline.run_analysis(df, Settings.load())
    _print_analysis(out)


def cmd_all(args):
    from src import pipeline
    from src.config import Settings
    df = pipeline.collect(args.start, args.end, args.lawd)
    if df.empty:
        print("수집된 데이터가 없습니다.")
        return
    out = pipeline.run_analysis(df, Settings.load())
    _print_analysis(out)


def cmd_selftest(args):
    """API 없이 합성 데이터로 전체 분석 로직을 점검한다."""
    from src.selftest import run_selftest
    run_selftest()


def _print_analysis(out: dict):
    print("\n=== 거리구간별 구축 아파트 상승률 ===")
    appr = out.get("appreciation_by_distance")
    if appr is not None and not appr.empty:
        print(appr.to_string(index=False))
    did = out.get("did")
    if did:
        print("\n=== 이벤트 스터디 간이 DID (관리처분인가 전후) ===")
        print(f"  근거리(treated) 사후 상승: {did.get('treated')} pt")
        print(f"  원거리(control) 사후 상승: {did.get('control')} pt")
        print(f"  순효과(DID): {did.get('did_effect_pp')} pp  ← 재개발 근접 프리미엄")
    print("\n차트/표는 outputs/ 폴더에 저장되었습니다.")


def main(argv=None):
    p = argparse.ArgumentParser(description="서울 재개발 인근 구축 아파트 가격 분석")
    sub = p.add_subparsers(dest="cmd", required=True)

    pc = sub.add_parser("collect", help="실거래가 수집")
    pc.add_argument("--start", required=True, help="시작 YYYYMM")
    pc.add_argument("--end", required=True, help="종료 YYYYMM")
    pc.add_argument("--lawd", nargs="*", help="특정 자치구 코드(들). 생략 시 config 재개발 구역의 구 전체")
    pc.set_defaults(func=cmd_collect)

    pa = sub.add_parser("analyze", help="수집 데이터 분석 + 차트")
    pa.set_defaults(func=cmd_analyze)

    pall = sub.add_parser("all", help="수집 + 분석")
    pall.add_argument("--start", required=True, help="시작 YYYYMM")
    pall.add_argument("--end", required=True, help="종료 YYYYMM")
    pall.add_argument("--lawd", nargs="*")
    pall.set_defaults(func=cmd_all)

    pt = sub.add_parser("selftest", help="합성 데이터로 파이프라인 점검(API 불필요)")
    pt.set_defaults(func=cmd_selftest)

    args = p.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    sys.exit(main())
