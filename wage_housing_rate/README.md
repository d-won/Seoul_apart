# 시간당 임금 · 서울 아파트 실거래가격지수 · 정책금리 (월별 실측)

세 지표가 지난 20여 년 어떻게 움직였는지 **월별 실측치**로 비교합니다.

1. **시간당 명목임금** — 원/시간 (KOSIS 사업체노동력조사)
2. **서울 아파트 실거래가격지수** — 2017.11=100 (한국부동산원)
3. **정책금리** — 한국은행 기준금리(%)

단위가 완전히 다르므로 **이중 축을 쓰지 않고**, ① 각 지표를 고유 단위로 보여주는
3단 패널과 ② 임금·아파트값을 공통 출발선(**2020.1=100**)에 놓은 지수 비교로 나눠 그립니다.

> **전 지표 월별 실측**입니다. 값은 KOSIS OpenAPI에서 직접 받아 `data/*_monthly.csv`에
> 저장돼 있습니다. 보간·추정 없이, 받은 월만 사용하고 **못 받은 구간은 비워** 둡니다.

## 한눈에 보기

- 2020.1(공통 기준월) 이후, 서울 아파트 실거래가격지수는 **+47%**(지수 100→147),
  시간당 명목임금은 **+12%**(지수 100→112)로 아파트값이 임금을 크게 앞질렀습니다.
- 아파트 실거래가격지수(서울)는 2006.1 58.5 → 2021 고점 → 2022 조정 → **2026.4 196.3**.
- 정책금리는 2020년 0.50% 저점 → 2023년 3.50% → **2026.7 2.75%**.
- 시간당 임금은 **명목·상여 포함**이라 1월·분기말 등 상여 지급월에 값이 크게 튑니다(계절성).

### 커버리지(월별 실측 구간)

| 지표 | 표 | 주기·기간 |
|---|---|---|
| 서울 아파트 실거래가격지수 | KOSIS `DT_KAB_11672_S1` (orgId 408, 서울) | 월 · 2006.01 ~ 2026.04 |
| 시간당 임금(임금총액/근로시간) | KOSIS `DT_118N_MON041`(2011~2019, 9차분류) + `DT_118N_MON051`(2020~, 10차분류), 전산업·전규모 | 월 · 2011.01 ~ 2025.12 |
| 기준금리(월말 유효금리) | 한국은행 변경 이력 | 월 · 2005.01 ~ 2026.07 |

## 실행

```bash
pip install -r requirements.txt
python build_charts.py        # outputs/ 에 PNG 2종 생성
```

산출물
- `outputs/three_indicators.png` — 3단 패널(임금 / 아파트 지수 / 금리), 모두 월별
- `outputs/wage_vs_apartment_index.png` — 2020.1=100 지수 비교
- `chart.html` — 인터랙티브 버전(호버 툴팁·다크모드·월별 데이터 표). 브라우저로 바로 열기.

> 한글 라벨을 위해 나눔고딕 등 한글 폰트 설치를 권장합니다(없으면 자동 영문 폴백).
> `sudo apt-get install fonts-nanum` 후 matplotlib 폰트 캐시가 갱신됩니다.

## 데이터를 다시 받으려면 (KOSIS OpenAPI)

