"""분석: 구축 판정, 이상치 처리, 가격추이, 거리구간 비교, 이벤트 스터디.

핵심 지표는 '평단가'(만원/3.3㎡)의 월별 중앙값(median). 중앙값은 특이 거래·평형 구성
변화에 덜 흔들려 시세 추이 대용치로 적합하다.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import Settings


# ---------------------------------------------------------------- 전처리

def mark_old_apartments(df: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    """거래 시점 기준 준공 후 경과연수 >= 임계값 이면 구축(is_old=True)."""
    df = df.copy()
    df["age_at_deal"] = df["year"] - df["build_year"]
    df["is_old"] = df["age_at_deal"] >= settings.old_apartment_min_age
    return df


def clean(df: pd.DataFrame, settings: Settings) -> pd.DataFrame:
    """해제거래 제외, 면적 필터, 결측/이상 평단가 제거 + winsorize."""
    df = df.copy()
    if "is_cancelled" in df:
        df = df[~df["is_cancelled"].fillna(False)]
    if "area_m2" in df:
        df = df[(df["area_m2"] >= settings.min_area_m2) & (df["area_m2"] <= settings.max_area_m2)]
    df = df[df["price_per_pyeong"].notna() & (df["price_per_pyeong"] > 0)]

    lo = df["price_per_pyeong"].quantile(settings.winsor_lower_pct)
    hi = df["price_per_pyeong"].quantile(settings.winsor_upper_pct)
    df = df[(df["price_per_pyeong"] >= lo) & (df["price_per_pyeong"] <= hi)]
    return df


# ---------------------------------------------------------------- 가격 추이

def monthly_median(df: pd.DataFrame, group_cols: list[str] | None = None) -> pd.DataFrame:
    """월별(그룹별) 평단가 중앙값과 거래건수."""
    keys = ["ym"] + (group_cols or [])
    g = (
        df.groupby(keys)
        .agg(
            median_ppp=("price_per_pyeong", "median"),
            mean_ppp=("price_per_pyeong", "mean"),
            n_trades=("price_per_pyeong", "size"),
        )
        .reset_index()
    )
    g["ym_date"] = pd.PeriodIndex(g["ym"], freq="M").to_timestamp()
    return g.sort_values(keys)


def appreciation_summary(monthly: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    """그룹별 첫달 대비 마지막달 상승률(%) 요약."""
    rows = []
    for key, sub in monthly.groupby(group_cols):
        # groupby(list)는 단일 컬럼도 1-튜플 키를 준다 → 정규화
        key_tuple = key if isinstance(key, tuple) else (key,)
        sub = sub.sort_values("ym_date")
        # 거래가 희박한 달의 노이즈를 줄이려 3개월 이동평균 양끝 비교
        sub = sub[sub["n_trades"] >= 1]
        if len(sub) < 2:
            continue
        first = sub["median_ppp"].head(3).mean()
        last = sub["median_ppp"].tail(3).mean()
        rows.append(
            {
                **dict(zip(group_cols, key_tuple)),
                "start_ppp": round(first, 1),
                "end_ppp": round(last, 1),
                "change_pct": round((last / first - 1) * 100, 1),
                "n_trades": int(sub["n_trades"].sum()),
            }
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 거리구간 비교

def distance_band_trends(df_old: pd.DataFrame) -> pd.DataFrame:
    """구축 아파트만으로 거리구간별 월별 평단가 추이."""
    return monthly_median(df_old, group_cols=["dist_band"])


def distance_band_appreciation(df_old: pd.DataFrame) -> pd.DataFrame:
    """거리구간별 전체 기간 상승률."""
    m = distance_band_trends(df_old)
    return appreciation_summary(m, ["dist_band"])


# ---------------------------------------------------------------- 이벤트 스터디

def event_study(
    df_old: pd.DataFrame,
    areas: list,
    settings: Settings,
    treated_band: str = "0-500m",
    control_bands: tuple[str, ...] = ("2000m+",),
) -> pd.DataFrame:
    """재개발 이벤트(t=0) 기준 상대월별 가격지수.

    각 구역의 지정 이벤트월을 t=0으로 맞추고, 인근(treated) vs 원거리(control) 구축의
    평단가를 이벤트월=100 으로 정규화한 지수의 평균을 상대월별로 산출한다.
    """
    ekey = settings.event_key
    before, after = settings.event_window_before, settings.event_window_after
    area_by_id = {a.id: a for a in areas}

    frames = []
    for area_id, sub in df_old.groupby("nearest_area_id"):
        area = area_by_id.get(area_id)
        if area is None:
            continue
        em = area.event_month(ekey)
        if not em:
            continue
        t0 = pd.Period(em, freq="M")

        # 이 구역에 배정된 구축 거래를 treated/control 로 나눠 상대월 지수화
        for label, band_sel in (("treated", (treated_band,)), ("control", control_bands)):
            part = sub[sub["dist_band"].isin(band_sel)]
            if part.empty:
                continue
            m = monthly_median(part)
            m["rel_month"] = [(p - t0).n for p in pd.PeriodIndex(m["ym"], freq="M")]
            m = m[(m["rel_month"] >= -before) & (m["rel_month"] <= after)]
            if m.empty:
                continue
            base = m.loc[m["rel_month"].abs().idxmin(), "median_ppp"]  # t=0 근처 기준값
            if not base or base <= 0:
                continue
            m["index_100"] = m["median_ppp"] / base * 100
            m["group"] = label
            m["area_id"] = area_id
            frames.append(m[["rel_month", "index_100", "group", "area_id", "n_trades"]])

    if not frames:
        return pd.DataFrame()

    allm = pd.concat(frames, ignore_index=True)
    # 상대월 × 그룹 평균 지수 (구역 간 평균)
    out = (
        allm.groupby(["group", "rel_month"])
        .agg(index_mean=("index_100", "mean"), n_areas=("area_id", "nunique"), n_trades=("n_trades", "sum"))
        .reset_index()
        .sort_values(["group", "rel_month"])
    )
    return out


def diff_in_diff(event_df: pd.DataFrame, post_from: int = 13) -> dict:
    """이벤트 스터디 결과에서 간이 DID: (treated 사후상승 - control 사후상승).

    끝점 한 값만 쓰면 노이즈에 취약하므로, 사전(rel_month<=0) 평균 대비
    사후 안정구간(rel_month>=post_from) 평균의 상승폭을 그룹별로 구해 그 차를 DID로 본다.
    post_from 을 두는 이유: 이벤트 직후 몇 개월은 효과가 채 반영되기 전이라 제외.
    """
    if event_df.empty:
        return {}
    res = {}
    for grp in ("treated", "control"):
        g = event_df[event_df["group"] == grp]
        if g.empty:
            continue
        pre = g[g["rel_month"] <= 0]["index_mean"]
        post = g[g["rel_month"] >= post_from]["index_mean"]
        if post.empty:  # 사후 안정구간이 없으면 사후 전체로 폴백
            post = g[g["rel_month"] > 0]["index_mean"]
        if pre.empty or post.empty:
            continue
        res[grp] = round(float(post.mean()) - float(pre.mean()), 1)
    if "treated" in res and "control" in res:
        res["did_effect_pp"] = round(res["treated"] - res["control"], 1)
    return res
