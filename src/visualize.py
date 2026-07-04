"""시각화: 가격추이 라인, 거리구간 비교 막대/라인, 이벤트 스터디 지수 차트.

matplotlib 사용. 한글 폰트가 시스템에 없으면 라벨이 깨질 수 있어, 폰트 자동탐색 후
없으면 영문 라벨로 폴백한다.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd

# 색상: 색약 친화 팔레트 (근거리=강조, 원거리=회색계열)
COLORS = ["#2563eb", "#16a34a", "#ea580c", "#9ca3af", "#7c3aed"]


def _setup_font() -> bool:
    """한글 폰트가 있으면 설정하고 True 반환."""
    candidates = ["NanumGothic", "Malgun Gothic", "AppleGothic", "Noto Sans CJK KR", "Noto Sans KR"]
    available = {f.name for f in fm.fontManager.ttflist}
    for c in candidates:
        if c in available:
            plt.rcParams["font.family"] = c
            plt.rcParams["axes.unicode_minus"] = False
            return True
    return False


HAS_KR = _setup_font()


def _t(kr: str, en: str) -> str:
    return kr if HAS_KR else en


def plot_price_trend(monthly: pd.DataFrame, out: Path, group_col: str | None = None):
    """월별 평단가 중앙값 추이."""
    fig, ax = plt.subplots(figsize=(11, 6))
    if group_col:
        for i, (key, sub) in enumerate(monthly.groupby(group_col)):
            sub = sub.sort_values("ym_date")
            ax.plot(sub["ym_date"], sub["median_ppp"], label=str(key), color=COLORS[i % len(COLORS)], lw=2)
        ax.legend(title=_t("거리구간", "Distance band"))
    else:
        m = monthly.sort_values("ym_date")
        ax.plot(m["ym_date"], m["median_ppp"], color=COLORS[0], lw=2)
    ax.set_title(_t("월별 평단가 중앙값 추이", "Monthly median price per pyeong"))
    ax.set_xlabel(_t("계약월", "Month"))
    ax.set_ylabel(_t("평단가 (만원/3.3㎡)", "10k KRW / 3.3m2"))
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def plot_distance_appreciation(appr: pd.DataFrame, out: Path):
    """거리구간별 상승률 막대."""
    order = ["0-500m", "500-1000m", "1000-2000m", "2000m+", "unknown"]
    appr = appr.copy()
    appr["order"] = appr["dist_band"].map({b: i for i, b in enumerate(order)}).fillna(99)
    appr = appr.sort_values("order")
    fig, ax = plt.subplots(figsize=(9, 6))
    bars = ax.bar(appr["dist_band"], appr["change_pct"], color=COLORS[0])
    for b, v in zip(bars, appr["change_pct"]):
        ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.0f}%", ha="center", va="bottom")
    ax.set_title(_t("재개발 구역 거리구간별 구축 아파트 상승률", "Old-apt appreciation by distance to redevelopment"))
    ax.set_xlabel(_t("재개발 구역으로부터 거리", "Distance to redevelopment site"))
    ax.set_ylabel(_t("기간 상승률 (%)", "Total appreciation (%)"))
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out


def plot_event_study(event_df: pd.DataFrame, out: Path):
    """이벤트월(t=0)=100 정규화 지수, treated vs control."""
    fig, ax = plt.subplots(figsize=(11, 6))
    style = {"treated": (COLORS[0], _t("근거리(0-500m)", "Near (0-500m)")),
             "control": (COLORS[3], _t("원거리(대조군)", "Far (control)"))}
    for grp, (color, label) in style.items():
        g = event_df[event_df["group"] == grp].sort_values("rel_month")
        if g.empty:
            continue
        ax.plot(g["rel_month"], g["index_mean"], color=color, lw=2, marker="o", ms=3, label=label)
    ax.axvline(0, color="#ef4444", ls="--", lw=1, label=_t("이벤트 시점", "Event (t=0)"))
    ax.axhline(100, color="#d1d5db", lw=1)
    ax.set_title(_t("재개발 이벤트 전후 인근 구축 아파트 가격지수", "Event study: old-apt price index around redevelopment event"))
    ax.set_xlabel(_t("이벤트 기준 상대월", "Months relative to event"))
    ax.set_ylabel(_t("가격지수 (t=0 → 100)", "Price index (t=0 = 100)"))
    ax.legend()
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    return out
