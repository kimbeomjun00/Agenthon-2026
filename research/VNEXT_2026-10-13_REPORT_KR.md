## Executive summary (read this first)

V11을 바탕으로 VNext 연구 후보를 구현하고 검증했습니다. 데이터 공백 처리와 월별 물가지수 추세가 개선의 핵심입니다. 일별 시장 전반을 확실하게 이기는 새 모델을 만들었다는 결론은 아직 낼 수 없습니다. 고용·실업률에서는 악화도 확인했습니다. 기존 V11을 기준점으로 유지하고, VNext를 비교 후보로 활용하는 것이 현재 증거에 맞습니다.

이 ZIP은 연구 결과물입니다. 제출 descriptor, team claim, 이미지 registry 업로드, Codabench 제출용 ZIP은 만들지 않았습니다. 다음 대화에서 함께 준비하면 됩니다.

### 먼저 읽을 결과

아래 값은 과거 입력의 변동성으로 단위를 보정한 marginal CRPS입니다. 낮을수록 좋습니다. 주최 측의 카드별 M0 scale을 사용한 공식 composite가 아닙니다. V11 기록의 -2.2219와 비교할 수 없습니다.

| 패널 | V11 | VNext | 오차 감소율 | 연도 블록 95% 구간 |
|---|---:|---:|---:|---:|
| 금리 | 0.696482 | 0.696936 | -0.07% | -0.37% ~ +0.29% |
| FX | 0.518787 | 0.518906 | -0.02% | -0.40% ~ +0.45% |
| 주식 요인 | 0.606973 | 0.600938 | +0.99% | -0.12% ~ +1.82% |
| 월별 거시지표 | 2.692144 | 1.557568 | +42.14% | +18.91% ~ +71.88% |

최종 비교는 2020~2024년의 인위적 예측 시점 128개를 사용했습니다. 각 시점에서 2,000 draws, 시드 42와 77로 반복했습니다. 두 시드는 같은 128개 시점의 반복이지 독립된 256개 시장 사건이 아닙니다. 연도 단위 재표집을 5,000회 했지만 연도 블록이 4~5개라 신뢰구간은 참고 수준입니다. 금리·FX·요인 모두 구간에 0이 들어가므로 우위를 확정하지 않습니다.

월별 지표 평균은 좋아졌지만 세부 항목을 분리해야 합니다.

| 지표 | V11 | VNext | 오차 감소율 |
|---|---:|---:|---:|
| CPI_ALL | 3.119360 | 1.661542 | +46.73% |
| CPI_CORE | 5.329749 | 1.918902 | +64.00% |
| NFP | 1.381658 | 1.573529 | -13.89% |
| UNRATE | 0.937807 | 1.076297 | -14.77% |

NFP와 UNRATE에서 숫자만 사용하는 VNext가 악화했습니다. 월별 패널 전체를 하나의 정답처럼 보고 개선됐다고 말하면 안 됩니다. 물가지수의 추세 모델은 유망하고 고용의 추세·충격 모델은 추가 검토가 필요합니다. raw marginal/joint/tail 평균도 reports에 따로 실었습니다. 원단위 값은 자산의 단위에 좌우되며, 월별 묶음의 raw 오차 중 일부는 악화했습니다. 임의로 공식 점수로 환산하지 않았습니다.

### 실제로 바꾼 모델

