# 서울 재개발 인근 구축 아파트 가격 분석

서울의 지난 10년(2015~) 아파트 실거래가를 바탕으로,
**재개발·재건축된 지역 주변의 "구축" 아파트가 얼마나 올랐는지**, 그리고
**재개발되지 않았더라도 인근에 있으면 그 파급효과(근접 프리미엄)를 받는지**를
데이터로 측정하는 분석 파이프라인입니다.

- **데이터**: 국토교통부 실거래가 공개시스템 오픈API (아파트 매매 상세)
- **측정**: ① 거리 구간별 상승률 비교 + ② 재개발 이벤트 전후 이벤트 스터디(DID) — 두 방법 결합
- 자세한 설계는 **[docs/methodology.md](docs/methodology.md)** 참고

> ⚠️ 이 저장소는 **분석 코드**입니다. 실거래가 원본(`data/raw/`)은 용량 문제로 포함하지 않습니다.
> 아래처럼 직접 수집해 실행하세요. 수집 경로는 두 가지입니다:
> - **`--source rt`** (권장·인증키 불필요): 국토부 실거래가 공개시스템(rt.molit.go.kr)의 자료제공 CSV.
> - **`--source api`** (기본): 공공데이터포털 오픈API. 인증키 필요(`.env`).
>
> `outputs/` 의 차트·CSV·핸드폰 리포트(`report.html`)는 8개 구(재개발 10곳 소재)의
> **2016.1–2026.6 실거래 254,612건**으로 채워 커밋돼 있습니다.

---

## 빠른 시작

```bash
# 1) 의존성 설치
pip install -r requirements.txt

# 2) 국토부 API 인증키 설정
#    발급: https://www.data.go.kr/data/15126469/openapi.do
cp .env.example .env
#    .env 파일을 열어 MOLIT_SERVICE_KEY 에 발급받은 '일반 인증키(Decoding)' 입력

# 3) (선택) API 없이 파이프라인 자체 점검 — 합성 데이터로 로직 검증
python run.py selftest

# 4) 실거래 수집 + 분석 (인증키 없이, rt.molit.go.kr 경로)
python run.py all --start 201601 --end 202606 --source rt

# 결과: outputs/ 폴더의 차트(.png)와 표(.csv), 콘솔의 상승률·DID 요약
```

수집과 분석을 나눠서 실행할 수도 있습니다:

```bash
# 재개발 구역 소속 8개 구 전체(2016-01 ~ 2026-06), 인증키 불필요
python run.py collect --start 201601 --end 202606 --source rt
python run.py collect --start 201601 --end 202606 --source rt --lawd 11740 11680  # 특정 구만
python run.py coords                                        # 거리 분석용 단지 좌표 수집
python run.py analyze                                       # 이미 받은 데이터로 분석
```

> 거리 구간·이벤트 스터디 분석은 아파트 좌표가 있어야 합니다. `python run.py coords` 가
> rt.molit.go.kr 지도검색에서 대상 구의 단지 좌표를 모아 `config/apartment_coords.yaml` 에 저장합니다.

---

## 무엇을 분석하나

1. **거리 구간 비교** — 재개발 구역 중심에서 `0–500m / 500–1000m / 1000–2000m / 2000m+`
   구간별로 구축 아파트 평단가 상승률을 비교. *가까울수록 더 올랐는가?*
   `2000m+` 는 광역 시장 흐름을 대표하는 **대조군**.
2. **이벤트 스터디 + DID** — 각 구역의 **관리처분인가** 시점을 `t=0` 으로 맞추고,
   근거리(0–500m) vs 원거리(2000m+) 구축의 가격지수를 비교.
   이벤트 이후 근거리만 위로 벌어지는 폭 = **재개발 근접 프리미엄**.

`python run.py selftest` 는 의도적으로 근접 프리미엄을 심은 합성 데이터에서
파이프라인이 그 효과를 되짚어내는지 검증합니다(실제 시세 아님).

---

## 구조

```
├── run.py                       # CLI 진입점 (collect / analyze / all / selftest)
├── config/
│   ├── redevelopment_areas.yaml # 재개발 구역 정의 (구·법정동·좌표·이벤트 시점) ← 핵심 수정 대상
│   ├── apartment_coords.yaml    # 아파트별 좌표 (거리 분석용) — 관심 단지 등록
│   └── settings.yaml            # 분석 파라미터 (구축 기준·거리구간·이벤트 등)
├── src/
│   ├── config.py                # 설정/인증키 로딩
│   ├── fetch.py                 # 국토부 오픈API 수집 (재시도·페이징)
│   ├── fetch_rt.py              # 국토부 실거래가공개시스템 CSV 수집 (인증키 불필요)
│   ├── fetch_coords.py          # 단지 좌표 수집 (거리 분석용, rt.molit 지도검색)
│   ├── geo.py                   # haversine 거리·거리구간 분류
│   ├── analyze.py               # 정제·가격추이·거리비교·이벤트스터디·DID
│   ├── visualize.py             # 차트 (matplotlib)
│   ├── pipeline.py              # 전체 오케스트레이션
│   └── selftest.py              # 합성 데이터 자체점검
├── docs/methodology.md          # 방법론 상세
├── outputs/                     # 차트·표 산출물 (gitignore)
└── data/                        # raw/processed 데이터 (gitignore)
```

## 커스터마이징

- **분석할 재개발 구역 추가/수정**: `config/redevelopment_areas.yaml`
  (2015~2025 주요 단지 10곳이 조사·수록되어 있음. 좌표·이벤트월은 추정치 포함이라
  `note` 의 확실/추정/불확실 표기를 확인하고 정비사업 정보몽땅 등으로 교차검증 권장.)
- **거리 구간·구축 기준·이벤트 종류 변경**: `config/settings.yaml`
- **거리 분석 정밀도**: `config/apartment_coords.yaml` 에 관심 단지 좌표를 등록할수록 정확.

## 참고 / 한계

- 국토부 API는 **월 단위·구 단위** 조회라 10년치는 (구 × 개월) 만큼 반복 호출합니다(시간 소요).
- 실거래에 위경도가 없어, 거리 분석은 등록된 좌표가 있는 단지에 한합니다.
- 한글 차트 라벨을 위해 시스템에 나눔고딕 등 한글 폰트 설치를 권장합니다
  (없으면 자동으로 영문 라벨로 폴백).
- 준실험 설계로, 지하철 개통·학군·거시정책 등 교란요인이 남습니다.
  인과 해석의 한계는 [docs/methodology.md](docs/methodology.md) §6 참고.
