#!/usr/bin/env python3
"""임금 · 서울 아파트 실거래가 · 정책금리 라인 차트 생성.

  1) 시간당 명목임금 (원/시간)
  2) 서울 아파트 실거래가 (평균 실거래가 / 실거래가격지수)
  3) 정책금리 = 한국은행 기준금리 (%)

단위가 완전히 다르므로 하나의 y축에 겹치지 않는다(이중 축 금지).
  - fig1: 3단 패널(스몰 멀티플) — 각 지표를 고유 단위로 표시
  - fig2: 임금 vs 아파트값을 지수화(첫 시점=100)한 비교

월별/연간 자동 감지:
  data/<name>_monthly.csv (month='YYYY-MM' 열) 가 있으면 **실측 월별**로 그리고,
  없으면 data/<name>.csv (year 열) 의 연간값으로 그린다.
  → 통계포털에서 월별을 받아 *_monthly.csv 로 저장하면 자동으로 월별 차트가 된다.

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

C_WAGE = "#2a78d6"   # blue
C_APT = "#eb6834"    # orange
C_RATE = "#008300"   # green
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"


def _setup_korean_font() -> bool:
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
    return ko if KO else en


def get_series(monthly_name: str, annual_name: str, valcol: str):
    """월별 파일이 있으면 (t, v, 'monthly'), 없으면 연간 (t, v, 'annual').

    t = 소수 연도(2020.0 = 2020-01). 반환: DataFrame[t, v], mode 문자열.
    """
    mpath = os.path.join(DATA, monthly_name)
    if os.path.exists(mpath):
        m = pd.read_csv(mpath, comment="#")
        ym = m["month"].str.split("-", expand=True).astype(int)
        m = m.assign(t=ym[0] + (ym[1] - 1) / 12.0, v=m[valcol])
        return m[["t", "v"]].dropna().sort_values("t").reset_index(drop=True), "monthly"
    a = pd.read_csv(os.path.join(DATA, annual_name), comment="#")
    a = a.assign(t=a["year"].astype(float), v=a[valcol])
    return a[["t", "v"]].dropna().sort_values("t").reset_index(drop=True), "annual"


def _style_axis(ax):
    ax.grid(True, axis="y", color=GRID, linewidth=0.8, zorder=0)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#c3c2b7")
    ax.tick_params(colors=MUTED, labelsize=9)


def _plot_series(ax, s, mode, color, endfmt):
    if mode == "monthly":
        # 금리는 계단, 그 외 월별은 실선(마커 없음 — 점이 너무 많음)
        style = "steps-post" if color == C_RATE else "default"
        ax.plot(s["t"], s["v"], color=color, linewidth=1.6, drawstyle=style, zorder=3)
    else:
        ax.plot(s["t"], s["v"], color=color, linewidth=2.2, marker="o",
                markersize=4, zorder=3)
    yv = s["v"].iloc[-1]
    ax.annotate(endfmt(yv), xy=(s["t"].iloc[-1], yv), xytext=(6, 0),
                textcoords="offset points", va="center", fontsize=9,
                color=color, fontweight="bold")


def _xticks(ax, tmin, tmax):
    lo, hi = int(tmin), int(tmax) + 1
    step = 3 if (hi - lo) > 12 else 2
    ax.set_xticks(list(range(lo - lo % step, hi + 1, step)))


def fig_three_panels(wage, wmode, apt, amode, rate, rmode):
    fig, axes = plt.subplots(3, 1, figsize=(10, 11), sharex=True)
    tags = {"monthly": L("월별", "monthly"), "annual": L("연간", "annual")}
    fig.suptitle(L("세 지표 추이 — 임금·아파트 %s / 금리 %s"
                   % (tags[wmode], tags[rmode]),
                   "Three indicators — wage/apt %s / rate %s" % (wmode, rmode)),
                 fontsize=14, fontweight="bold", color=INK, y=0.98)

    _plot_series(axes[0], wage, wmode, C_WAGE, lambda v: f"{v:,.0f}")
    axes[0].set_title(L("① 시간당 명목임금", "1) Hourly nominal wage"),
                      fontsize=12, color=INK, loc="left", pad=8)
    axes[0].set_ylabel(L("원 / 시간", "KRW / hour"), fontsize=10, color=MUTED)

    _plot_series(axes[1], apt, amode, C_APT, lambda v: f"{v:,.1f}")
    axes[1].set_title(L("② 서울 아파트 실거래가격지수", "2) Seoul apt. real-transaction price index"),
                      fontsize=12, color=INK, loc="left", pad=8)
    axes[1].set_ylabel(L("지수 (2017.11=100)", "Index (2017.11=100)"), fontsize=10, color=MUTED)

    _plot_series(axes[2], rate, rmode, C_RATE, lambda v: f"{v:.2f}")
    axes[2].set_title(L("③ 정책금리 (한국은행 기준금리)", "3) Policy rate (BOK base rate)"),
                      fontsize=12, color=INK, loc="left", pad=8)
    axes[2].set_ylabel(L("%", "%"), fontsize=10, color=MUTED)

    for ax in axes:
        _style_axis(ax)
    tmin = min(wage["t"].min(), apt["t"].min(), rate["t"].min())
    tmax = max(wage["t"].max(), apt["t"].max(), rate["t"].max())
    _xticks(axes[-1], tmin, tmax)
    axes[-1].set_xlabel(L("연도", "Year"), fontsize=10, color=MUTED)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    path = os.path.join(OUT, "three_indicators.png")
    fig.savefig(path, dpi=150, facecolor="#fcfcfb")
    plt.close(fig)
    return path


def fig_indexed(wage, wmode, apt, amode, rate, rmode):
    fig, ax = plt.subplots(figsize=(10, 6))
    # 공통 기준시점 = 두 계열 모두 값이 있는 첫 시점(월별 임금이 2020~라 대개 2020.01).
    # 서로 다른 시점을 100으로 잡으면 비교가 왜곡되므로 공통 기준월=100으로 맞춘다.
    base_t = max(wage["t"].iloc[0], apt["t"].iloc[0])

    def _rebase(s):
        b = s.loc[s["t"] >= base_t - 1e-9, "v"].iloc[0]
        return s.assign(v=s["v"] / b * 100)

    wi, ai = _rebase(wage), _rebase(apt)
    by, bm = int(base_t), round((base_t - int(base_t)) * 12) + 1
    base = f"{by}.{bm:02d}"
    ax.set_title(L(f"임금 vs 서울 아파트값 vs 정책금리 — {base}=100 지수 + 금리(%)",
                   f"Wage vs Seoul apt. (={base}=100) vs policy rate (%)"),
                 fontsize=14, fontweight="bold", color=INK, loc="left", pad=12)
    for s, mode, color, ko, en in [
        (wi, wmode, C_WAGE, "시간당 명목임금", "Hourly wage"),
        (ai, amode, C_APT, "서울 아파트 실거래가격지수", "Seoul apt. price index"),
    ]:
        marker = "" if mode == "monthly" else "o"
        ax.plot(s["t"], s["v"], color=color, linewidth=2.4, marker=marker,
                markersize=4, label=L(ko, en), zorder=3)
        ax.annotate(f"{s['v'].iloc[-1]:,.0f}", xy=(s["t"].iloc[-1], s["v"].iloc[-1]),
                    xytext=(6, 0), textcoords="offset points", va="center",
                    fontsize=10, color=color, fontweight="bold")
    ax.axhline(100, color=MUTED, linewidth=0.8, linestyle="--", zorder=1)
    _style_axis(ax)
    ax.set_ylabel(f"{base}=100", fontsize=10, color=MUTED)
    ax.set_xlabel(L("연도", "Year"), fontsize=10, color=MUTED)

    # 정책금리는 단위(%)가 달라 오른쪽 축에 겹쳐 그린다.
    axR = ax.twinx()
    rstyle = "steps-post" if rmode == "monthly" else "default"
    axR.plot(rate["t"], rate["v"], color=C_RATE, linewidth=1.5, drawstyle=rstyle,
             zorder=2, alpha=0.9)
    axR.annotate(f"{rate['v'].iloc[-1]:.2f}%", xy=(rate["t"].iloc[-1], rate["v"].iloc[-1]),
                 xytext=(6, 0), textcoords="offset points", va="center",
                 fontsize=9, color=C_RATE, fontweight="bold")
    axR.set_ylabel(L("정책금리 %", "Policy rate %"), fontsize=10, color=C_RATE)
    axR.tick_params(axis="y", colors=C_RATE, labelsize=9)
    for sp in ("top",):
        axR.spines[sp].set_visible(False)
    axR.spines["right"].set_color(C_RATE)
    # 정책금리 범례 항목(우축이라 프록시 선으로 추가)
    ax.plot([], [], color=C_RATE, linewidth=1.6, label=L("정책금리(우축 %)", "Policy rate (right, %)"))

    _xticks(ax, min(wi["t"].min(), ai["t"].min(), rate["t"].min()),
            max(wi["t"].max(), ai["t"].max(), rate["t"].max()))
    ax.legend(frameon=False, fontsize=11, loc="upper left")
    fig.tight_layout()
    path = os.path.join(OUT, "wage_vs_apartment_index.png")
    fig.savefig(path, dpi=150, facecolor="#fcfcfb")
    plt.close(fig)
    return path


def main():
    os.makedirs(OUT, exist_ok=True)
    wage, wmode = get_series("hourly_wage_monthly.csv", "hourly_wage.csv", "hourly_wage_won")
    apt, amode = get_series("seoul_apt_monthly.csv", "seoul_apartment.csv", "seoul_apt_avg_price_100m")
    rate, rmode = get_series("base_rate_monthly.csv", "base_rate.csv", "base_rate_pct")

    p1 = fig_three_panels(wage, wmode, apt, amode, rate, rmode)
    p2 = fig_indexed(wage, wmode, apt, amode, rate, rmode)
    print(f"한글 폰트: {'사용' if KO else '미설치 → 영문 라벨'}")
    print(f"임금={wmode}, 아파트={amode}, 금리={rmode}")
    print(f"저장: {p1}\n저장: {p2}")


if __name__ == "__main__":
    main()