1. 긴 데이터 공백을 하루 변화로 취급하지 않습니다. 각 자산에서 공백을 제거한 뒤 날짜로 공동 정렬합니다. 마지막 관측값은 그대로 현재 앵커로 씁니다.
2. FX는 비율 변화가 자연스럽도록 log level 변화 후보를 씁니다. 물가지수처럼 전부 양수인 월별 그룹도 이 표현을 사용할 수 있습니다. 누적 factor log return은 log(1+r)를 더합니다.
3. 일별 변동성은 과거 각 시점의 정보만으로 필터링합니다. 개별 날짜의 변동성이 큰 이유와 충격의 크기를 구분하는 historical simulation 후보를 추가했습니다.
4. 과거의 연속된 경로와 평균 5일 블록을 함께 비교합니다. 공백을 가로질러 블록을 연결하지 않습니다.
5. 월별 후보에 12개월/36개월 추세와 변화의 autoregression을 넣었습니다. 월별 horizon key와 실제 observation month를 구분하고 publication lag를 포함합니다.
6. 현재 카드 이전에 결과가 확정된 8개 비중첩 블록에서 후보를 비교하고 완만하게 혼합합니다. 한 draw 전체가 하나의 후보를 쓰므로 자산·기간의 공동 구조를 유지합니다. 이 선택 목표는 marginal CRPS 대리목표이며 공식 composite 최적화와 동일하지 않습니다.
7. 오래된 FX 대상 기록에는 현재 입력의 G10 proxy 경로를 절반 혼합할 수 있습니다. 과거에 실제로 겹친 날짜만으로 회귀합니다.
8. V11의 시나리오 표현은 유지했습니다. 새 guarded 정책은 입력 문서 ID와 confidence를 확인하고, 월별 이동량에는 실제 월수를 사용합니다. 실제 House의 정확도 효과는 검증하지 못했습니다.

### 실험의 범위와 한계

- 2006~2019년의 80개 인위적 시점에서 후보 구조를 탐색했습니다. 별도 후반 구간 비교와 시드 반복을 남겼습니다.
- 공식 practice card의 숨은 정답을 재구성하거나 카드 ID별 답을 저장하지 않았습니다. 같은 공개 패널 안에서 임의 시점을 자른 numerical backtest입니다. 다른 카드의 정답 lookup은 추론 코드에 없습니다.
- 코드의 경계 오류를 수정한 후 같은 후반 시점을 다시 실행한 기록도 보존했습니다. 후반 구간에 전혀 손대지 않은 별도 연구기관의 검증으로 주장하지 않습니다. 코드 변경은 경계 처리였고, 후반 점수에 맞춘 고정 학습 파라미터는 이미지에 넣지 않았습니다.
- 월별 비교는 특정 공개 macro vintage에 기반합니다. 역사 당시의 release vintage를 완벽히 재현하지 못하므로 실시간 거시 backtest가 아닙니다. 이 제한은 물가 개선 수치에도 적용됩니다.
- 5년 공백의 별도 G10 실험 24개에서 보정 CRPS는 V11 0.778466, 공백 제거+adaptive 0.544193, proxy 혼합 0.538496이었습니다. 이것은 인위적인 G10 실험이며 대회의 실제 EM 카드에서 우위를 증명하지 않습니다.
- 실제 House endpoint는 대회 실행 환경에만 주어집니다. 모의 JSON 테스트는 데이터 흐름·형식 확인이며 text uplift의 증거가 아닙니다. guarded 정책이 원래 V11 정책보다 낫다는 결론도 아직 없습니다.
- 업로드된 V11 소스는 재구성본입니다. 원래 제출 이미지와 byte-identical하지 않다는 provenance를 보존했습니다. 원본 기록의 submission score를 새 로컬 비교의 결과처럼 쓰지 않았습니다.

### 검증 기록

