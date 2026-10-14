# Agenthon 2026 Track 2 — VStack Stable Final Candidate

## 한국어

### 최종 선택

- 선택 모델: `VStack`
- 실행 모드: `stable`
- 선택일: 2026-10-14
- 상태: 최종 제출 후보 패키지 생성 및 로컬 검증 완료, 공식 결과 대기

`stable`은 새 스태킹 후보의 성과가 모든 검증 구간에서 일관되지 않았기 때문에 채택한 보수적 통합입니다. 알려진 단일 패널에는 검증된 계열별 경로를 사용하고, 혼합·미확인 입력에는 안전한 공동 기본분포를 사용합니다. CPI/PCE에는 앞선 물가 전용 모델에서 확인한 개선을 유지합니다.

### 제출 이미지

| 항목 | 값 |
| --- | --- |
| Registry | `docker.io` |
| Repository | `kbj710211/agenthon-t2-v11` |
| Tag | `vstack-stable-final-20261014` |
| Immutable digest | `sha256:fd71445dd5cd3a1f44d22dcb535cc626e96c97382b9deaf59732c0ba7a8b7ce9` |
| Platform | `linux/amd64` |
| Interface label | `qfbench2.interface_version=2.0` |
| Runtime user | `runner` |

### 최종 재검증

- 최종 Docker 이미지 테스트: **15/15 통과**
- 네트워크 차단, 읽기 전용 root filesystem, non-root 실행 스모크 테스트: 통과
- 공식 `qfbench2_common` 스모크 판정: `admissible=True`
- 출력 파일: `forecast.parquet`, `forecast_meta.json`, `forecast_rationale.md` 정확히 3개
- Docker Hub anonymous pull 및 immutable digest 대조: 통과
- 최종 제출 ZIP 구조: `submission.json`, `team-claim.json` 정확히 2개
- 제출 descriptor 공식 계약 검증: 통과
- 새 패키지의 파생 Team ID와 기존 정상 패키지의 Team ID: 일치

최종 로컬 제출 ZIP의 SHA-256은 `FD3F962DF8CBC4E73511EEB440D97EFA8E206A8AF9DCAD047327D85FA7422823`입니다. 실제 제출 ZIP과 `team-claim.json`은 대회 제출 전 공개 저장소에 포함하지 않았습니다. Team Key는 이미지, 소스, descriptor, Git 기록 어디에도 저장하지 않았습니다.

[`submission_vstack_stable_final_descriptor.json`](submission_vstack_stable_final_descriptor.json)은 팀 인증값을 제거한 공개용 descriptor 템플릿입니다. 공식 패킹 도구가 Team Key 입력 시 `team_id`, `descriptor_digest`, `team-claim.json`을 다시 계산합니다.

### 해석상 주의

이 기록은 구조·실행·패키징 검증 결과입니다. 공식 Codabench 점수 또는 최종 순위를 의미하지 않습니다. 공식 결과가 나올 때까지 모델과 이미지 digest를 동결합니다.

---

## English

### Final selection

- Selected model: `VStack`
- Runtime mode: `stable`
- Selection date: 2026-10-14
- Status: final candidate package built and locally validated; official result pending

`stable` is the conservative integration selected because the new stacking candidate did not improve consistently across evaluation periods. It uses validated domain paths for known single-panel inputs, the safe joint baseline for mixed or unknown inputs, and retains the earlier CPI/PCE specialist improvements.

### Submission image

| Field | Value |
| --- | --- |
| Registry | `docker.io` |
| Repository | `kbj710211/agenthon-t2-v11` |
| Tag | `vstack-stable-final-20261014` |
| Immutable digest | `sha256:fd71445dd5cd3a1f44d22dcb535cc626e96c97382b9deaf59732c0ba7a8b7ce9` |
| Platform | `linux/amd64` |
| Interface label | `qfbench2.interface_version=2.0` |
| Runtime user | `runner` |

### Final revalidation

- Final Docker image tests: **15/15 passed**
- Offline, read-only-root, non-root container smoke run: passed
- Official `qfbench2_common` smoke result: `admissible=True`
- Output contract: exactly `forecast.parquet`, `forecast_meta.json`, and `forecast_rationale.md`
- Anonymous Docker Hub pull and immutable-digest comparison: passed
- Final submission ZIP: exactly `submission.json` and `team-claim.json`
- Official descriptor-contract validation: passed
- Derived Team ID matches the earlier valid package: confirmed

The final local submission ZIP has SHA-256 `FD3F962DF8CBC4E73511EEB440D97EFA8E206A8AF9DCAD047327D85FA7422823`. The actual submission ZIP and `team-claim.json` are intentionally not committed to this public repository before submission. The Team Key was never stored in the image, source, descriptor, or Git history.

[`submission_vstack_stable_final_descriptor.json`](submission_vstack_stable_final_descriptor.json) is a public descriptor template with team-authentication fields omitted. The official packer recomputes `team_id`, `descriptor_digest`, and `team-claim.json` when the Team Key is entered.

### Interpretation

These checks establish structural, runtime, and packaging validity. They do not constitute an official Codabench score or final ranking. The selected model and immutable image digest are frozen while the official result is pending.

