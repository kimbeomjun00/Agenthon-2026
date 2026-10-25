# Agenthon 2026 Track 2 — Volatility-Adaptive V2 Replacement Candidate

## 한국어

### 선택 및 현재 상태

- 모델: `VStack Short V2 + Volatility-Adaptive V2`
- 기본 실행 모드: `short_v2_adaptive`
- 동결일: 2026-10-25
- 상태: 교체 제출 ZIP 생성·검증 및 SHA-256 사전 등록 완료
- 기존 Final 업로드: VStack Stable
- 다음 단계: CodaBench 복구 또는 주최 측 대체 제출 경로가 열리면 아래 지문과 동일한 ZIP을 변경 없이 제출

### 제출 이미지

| 항목 | 값 |
| --- | --- |
| Registry | `docker.io` |
| Repository | `kbj710211/agenthon-t2-v11` |
| Tag | `adaptive-v2-final-20261025` |
| Immutable digest | `sha256:40509e6a4c0c6b37ef64beb9cf626a07f8b6b55abbcaf8931ceb1edf93c5decb` |
| Platform | `linux/amd64` |
| Interface label | `qfbench2.interface_version=2.0` |
| Default mode | `short_v2_adaptive` |

Docker Hub의 익명 registry 조회에서 이미지가 공개 상태이며 위 immutable digest와 일치함을 확인했습니다.

### 공개 practice 결과

공식 short-horizon practice 22개 카드와 동일한 다섯 seed를 사용했습니다. 점수는 낮을수록 좋습니다.

| 후보 | 평균 점수 | 재구성 Gaussian M0 대비 |
| --- | ---: | ---: |
| 기존 제출 VStack Stable | 1.160303 | -1.58% |
| 재구성 Gaussian M0 | 1.142238 | 기준 |
| Short V2 | 1.061779 | +7.04% |
| **Volatility-Adaptive V2** | **1.057194** | **+7.45%** |

Adaptive V2는 F3 카드에서만 cutoff 이전 20일/120일 변동성 비율로 경로를 제한적으로 재조정합니다. 변경된 F3 5개 카드의 5-seed 평균에서 5/5 개선했고, 나머지 카드 결과는 Short V2와 동일했습니다. 공개 practice가 후보 선택에 사용됐으므로 이 결과는 Final 점수나 순위를 보장하지 않습니다.

### 최종 검증

- 소스 테스트: **32/32 통과**
- 공식 practice 카드: **22/22 admissible**, g0–g3 전부 통과
- 직접 실행과 Docker 실행의 최대 forecast 값 차이: `2.842170943040401e-14`
- 최대 점수 차이: `3.0531133177191805e-16`
- 22개 중 20개 출력은 byte-identical이며, 나머지 둘도 위 부동소수점 수준에서 수치적으로 동일
- 최종 ZIP 구성: `submission.json`, `team-claim.json` 정확히 두 파일
- ZIP 무결성 검사: 통과

### 교체 제출 ZIP 고정 기록

- 파일명: `submission_vstack_adaptive_v2_final.zip`
- SHA-256: `daf51bfdae16bd3408b7ce9538d9524ba062e459c24748e8c6eb026a910b7b62`
- 공식 사전 등록 댓글: [Team 478 fingerprint](https://github.com/Agenthon-2026/track2-forecasting-public/issues/4#issuecomment-6394805871)

대회 규정상 사전 등록된 지문과 실제 제출 파일이 일치해야 하므로 이 ZIP은 수정하거나 다시 압축하지 않습니다. 실제 ZIP, Team Key, `team-claim.json`과 인증값은 공개 저장소에 포함하지 않습니다. [`submission_vstack_adaptive_v2_final_descriptor.json`](submission_vstack_adaptive_v2_final_descriptor.json)은 인증정보를 제외한 공개용 descriptor입니다.

---

## English

### Selection and current status

- Model: `VStack Short V2 + Volatility-Adaptive V2`
- Default runtime mode: `short_v2_adaptive`
- Frozen: 2026-10-25
- Status: replacement ZIP built, validated, and fingerprinted before the original deadline
- Existing Final upload: VStack Stable
- Next step: submit the exact unchanged ZIP when CodaBench recovers or the organizer opens an alternate route

### Submission image

| Field | Value |
| --- | --- |
| Registry | `docker.io` |
| Repository | `kbj710211/agenthon-t2-v11` |
| Tag | `adaptive-v2-final-20261025` |
| Immutable digest | `sha256:40509e6a4c0c6b37ef64beb9cf626a07f8b6b55abbcaf8931ceb1edf93c5decb` |
| Platform | `linux/amd64` |
| Interface label | `qfbench2.interface_version=2.0` |
| Default mode | `short_v2_adaptive` |

An anonymous Docker Hub registry lookup confirmed that the image is public and resolves to the immutable digest above.

### Public practice result

The comparison uses the 22 official short-horizon practice cards and the same five Monte Carlo seeds. Lower is better.

| Candidate | Mean score | vs reconstructed Gaussian M0 |
| --- | ---: | ---: |
| Existing submitted VStack Stable | 1.160303 | -1.58% |
| Reconstructed Gaussian M0 | 1.142238 | reference |
| Short V2 | 1.061779 | +7.04% |
| **Volatility-Adaptive V2** | **1.057194** | **+7.45%** |

Adaptive V2 changes only F3 cards, using cutoff-local 20-day versus 120-day volatility to rescale complete paths within bounded limits. It improved the five-seed mean on all five changed F3 cards, while every non-F3 result remained identical to Short V2. Because the public practice set was used for candidate selection, this does not guarantee the Final score or rank.

### Final validation

- Source tests: **32/32 passed**
- Official practice cards: **22/22 admissible**, all g0–g3 gates passed
- Maximum forecast-value difference between direct and Docker execution: `2.842170943040401e-14`
- Maximum score difference: `3.0531133177191805e-16`
- 20 of 22 outputs were byte-identical; the other two were numerically identical to floating-point precision above
- Final ZIP contains exactly `submission.json` and `team-claim.json`
- ZIP integrity check: passed

### Frozen replacement ZIP record

- File name: `submission_vstack_adaptive_v2_final.zip`
- SHA-256: `daf51bfdae16bd3408b7ce9538d9524ba062e459c24748e8c6eb026a910b7b62`
- Official timestamped comment: [Team 478 fingerprint](https://github.com/Agenthon-2026/track2-forecasting-public/issues/4#issuecomment-6394805871)

The ZIP must not be edited or repacked because the submitted file must match the preregistered fingerprint. The actual ZIP, Team Key, `team-claim.json`, and authentication material are intentionally excluded from this public repository. [`submission_vstack_adaptive_v2_final_descriptor.json`](submission_vstack_adaptive_v2_final_descriptor.json) is a public descriptor without authentication fields.
