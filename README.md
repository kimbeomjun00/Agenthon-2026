# Agenthon 2026 Track 2 — 금융 시계열 확률예측 연구

## 한국어

### 프로젝트 소개

이 저장소는 [Agenthon 2026](https://www.agenthon.net/#tracks) Track 2의 금융 시계열 확률예측 문제를 위해 개발한 개인 연구 기록입니다. 공식 대회 저장소는 [Agenthon-2026/track2-forecasting-public](https://github.com/Agenthon-2026/track2-forecasting-public)입니다.

목표는 각 과제의 기준일(as-of)까지 제공된 수치 패널과 시점이 고정된 텍스트를 이용해 미래를 하나의 값이 아닌 **공동 Monte Carlo 표본 분포**로 예측하는 것입니다.

다루는 패널은 다음과 같습니다.

| 패널 | 주요 계열 | 예측 특성 |
| --- | --- | --- |
| 미국 국채 금리 | UST 2Y, 5Y, 7Y, 10Y, 20Y, 30Y | 수익률곡선의 수준·기울기·곡률과 공동 움직임 |
| G10 FX | EUR, GBP, JPY, CHF, AUD, CAD, NZD, SEK, NOK, DKK | 달러 공통요인, 로그가격, 변동성 상태 |
| 거시지표 | CPI, PCE, NFP, UNRATE 등 | 월간 관측, 발표시차, 추세와 추세 불확실성 |
| 주식 팩터 | MKT, SMB, HML, MOM, BAB, QMJ | 일별 수익률, 비정규 꼬리, 변동성 군집 |

### 연구 흐름

- **V11** — 경험적 공동 경로와 House 텍스트 시나리오를 결합한 기준 모델입니다. Development 기록 점수는 **-2.2219**입니다.
- **VNext** — 패널별 적응형 수치 모델을 탐색했습니다.
- **VSpecial** — 28개 계열을 개별 비교하고 CPI/PCE 물가 계열에 불확실성 추세 모델을 채택했습니다.
- **VSpecial2 Audit** — 과적합, 미래정보 누출, 평가 집계와 재현성을 재점검했습니다.
- **VExpert** — 금리·FX·팩터·거시 계열별 전문가 후보와 통합 라우팅을 실험했습니다.
- **VStack** — 확률분포 스태킹을 순차 검증하고, 결과가 일관되지 않을 때 기존 검증 경로로 복귀하는 보수적 통합을 완성했습니다.
- **Short V2 / Volatility-Adaptive V2** — 공개된 1–4영업일 practice 카드에 맞춰 단기 라우터를 재설계하고, F3 카드에만 cutoff-local 변동성 적응을 적용했습니다.

### 공식 최종 제출 모델: `short_v2_adaptive` (2026-10-26)

공식 22개 short-horizon practice 카드가 공개된 뒤, 동일한 카드와 다섯 개 Monte Carlo seed로 기존 제출 이미지와 새 후보를 다시 비교했습니다. 점수는 낮을수록 좋습니다.

| 후보 | 공개 practice 평균 | 재구성 Gaussian M0 대비 |
| --- | ---: | ---: |
| 기존 제출 VStack Stable | 1.160303 | -1.58% |
| 재구성 Gaussian M0 | 1.142238 | 기준 |
| Short V2 | 1.061779 | +7.04% |
| **Volatility-Adaptive V2** | **1.057194** | **+7.45%** |

공식 최종 모델은 **Volatility-Adaptive V2**입니다. Short V2의 단기 전용 라우팅을 유지하면서 F3 카드에서만 최근 20일과 120일의 cutoff-local 변동성을 비교해 완성된 경로를 제한적으로 재조정합니다. F1·F2·F4·월별 및 미지원 입력은 Short V2와 동일합니다. 전 자산군에 적응을 적용하는 후보는 악화되어 기각했습니다.

#### 모델 작동 방식

| 입력 유형 | 활성 수치 경로 |
| --- | --- |
| Treasury F1/F2 | 기존 검증 금리 경로를 그대로 유지 |
| FX F3 | 연속된 과거 구간을 공동으로 재표본화하여 자산 간·시계열 의존성을 보존 |
| 그 밖의 일별 카드 | 기준일 이전 최근 300개 관측으로 추정한 공동 Gaussian random walk |
| 월별 또는 미지원 입력 | 동결된 VStack Stable 경로로 안전하게 복귀 |

F3 변동성 보정은 각 자산의 빠른 변동성(20일 반감기)과 느린 변동성(120일 반감기)의 비율을 계산한 뒤, 5% 이내 변화는 무시하고 공통 시장 신호를 25% 혼합합니다. 최종 배율은 0.80–1.25로 제한하며, 마지막 관측값을 기준으로 전체 Monte Carlo 경로를 확대하거나 축소합니다. 방향을 예측하는 신호가 아니라 현재 변동성 상태에 맞춰 **분포의 폭**만 조정하는 장치입니다.

텍스트는 기준일 이전 문서만 읽는 기존 guarded House 경로를 유지합니다. 제공 문서 ID로 검증되지 않은 근거는 중립화하고, 유효한 시나리오도 신뢰도와 상한을 적용한 뒤 수치 분포에 제한적으로 반영합니다. 카드 ID, 정답표, 외부 시세 또는 미래 데이터는 추론에 사용하지 않습니다.

#### 최종 모델 수식

기준일을 $T$, 자산 수를 $p$, Monte Carlo draw 수를 $D=2000$으로 둡니다. 최종 출력은 모든 자산과 horizon을 함께 담는 공동 표본

$$
\widehat{Y}\in\mathbb{R}^{D\times H\times p}
$$

입니다.

**1. 일반 일별 경로 — 공동 Gaussian random walk**

기준일 이전 최근 $n\le 299$개의 일별 변화량 $x_t=y_t-y_{t-1}$으로 평균과 공분산을 추정합니다.

$$
\widehat\mu=\frac{1}{n}\sum_{t=T-n+1}^{T}x_t,
\qquad
\widehat\Sigma=\operatorname{Cov}(x_t)+\varepsilon I
$$

각 draw의 공동 innovation과 미래 수준은 다음과 같습니다.

$$
\epsilon_{d,h}\sim\mathcal{N}(\widehat\mu,\widehat\Sigma),
\qquad
\widetilde y_{d,h}=y_T+\sum_{k=1}^{h}\epsilon_{d,k}
$$

공분산을 공동으로 추정하고 같은 draw 안에서 모든 자산을 함께 생성하므로 자산 간 의존성을 유지합니다.

**2. FX F3 — 연속 역사경로 재표본화**

FX는 로그 변화량 $r_t=\log(y_t/y_{t-1})$을 사용합니다. 과거의 연속 구간 시작점 $b_d$를 뽑고, 당시의 causal volatility로 표준화한 경로를 현재 변동성으로 다시 스케일합니다.

$$
u_t=\frac{r_t-\bar r}{\sigma_{t^-}},
\qquad
\widehat r_{d,h}=\bigl(u_{b_d+h}-\bar u_h\bigr)\sigma_T+\bar r
$$

$$
\widetilde y_{d,h}=y_T\exp\left(\sum_{k=1}^{h}\widehat r_{d,k}\right)
$$

각 draw가 완성된 과거 구간 전체를 사용하므로 독립적인 일별 재표본화보다 시계열 지속성과 자산 간 동조를 더 잘 보존합니다.

**3. F3 전용 fast/slow 변동성 적응**

반감기 $\lambda\in\{20,120\}$인 지수가중 변동성을 계산합니다. 코드에서는 최근 가중분산 90%와 전체 표본분산 10%를 혼합합니다.

$$
w_k^{(\lambda)}=\frac{2^{-k/\lambda}}{\sum_j2^{-j/\lambda}},
\qquad
\sigma_\lambda^2=0.9\sum_k w_k^{(\lambda)}(x_{T-k}-\mu_\lambda)^2
+0.1\operatorname{Var}(x)
$$

자산 $j$의 fast/slow 비율과 deadband 적용값은

$$
q_j=\operatorname{clip}\left(\frac{\sigma_{20,j}}{\sigma_{120,j}},0.5,2.0\right),
$$

$$
a_j=\operatorname{sign}(\log q_j)
\max\bigl(|\log q_j|-\log(1.05),0\bigr)
$$

입니다. 자산별 신호 75%와 전체 자산의 중앙값 신호 25%를 결합한 최종 배율은

$$
m_j=\operatorname{clip}\left[
\exp\left(0.75a_j+0.25\operatorname{median}(a)\right),
0.80,1.25
\right].
$$

이 배율은 방향이 아니라 경로의 폭만 조정합니다.

$$
\widehat y_{d,h,j}=y_{T,j}+m_j(\widetilde y_{d,h,j}-y_{T,j})
$$

로그 경로에서는 양수성을 보존하기 위해

$$
\widehat y_{d,h,j}=y_{T,j}
\exp\left[m_j\log\left(\frac{\widetilde y_{d,h,j}}{y_{T,j}}\right)\right]
$$

을 사용합니다. 이 조정은 **F3 카드에만** 적용됩니다.

**4. Guarded House 텍스트 시나리오**

유효한 문서 ID를 인용한 시나리오 $s$만 확률 $p_s$로 선택합니다. 수치경로 평균을 $\bar y_{h,j}$, horizon별 shift를 $\delta_{s,j}$, 변동성 배율을 $v_{s,j}$라 하면

$$
y'_{d,h,j}=\bar y_{h,j}
+v_{s,j}(\widehat y_{d,h,j}-\bar y_{h,j})
+\delta_{s,j}\,\sigma_j\frac{h}{H}.
$$

$\delta$와 $v$는 House confidence로 축소되고 고정 범위로 제한됩니다. 근거가 없거나 제공 corpus 밖의 문서를 인용하면 $\delta=0$, $v=1$로 중립화됩니다.

모델이 겨냥하는 공식 카드 손실은

$$
L=0.5L_{\text{marginal CRPS}}
+0.3L_{\text{joint variogram}}
+0.2L_{\text{tail}}
$$

이며 낮을수록 좋습니다. 공식 웹 leaderboard는 전 트랙 표시 방향을 맞추기 위해 Track 2 loss를 higher-is-better 점수로 변환합니다.

- 공개 practice: F3 5개 카드의 5-seed 평균에서 **5/5 개선**, 비-F3 결과는 Short V2와 동일
- 답안 비사용 롤링 검증: 전체 +1.75%, 2018–2024 +2.64%
- 최종 소스 테스트: **32/32 통과**
- 새 Docker 이미지: `docker.io/kbj710211/agenthon-t2-v11@sha256:40509e6a4c0c6b37ef64beb9cf626a07f8b6b55abbcaf8931ceb1edf93c5decb`
- 새 이미지의 공식 practice 구조 검증: **22/22 admissible**, g0–g3 전부 통과
- CodaBench 제출 ID **1009150**: `Finished`
- 운영진이 Team 478의 Track 2 최종 엔트리로 공식 인정
- **공식 Final 결과: 55위 / 83개 scored entries, 표시 점수 -1.0818**

공개 practice는 모델 선택에 사용된 작은 표본이므로 위 결과는 Final 점수나 순위를 보장하지 않습니다. 상세 기록은 [Adaptive V2 제출 상태](submission/VSTACK_ADAPTIVE_V2_FINAL.md)와 [재현 연구 폴더](VStackAdaptiveV2/)에 있습니다.

### 주요 파일

| 파일 | 내용 |
| --- | --- |
| [Final 결과 및 회고](research/FINAL_RESULTS_2026-11-03.md) | 공식 55위 결과, 해석 한계와 후속 연구 과제 |
| [VStackAdaptiveV2/](VStackAdaptiveV2/) | Short V2·변동성 적응형 V2 최종 소스, 결과표와 재현 코드 |
| [Adaptive V2 제출 상태](submission/VSTACK_ADAPTIVE_V2_FINAL.md) | 이미지 digest, 검증 결과, 교체 제출 ZIP 지문과 현재 상태 |
| [Short/Adaptive V2 연구 ZIP](research/Agenthon_VStack_Short_and_Adaptive_V2_2026-10-21.zip) | Team Key와 제출 인증정보를 제외한 연구 번들 |

> **주의:** `research/*.zip`은 연구·재현용 번들입니다. Codabench 제출용 `submission.zip`이 아니며 팀 인증 파일이나 제출 자격을 포함하지 않습니다.

---

# Agenthon 2026 Track 2 — Financial Time-Series Probabilistic Forecasting

## English

### Overview

This repository is a personal research record for the financial time-series probabilistic forecasting task in [Agenthon 2026](https://www.agenthon.net/#tracks) Track 2. The official competition repository is [Agenthon-2026/track2-forecasting-public](https://github.com/Agenthon-2026/track2-forecasting-public).

The objective is to use only numerical panels and timestamped text available at each task's as-of date and predict the future as a **joint Monte Carlo sample distribution**, rather than as a single point estimate.

The project covers four data domains:

| Panel | Main series | Forecasting focus |
| --- | --- | --- |
| U.S. Treasury rates | UST 2Y, 5Y, 7Y, 10Y, 20Y, 30Y | Curve level, slope, curvature, and joint movement |
| G10 FX | EUR, GBP, JPY, CHF, AUD, CAD, NZD, SEK, NOK, DKK | Common USD factor, log prices, and volatility regimes |
| Macro releases | CPI, PCE, NFP, UNRATE, and related series | Monthly timing, release lags, trends, and trend uncertainty |
| Equity factors | MKT, SMB, HML, MOM, BAB, QMJ | Daily returns, non-Gaussian tails, and volatility clustering |

### Research progression

- **V11** — The reference model combining empirical joint paths with House-generated text scenarios. Its recorded Development score is **-2.2219**.
- **VNext** — Explored panel-adaptive numerical models.
- **VSpecial** — Compared 28 series individually and adopted uncertain-trend models for CPI/PCE inflation series.
- **VSpecial2 Audit** — Rechecked overfitting, leakage, aggregation, and reproducibility.
- **VExpert** — Tested domain-specific experts and integrated routing for rates, FX, factors, and macro.
- **VStack** — Added chronological distribution stacking and completed a conservative integration that falls back to validated paths when the new optimizer is not consistently better.
- **Short V2 / Volatility-Adaptive V2** — Redesigned the router for the published one-to-four-business-day practice shape and restricted cutoff-local volatility adaptation to F3 cards.

### Official Final entry: `short_v2_adaptive` (2026-10-26)

After the 22 official short-horizon practice cards were published, the existing submitted image and new candidates were reevaluated on the same cards with five Monte Carlo seeds. Lower is better.

| Candidate | Public practice mean | vs reconstructed Gaussian M0 |
| --- | ---: | ---: |
| Existing submitted VStack Stable | 1.160303 | -1.58% |
| Reconstructed Gaussian M0 | 1.142238 | reference |
| Short V2 | 1.061779 | +7.04% |
| **Volatility-Adaptive V2** | **1.057194** | **+7.45%** |

The official Final model is **Volatility-Adaptive V2**. It retains the Short V2 router and changes only F3 cards, using cutoff-local 20-day versus 120-day volatility to rescale complete paths within bounded limits. F1, F2, F4, monthly, and unsupported routes remain identical to Short V2. Global adaptation across all families was tested and rejected after it degraded performance.

#### How the model works

| Input type | Active numerical route |
| --- | --- |
| Treasury F1/F2 | Preserve the established validated rates path |
| FX F3 | Resample contiguous historical joint paths to retain cross-asset and serial dependence |
| Other daily cards | Joint Gaussian random walk fitted on the latest 300 cutoff-valid observations |
| Monthly or unsupported inputs | Fall back to the frozen VStack Stable path |

The F3 volatility adjustment compares per-asset fast and slow volatility estimates with 20-day and 120-day half-lives. It ignores changes inside a 5% deadband, pools 25% of a common cross-asset regime signal, and clips the final multiplier to 0.80–1.25. Complete Monte Carlo paths are then expanded or contracted around the last observed level. This is a direction-free calibration of the **distribution width**, not a directional trading signal.

The inherited guarded House-text path reads only documents available by the cutoff. Unsupported citations are neutralized, and valid scenarios are confidence-weighted and bounded before they can alter the numerical distribution. Runtime inference does not use card IDs, answer tables, external quotes, or future data.

#### Final model equations

Let $T$ be the cutoff date, $p$ the number of target assets, and $D=2000$ the number of Monte Carlo draws. The model outputs a joint sample

$$
\widehat{Y}\in\mathbb{R}^{D\times H\times p}.
$$

**1. General daily route — joint Gaussian random walk**

Using the latest $n\le 299$ cutoff-valid daily changes $x_t=y_t-y_{t-1}$,

$$
\widehat\mu=\frac{1}{n}\sum_{t=T-n+1}^{T}x_t,
\qquad
\widehat\Sigma=\operatorname{Cov}(x_t)+\varepsilon I.
$$

Joint innovations and future levels are

$$
\epsilon_{d,h}\sim\mathcal{N}(\widehat\mu,\widehat\Sigma),
\qquad
\widetilde y_{d,h}=y_T+\sum_{k=1}^{h}\epsilon_{d,k}.
$$

All assets are generated together within each draw, preserving the fitted cross-asset dependence.

**2. FX F3 — contiguous historical-path resampling**

For FX log changes $r_t=\log(y_t/y_{t-1})$, the model samples a historical block origin $b_d$, standardizes the block by its causal volatility, and rescales it to the current regime:

$$
u_t=\frac{r_t-\bar r}{\sigma_{t^-}},
\qquad
\widehat r_{d,h}=\bigl(u_{b_d+h}-\bar u_h\bigr)\sigma_T+\bar r,
$$

$$
\widetilde y_{d,h}=y_T\exp\left(\sum_{k=1}^{h}\widehat r_{d,k}\right).
$$

Sampling complete blocks retains serial persistence and joint cross-asset movement better than independent daily resampling.

**3. F3-only fast/slow volatility adaptation**

For half-life $\lambda\in\{20,120\}$, the implementation mixes 90% exponentially weighted variance with 10% full-sample variance:

$$
w_k^{(\lambda)}=\frac{2^{-k/\lambda}}{\sum_j2^{-j/\lambda}},
\qquad
\sigma_\lambda^2=0.9\sum_k w_k^{(\lambda)}(x_{T-k}-\mu_\lambda)^2
+0.1\operatorname{Var}(x).
$$

For asset $j$,

$$
q_j=\operatorname{clip}\left(\frac{\sigma_{20,j}}{\sigma_{120,j}},0.5,2.0\right),
$$

$$
a_j=\operatorname{sign}(\log q_j)
\max\bigl(|\log q_j|-\log(1.05),0\bigr),
$$

and the final multiplier combines 75% asset-specific and 25% common regime information:

$$
m_j=\operatorname{clip}\left[
\exp\left(0.75a_j+0.25\operatorname{median}(a)\right),
0.80,1.25
\right].
$$

It changes path width, not direction:

$$
\widehat y_{d,h,j}=y_{T,j}+m_j(\widetilde y_{d,h,j}-y_{T,j}).
$$

For log paths, positivity is preserved with

$$
\widehat y_{d,h,j}=y_{T,j}
\exp\left[m_j\log\left(\frac{\widetilde y_{d,h,j}}{y_{T,j}}\right)\right].
$$

This adjustment is applied **only to F3 cards**.

**4. Guarded House-text scenarios**

Only scenarios citing valid supplied document IDs are sampled with probability $p_s$. With numerical path mean $\bar y_{h,j}$, scenario shift $\delta_{s,j}$, and volatility multiplier $v_{s,j}$,

$$
y'_{d,h,j}=\bar y_{h,j}
+v_{s,j}(\widehat y_{d,h,j}-\bar y_{h,j})
+\delta_{s,j}\,\sigma_j\frac{h}{H}.
$$

$\delta$ and $v$ are confidence-shrunk and bounded. A scenario with an unsupported citation is neutralized to $\delta=0$ and $v=1$.

The official per-card objective is

$$
L=0.5L_{\text{marginal CRPS}}
+0.3L_{\text{joint variogram}}
+0.2L_{\text{tail}},
$$

where lower is better. The public leaderboard converts the Track 2 loss to a common higher-is-better display direction.

- Public practice: improved the five-seed mean on **5/5** changed F3 cards; non-F3 results are identical to Short V2
- Answer-free rolling validation: +1.75% overall and +2.64% in 2018–2024
- Final source tests: **32/32 passed**
- New Docker image: `docker.io/kbj710211/agenthon-t2-v11@sha256:40509e6a4c0c6b37ef64beb9cf626a07f8b6b55abbcaf8931ceb1edf93c5decb`
- Official practice structural checks: **22/22 admissible**, all g0–g3 gates passed
- CodaBench submission ID **1009150**: `Finished`
- The organizers explicitly accepted it as Team 478's Track 2 Final entry
- **Official Final result: 55th of 83 scored entries, displayed score -1.0818**

Because the small public practice set was used for selection, these results do not guarantee the Final score or rank. See the [Adaptive V2 submission status](submission/VSTACK_ADAPTIVE_V2_FINAL.md) and [reproducible research folder](VStackAdaptiveV2/) for details.

### Key files

| File | Description |
| --- | --- |
| [Final result and retrospective](research/FINAL_RESULTS_2026-11-03.md) | Official 55th-place result, interpretation limits, and future research priorities |
| [VStackAdaptiveV2/](VStackAdaptiveV2/) | Final Short V2 and Volatility-Adaptive V2 source, result tables, and reproduction code |
| [Adaptive V2 submission status](submission/VSTACK_ADAPTIVE_V2_FINAL.md) | Image digest, validation, replacement ZIP fingerprint, and current status |
| [Short/Adaptive V2 research ZIP](research/Agenthon_VStack_Short_and_Adaptive_V2_2026-10-21.zip) | Research bundle without Team Key or submission authentication material |

> **Important:** Files under `research/*.zip` are research and reproduction bundles. They are not Codabench `submission.zip` files and do not contain team authentication claims.
