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

- 공개 practice: F3 5개 카드의 5-seed 평균에서 **5/5 개선**, 비-F3 결과는 Short V2와 동일
- 답안 비사용 롤링 검증: 전체 +1.75%, 2018–2024 +2.64%
- 최종 소스 테스트: **32/32 통과**
- 새 Docker 이미지: `docker.io/kbj710211/agenthon-t2-v11@sha256:40509e6a4c0c6b37ef64beb9cf626a07f8b6b55abbcaf8931ceb1edf93c5decb`
- 새 이미지의 공식 practice 구조 검증: **22/22 admissible**, g0–g3 전부 통과
- CodaBench 제출 ID **1009150**: `Finished`
- 운영진이 Team 478의 Track 2 최종 엔트리로 공식 인정했으며 추가 업로드 불필요
- 잠정 순위는 2026-10-28부터 갱신되고 최종 결과는 2026-11-13 발표 예정

공개 practice는 모델 선택에 사용된 작은 표본이므로 위 결과는 Final 점수나 순위를 보장하지 않습니다. 상세 기록은 [Adaptive V2 제출 상태](submission/VSTACK_ADAPTIVE_V2_FINAL.md)와 [재현 연구 폴더](VStackAdaptiveV2/)에 있습니다.

### 이전 권장 연구 모드: `stable`

새 스태킹 후보 `stack50`은 개발 구간에서는 선택됐지만 2020–2024 탐색 구간에서 직전 모델을 일관되게 이기지 못했습니다. 따라서 최종 기본 모드는 성능을 과장하지 않는 `stable`입니다.

- 알려진 단일 패널 입력: 검증된 `fast_price` 계열별 경로를 그대로 사용
- 혼합 또는 미확인 입력: 안전한 공동 기본분포로 복귀
- CPI/PCE: 앞선 물가 전용 모델의 개선을 유지
- 새 스태킹: 연구 비교용 `--mode optimized`로만 보존

#### VSpecial 대비 로컬 연구 결과

아래 값은 동일한 로컬 평가 함수에서 계산한 **CRPS 손실 감소율**입니다. 양수는 개선, 음수는 악화입니다. 공식 Codabench 점수나 전체 대회 점수와 동일하지 않습니다.

| 패널 | `stable`의 CRPS 변화 |
| --- | ---: |
| Rates | +0.16% |
| FX | +0.00% |
| Factors | +0.06% |
| Macro | +6.04% |
| Mixed rates + FX | +0.00% |

물가 계열의 VSpecial 대비 개별 CRPS 변화는 CPI_ALL **+30.60%**, CPI_CORE **+13.53%**, PCE_ALL **+8.91%**, PCE_CORE **+9.16%**였습니다. 이 수치는 이번 스태킹에서 새로 만든 성과가 아니라 이전 물가 모델의 개선을 유지한 결과입니다.

### 최초 Final 업로드 (2026-10-14)

최초 Final 업로드는 **VStack `stable`**로 동결했습니다. 이후 공개 short-horizon practice set 검증에 따라 교체 후보를 Volatility-Adaptive V2로 갱신했습니다.

- 공개 이미지: `docker.io/kbj710211/agenthon-t2-v11@sha256:fd71445dd5cd3a1f44d22dcb535cc626e96c97382b9deaf59732c0ba7a8b7ce9`
- 필수 인터페이스 라벨: `qfbench2.interface_version=2.0`
- 최종 재빌드 이미지 테스트: **15/15 통과**
- 오프라인·읽기 전용·non-root 컨테이너 스모크 및 공식 구조 판정: 통과
- 제출 ZIP 계약 및 기존 정상 패키지와의 Team ID 일치: 확인
- 공식 Codabench 결과: 대기 중

자세한 이미지·패키징 검증 기록과 공개용 descriptor 템플릿은 [최종 제출 기록](submission/VSTACK_STABLE_FINAL.md)에 있습니다. 실제 Team Key와 `team-claim.json`은 저장소에 포함하지 않았습니다.

### 검증

최종 `stable` 연구 이미지에 대해 다음을 확인했습니다.

- 수치·cutoff·회귀·경로 동일성 테스트: **61/61 통과**
- 공개 과제의 공식 구조 게이트: **103/103 통과**
- F1–F4 모의 House 처리: **4/4 통과**
- 네트워크 차단 및 읽기 전용 컨테이너 실행: **4/4 통과**
- 실제 입력의 최초/최종 시점, 두 seed, 다섯 범위에서 대조 경로 일치: **20/20**

구조 검증 통과는 공식 정확도나 최종 대회 성적을 보장하지 않습니다.

### 주요 파일