`build_charts.py`는 `data/*_monthly.csv`(월별)가 있으면 **자동으로 월별 차트**로 그립니다.
월별 CSV는 `src/fetch_live.py`가 KOSIS OpenAPI에서 받아 만듭니다. **KOSIS 인증키**만 있으면 됩니다
(발급: <https://kosis.kr/openapi/> · 무료).

```bash
KEY='발급받은_KOSIS_인증키'   # 예: ...==  (base64, = 패딩 포함)
EP='https://kosis.kr/openapi/Param/statisticsParameterData.do?method=getList&format=json&jsonVD=Y'

# 서울 아파트 실거래가격지수 (지수 항목 itmId=T1, 서울 objL1=030)
export KOSIS_APT_URL="$EP&apiKey=$KEY&orgId=408&tblId=DT_KAB_11672_S1&prdSe=M&startPrdDe=200601&endPrdDe=202612&objL1=030&itmId=T1&objL2=&objL3=&objL4=&objL5=&objL6=&objL7=&objL8="

# 시간당 임금 = 전체임금총액(MD_12) ÷ 전체근로시간(MD_7), 전산업·전규모(objL2=size01)
# 신계열 2020~ (MON051, 10차분류 전체=190326INDUSTRY_10S0)
WNEW="$EP&apiKey=$KEY&orgId=118&tblId=DT_118N_MON051&prdSe=M&startPrdDe=202001&endPrdDe=202512&objL1=190326INDUSTRY_10S0&objL2=size01&objL3=&objL4=&objL5=&objL6=&objL7=&objL8="
export KOSIS_WAGE_PAY_URL="$WNEW&itmId=13103110311MD_12"
export KOSIS_WAGE_HRS_URL="$WNEW&itmId=13103110311MD_7"
# 구계열 2011~2019 (MON041, 9차분류 전체=15118INDUSTRY_9S0) — 2020 개편 전 구간
WOLD="$EP&apiKey=$KEY&orgId=118&tblId=DT_118N_MON041&prdSe=M&startPrdDe=201101&endPrdDe=201912&objL1=15118INDUSTRY_9S0&objL2=size01&objL3=&objL4=&objL5=&objL6=&objL7=&objL8="
export KOSIS_WAGE_PAY_URL2="$WOLD&itmId=13103110311MD_12"
export KOSIS_WAGE_HRS_URL2="$WOLD&itmId=13103110311MD_7"

python src/fetch_live.py      # → data/seoul_apt_monthly.csv, data/hourly_wage_monthly.csv
python build_charts.py        # → 세 지표 모두 월별로 재생성
```

> 참고: 데이터 값은 `Param/statisticsParameterData.do` 엔드포인트가 반환합니다
> (`statisticsData.do?method=getList`는 같은 파라미터에도 `err:20`을 내는 경우가 있음).
> 표별 코드(objL1 지역·itmId 항목)는 `statisticsData.do?method=getMeta&type=ITM`으로 확인할 수 있습니다.

## 구조

```
wage_housing_rate/
├── build_charts.py                 # matplotlib 라인 차트 생성(월별/연간 자동 감지)
├── chart.html                      # 인터랙티브 차트(자체 완결 HTML, 값 인라인 임베드)
├── requirements.txt
├── data/
│   ├── hourly_wage_monthly.csv     # 시간당 명목임금 (원/시간, 월별 2020.1~2025.12) ← KOSIS
│   ├── seoul_apt_monthly.csv       # 서울 아파트 실거래가격지수 (2017.11=100, 월별 2006.1~) ← KOSIS
│   ├── base_rate_monthly.csv       # 한국은행 기준금리 (%, 월별 2026.07까지, 변경이력 기반)
│   ├── hourly_wage.csv             # (구) 연간 임금 — 월별 파일 없을 때의 폴백
│   ├── seoul_apartment.csv         # (구) 연간 아파트 — 폴백
│   └── base_rate.csv               # (구) 연말 기준금리 — 폴백
├── src/fetch_live.py               # KOSIS(·ECOS) API 월별 수집
└── outputs/                        # 생성된 PNG
```

`build_charts.py`는 `*_monthly.csv`가 있으면 월별로, 없으면 `*.csv`(연간)로 폴백합니다.

## 한계

- **월별 커버리지가 지표마다 다릅니다**(임금 2020.1~, 아파트 2006.1~, 금리 2005.1~).
  받지 못한 구간은 추정하지 않고 그대로 비워 둡니다.
- 시간당 임금은 **명목**(물가 미반영)이며 상여 포함으로 월 변동이 큽니다. 추세는 12개월 흐름으로.
- 아파트는 **평균가(억원)가 아니라 실거래가격지수**입니다(2017.11=100).
- 준실험적 비교가 아니라 **단순 시계열 병치**입니다. 동반 움직임은 상관일 뿐 인과가 아니며,
  유동성·공급·제도 등 다른 요인이 함께 작용합니다.
