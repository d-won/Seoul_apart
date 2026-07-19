#!/usr/bin/env python3
"""최근 20년(2005~2024) 세 지표 라인 차트 생성.

  1) 시간당 명목임금 (원/시간)
  2) 서울 아파트 실거래가 (한국부동산원 실거래가격지수 및 평균 실거래가)
  3) 정책금리 = 한국은행 기준금리 (%, 연말 기준)

세 지표는 단위가 완전히 다르므로 하나의 y축에 겹치지 않는다(이중 축 금지).
  - fig1: 3단 패널(스몰 멀티플) — 각 지표를 고유 단위로 표시
  - fig2: 임금 vs 아파트값을 2005=100 으로 지수화한 비교(둘 다 '가격'이라 비교 가능)

실행:  python build_charts.py
결과:  outputs/three_indicators.png , outputs/wage_vs_apartment_index.png
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")
OUT = os.path.join(HERE, "outputs")

# 팔레트 (dataviz 기준 색)
C_WAGE = "#2a78d6"   # blue
C_APT = "#eb6834"    # orange
C_RATE = "#008300"   # green
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"


def _setup_korean_font() -> bool:
    """시스템에 한글 폰트가 있으면 사용, 없으면 영문 라벨 폴백."""
    candidates = ["NanumGothic", "Malgun Gothic", "AppleGothic",
                  "Noto Sans CJK KR", "Noto Sans KR", "UnDotum"]
    available = {f.name for f in fm.fontManager.ttflist}
    for name in candidates:
        if name in available:
            plt.rcParams["font.family"] = name
            plt.rcParams["axes.unicode_minus"] = False
            return True
    plt.rcParams["axes.unicode_minus"] = False
    return False


KO = _setup_korean_font()


def L(ko: str, en: str) -> str:
    """한글 폰트가 있으면 한글, 없으면 영문 라벨."""
    return ko if KO else en


def load() -> pd.DataFrame:
    wage = pd.read_csv(os.path.join(DATA, "hourly_wage.csv"), comment="#")
    apt = pd.read_csv(os.path.join(DATA, "seoul_apartment.csv"), comment="#")
    rate = pd.read_csv(os.path.join(DATA, "base_rate.csv"), comment="#")
    df = wage.merge(apt, on="year").merge(rate, on="year")
    return df.sort_values("year").reset_index(drop=True)


def _style_axis(ax):
    ax.grid(True, axis="y", color=GRID, linewidth=0.8, zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#c3c2b7")
    ax.tick_params(colors=MUTED, labelsize=9)


def fig_three_panels(df: pd.DataFrame):
    fig, axes = plt.subplots(3, 1, figsize=(10, 11), sharex=True)
    fig.suptitle(L("최근 20년 세 지표 추이 (2005–2024)",
                   "Three indicators, 2005–2024"),
                 fontsize=15, fontweight="bold", color=INK, y=0.98)

    panels = [
        (axes[0], df["hourly_wage_won"], C_WAGE,
         L("① 시간당 명목임금", "1) Hourly nominal wage"),
         L("원 / 시간", "KRW / hour")),
        (axes[1], df["seoul_apt_avg_price_100m"], C_APT,
         L("② 서울 아파트 평균 실거래가", "2) Seoul apt. avg. transaction price"),
         L("억 원", "100M KRW")),
        (axes[2], df["base_rate_pct"], C_RATE,
         L("③ 정책금리 (한국은행 기준금리, 연말)", "3) Policy rate (BOK base rate, y/e)"),
         L("%", "%")),
    ]
    for ax, series, color, title, ylab in panels:
        ax.plot(df["year"], series, color=color, linewidth=2.2,
                marker="o", markersize=4, zorder=3)
        ax.set_title(title, fontsize=12, color=INK, loc="left", pad=8)
        ax.set_ylabel(ylab, fontsize=10, color=MUTED)
        _style_axis(ax)
        # 마지막 값 라벨
        yv = series.iloc[-1]
        ax.annotate(f"{yv:,.2f}".rstrip("0").rstrip(".") if ylab == "%" else f"{yv:,.0f}"
                    if ylab != L("억 원", "100M KRW") else f"{yv:,.1f}",
                    xy=(df["year"].iloc[-1], yv),
                    xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=9, color=color, fontweight="bold")

    axes[-1].set_xlabel(L("연도", "Year"), fontsize=10, color=MUTED)
    axes[-1].set_xticks(df["year"][::2])
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    path = os.path.join(OUT, "three_indicators.png")
    fig.savefig(path, dpi=150, facecolor="#fcfcfb")
    plt.close(fig)
    return path


def fig_indexed(df: pd.DataFrame):
    base_year = df["year"].iloc[0]
    wage_idx = df["hourly_wage_won"] / df["hourly_wage_won"].iloc[0] * 100
    apt_idx = df["seoul_apt_avg_price_100m"] / df["seoul_apt_avg_price_100m"].iloc[0] * 100

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.set_title(L(f"임금 vs 서울 아파트값 — {base_year}년=100 지수 비교",
                   f"Wage vs Seoul apt. — indexed to {base_year}=100"),
                 fontsize=14, fontweight="bold", color=INK, loc="left", pad=12)
    ax.plot(df["year"], wage_idx, color=C_WAGE, linewidth=2.4, marker="o",
            markersize=4, label=L("시간당 명목임금", "Hourly wage"), zorder=3)
    ax.plot(df["year"], apt_idx, color=C_APT, linewidth=2.4, marker="o",
            markersize=4, label=L("서울 아파트 실거래가", "Seoul apt. price"), zorder=3)
    ax.axhline(100, color=MUTED, linewidth=0.8, linestyle="--", zorder=1)
    _style_axis(ax)
    ax.set_ylabel(L(f"{base_year}=100", f"{base_year}=100"), fontsize=10, color=MUTED)
    ax.set_xlabel(L("연도", "Year"), fontsize=10, color=MUTED)
    ax.set_xticks(df["year"][::2])
    ax.legend(frameon=False, fontsize=11, loc="upper left")

    for series, color in ((wage_idx, C_WAGE), (apt_idx, C_APT)):
        ax.annotate(f"{series.iloc[-1]:,.0f}",
                    xy=(df["year"].iloc[-1], series.iloc[-1]),
                    xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=10, color=color, fontweight="bold")

    fig.tight_layout()
    path = os.path.join(OUT, "wage_vs_apartment_index.png")
    fig.savefig(path, dpi=150, facecolor="#fcfcfb")
    plt.close(fig)
    return path


def main():
    os.makedirs(OUT, exist_ok=True)
    df = load()
    p1 = fig_three_panels(df)
    p2 = fig_indexed(df)
    print(f"한글 폰트: {'사용' if KO else '미설치 → 영문 라벨'}")
    print(f"저장: {p1}")
    print(f"저장: {p2}")
    print("\n=== 데이터 ===")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