| 파일 | 내용 |
| --- | --- |
| [PDF 보고서 아카이브](reports/README.md) | V1-V13, Gaussian Reset, VNext-VStack의 버전별 보고서 |
| [V11/](V11/) | 기준 구현, Docker 구성, 테스트와 회고 |
| [V11 최종 기록](V11/V11_FINAL.md) | V11 구조, Development 점수, 이미지 기록 |
| [VNext/](VNext/) | 패널별 적응형 수치 모델의 실행 소스 |
| [VSpecial/](VSpecial/) | CPI/PCE 물가 계열 전문 모델의 실행 소스 |
| [VSpecial2/](VSpecial2/) | 과적합·누출 감사를 반영한 후속 실행 소스 |
| [VExpert/](VExpert/) | 금리·FX·팩터·거시 계열별 전문가 모델 소스 |
| [VStack/](VStack/) | 전문가 라우팅과 보수적 스태킹을 통합한 최신 소스 |
| [VStackAdaptiveV2/](VStackAdaptiveV2/) | Short V2·변동성 적응형 V2 최종 소스, 결과표와 재현 코드 |
| [Adaptive V2 제출 상태](submission/VSTACK_ADAPTIVE_V2_FINAL.md) | 이미지 digest, 검증 결과, 교체 제출 ZIP 지문과 현재 상태 |
| [Short/Adaptive V2 연구 ZIP](research/Agenthon_VStack_Short_and_Adaptive_V2_2026-10-21.zip) | Team Key와 제출 인증정보를 제외한 연구 번들 |
| [VStack 연구 ZIP](research/Agenthon_VStack_2026-10-13_Research.zip) | 최신 통합 소스, 재현 코드와 검증 자료 |
| [VStack 한국어 요약](research/VSTACK_2026-10-13_SUMMARY_KR.md) | 모델 선택, 패널 결과, 검증 범위와 한계 |
| [VStack 28계열 결과](research/VSTACK_ASSET_RESULTS_28.csv) | 계열별 비교표 |
| [VExpert 연구 ZIP](research/Agenthon_VExpert_2026-10-13_Research.zip) | 계열별 전문가 모델 연구 |
| [VSpecial 연구 ZIP](research/Agenthon_VSpecial_2026-10-13_Final.zip) | 물가 전문 모델과 28계열 비교 |
| [VSpecial 요약](research/VSPECIAL_2026-10-13_SUMMARY_KR.md) | 물가 개선과 계열별 채택 판단 |
| [VNext 연구 ZIP](research/Agenthon_VNext_2026-10-13_Final.zip) | 초기 패널별 적응형 모델 연구 |

> **주의:** `research/*.zip`은 연구·재현용 번들입니다. Codabench 제출용 `submission.zip`이 아니며 팀 인증 파일이나 제출 자격을 포함하지 않습니다.

### PDF 보고서

[`reports/`](reports/)에는 기존 V1-V13·Gaussian Reset 보고서와 새로 만든 VNext·VSpecial·VSpecial2 Audit·VExpert·VStack 보고서가 정리되어 있습니다. 전체 버전의 언어·연구 단계·핵심 판단은 [보고서 인덱스](reports/README.md)에서 확인할 수 있습니다.

### 해석상 한계

- 2020–2024 구간은 반복 연구 과정에서 이미 확인했으므로 완전히 새로운 홀드아웃이 아닙니다.
- 거시 데이터는 수정된 단일 빈티지이며 실시간 발표 빈티지 백테스트가 아닙니다.
- GDP는 연속 이력이 없어 검증하지 못했습니다.
- 실제 House 응답의 정확도 기여와 공식 M0 정규화 점수는 확인하지 못했습니다.
- 로컬 패널별 개선률을 평균해 전체 대회 점수 개선으로 해석하면 안 됩니다.

이 저장소는 결과가 좋았던 실험뿐 아니라 실패한 후보와 보수적으로 채택하지 않은 이유도 함께 보존합니다.

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

- Public practice: improved the five-seed mean on **5/5** changed F3 cards; non-F3 results are identical to Short V2
- Answer-free rolling validation: +1.75% overall and +2.64% in 2018–2024
- Final source tests: **32/32 passed**
- New Docker image: `docker.io/kbj710211/agenthon-t2-v11@sha256:40509e6a4c0c6b37ef64beb9cf626a07f8b6b55abbcaf8931ceb1edf93c5decb`
- Official practice structural checks: **22/22 admissible**, all g0–g3 gates passed
- CodaBench submission ID **1009150**: `Finished`
- The organizers explicitly accepted it as Team 478's Track 2 Final entry; no further upload is required
- Provisional standings are scheduled from 2026-10-28 and Final results for 2026-11-13

Because the small public practice set was used for selection, these results do not guarantee the Final score or rank. See the [Adaptive V2 submission status](submission/VSTACK_ADAPTIVE_V2_FINAL.md) and [reproducible research folder](VStackAdaptiveV2/) for details.

### Previous recommended research mode: `stable`

The new `stack50` candidate was selected on the development period, but it did not consistently outperform the preceding model in the exploratory 2020–2024 evaluation. The default is therefore the conservative `stable` mode.

- Known single-panel inputs call the validated `fast_price` domain path directly.
- Mixed or unknown inputs fall back to the safe joint baseline.
- Prior CPI/PCE specialist gains are preserved.
- The new stack remains available only for research comparison as `--mode optimized`.

#### Local research results versus VSpecial

