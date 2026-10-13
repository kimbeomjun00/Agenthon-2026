# Agenthon 2026 Track 2 보고서 아카이브

## 한국어

이 디렉터리는 Agenthon 2026 Track 2 연구의 버전별 PDF 기록을 시간 순서대로 보존합니다. 기존 `C:\Users\kimbu\Desktop\Agenthon` 폴더의 PDF는 내용 변경 없이 옮겼고, PDF가 없던 후속 연구 버전 VNext, VSpecial, VSpecial2 Audit, VExpert, VStack에는 한국어 본문과 영어 요약을 포함한 4페이지 보고서를 추가했습니다.

파일 크기, 페이지 수와 SHA-256은 [`MANIFEST_SHA256.csv`](MANIFEST_SHA256.csv)에 기록했습니다.

### 커버리지

- V1-V6: 한국어·영어 개별 보고서
- V7-V8: 두 버전을 함께 다룬 한국어·영어 보고서
- V9-V13: 버전별 개발·회고 보고서
- Gaussian Reset / WIDTH090: V13 이후 reset branch 회고
- VNext-VStack: 새로 추가한 한국어 본문 + 영어 요약 통합 보고서

따라서 현재 연구 기록에 등장하는 V1부터 V13, Gaussian Reset, VNext, VSpecial, VSpecial2 Audit, VExpert, VStack이 모두 PDF로 연결됩니다.

### Quant 연구 계보

| 버전 | 한국어 | English | 기록 성격 |
| --- | --- | --- | --- |
| V1 | [KR](Agenthon_T2_Quant_V1_Report_KR.pdf) | [EN](Agenthon_T2_Quant_V1_Report_EN.pdf) | Gaussian baseline에서 regime-aware bootstrap으로 전환 |
| V2 | [KR](Agenthon_T2_Quant_V2_Report_KR.pdf) | [EN](Agenthon_T2_Quant_V2_Report_EN.pdf) | EWMA + Student-t dependence 실험 |
| V3 | [KR](Agenthon_T2_Quant_V3_Report_KR.pdf) | [EN](Agenthon_T2_Quant_V3_Report_EN.pdf) | PCA yield-curve factor model |
| V4 | [KR](Agenthon_T2_Quant_V4_Report_KR.pdf) | [EN](Agenthon_T2_Quant_V4_Report_EN.pdf) | Text-conditioned tail mixture |
| V5 | [KR](Agenthon_T2_Quant_V5_Report_KR.pdf) | [EN](Agenthon_T2_Quant_V5_Report_EN.pdf) | Joint dependence와 copula shrinkage |
| V6 | [KR](Agenthon_T2_Quant_V6_Report_KR.pdf) | [EN](Agenthon_T2_Quant_V6_Report_EN.pdf) | 보수적 최종 통합과 제출 파이프라인 |
| V7-V8 | [KR](Agenthon_T2_V7_V8_Report_KR.pdf) | [EN](Agenthon_T2_V7_V8_Report_EN.pdf) | Legacy 전환과 text-gated mixture 연구 |
| V9 | [KR](Agenthon_T2_V9_Development_Report_KR.pdf) | - | Text-gated probabilistic mixture-of-experts |
| V10 | [회고](Agenthon_T2_V10_Directional_Soft_Tilt_Retrospective_2026-10-11.pdf) | 문서 내 영문 용어 병기 | Directional soft tilt, sealed 열위 |
| V11 | [회고](Agenthon_T2_V11_E2_V8_Scenario_Mixture_Retrospective_2026-10-11.pdf) | 문서 내 영문 용어 병기 | E2 90/10 + V8 scenario mixture, 기준 champion |
| V12 | [회고](Agenthon_T2_V12_F3_Conditional_Pool_Retrospective_2026-10-12.pdf) | 문서 내 영문 용어 병기 | F3 conditional pool, 제출 전 중단 |
| V13 | [회고](Agenthon_T2_V13_WIDTH085_Retrospective_2026-10-12.pdf) | 문서 내 영문 용어 병기 | WIDTH085, sealed 결과로 기각 |
| Reset | [회고](Agenthon_T2_Gaussian_Reset_WIDTH090_Retrospective_2026-10-12.pdf) | 문서 내 영문 용어 병기 | 공식 Gaussian 재점검과 WIDTH090 기각 |

### 후속 계열별·통합 연구

| 버전 | 통합 보고서 | 핵심 판단 |
| --- | --- | --- |
| VNext | [KR + EN](Agenthon_T2_VNext_Research_Report_KR_EN_2026-10-13.pdf) | 공백 처리와 물가 추세는 유망, 전 패널 교체 근거는 부족 |
| VSpecial | [KR + EN](Agenthon_T2_VSpecial_Research_Report_KR_EN_2026-10-13.pdf) | CPI/PCE 네 계열에만 전문 모델 채택 |
| VSpecial2 Audit | [KR + EN](Agenthon_T2_VSpecial2_Audit_Research_Report_KR_EN_2026-10-13.pdf) | 입력 무결성 수정, CPI 혼합 기본 채택 보류 |
| VExpert | [KR + EN](Agenthon_T2_VExpert_Research_Report_KR_EN_2026-10-13.pdf) | 28계열 전문가 실험, fast_price를 비교 후보로 보존 |
| VStack | [KR + EN](Agenthon_T2_VStack_Research_Report_KR_EN_2026-10-13.pdf) | 새 stack 대신 회귀 방지형 stable 통합 채택 |

