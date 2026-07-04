"""설정 로딩: 환경변수(.env), 분석 파라미터(settings.yaml), 재개발 단지(redevelopment_areas.yaml)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

# 프로젝트 루트 (이 파일 기준 상위 폴더)
ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
OUTPUT_DIR = ROOT / "outputs"


def load_service_key() -> str:
    """국토부 API 인증키를 .env 또는 환경변수에서 읽는다."""
    load_dotenv(ROOT / ".env")
    key = os.getenv("MOLIT_SERVICE_KEY", "").strip()
    if not key or key.startswith("여기에"):
        raise RuntimeError(
            "MOLIT_SERVICE_KEY 가 설정되지 않았습니다.\n"
            "  1) https://www.data.go.kr/data/15126469/openapi.do 에서 인증키를 발급받고\n"
            "  2) `cp .env.example .env` 후 .env 에 키를 넣으세요."
        )
    return key


def _read_yaml(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@dataclass
class Settings:
    """분석 파라미터."""

    # 구축 아파트 판정: 거래 시점 기준 준공 후 경과연수(년) 이상이면 '구축'
    old_apartment_min_age: int = 15
    # 거리 구간(m) 경계 — 재개발 구역 중심으로부터
    distance_bands_m: list[int] = field(default_factory=lambda: [500, 1000, 2000])
    # 이벤트 스터디 윈도우(개월): 이벤트 전/후 몇 개월을 볼지
    event_window_before: int = 24
    event_window_after: int = 36
    # 이벤트 스터디 기준 이벤트 종류 (config의 events 키)
    event_key: str = "management_disposal"  # 관리처분인가
    # 이상치 제거: 평단가 상/하위 백분위수 컷
    winsor_lower_pct: float = 0.01
    winsor_upper_pct: float = 0.99
    # 전용면적 필터(㎡) — 너무 작거나 큰 특수 물건 제외
    min_area_m2: float = 20.0
    max_area_m2: float = 300.0

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        path = path or (CONFIG_DIR / "settings.yaml")
        if not path.exists():
            return cls()
        raw = _read_yaml(path)
        known = {k: raw[k] for k in raw if k in cls.__annotations__}
        return cls(**known)


@dataclass
class RedevArea:
    """재개발/재건축 구역 하나."""

    id: str
    name: str
    sigungu: str          # 자치구
    lawd_cd: str          # 시군구 법정동코드 (5자리)
    dong: str             # 법정동
    lat: float
    lon: float
    type: str             # 재건축 / 재개발
    events: dict[str, str]  # {이벤트키: 'YYYY-MM'}
    households: int | None = None
    note: str = ""

    def event_month(self, key: str) -> str | None:
        return self.events.get(key)


def load_areas(path: Path | None = None) -> list[RedevArea]:
    path = path or (CONFIG_DIR / "redevelopment_areas.yaml")
    raw = _read_yaml(path)
    areas = []
    for a in raw.get("areas", []):
        areas.append(
            RedevArea(
                id=a["id"],
                name=a["name"],
                sigungu=a["sigungu"],
                lawd_cd=str(a["lawd_cd"]),
                dong=a.get("dong", ""),
                lat=float(a["lat"]),
                lon=float(a["lon"]),
                type=a.get("type", ""),
                events={k: str(v) for k, v in (a.get("events") or {}).items()},
                households=a.get("households"),
                note=a.get("note", ""),
            )
        )
    return areas


def load_lawd_codes(path: Path | None = None) -> dict[str, str]:
    """서울 자치구 법정동코드 매핑 {구이름: 코드}."""
    path = path or (CONFIG_DIR / "redevelopment_areas.yaml")
    raw = _read_yaml(path)
    return {k: str(v) for k, v in (raw.get("seoul_lawd_codes") or {}).items()}