The following figures are **CRPS loss reductions** computed with the same local evaluation procedure. Positive values indicate improvement. They are not official Codabench scores or overall competition-score changes.

| Panel | `stable` CRPS change |
| --- | ---: |
| Rates | +0.16% |
| FX | +0.00% |
| Factors | +0.06% |
| Macro | +6.04% |
| Mixed rates + FX | +0.00% |

Series-level changes versus VSpecial were CPI_ALL **+30.60%**, CPI_CORE **+13.53%**, PCE_ALL **+8.91%**, and PCE_CORE **+9.16%**. These are retained gains from the earlier inflation model, not newly created gains from stacking.

### Initial Final upload (2026-10-14)

The initial Final upload was frozen as **VStack `stable`**. After the short-horizon practice set was published, the replacement candidate was updated to Volatility-Adaptive V2.

- Public image: `docker.io/kbj710211/agenthon-t2-v11@sha256:fd71445dd5cd3a1f44d22dcb535cc626e96c97382b9deaf59732c0ba7a8b7ce9`
- Required interface label: `qfbench2.interface_version=2.0`
- Final rebuilt-image tests: **15/15 passed**
- Offline, read-only, non-root smoke run and official structural check: passed
- Submission ZIP contract and Team ID match against the earlier valid package: confirmed
- Official Codabench result: pending

See the [final submission record](submission/VSTACK_STABLE_FINAL.md) for the image, packaging checks, and a public descriptor template. The actual Team Key and `team-claim.json` are not stored in this repository.

### Validation

The final `stable` research image passed:

- **61/61** numerical, cutoff, regression, and path-identity tests
- **103/103** official structural gates on the public tasks
- **4/4** mock House-family flows
- **4/4** offline, read-only container runs
- **20/20** exact control-path checks across real input endpoints, two seeds, and five scopes

Passing structural validation does not guarantee official predictive accuracy or final competition performance.

### Key files

| File | Description |
| --- | --- |
| [PDF report archive](reports/README.md) | Versioned reports for V1-V13, Gaussian Reset, and VNext-VStack |
| [V11/](V11/) | Reference implementation, Docker setup, tests, and retrospective |
| [V11 final record](V11/V11_FINAL.md) | V11 architecture, Development score, and image record |
| [VNext/](VNext/) | Runnable source for the panel-adaptive numerical model |
| [VSpecial/](VSpecial/) | Runnable source for the CPI/PCE inflation specialists |
| [VSpecial2/](VSpecial2/) | Follow-up source after overfitting and leakage audits |
| [VExpert/](VExpert/) | Domain-expert source for rates, FX, factors, and macro series |
| [VStack/](VStack/) | Latest source integrating expert routing with conservative stacking |
| [VStackAdaptiveV2/](VStackAdaptiveV2/) | Final Short V2 and Volatility-Adaptive V2 source, result tables, and reproduction code |
| [Adaptive V2 submission status](submission/VSTACK_ADAPTIVE_V2_FINAL.md) | Image digest, validation, replacement ZIP fingerprint, and current status |
| [Short/Adaptive V2 research ZIP](research/Agenthon_VStack_Short_and_Adaptive_V2_2026-10-21.zip) | Research bundle without Team Key or submission authentication material |
| [VStack research ZIP](research/Agenthon_VStack_2026-10-13_Research.zip) | Latest integration source, reproduction code, and validation evidence |
| [VStack Korean summary](research/VSTACK_2026-10-13_SUMMARY_KR.md) | Model selection, panel results, validation scope, and limitations |
| [VStack 28-series results](research/VSTACK_ASSET_RESULTS_28.csv) | Per-series comparison table |
| [VExpert research ZIP](research/Agenthon_VExpert_2026-10-13_Research.zip) | Domain-expert model research |
| [VSpecial research ZIP](research/Agenthon_VSpecial_2026-10-13_Final.zip) | Inflation specialist and 28-series comparison |
| [VSpecial summary](research/VSPECIAL_2026-10-13_SUMMARY_KR.md) | Inflation results and series-level adoption decisions |
| [VNext research ZIP](research/Agenthon_VNext_2026-10-13_Final.zip) | Earlier panel-adaptive model research |

> **Important:** Files under `research/*.zip` are research and reproduction bundles. They are not Codabench `submission.zip` files and do not contain team authentication claims.

### PDF reports

[`reports/`](reports/) contains the existing V1-V13 and Gaussian Reset reports together with newly created reports for VNext, VSpecial, VSpecial2 Audit, VExpert, and VStack. See the [report index](reports/README.md) for language coverage, research stage, and the main decision for every version.

### Limitations

- The 2020–2024 period had already been inspected during earlier research and is not a pristine holdout.
- Macro data uses one revised vintage rather than real-time release vintages.
- GDP could not be validated because a continuous history was unavailable.
- The real accuracy contribution from House responses and the official M0-normalized score remain untested.
- Local panel-level improvements must not be averaged or interpreted as an overall competition-score gain.

This repository preserves unsuccessful candidates and the reasons for conservative non-adoption, not only favorable results.