### 읽을 때 주의할 점

- 로컬 CRPS·joint·tail 수치는 공식 Codabench 점수가 아닙니다.
- 버전마다 비교 기준, 평가 시점, 데이터 빈티지가 다를 수 있습니다.
- 구조 게이트 통과는 예측 정확도나 대회 규정 전체 승인을 의미하지 않습니다.
- 자세한 수치, 재현 코드와 provenance는 루트의 [`research/`](../research/) 번들을 확인하세요.

---

# Agenthon 2026 Track 2 Report Archive

## English

This directory preserves the version-by-version PDF record of the Agenthon 2026 Track 2 research program. Existing PDFs from the local archive were copied without content changes. Five previously undocumented research versions - VNext, VSpecial, VSpecial2 Audit, VExpert, and VStack - now have four-page reports with Korean main text and an English summary.

File sizes, page counts, and SHA-256 hashes are recorded in [`MANIFEST_SHA256.csv`](MANIFEST_SHA256.csv).

### Coverage

- V1-V6: separate Korean and English reports
- V7-V8: combined Korean and English reports
- V9-V13: development or retrospective reports for each version
- Gaussian Reset / WIDTH090: the post-V13 reset-branch retrospective
- VNext-VStack: newly added bilingual executive research reports

The archive therefore covers V1 through V13, Gaussian Reset, VNext, VSpecial, VSpecial2 Audit, VExpert, and VStack.

### Quant research lineage

| Version | Korean / primary report | English | Research role |
| --- | --- | --- | --- |
| V1 | [KR](Agenthon_T2_Quant_V1_Report_KR.pdf) | [EN](Agenthon_T2_Quant_V1_Report_EN.pdf) | Gaussian baseline to regime-aware bootstrap |
| V2 | [KR](Agenthon_T2_Quant_V2_Report_KR.pdf) | [EN](Agenthon_T2_Quant_V2_Report_EN.pdf) | EWMA + Student-t dependence |
| V3 | [KR](Agenthon_T2_Quant_V3_Report_KR.pdf) | [EN](Agenthon_T2_Quant_V3_Report_EN.pdf) | PCA yield-curve factors |
| V4 | [KR](Agenthon_T2_Quant_V4_Report_KR.pdf) | [EN](Agenthon_T2_Quant_V4_Report_EN.pdf) | Text-conditioned tail mixture |
| V5 | [KR](Agenthon_T2_Quant_V5_Report_KR.pdf) | [EN](Agenthon_T2_Quant_V5_Report_EN.pdf) | Joint dependence and copula shrinkage |
| V6 | [KR](Agenthon_T2_Quant_V6_Report_KR.pdf) | [EN](Agenthon_T2_Quant_V6_Report_EN.pdf) | Conservative final integration and pipeline |
| V7-V8 | [KR](Agenthon_T2_V7_V8_Report_KR.pdf) | [EN](Agenthon_T2_V7_V8_Report_EN.pdf) | Legacy transition and text-gated mixtures |
| V9 | [KR](Agenthon_T2_V9_Development_Report_KR.pdf) | - | Text-gated probabilistic mixture-of-experts |
| V10 | [Retrospective](Agenthon_T2_V10_Directional_Soft_Tilt_Retrospective_2026-10-11.pdf) | Mixed terminology | Directional soft tilt; inferior sealed result |
| V11 | [Retrospective](Agenthon_T2_V11_E2_V8_Scenario_Mixture_Retrospective_2026-10-11.pdf) | Mixed terminology | E2 90/10 + V8 scenario mixture; reference champion |
| V12 | [Retrospective](Agenthon_T2_V12_F3_Conditional_Pool_Retrospective_2026-10-12.pdf) | Mixed terminology | F3 conditional pool; stopped before submission |
| V13 | [Retrospective](Agenthon_T2_V13_WIDTH085_Retrospective_2026-10-12.pdf) | Mixed terminology | WIDTH085; rejected after sealed evaluation |
| Reset | [Retrospective](Agenthon_T2_Gaussian_Reset_WIDTH090_Retrospective_2026-10-12.pdf) | Mixed terminology | Official Gaussian reset and WIDTH090 rejection |

### Later specialist and integration research

| Version | Bilingual report | Main decision |
| --- | --- | --- |
| VNext | [KR + EN](Agenthon_T2_VNext_Research_Report_KR_EN_2026-10-13.pdf) | Better gap handling and inflation trends, but no broad replacement case |
| VSpecial | [KR + EN](Agenthon_T2_VSpecial_Research_Report_KR_EN_2026-10-13.pdf) | Adopt specialists only for four CPI/PCE series |
| VSpecial2 Audit | [KR + EN](Agenthon_T2_VSpecial2_Audit_Research_Report_KR_EN_2026-10-13.pdf) | Repair input integrity; keep CPI mixture optional |
| VExpert | [KR + EN](Agenthon_T2_VExpert_Research_Report_KR_EN_2026-10-13.pdf) | Test 28-series experts; retain fast_price as a comparator |
| VStack | [KR + EN](Agenthon_T2_VStack_Research_Report_KR_EN_2026-10-13.pdf) | Prefer regression-safe stable integration over the new stack |

### Interpretation notes

- Local CRPS, joint, and tail figures are not official Codabench scores.
- Comparison baselines, evaluation origins, and data vintages can differ by version.
- Passing structural gates does not certify predictive accuracy or complete rule compliance.
- See [`research/`](../research/) for detailed tables, reproduction code, and provenance.
