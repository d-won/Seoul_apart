# RUN_MONTHLY — 집값·임금을 실측 월별로 채우는 실행 지시

이 문서는 **네트워크(kosis.kr)가 열린 세션의 Claude가 읽고 그대로 실행**하기 위한 지시서다.
목표: **서울 아파트 실거래가·시간당 임금을 KOSIS 실측 월별로** 채운다.
(정책금리는 이미 변경이력 기반 실측 월별 완료 — ECOS/추가키 불필요.)

## 사용자가 주는 것
KOSIS OpenAPI URL 2개(인증키 포함, **수록주기=월**):
- `KOSIS_APT_URL` — 아파트 실거래가격지수 `DT_KAB_11672_S1`(서울), 월별
- `KOSIS_WAGE_URL` — 시간당 임금 `DT_118N_MON051`(시간당 임금총액), 월별

사용자가 이 URL을 메시지로 주면 아래를 실행한다.

## 실행 순서

1. 브랜치 최신화
   ```bash
   git fetch origin claude/korea-wage-housing-rate-charts-3sbkm6
   git checkout claude/korea-wage-housing-rate-charts-3sbkm6
   git pull origin claude/korea-wage-housing-rate-charts-3sbkm6
   ```
2. 접속 확인(200 계열이어야 함): `curl -sS -o /dev/null -w "%{http_code}\n" https://kosis.kr`
3. 수집
   ```bash
   cd wage_housing_rate
   pip install -r requirements.txt
   export KOSIS_APT_URL='<사용자가 준 아파트 URL>'
   export KOSIS_WAGE_URL='<사용자가 준 임금 URL>'
   python src/fetch_live.py
   ```
   - `data/seoul_apt_monthly.csv`, `data/hourly_wage_monthly.csv` 생성 확인.
   - 값 상식 검증: 임금 약 1만~2.7만 원/시간, 아파트 지수/가격 추세.
   - 실패 시: KOSIS JSON 응답을 출력해 `PRD_DE`가 `YYYYMM`(월)인지, `DT` 값 위치를 확인하고
     `src/fetch_live.py`의 파싱 또는 URL을 고친다.
   - **아파트 표가 '지수'면** 열 값이 지수다 → 라벨/단위를 '실거래가격지수'로 표기(평균가 억원 아님).
4. PNG 재생성: `python build_charts.py`
   - 로그에 `임금=monthly, 아파트=monthly, 금리=monthly` 확인.
   - `outputs/three_indicators.png`, `outputs/wage_vs_apartment_index.png` 눈으로 검증.
5. 인터랙티브(`chart.html`) 월별화
   - `chart.html`에는 이미 시간축 차트 함수 `makeMonthly()`가 있고 금리 패널이 그것을 쓴다.
   - `WAGE`/`APT` 배열을 `data/*_monthly.csv`의 월별 값으로 교체하고, ①②패널과 상단
     "2005=100 지수 비교" 히어로도 `makeMonthly()`(동일 시간축 방식)로 바꿔 세 지표 모두 월별 렌더.
   - CSP상 런타임 CSV 로드 불가 → 값은 `chart.html`에 **인라인 임베드**.
   - KPI·부제·데이터표의 "연간/2025까지" 문구를 월별·최신월 기준으로 갱신.
6. 커밋·푸시
   ```bash
   git add -A
   git commit -m "Fill wage & Seoul apartment with real monthly data (KOSIS)"
   git push -u origin claude/korea-wage-housing-rate-charts-3sbkm6
   ```

## 원칙
- **보간·추정 금지.** 받은 실측 월별만 사용한다.
- KOSIS에서 못 받은 구간은 채우지 말고 **빈 구간으로 그대로 표기**한다.
- 산업분류 개편 등 계열 단절이 있으면 주석으로 남긴다.
