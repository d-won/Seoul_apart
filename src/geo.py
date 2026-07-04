"""지리 계산: 재개발 구역 중심과 거래 아파트 사이 거리, 거리 구간(band) 분류.

문제: 국토부 실거래가에는 위경도가 없다. 아파트명 + 법정동 + 지번만 있다.
해결 전략(우선순위):
  1) config/apartment_coords.yaml 에 아파트별 좌표를 등록해 두면 그걸 사용(가장 정확).
  2) 없으면 카카오/네이버 지오코딩 API로 (법정동+지번 또는 도로명) → 좌표 변환(선택적).
  3) 그래도 없으면 해당 거래는 거리 분석에서 제외(가격추이 분석에는 계속 사용).

여기서는 (1) 사전 등록 좌표 + haversine 거리 + 구간 분류를 제공한다.
지오코딩은 geocode.py(선택)에서 처리하며, 키가 없으면 (1)만으로 동작한다.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Iterable

import pandas as pd
import yaml

EARTH_R_M = 6_371_000.0


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """두 좌표 사이 대권 거리(미터)."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_R_M * math.asin(math.sqrt(a))


def distance_band(dist_m: float, bands: list[int]) -> str:
    """거리(m)를 구간 라벨로. bands=[500,1000,2000] -> '0-500m','500-1000m','1000-2000m','2000m+'."""
    prev = 0
    for b in bands:
        if dist_m <= b:
            return f"{prev}-{b}m"
        prev = b
    return f"{prev}m+"


def load_apartment_coords(path: Path) -> dict[str, tuple[float, float]]:
    """아파트별 좌표 사전. key='법정동코드|아파트명', value=(lat, lon)."""
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    out: dict[str, tuple[float, float]] = {}
    for item in raw.get("apartments", []):
        key = f"{item['lawd_cd']}|{item['apt_name']}"
        out[key] = (float(item["lat"]), float(item["lon"]))
    return out


def attach_coords(df: pd.DataFrame, coords: dict[str, tuple[float, float]]) -> pd.DataFrame:
    """거래 DataFrame에 아파트 좌표(lat/lon)를 병합. sgg_cd + apt_name 기준."""
    df = df.copy()
    lawd = df.get("sgg_cd", pd.Series([""] * len(df))).astype(str)
    key = lawd.str.slice(0, 5) + "|" + df["apt_name"].astype(str)
    df["apt_lat"] = key.map(lambda k: coords.get(k, (None, None))[0])
    df["apt_lon"] = key.map(lambda k: coords.get(k, (None, None))[1])
    return df


def nearest_area_distance(
    df: pd.DataFrame,
    areas: Iterable,
    bands: list[int],
) -> pd.DataFrame:
    """각 거래에서 가장 가까운 재개발 구역까지 거리와 그 구역 id, 거리구간을 부여.

    좌표가 없는 거래는 dist_m=NaN, band='unknown'.
    """
    df = df.copy()
    area_list = list(areas)

    dist_col = []
    id_col = []
    band_col = []

    for lat, lon in zip(df.get("apt_lat"), df.get("apt_lon")):
        if lat is None or lon is None or pd.isna(lat) or pd.isna(lon):
            dist_col.append(float("nan"))
            id_col.append(None)
            band_col.append("unknown")
            continue
        best_d = float("inf")
        best_id = None
        for a in area_list:
            d = haversine_m(lat, lon, a.lat, a.lon)
            if d < best_d:
                best_d = d
                best_id = a.id
        dist_col.append(best_d)
        id_col.append(best_id)
        band_col.append(distance_band(best_d, bands))

    df["nearest_area_id"] = id_col
    df["dist_m"] = dist_col
    df["dist_band"] = band_col
    return df
