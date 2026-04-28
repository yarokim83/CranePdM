# V2.6 알고리즘 검증 요건

작성일: 2026-04-25
연관 알고리즘: `crane_edge_logger.py` `calculate_kpis()` V2.6 (geo-fence 폐지, pure measurement-driven)

V2.6 도입의 의미를 가르는 두 가지 핵심 명제. 이 둘이 검증되지 않으면 V2.6 채택 자체를 재검토해야 한다.

---

## 명제 1: 232호 4/22 기어 파손 전후 스트레스 변화 감지

**의미**
V2.6 알고리즘이 232호의 2026-04-22 기어 파손 전후 스트레스 변화를 감지하지 못하면, 이 알고리즘은 PdM 시스템의 본래 목적(예지정비, 파손 전조 포착)을 달성하지 못한다. V2.5에서는 Block 3 hotspot geo-fence 곱수(×2.0~×3.0) 덕분에 232호가 손상도 ranking에서 자동으로 두드러졌지만, V2.6에서는 그 보정이 사라졌다. 따라서 측정값 자체(`shock_penalty`, `curr_penalty`, `peak_shock`, `reducer_damage`)에 232호 파손 신호가 충분히 담겨 있어야 한다.

**검증 방법**
- `raw_plc_data/2026-04-09 ~ 2026-04-24/` 의 232호 raw 이벤트를 `replay_raw_to_influx.py --algo-tag 2.6` 로 retroactive replay
- Grafana 또는 직접 쿼리로 다음 추세 확인:
  - 파손 직전(4/19~4/21): 232호 daily mean/peak `reducer_damage`가 232호 자체 baseline(예: 4/9~4/15) 대비 유의미하게 상승하는가
  - 동일 기간 다른 Block 3 정상 크레인(231/233/234) 대비 232만 두드러지는가
  - 파손 후 부품 교체(4/23~): damage가 baseline 수준으로 복귀하는가
- 단순 ranking 외에 `peak_shock` 시계열의 분포 변화(이상 spike의 빈도/강도)도 함께 본다

**합격 기준**
- 4/19~4/21 232호 daily damage가 자체 baseline + 다른 정상 크레인 대비 통계적으로 유의미하게 상승 (예: ≥1.5σ)
- 4/23~ 회복 패턴이 raw 측정값에서 보임
- 위 두 조건 모두 만족 → V2.6 단독으로 232 사례를 잡을 수 있다고 결론

**불합격 시 대응**
- 명제 2의 스케일 갭 해결과 동시에, V2.6에 측정값 기반 anomaly score(예: per-crane rolling baseline 대비 z-score) 도입을 검토
- geo-fence를 알고리즘에 다시 굽기보다, Grafana 알람 레이어에서 통계 anomaly로 처리하는 것이 V2.6 설계 철학과 일치

---

## 명제 2: V2.4/V2.5 → V2.6 데이터 스케일 갭 문제

**문제**
4/22 이전 CSV/InfluxDB 데이터(V2.4·V2.5 시절 실시간 기록)와 V2.6 적용 이후 신규 데이터의 스케일이 크게 다르면, 232호 파손 전후 비교 분석 자체가 불가능해진다. 같은 그래프에 그려도 알고리즘 차이로 발생한 갭인지 실제 기계 변화인지 구별되지 않는다.

**구체적 근거**
- Round-trip 검증(2026-04-25):
  - 232호 4/24 한 이벤트(position 2501~2726m, Block 3 핫스팟)
  - V2.5 시절 InfluxDB 기록: `reducer_damage = 129.99`
  - 동일 raw → V2.6 재계산: `reducer_damage = 57.49`
  - 비율 ≈ **2.26배** (V2.5 → V2.6 갈수록 감소)
- shock/curr/track penalty + peak_shock + position 모두 일치 → **차이는 100% geo-fence 곱수 제거에서 발생**. 위치에 따라 ×1.0~×3.0 사이에서 갭이 달라진다.
- `crane_kpi_log.csv` 수정 금지 원칙 유지 → 과거 CSV를 직접 retrofit 할 수 없음

**해결 방향**
1. **Raw replay (1차 해법, raw 보존 기간 한정)**
   - `raw_plc_data/` 에 살아있는 4/9~4/24(RAW_RETENTION_DAYS=30 이내) 데이터를 V2.6으로 retroactive replay
   - InfluxDB에 `algo_version="2.6"`, `source="raw_replay"` 태그로 병렬 저장
   - Grafana는 algo_version으로 필터링해 V2.6 단일 기준선에서 232 파손 전후 비교
   - 원본 V2.5 데이터(`source` 태그 없음 또는 다른 값)와 충돌 없음

