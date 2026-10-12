## Executive summary (read this first)

28개 계열을 하나씩 비교해 VSpecial 연구 결과를 만들었습니다. 물가 4계열에는 과거 추세와 추세 변화의 불확실성을 함께 반영하는 모델을 채택했습니다. 나머지는 V11을 기본으로 유지합니다. 자산별 모델을 다르게 만드는 것은 가능하지만, 테스트에서 작은 이득이 나온 모델을 모두 채택하는 것은 적절하지 않았습니다.

ZIP은 연구 코드와 결과입니다. 제출 descriptor, Codabench 제출용 ZIP, registry 업로드는 다음에 함께 준비합니다. 기본 실행 모드는 `price`이고, 전체 후보를 쓰는 `specialists` 및 제한 후보 `conservative`, 이전 VNext `adaptive` 모드도 비교용으로 남겼습니다.

### 핵심 결과

| 계열 | V11 대비 CRPS 감소 | 짧은 기간 조합에서 감소 | 90% 구간 실제 포함률 |
|---|---:|---:|---:|
| CPI_ALL | 42.2% | 47.0% | 73.3% |
| CPI_CORE | 60.9% | 55.3% | 76.7% |
| PCE_ALL | 61.9% | 51.7% | 80.0% |
| PCE_CORE | 69.4% | 65.1% | 80.0% |

이는 공개 과거 입력의 SD로 정규화한 **marginal CRPS 감소율**입니다. 주최 측 M0 scale의 공식 composite나 Codabench 점수가 아닙니다. primary 월간 steps는 [1,3,9], sensitivity는 [1,3,6]입니다. 원래 카드의 horizon key는 그대로 출력하고 실제 월수는 관측 기간·publication lag에서 계산합니다.

같은 월간 primary 사건 5개를 2,000 draws, 시드 42/77로 반복했습니다. 두 시드를 사건별로 평균했으며 10개 독립 사건으로 세지 않았습니다. sensitivity는 8개 사건이고 primary와 겹칠 수 있습니다. 월간 연도 블록이 4개뿐인 재표집 구간은 참고용입니다. 물가 개선이 크더라도 실시간 거래 성능이나 전체 대회 점수가 이만큼 개선된다는 의미는 아닙니다.

물가 4계열의 raw marginal, horizon joint variogram, tail pinball도 V11보다 줄었습니다. 다만 90% 예측구간의 실제 포함률은 표처럼 73~80%로 아직 낮습니다. 이전 VNext와 비교하면 CPI_ALL은 VNext 쪽 marginal CRPS가 더 좋고, 새 모델은 근원 CPI·PCE와 일부 포함률에서 더 좋았습니다. 새 버전이 모든 지표에서 앞선다고 주장하지 않습니다.

6개 월간 지표를 하나의 공동 grid로 묶은 로컬 composite 감소는 약 0.04%에 그쳤습니다. 원단위 NFP와 지표 간 차이가 공동 손실에 크게 영향을 주기 때문입니다. 개별 물가 오차 감소를 전체 공동 점수 감소로 표현하지 않았습니다. 실제 대회의 단위별 target grid와 M0 scale은 별개입니다.

### 계열별로 무엇을 시험했나

- 일별 15개 설정: V11형 empirical walk, EWMA 20/120, rolling variance, causal filtered historical simulation, Gaussian, Student-t, GARCH, 평균 0/축소/최근 momentum, 변화 AR, 수준 평균회귀, FX log walk.
- 월간 14개 설정: 무추세 기준, 6/12/36/60개월 추세, 감쇠 추세, 변화 AR, 국소 선형 추세, 계절성, robust median, 수준 평균회귀, log 추세, 추세 혼합.
- 물가 후속 32개 설정: 8개 추세 × 4개 추세 불확실성 강도. 공동 Gaussian 월별 충격과 공동 역사적 추세 변화 vector를 사용합니다. 한 draw의 미래 경로를 공유하므로 horizon 중첩을 유지합니다.
- 마지막 일별 추가: ridge VAR, 긴 학습 구간 VAR, 주·월 평균 lag를 쓰는 VAR, PCA 수준 평균회귀. PCA는 수준 목표에서만 의미가 있습니다. 최초 factors 개발 로그의 pca_revert는 VAR fallback 중복이며 후보 성능으로 따로 세지 않았습니다.

데이터에 실제로 있는 계열은 금리 6, G10 FX 10, 요인 6, 월간 6으로 총 28개입니다. GDP는 원래 안내 표에 적혀 있지만 공급 파일에 연속 GDP 이력이 없어 정확도 시험을 할 수 없었습니다. GDP 모델을 검증 완료로 표시하지 않았고, 알 수 없는 월간 계열은 기준 모델로 갑니다.

