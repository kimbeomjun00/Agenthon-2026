# Agenthon Track 2 — VStack Short V2 기준선 연구 결과

> 2026-10-20 후속 연구에서 F3 전용 변동성 적응형 V2까지 완성·검증했다.
> 최종 비교는 `ADAPTIVE_V2_RESULTS_KR.md`를 우선 참조한다. 이 문서는 동결된
> Short V2 기준선의 상세 기록으로 보존한다.

## 결론

VStack Short V2가 현재 공개된 22개 short-horizon practice card에서 가장 좋은 최종
연구 후보였습니다. 공식 정규화 점수는 낮을수록 좋습니다.

| 모델 | 22카드 × 5 seed 평균 | M0 대비 | 제출 VStack 대비 |
|---|---:|---:|---:|
| **VStack Short V2** | **1.0618** | **7.04% 개선** | **8.49% 개선** |
| VStack Short Safe | 1.0681 | 6.49% 개선 | 7.95% 개선 |
| Gaussian M0 재구성 | 1.1422 | 기준 | 1.56% 개선 |
| 기존 제출 VStack Stable | 1.1603 | 1.58% 악화 | 기준 |

V2의 다섯 seed 점수는 1.0501, 1.0672, 1.0638, 1.0588, 1.0690이었습니다.
모든 seed에서 M0와 기존 제출 VStack보다 낮았습니다.

## 기존 후보 선별

먼저 보존된 최종 후보 10개를 같은 22개 카드와 seed 42에서 비교했습니다.

| 순위 | 후보 | 점수 | M0 대비 |
|---:|---|---:|---:|
| 1 | VNext | 1.1627 | 1.79% 악화 |
| 2 | V11 | 1.1663 | 2.11% 악화 |
| 3 | VSpecial | 1.1671 | 2.18% 악화 |
| 4 | VSpecial2 | 1.1671 | 2.18% 악화 |
| 5 | VStack optimized | 1.1671 | 2.18% 악화 |
| 6–10 | VExpert/VStack 계열 | 약 1.1671 | 약 2.18% 악화 |

새 practice set의 단기국채와 EM 통화 이름이 기존 VExpert 분류표에 없어 여러 후보가
사실상 같은 fallback을 냈습니다. 자산 분류표를 확장한 정석 수정도 시험했지만 1.1658에
그쳐 문제를 해결하지 못했습니다.

## V2 설계

런타임은 카드 ID나 실현값을 조회하지 않습니다. 현재 카드의 cutoff-valid 입력만 사용합니다.

- 국채 F1/F2: 기존 cutoff-local 경험적 수치 엔진을 유지합니다.
- 그 밖의 일별 level 카드: 최근 300개 관측치로 추정한 joint Gaussian random walk를
  안전망으로 사용합니다.
- FX F3: 자산·시계열 간 공동 움직임을 보존하기 위해 volatility-scaled contiguous
  historical paths를 사용합니다.
- 월별 또는 지원하지 않는 입력: 기존 VStack Stable fallback을 유지합니다.
- 기존 guarded House-text transform은 숫자 예측 뒤에 그대로 적용됩니다.

Gaussian, FHS60, block bootstrap, direct paths, daily calibration, variance-term 모델도
같은 조건에서 따로 비교했습니다. Gaussian 전체 모델은 M0와 사실상 동률이었고 나머지
단일 모델은 전체 평균에서 M0를 이기지 못했습니다. V2는 각 모델을 카드의 공개적인
panel/family 구조에 따라 제한적으로 배치합니다.

## 패널·family 결과

V2의 5-seed 평균입니다.

| 패널 그룹 | 카드 | V2 | M0 대비 | 제출 VStack 대비 |
|---|---:|---:|---:|---:|
| UST bills | 8 | 1.0184 | 15.96% 개선 | 5.55% 개선 |
| EM FX | 11 | 0.9793 | 0.41% 개선 | 11.65% 개선 |
| G10 FX | 3 | 1.4799 | 3.86% 개선 | 5.71% 개선 |