- 최종 모델의 103/103 practice unit이 공식 g0~g3를 통과했습니다. 각 2,000 draws입니다.
- F1~F4 각각의 모의 text transform이 변경된 예측을 만들고 공식 gates를 통과했습니다.
- 실제 `forecast` 명령을 offline, read-only root, /tmp tmpfs 조건에서 4개 서로 다른 유형에 실행했습니다. 출력은 정확히 3개 파일이고 gates도 통과했습니다.
- VNext 자체 회귀 테스트 9개 통과. 미래 panel row 불변성, 긴 공백, 월별 추세, nested joint path, future/escape 문서 차단, citation, 월별 이동량, seed 재현성과 stale FX proxy 불변성을 검사합니다.
- qfbench2-common v2.6.0의 테스트 719개 통과.
- 공식 T2 전체 테스트: 469 통과, 1 실패, 2 integration skip. 실패는 원래 공식 코드의 `test_limits.py::test_uncompressed_budget`입니다. PyArrow 18.1.0에서 500,000행 상수-column 파일의 footer total_byte_size가 367 bytes로 기록되어 1024-byte 제한을 넘지 않는 테스트 가정 문제를 재현했습니다. 공식 scorer나 테스트를 고쳐서 초록색으로 만들지 않았습니다. 103개 정상 출력에 대한 실제 gates는 통과했습니다.
- 처음 나온 7개 shell 테스트 오류는 Windows checkout의 CRLF 때문이었습니다. 원본은 그대로 두고 임시 Linux 복사본의 shell 줄바꿈만 LF로 정규화하니 해결됐습니다. 전체 테스트가 모두 통과했다고 표현하지 않습니다.

### 파일 안내

- `VNext/`: 새 모델, 고정 dependencies, Dockerfile, 회귀 테스트와 README.
- `V11_reconstruction/`: 사용자가 올린 V11 기준점의 코드·Dockerfile·provenance.
- `research/`: 다시 실행할 benchmark와 검증 도구. `REPRODUCE.ps1`에 기존 GitHub 저장소의 로컬 경로를 넘깁니다.
- `reports/`: 집계 결과, 해시, gate 결과와 공식 테스트의 실제 실패 기록. 원시 패널·카드별 forecast·개별 인위적 시점의 loss는 공개 ZIP에 넣지 않았습니다.
- `MANIFEST.json`: 파일별 SHA-256. `provenance.json`: 코드·데이터·환경 버전.

### 재실행

ZIP을 풀고 PowerShell에서:

```powershell
.\research\REPRODUCE.ps1 -RepositoryPath 'C:\local\Agenthon-2026' -Task tests
.\research\REPRODUCE.ps1 -RepositoryPath 'C:\local\Agenthon-2026' -Task gates
.\research\REPRODUCE.ps1 -RepositoryPath 'C:\local\Agenthon-2026' -Task holdout42
```

RepositoryPath 아래에 `V11/units`가 있어야 합니다. Python은 Docker 내부에서 실행되므로 Windows에 별도로 설치할 필요가 없습니다. 빌드 때만 dependency 다운로드가 필요합니다. 실행은 network=none입니다.

### 다음 대화의 권장 방향

기존 V11을 유지하면서 VNext를 비교 후보로 사용합니다. 가장 근거가 있는 개선은 공백 처리와 물가 추세입니다. 일별의 소폭 변화와 고용 모델은 과장하지 않습니다. 실제 House를 쓰는 평가가 가능할 때 `text-policy v11`과 `guarded`를 비교하고, 그 결과와 per-card diagnostics를 보고 제출 후보를 결정하면 됩니다. 제출용 파일은 사용자 요청 후 함께 만듭니다.

### 근거 소스

공식 Track 2 commit a2c93e7b66b8c6a6c429fda81d6bc7873b7c5dec 기준 [README](https://github.com/Agenthon-2026/track2-forecasting-public/blob/a2c93e7b66b8c6a6c429fda81d6bc7873b7c5dec/README.md), [artifact policy](https://github.com/Agenthon-2026/track2-forecasting-public/blob/a2c93e7b66b8c6a6c429fda81d6bc7873b7c5dec/docs/ARTIFACT-POLICY.md), [월별 horizon](https://github.com/Agenthon-2026/track2-forecasting-public/blob/a2c93e7b66b8c6a6c429fda81d6bc7873b7c5dec/docs/MONTHLY-HORIZONS.md), [공식 평가 코드](https://github.com/Agenthon-2026/track2-forecasting-public/blob/a2c93e7b66b8c6a6c429fda81d6bc7873b7c5dec/qfbench2_track_forecasting/scoring.py). 실험 수치는 이 ZIP의 reports와 실행 스크립트에서 나온 값입니다.