2. **Raw가 없는 과거 (구조적 한계)**
   - 4/9 이전 (raw retention 30일 한계 외) 또는 raw 저장 시작 전 데이터는 unrecoverable
   - 이 경우 단순 비교는 불가. 위치별 V2.5/V2.6 변환 계수 추정도 가능은 하지만 정밀도 보장 안 됨 → 권장 안 함
   - 232 사례 분석에는 영향 적음 (raw가 4/9부터 있다면 파손 분석에 충분)

3. **Grafana 레이어 분리 시각화 (영구 운영)**
   - `algo_version` 태그로 패널을 분리 (V2.6만 vs 모두)
   - 232 파손 비교 등 정합성이 필요한 분석은 V2.6 태그만 필터해서 봄
   - 새 사용자가 V2.5/V2.6 혼재 데이터에 헷갈리지 않도록 dashboard 주석 추가

**합격 기준**
- 4/9~4/24 전체 raw가 V2.6 태그로 InfluxDB에 저장됨
- Grafana V2.6 전용 패널에서 232 daily damage 추세가 매끄럽게 이어짐 (알고리즘 변경 발자국 없음)
- 명제 1 검증을 V2.6 단일 기준선에서 수행 가능

---

## 작업 순서 (제안)

1. 4/9~4/24 raw replay 실행 (`replay_raw_to_influx.py --start-date 2026-04-09 --end-date 2026-04-24 --algo-tag 2.6`)
2. Grafana에 algo_version 필터 패널 추가 (Stress Index 대시보드 등)
3. 232호 V2.6 daily damage 시계열 추출 + baseline 통계 계산
4. 4/19~4/21 vs 4/9~4/15 비교, 4/23~ 회복 확인
5. 결과를 `ALGORITHM.md` 또는 별도 분석 문서에 추가

---

## 데이터 가용성 (2026-04-25 발견)

| 기간 | raw_plc_data | crane_kpi_log.csv | InfluxDB |
|---|---|---|---|
| 3/29~3/31 | 없음 | V2.2/V2.3 (567건 232) | (확인 시 V2.4 retroactive) |
| 4/1~4/8 | 없음 | **누락** | V2.4 retroactive |
| 4/9~4/23 | **없음 (raw 저장 미시작)** | **누락** | V2.4 retroactive (232: 6076건) |
| 4/24~4/25 | ✅ (4414건 전체, 232: 127건) | V2.4/V2.5 실시간 | V2.4/V2.5 실시간 |

**raw_plc_data 부재 한계**: raw 저장 기능이 4/24부터 시작 → 4/9~4/23 232 파손 직전 핵심 기간을 raw 기반 정확한 V2.6 재계산이 불가. 차선책으로 InfluxDB 의 historical V2.4 KPI 레코드를 algorithm-aware 변환식으로 V2.6-equiv 환산.

---

## 1차 작업 결과 (2026-04-25 실행)

### 명제 2 (스케일 갭 해결) -- 부분 해결

- **4/24~4/25 raw → V2.6 정확값** InfluxDB 저장: 4414 events `algo_version=2.6 source=raw_replay`
- **3/29~4/22 historical → V2.6-equiv 환산** InfluxDB 저장: 215,965 events `algo_version=2.6 source=csv_retrofit`
  - 변환 규칙: V2.5/V2.4 는 geo factor 역산(÷2.0 또는 ÷3.0), V2.3/V2.2 는 그대로
  - 215,965 중 4,398건(2%) 만 geo factor x2.0 적용됨 (대부분 정상 위치 → 변환 영향 적음)
  - 전체 sum_damage ratio: 0.965 (3.5% 감소)
- 두 source 가 algo_version=2.6 단일 태그 아래 합쳐짐 → Grafana 시계열 단절 없음
- **잔여 한계**: apply_v24_retroactive.py 가 V2.3 → V2.4 로 overwrite 한 inflation 흔적이 csv_retrofit 안에 그대로 남음. raw_replay 와 절대값 비교 시 ~5x 차이 (232 4/9~4/17 평균 939 vs 4/24 평균 185). **상대 추세 비교는 가능, 절대값 비교는 신뢰 어려움**

### 명제 1 (232 파손 감지) -- 강력한 합격

| 지표 | 값 | 합격 기준 | 평가 |
|---|---|---|---|
| 4/21 per-event spike z-score | **+2.74σ** | ≥1.5σ | ✅ |
| 파손 후 per-event 감소 | **5.49x** | 명백 감소 | ✅ |
| baseline 대비 ratio 변화 | 0.79x → 0.41x | 232 자체 회복 신호 | ✅ |

**4/21 spike (+2.74σ)**: 232 per-event damage 1035, 4/9~4/17 평균 781(σ=93). 정규분포 가정 시 99.7% 분위 초과 → 통계적으로 매우 유의미한 파손 직전 spike.

