# Agenthon 2026 Track 2 — Final Result and Retrospective

## 한국어

### 공식 결과

Agenthon 운영진은 2026-11-03 검증이 완료된 Final leaderboard를 공개했습니다.

| 항목 | 결과 |
| --- | --- |
| 팀 | `lifeisluck` (Team 478) |
| 최종 모델 | VStack Volatility-Adaptive V2 (`short_v2_adaptive`) |
| CodaBench 제출 ID | `1009150` |
| 공식 순위 | **55위** |
| 공식 표시 점수 | **-1.0818** |
| 점수를 받은 팀 | 83개 |
| 전체 게시 팀 | 87개 (4개 팀 not scored) |
| 우승 팀 / 점수 | Sitadel Insecurities / -0.9467 |
| 25위 점수 | -1.0049 |

공식 페이지는 모든 트랙의 표시 점수를 “높을수록 좋음”으로 통일하며, Track 2의 원시 Forecasting loss를 변환해 게시합니다. 따라서 위 음수 점수는 공개 practice의 로컬 loss와 직접 비교하지 않습니다. `lifeisluck`은 점수를 받은 83개 팀 중 55위로, 자신보다 낮은 점수를 받은 28개 팀보다 앞섰습니다.

공식 leaderboard: <https://www.agenthon.net/#leaderboard>

### 무엇이 확인됐는가

- 제출 ZIP, 팀 인증, Docker 이미지와 런타임 계약이 모두 정상 작동하여 공식 점수를 받았습니다.
- 대회 중 CodaBench 장애와 교체 제출 시각 문제에도 불구하고, 운영진 확인을 통해 제출 ID `1009150`이 최종 엔트리로 인정됐습니다.
- 모델은 누출 없이 cutoff 이전 데이터만 사용하고, 2,000개 공동 Monte Carlo 경로와 필수 산출물을 정상 생성했습니다.
- 83개 scored entries 중 55위로 완주했지만, 상위권 성능에는 도달하지 못했습니다.

### 해석상 중요한 한계

1. **Adaptive V2와 Stable의 Final 우열은 알 수 없습니다.** 공식 ranked run은 Adaptive V2에만 수행됐고 Stable은 같은 Final 카드에서 점수를 받지 않았습니다.
2. 공개 22개 short-horizon practice 카드에서 측정한 M0 대비 7.45% 개선은 Final 성능 개선을 보장하지 않았습니다. 이 결과는 후보 선택에 사용된 작은 공개 표본이었습니다.
3. Final의 카드별 점수와 구성요소가 공개되지 않아 55위의 원인을 금리, FX, F3 변동성 보정, 텍스트 경로 중 하나로 확정할 수 없습니다.
4. 공식 표시 점수는 leaderboard용 변환 점수이므로 로컬 practice 평균 `1.057194`와 숫자를 직접 대조하면 안 됩니다.

### 가능한 성능 제약 요인 — 가설

- 22개 공개 카드, 특히 변경된 F3 5개 카드에 후보 선택이 집중되어 일반화 오차가 컸을 가능성
- 단기 Gaussian random walk와 역사적 경로 재표본화가 실제 2026-10-27~30 시장 상태를 충분히 표현하지 못했을 가능성
- 변동성 적응을 F3에만 제한해 다른 family의 상태 변화에는 대응하지 못했을 가능성
- House 텍스트 경로의 실제 정확도 기여를 오프라인에서 검증하지 못한 상태로 제출한 한계

이는 카드별 Final 결과가 없는 상태의 가설이며 확정 원인이 아닙니다.

### 다음 연구에서 바꿀 점

- 소수 공개 카드가 아니라 여러 역사 구간에서 수백 개의 누출 방지 pseudo-Final 카드를 생성해 모델을 선택
- family·panel별 marginal, joint, tail 구성요소를 분리해 검증하고 라우터의 채택 조건을 사전 고정
- 변동성 배율뿐 아니라 drift, tail thickness, cross-asset copula의 상태 적응을 독립적으로 검증
- House 텍스트 사용/미사용 ablation을 동일 카드·동일 seed로 비교
- 후보 선택용 기간과 최종 검증 기간을 완전히 분리하고, 반복 실험에 사용한 기간은 holdout으로 재사용하지 않기

### 최종 판단

프로젝트는 제출 신뢰성, 누출 방지, 재현성과 실패 후보 기록이라는 공학적 목표는 달성했습니다. 예측 성능은 55위로 중하위권이었으며, 공개 practice 개선이 상위권 Final 성적으로 이어지지는 않았습니다. 따라서 Adaptive V2는 성공한 경쟁 모델이라기보다, 정상 완주한 보수적 연구 프로토타입으로 기록합니다.

---

## English

### Official result

The organizers published the verified Final leaderboard on 2026-11-03.

| Field | Result |
| --- | --- |
| Team | `lifeisluck` (Team 478) |
| Final model | VStack Volatility-Adaptive V2 (`short_v2_adaptive`) |
| CodaBench submission ID | `1009150` |
| Official rank | **55th** |
| Official displayed score | **-1.0818** |
| Scored teams | 83 |
| Listed teams | 87 (four not scored) |
| Winner / score | Sitadel Insecurities / -0.9467 |
| 25th-place score | -1.0049 |

The official site converts the raw Track 2 Forecasting loss to a common higher-is-better display convention. The negative displayed score should therefore not be compared directly with the local public-practice loss. `lifeisluck` ranked 55th among 83 scored entries, ahead of 28 other scored teams.

Official leaderboard: <https://www.agenthon.net/#leaderboard>

### What the result establishes

- The submission ZIP, team claim, Docker image, and runtime contract all worked and received an official score.
- Despite the CodaBench outage and replacement-upload timing issue, the organizers accepted submission `1009150` as the team's Final entry.
- The agent completed the ranked evaluation using cutoff-valid inputs and produced the required joint Monte Carlo forecasts.
- The entry finished 55th of 83 scored teams and did not reach the competitive top tier.

### Important limitations

1. **The Final does not establish whether Adaptive V2 beat Stable.** Only Adaptive V2 received a ranked run on the Final cards.
2. The 7.45% improvement over reconstructed M0 on the 22 public short-horizon practice cards did not guarantee a stronger Final placement. That small public set was used for candidate selection.
3. Per-card and component-level Final results are not public, so the outcome cannot be attributed conclusively to rates, FX, F3 volatility adaptation, or the text path.
4. The official displayed score is a leaderboard transformation and must not be compared numerically with the local practice mean of `1.057194`.

### Possible constraints — hypotheses, not findings

- Candidate selection may have overfit the 22 public cards, especially the five changed F3 cards.
- The short-horizon Gaussian walk and historical-path resampling may not have represented the 27–30 October 2026 market regime well enough.
- Restricting volatility adaptation to F3 left other families insensitive to regime shifts.
- The actual contribution of the guarded House-text path was not validated offline.

### Changes for future research

- Generate hundreds of leakage-safe pseudo-Final cards across multiple historical windows.
- Validate marginal, joint, and tail components separately by family and panel, with routing gates fixed in advance.
- Test regime adaptation for drift, tail thickness, and cross-asset copulas independently of volatility scaling.
- Run same-card, same-seed House-text ablations.
- Keep model-selection periods and final holdouts fully separate; never reuse repeatedly inspected periods as holdouts.

### Final assessment

The project achieved reliable packaging, cutoff safety, reproducibility, and transparent recording of rejected candidates. Its predictive result was 55th place, below the competitive tier. Adaptive V2 is therefore best recorded as a conservative research prototype that completed the official evaluation successfully, not as a top-performing competition model.