| Family | 카드 | V2 | M0 대비 | 제출 VStack 대비 |
|---|---:|---:|---:|---:|
| T2-F1 | 6 | 1.0866 | 14.74% 개선 | 1.13% 악화 |
| T2-F2 | 7 | 1.1912 | 6.70% 개선 | 3.48% 개선 |
| T2-F3 | 5 | 0.7352 | 3.55% 개선 | 4.36% 개선 |
| T2-F4 | 4 | 1.2062 | 1.92% 악화 | 26.86% 개선 |

F4는 기존 제출본보다 크게 좋아졌지만 아직 M0보다 약간 나쁩니다. F1도 M0보다는 크게
좋지만 기존 제출본보다 1.13% 나쁩니다. 전체 개선이 모든 family의 동시 개선을 뜻하지는
않습니다.

## 강건성 점검

- 카드별 5-seed 평균을 독립 단위로 한 bootstrap에서 V2−M0 점수 차이의 95% 구간은
  **−0.1725 ~ −0.0057**이었습니다. 낮을수록 좋으므로 0 아래가 개선 방향입니다.
- V2−기존 제출 VStack의 95% 구간은 **−0.2389 ~ −0.0029**였습니다.
- 22개 카드 중 어느 하나를 제외해도 V2−M0 평균은 **−0.0893 ~ −0.0543**으로
  개선 방향을 유지했습니다.
- 22개 카드는 서로 다른 as-of 날짜를 사용했습니다.
- Short Safe에서 V2로 바뀐 것은 FX F3 세 카드뿐이며, 세 카드 모두 다섯 seed 평균에서
  개선되었습니다. 해당 세 카드의 평균 차이는 −0.0465였습니다.
- 카드 승률은 M0 대비 13/22, 기존 제출 VStack 대비 13/22입니다. 평균 개선은 일부
  큰 국채·F4 손실 감소의 영향도 받으므로 승률과 함께 봐야 합니다.

## 실행·Docker 검증

- Python 회귀 테스트: **19/19 통과**
- 공식 practice card Docker 실행: **22/22 admissible**
- 공식 g0–g3 게이트: **22/22 전부 통과**
- 로컬 소스와 Docker 공식 점수 최대 차이: **2.22e−16**
- forecast 값 최대 차이: **2.84e−14**
- 22개 중 20개 Parquet은 byte-identical이었고, 나머지 2개 차이는 Linux/Windows
  부동소수점 연산의 기계 정밀도 수준이었습니다.
- 검증 이미지: `agenthon-vstack-short-v2:research`
- 로컬 image ID: `sha256:73caeef21915d662605d14702947762ce683860306f5de77f512f11a700652af`
- 플랫폼: Linux/amd64

## 중요한 제한

1. 22개 공개 카드는 historical practice set입니다. 설계와 선택에 사용했으므로 완전히
   독립적인 Final holdout이 아닙니다.
2. Final은 같은 형태지만 하나의 더 늦은 as-of 날짜를 사용합니다. 시점·regime 전이는
   아직 검증되지 않았습니다.
3. 로컬에서는 House API가 없어 `reasoning_applied=false`였습니다. 본 수치는 숫자 fallback
   성능이며 실제 House reasoning의 이득 또는 손실은 포함하지 않습니다.
4. bootstrap 표본은 카드 22개뿐입니다. V2 구간이 0 아래이기는 하지만 여유가 크지는
   않습니다.
5. 이 폴더는 연구 후보입니다. Team Key가 포함된 최종 제출 ZIP은 만들지 않았습니다.

## 판단

공개 practice set을 근거로 보면 기존 VStack Stable보다 **VStack Short V2**가 더 나은
보수적 기준선이다. 이후 연구에서 F3에만 cutoff-local 변동성 적응을 적용한 별도 후보가
Short V2를 소폭 개선했다. 세부 결과와 최종 판단은 `ADAPTIVE_V2_RESULTS_KR.md`에 있다.
