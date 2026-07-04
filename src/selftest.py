"""합성 데이터로 파이프라인 전체를 점검한다 (국토부 API 불필요).

목적:
  - 수집 이후 단계(정제→거리→분석→시각화)가 오류 없이 동작하는지 확인
  - 의도적으로 '근접 프리미엄'을 심은 합성 데이터에서 분석이 그 효과를 되짚어내는지 검증

⚠ 여기서 만드는 숫자는 전부 '합성(가짜)' 데이터입니다. 실제 시세가 아닙니다.
   실제 분석은 `python run.py collect` 로 국토부 실거래가를 받아서 수행하세요.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from . import analyze, geo, visualize
from .config import OUTPUT_DIR, Settings, load_areas


def _synth_frame(seed: int = 42) -> pd.DataFrame:
    """재개발 구역 주변에 '가까울수록 더 오른' 구축 아파트 거래를 합성.

    각 구역 주변 여러 거리대에 가상의 구축 단지를 배치하고, 관리처분(t=0) 이후
    근거리일수록 가파른 상승을 부여한다.
    """
    rng = np.random.default_rng(seed)
    areas = load_areas()
    months = pd.period_range("2015-01", "2025-06", freq="M")

    rows = []
    # 거리대별 (오프셋 미터, 사후 추가 상승계수)
    ring_specs = [
        (300, 0.55),    # 0-500m : 강한 프리미엄
        (750, 0.30),    # 500-1000m
        (1500, 0.15),   # 1000-2000m
        (3000, 0.02),   # 2000m+ : 대조군 (거의 무관)
    ]
    for a in areas:
        em = a.event_month("management_disposal")
        t0 = pd.Period(em, freq="M") if em else pd.Period("2018-01", freq="M")
        base_ppp = float(rng.uniform(2500, 6000))  # 구별 기준 평단가
        for ri, (offset_m, post_boost) in enumerate(ring_specs):
            # 구역 중심에서 동쪽으로 offset_m 만큼 떨어진 가상 단지 좌표
            dlat = 0.0
            dlon = offset_m / (111_320 * math.cos(math.radians(a.lat)))
            apt_lat, apt_lon = a.lat + dlat, a.lon + dlon
            apt_name = f"합성_{a.id}_{offset_m}m"
            build_year = int(rng.integers(1988, 2002))  # 구축
            for m in months:
                rel = (m - t0).n
                # 공통 시장 추세(완만) + 사후 근접 부스트(로지스틱)
                trend = 1.0 + 0.006 * (m - months[0]).n
                boost = post_boost / (1 + math.exp(-0.15 * rel)) if rel > -24 else 0.0
                ppp = base_ppp * trend * (1 + boost) * rng.normal(1.0, 0.03)
                n = int(rng.integers(1, 5))
                for _ in range(n):
                    area_m2 = float(rng.choice([59.9, 84.9, 114.8]))
                    price = ppp / 3.3058 * area_m2
                    rows.append(
                        {
                            "apt_name": apt_name,
                            "area_m2": area_m2,
                            "year": m.year,
                            "month": m.month,
                            "day": int(rng.integers(1, 28)),
                            "build_year": build_year,
                            "price_manwon": round(price, 0),
                            "sgg_cd": a.lawd_cd,
                            "legal_dong": a.dong,
                            "is_cancelled": False,
                            "_apt_lat": apt_lat,
                            "_apt_lon": apt_lon,
                        }
                    )

    df = pd.DataFrame(rows)
    df["deal_date"] = pd.to_datetime(dict(year=df.year, month=df.month, day=df.day))
    df["ym"] = df["deal_date"].dt.to_period("M").astype(str)
    df["price_per_m2"] = df["price_manwon"] / df["area_m2"]
    df["price_per_pyeong"] = df["price_per_m2"] * 3.3058
    return df


def run_selftest():
    print("합성 데이터 생성 중... (⚠ 실제 시세 아님)")
    settings = Settings.load()
    areas = load_areas()
    df = _synth_frame()
    print(f"  합성 거래 {len(df):,} 건 생성")

    df = analyze.mark_old_apartments(df, settings)
    df = analyze.clean(df, settings)

    # 합성 데이터는 좌표를 직접 넣어 거리 계산
    df["apt_lat"] = df["_apt_lat"]
    df["apt_lon"] = df["_apt_lon"]
    df = geo.nearest_area_distance(df, areas, settings.distance_bands_m)
    df_old = df[df["is_old"]].copy()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    appr = analyze.distance_band_appreciation(df_old)
    print("\n=== [합성] 거리구간별 상승률 (가까울수록 커야 정상) ===")
    print(appr.to_string(index=False))

    event_df = analyze.event_study(df_old, areas, settings)
    did = analyze.diff_in_diff(event_df)
    print("\n=== [합성] 이벤트 스터디 간이 DID ===")
    print(f"  근거리 사후상승={did.get('treated')} / 원거리={did.get('control')} / DID={did.get('did_effect_pp')} pp")

    # 차트도 실제로 그려지는지 확인
    band_trend = analyze.distance_band_trends(df_old)
    visualize.plot_price_trend(band_trend, OUTPUT_DIR / "selftest_trend_by_distance.png", group_col="dist_band")
    visualize.plot_distance_appreciation(appr, OUTPUT_DIR / "selftest_appreciation.png")
    if not event_df.empty:
        visualize.plot_event_study(event_df, OUTPUT_DIR / "selftest_event_study.png")

    # 검증: 근거리가 원거리보다 더 올랐는지
    band_map = {r["dist_band"]: r["change_pct"] for _, r in appr.iterrows()}
    near = band_map.get("0-500m", 0)
    far = band_map.get("2000m+", 0)
    ok = near > far and (did.get("did_effect_pp", 0) or 0) > 0
    print("\n" + ("✅ 자체점검 통과: 파이프라인이 근접 프리미엄을 정상 복원함."
                   if ok else "❌ 자체점검 실패: 로직 확인 필요."))
    print("   차트: outputs/selftest_*.png (⚠ 합성 데이터 기반, 실제 시세 아님)")
    return ok