### 28개 계열 결정표

| 계열 | 개발 기간 최고 후보 | 개발 CRPS 감소 | 후속 Phase 1 변화 | 채택 |
|---|---|---:|---:|---|
| BAB | specialists | +6.7% | +1.5% | V11 |
| HML | momentum | +10.5% | +0.4% | V11 |
| MKT | garch | +0.2% | +0.3% | V11 |
| MOM | ewma20 | +1.3% | +0.3% | V11 |
| QMJ | ridge_var_long | +1.7% | +0.1% | V11 |
| SMB | ridge_var_long | +3.6% | +0.4% | V11 |
| AUD | momentum | +2.4% | +0.0% | V11 |
| CAD | momentum | +1.1% | +0.7% | V11 |
| CHF | pca_revert | +1.8% | -0.4% | V11 |
| DKK | momentum | +1.7% | -0.0% | V11 |
| EUR | momentum | +1.9% | +0.0% | V11 |
| GBP | momentum | +1.5% | +0.1% | V11 |
| JPY | ridge_var_long | +0.6% | +0.5% | V11 |
| NOK | momentum | +1.1% | -0.0% | V11 |
| NZD | momentum | +0.8% | +0.0% | V11 |
| SEK | momentum | +1.9% | +0.0% | V11 |
| CPI_ALL | trend60:u1 | +30.3% | +45.4% | inflation_uncertain_trend |
| CPI_CORE | seasonal:u1 | +79.9% | +53.6% | inflation_uncertain_trend |
| NFP | trend6:u0 | +34.0% | -3.4% | V11 |
| PCE_ALL | trend60 | +36.8% | +59.3% | inflation_uncertain_trend |
| PCE_CORE | trend60 | +76.6% | +67.4% | inflation_uncertain_trend |
| UNRATE | local_linear:u1 | +7.8% | -1.5% | V11 |
| UST_10Y | pca_revert | +2.3% | -0.1% | V11 |
| UST_20Y | pca_revert | +1.7% | -0.2% | V11 |
| UST_2Y | specialists | +1.1% | +0.0% | V11 |
| UST_30Y | pca_revert | +2.5% | -0.2% | V11 |
| UST_5Y | ridge_var | +0.7% | -0.3% | V11 |
| UST_7Y | pca_revert | +0.8% | -0.4% | V11 |

개발 최고 후보는 2006~2019의 후보 순위입니다. 후속 Phase 1 열은 후보를 자산별로 고르는 실제 runtime router의 2020년 이후 결과입니다. 서로 다른 모델/기간이므로 개발 최고 후보의 이득이 그대로 재현됐다는 뜻은 아닙니다. CSV에는 마지막 공동 선형 후보의 탐색적 최고 결과도 별도로 넣었습니다. 후속 기간에서 최고인 후보를 소급해 고른 값은 검증된 채택 성능으로 취급하지 않습니다.

HML/BAB/SMB의 개발 이득은 후속 구간에서 약 0.4~1.5%로 작아졌습니다. 고용 NFP의 Phase 1은 약 3.4% 악화했습니다. UNRATE도 악화했습니다. 마지막 공동 선형 모델은 패널 평균으로 금리 최대 약 1.8%, FX 약 0.6%, 요인 약 1.1%의 marginal 개선을 보였지만 일부 자산의 joint/tail은 악화했고 개발/후속 승자가 달랐습니다. 여러 후보를 비교한 후의 작은 최고값을 이유로 기본 모델을 교체하지 않았습니다. 모두 소스와 집계 결과를 남겼습니다.

### 채택한 모델의 구조

`inflation.py`는 현재 입력만으로 각 물가 계열의 추세, 분산, 공동 상관과 추세 변화 분포를 추정합니다. 최대 8개 비중첩·완전히 해결된 과거 block에서 각 후보를 비교합니다. 과거 점수가 3% 이상 좋아지고 절반 이상의 fold에서 이겨야 채택하며, 15%의 전체 draw는 baseline으로 남깁니다. CPI/PCE마다 다른 후보를 선택할 수 있습니다.

다른 월간 지표는 원래 Gaussian walk와 같은 공동 충격을 사용합니다. 일별 계열은 업로드된 V11 numerical sampler를 호출합니다. 긴 FX 공백은 별도 처리합니다. 공통 draw 번호만 맞춘 것이 아니라 실제 공동 충격 경로를 공유합니다. 월간 selector는 scaled CRPS/pinball 대리목표이고 공식 composite 최적화와 동일하지 않습니다.

