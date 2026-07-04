"""전체 파이프라인 오케스트레이션: 수집 → 정제 → 거리부여 → 분석 → 시각화."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from tqdm import tqdm

from . import analyze, fetch, geo, visualize
from .config import (
    CONFIG_DIR,
    OUTPUT_DIR,
    PROCESSED_DIR,
    RAW_DIR,
    Settings,
    load_areas,
    load_service_key,
)


def collect(start_ym: str, end_ym: str, lawd_codes: list[str] | None = None) -> pd.DataFrame:
    """지정 구·기간의 실거래를 수집해 정제 DataFrame으로 반환하고 raw 저장."""
    key = load_service_key()
    client = fetch.MolitClient(key)
    areas = load_areas()
    codes = lawd_codes or sorted({a.lawd_cd for a in areas})
    months = fetch.month_range(start_ym, end_ym)

    all_frames = []
    for code in codes:
        results = []
        for ym in tqdm(months, desc=f"[{code}] 수집", unit="월"):
            results.append(client.fetch_month(code, ym))
        df = fetch.to_dataframe(results)
        if not df.empty:
            fetch.save_raw(df, code, RAW_DIR)
            all_frames.append(df)
    if not all_frames:
        return pd.DataFrame()
    return pd.concat(all_frames, ignore_index=True)


def load_collected() -> pd.DataFrame:
    """이미 수집해 둔 raw parquet 들을 합쳐서 로드."""
    frames = [pd.read_parquet(p) for p in sorted(RAW_DIR.glob("trades_*.parquet"))]
    if not frames:
        raise RuntimeError("data/raw 에 수집된 데이터가 없습니다. 먼저 collect 를 실행하세요.")
    return pd.concat(frames, ignore_index=True)


def run_analysis(df: pd.DataFrame, settings: Settings | None = None) -> dict:
    """정제 → 구축판정 → 좌표/거리 → 각종 분석 + 차트 저장. 산출물 dict 반환."""
    settings = settings or Settings.load()
    areas = load_areas()

    df = analyze.mark_old_apartments(df, settings)
    df = analyze.clean(df, settings)

    # 좌표 부여 & 최근접 재개발 구역 거리
    coords = geo.load_apartment_coords(CONFIG_DIR / "apartment_coords.yaml")
    df = geo.attach_coords(df, coords)
    df = geo.nearest_area_distance(df, areas, settings.distance_bands_m)

    df_old = df[df["is_old"]].copy()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(PROCESSED_DIR / "trades_processed.parquet", index=False)

    outputs: dict[str, object] = {}

    # 1) 전체 가격 추이
    overall = analyze.monthly_median(df_old)
    overall.to_csv(OUTPUT_DIR / "trend_overall.csv", index=False)
    outputs["trend_overall_chart"] = visualize.plot_price_trend(overall, OUTPUT_DIR / "trend_overall.png")

    # 2) 거리구간별 추이 & 상승률
    band_trend = analyze.distance_band_trends(df_old)
    band_trend.to_csv(OUTPUT_DIR / "trend_by_distance.csv", index=False)
    outputs["trend_by_distance_chart"] = visualize.plot_price_trend(
        band_trend, OUTPUT_DIR / "trend_by_distance.png", group_col="dist_band"
    )
    band_appr = analyze.distance_band_appreciation(df_old)
    band_appr.to_csv(OUTPUT_DIR / "appreciation_by_distance.csv", index=False)
    if not band_appr.empty:
        outputs["appreciation_chart"] = visualize.plot_distance_appreciation(
            band_appr, OUTPUT_DIR / "appreciation_by_distance.png"
        )
    outputs["appreciation_by_distance"] = band_appr

    # 3) 이벤트 스터디 + DID
    event_df = analyze.event_study(df_old, areas, settings)
    if not event_df.empty:
        event_df.to_csv(OUTPUT_DIR / "event_study.csv", index=False)
        outputs["event_study_chart"] = visualize.plot_event_study(event_df, OUTPUT_DIR / "event_study.png")
        outputs["did"] = analyze.diff_in_diff(event_df)

    return outputs