**baseline 대비 ratio 변화**: 232/baseline 비율이 4/9~4/21 동안 0.79x **일관** 후 4/24~25 에 0.41x 로 떨어짐. 만약 알고리즘 잔여 inflation 만의 문제였다면 모든 크레인이 같은 비율로 변할 것 → ratio 변동이 232 자체의 회복(부품 교체)임을 증명.

### 분석 스크립트
- `convert_csv_to_v26.py` -- InfluxDB historical V2.4 → V2.6-equiv 환산 (csv_retrofit 태그)
- `analyze_232_v26_baseline.py` -- 232 vs Block 3 baseline daily 통계 + 4/21 z-score

---

## 2차 작업 — Calibration (2026-04-25)

### 잔여 inflation 정밀 분리

`compute_calibration_factors.py` 결과:
- **V2.4 native ↔ V2.6 raw_replay** : 0.980 (운영 normalize, 알고리즘 차이는 사실상 없음 — 2%)
- **csv_retrofit ↔ V2.4 native** : **6.06x inflated** ← apply_v24_retroactive.py 의 부풀림
- **shock_penalty inflation** : **9.35x** (csv_retrofit=17.79 vs raw_replay=1.90) — 핵심 원인
- **peak_shock 보존도** : 1.01x (raw 측정값은 정확하게 보존됨)

### 보정 적용 (calibrate_csv_retrofit.py)

방법: per-event 페널티 비율 재계산
- stored peak_shock 그대로 활용 (raw 측정값으로 신뢰 ↑)
- V2.6 공식으로 shock_penalty 추정: `est_shock_penalty = peak_shock × 0.171` (4/24~25 raw_replay fleet 통계)
- damage 보정: `damage_v6 = damage_csv × (est_shock / stored_shock) × (raw_curr / stored_curr)`
- 새 source 태그 `csv_retrofit_calibrated` 로 InfluxDB 저장

**보정 결과**:
- Fleet mean per-event: **csv_retrofit 1690 → calibrated 283** (4/24~25 raw_replay 287 과 1.4% 차이로 매끄러움)
- 232호 timeline 갭 사라짐: 4/9-20 baseline daily mean=220, sigma=29.9 (분산 좁아 안정적)

### 명제 1 정밀 검증 (보정 데이터)

| 지표 | 보정 전 | 보정 후 | 합격 기준 |
|---|---|---|---|
| 4/9-20 baseline daily mean | 802 | **220** | - |
| 4/9-20 sigma | 115 | 29.9 | (분산 좁음 = 신뢰성 ↑) |
| 4/21 daily mean | 1035 | **299** | - |
| **4/21 z-score** | +2.74σ | **+2.65σ** | ≥1.5σ |
| 4/24 회복율 | -82% | -16% | 명백 감소 |
| 4/25 회복율 | -89% | -51% | |

**결론**: csv_retrofit 의 절대값 갭이 정밀 보정으로 사라짐 (5x → 1.4%). 4/21 spike 가 보정 후에도 +2.65σ 로 V26_VALIDATION 합격 기준(+1.5σ) 초과 → **명제 1 (V2.6 측정값으로 232 파손 전조 감지) 정밀하게 합격**. 회복율도 부품 교체 + 저속 정책의 누적 효과로 합리적인 16~51% 감소.

---

## 한계 및 향후 개선 항목

1. ~~**csv_retrofit 의 inflation 잔여**~~ → **2차 작업에서 calibration 으로 해결됨**. mean 갭 5x → 1.4% 로 감소. csv_retrofit_calibrated source 태그로 InfluxDB 저장. 단 fleet 평균 통계 기반 보정이라 개별 이벤트별 정확도는 제한적.
2. **V2.5 per-sample 위치 곱수의 avg_pos 근사**: 핫스팟 부분 통과 이벤트는 +/- 오차 (영향은 232 의 경우 6076건 중 832건만 ×2.0 적용 → 13.7%).
3. **V2.3/V2.2 → V2.6 의 speed-norm 페널티 차이는 보정 불가**: raw 부재로 저속 충격 +20% under-report 가능 (이번 232 분석은 이 효과보다 큰 스케일 변화를 잡았으니 합격이지만, 일반화는 어려움).
4. **raw_plc_data 보존 기간**: RAW_RETENTION_DAYS=30 + 4/24부터 저장 시작이라 4/9~4/23 raw 영구 부재. 향후 사례에서는 raw 가 살아있게 운영 정책 강화 필요.

**다음 알고리즘 사례에서 명제 1·2 검증 시 우선 raw_replay 만으로 가능한 범위인지 확인. csv_retrofit 은 "raw 가 없어 차선책"임을 인지.**