긴 FX 공백의 회귀는 현재 G10 proxy가 제공되고 과거 겹치는 날짜가 있을 때만 실행합니다. 10개 G10 통화에 인위적인 5년 공백을 넣은 24개 공동 사례에서 평균 보정 CRPS는 V11 0.816186 → 공백 안전 처리 0.707604 → proxy 혼합 0.695661이었습니다. 개선의 큰 부분은 공백을 하루 충격으로 잘못 계산하지 않는 데서 왔습니다. 대회 실제 EM 카드의 정확도를 증명한 결과는 아닙니다.

### 검증 조건과 한계

개발: 일별 패널당 36개 non-overlap origin, 월간 18개 origin, 1,000 draws. 후속: 금리 19·FX 19·요인 17·월간 5개 origin, 2,000 draws, 두 시드. 난수 반복, 다른 horizon grid, 같은 사건의 다른 모델을 독립 사례로 세지 않았습니다. 2020~2024는 이전 VNext 연구에서도 확인한 데이터라 완전히 새로운 holdout이 아닙니다. 후속 물가 개선과 최종 지원 범위 결정은 탐색적 연구이며 pristine final validation으로 표현하지 않습니다.

macro 데이터는 하나의 revised vintage입니다. 역사 당시 release vintage를 재현한 real-time backtest가 아닙니다. 입력만으로 만든 로컬 reference expectation은 24개 모의 결과에 기반하며 주최 측 M0 ref_scale과 같지 않습니다. 정규화 CRPS, 로컬 composite, raw component를 구분해 CSV에 기록했습니다. source hash와 코드 hash를 남겼고 default engine의 측정 파일과 ZIP 소스가 같은지 검사했습니다.

실제 House endpoint는 사용하지 못했습니다. 숫자 시험은 text off이고, 모의 JSON은 흐름 검증입니다. 기존 guarded text 정책의 실제 text uplift 및 원래 V11 text 정책 대비 성능은 미검증입니다. 하나의 House 시나리오가 공동 draw에 적용되며 추세를 이중 반영하지 않도록 prompt를 명시했습니다.

업로드된 V11은 재구성본입니다. 원래 제출 이미지와 byte-identical하지 않다는 provenance를 보존했습니다. 이전 제출 score -2.2219와 여기 수치를 직접 비교할 수 없습니다. inference는 현재 입력만 읽고 benchmark loss·과거 정답·학습된 정책 artifact를 읽지 않습니다.

### 실행 검증

- 최종 공개 카드 **103/103**이 공식 g0~g3를 통과: 각 2,000 draws.
- F1~F4 모의 House response가 변환을 만들고 gates 통과.
- 자체 회귀 테스트 **15개 통과**: cutoff, gaps, 월간 추세·lag, joint 경로, citation, 재현성, non-price baseline 동일성, 공동 회귀 충격.
- 실제 `forecast` 명령: 읽기 전용 root, offline, tmpfs 조건에서 네 가족 카드 모두 통과. 출력은 정확히 세 파일.
- 공식 scoring/helper 코드는 수정하지 않았습니다. 이전 동일 toolkit 검증은 common 719 통과, T2 469 통과/1 upstream footer-budget 테스트 실패/2 skip이었습니다. 이번에는 모델 테스트와 실제 g0~g3를 실행했습니다. 공식 전체 suite를 전부 통과했다고 주장하지 않습니다.

### 파일 안내

- `VSpecial/`: 기본 물가 hybrid와 연구 후보, tests, 고정 dependencies, Dockerfile.
- `V11_reconstruction/`: 비교에 사용한 V11 코드와 원본 provenance.
- `research/`: 실행 가능한 benchmark, 시점 분리 계획, 후속 실험 설명, 재실행 PowerShell.
- `reports/ASSET_DECISIONS_28.csv`: 28개 개별 결정과 비교 결과.
- `reports/`: 후보별 집계, paired 연도 block 구간, 실행·gate 기록. 패널 원본, 카드별 forecast, 사건별 원시 loss는 공개 ZIP에서 제외했습니다.
- `MANIFEST.json`: 포함 파일 SHA-256. `provenance.json`: 데이터·모델·환경 출처.

재실행: GitHub 저장소를 로컬에 내려받아 V11/units를 확보한 뒤 `research/REPRODUCE.ps1 -RepositoryRoot 'C:\absolute\Agenthon-2026'`를 실행합니다. Docker가 필요하고 결과 폴더는 덮어쓰지 않습니다. 추가 후보는 experiment.py의 --candidates/--inflation-grid/--crossasset-grid로 재실행합니다.

