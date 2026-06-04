---
date: 2026-06-02
tags:
  - rfic
  - lc-dco
  - ihp-sg13g2
  - subthreshold
  - ble
project: IHP SG13G2 130nm Subthreshold LC-DCO
status: in-progress
---

# 2026-06-02 LC-DCO Phase 2 진행 노트

## 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 공정 | IHP SG13G2 130nm |
| 목표 주파수 | 2.4 GHz (BLE) |
| 동작 영역 | Subthreshold |
| 경로 | ~/rfic_project/ (WSL2 Ubuntu 24.04) |
| PDK | ~/tools/IHP-Open-PDK/ihp-sg13g2/ |

---

## Phase 1 요약 (이전 세션)

> [!success] Phase 1 완료
> - MSB=0 발진 확인
> - f ≈ 4.42 GHz, swing ≈ 150 mV, P ≈ 200 μW

---

## Phase 2 작업 내용

### 1. Current DAC I_ref 업그레이드 (10 μA → 15 μA)

> [!note] 변경 내용
> - **파일**: ~/rfic_project/circuits/blocks/tail_current_dac.cir
> - **변경**: I_ref 10 μA → 15 μA (전체 1.5배 스케일업)
> - **목적**: MSB=28→31 구간 발진 실패 문제 해결

| 코드워드 | I_tail |
|---------|--------|
| MSB=0   | 150 μA |
| MSB=31  | 615 μA |

---

### 2. Phase A Sweep 결과 (MSB 0→31, LSB=0)

> [!success] MSB sweep 전 구간 발진 성공

| MSB | f (GHz) | swing (mV) | I (μA) | 상태 |
|-----|---------|-----------|--------|------|
| 0   | 4.420   | 276       | 150    | ✓    |
| 4   | 4.040   | 314       | 210    | ✓    |
| 8   | 3.760   | 365       | 270    | ✓    |
| 12  | 3.520   | 365       | 330    | ✓    |
| 16  | 3.320   | 420       | 390    | ✓    |
| 20  | 3.160   | 372       | 450    | ✓    |
| 24  | 3.000   | 319       | 510    | ✓    |
| 28  | 2.880   | 231       | 570    | ✓    |
| 31  | 2.800   | 155       | 615    | ✓ ← I_ref=15μA 덕분에 발진! |

---

### 3. Phase B 문제 발견 (MSB=31, LSB sweep)

> [!warning] LSB 추가 시 발진 즉시 사망

| LSB | swing (mV) | 상태 |
|-----|-----------|------|
| 0   | 155       | ✓    |
| 4   | 12.6      | ✗    |
| 8+  | ≈ 0       | ✗    |

---

### 4. 진단 시뮬레이션 (1 μs 확장)

> [!note] 조건: MSB=31, LSB=4

| 시간 구간            | swing (mV) |
|---------------------|-----------|
| EARLY (150–200 ns)  | 12.6      |
| LATE (800–1000 ns)  | 1.67      |

> [!warning] 결론
> Startup 지연이 아니라 **진짜 발진 실패** — oscillation is decaying

---

## 근본 원인 분석

> [!note] 핵심 문제
> Current DAC가 **MSB만 추적**하고 **LSB는 추적하지 않음**

**인과 관계:**

LSB 추가 → C 증가 → f 감소 → Rp = ω²L²/Rs 감소 → gm × Rp < 1 → 발진 실패

**수치:**
- Rp(f=2.8 GHz) ≈ 424 Ω
- Rp(f=2.4 GHz) ≈ 311 Ω → **26% 감소**

**발진 조건 수식:**

Rp = (ωL)² / Rs

발진 조건: (gm_N + gm_P) × Rp > 1

---

## 다음 단계 (미완료)

> [!todo] 수정 필요 사항

### 1. tail_current_dac.cir 수정 — LSB 추적 전류 브랜치 추가

- **현재 포트**: vs vdd msb4 msb3 msb2 msb1 msb0
- **새 포트**: vs vdd msb4 msb3 msb2 msb1 msb0 lsb4 lsb3 lsb2 lsb1 lsb0
- LSB=31에서 ~186 μA 추가 필요 (Rp 26% 감소 보상)
- I_unit_LSB ≈ 6 μA/step → W_lsb ≈ 0.8 μm (I_ref=15 μA, W_ref=2 μm 기준)

### 2. lc_dco_top.cir 수정 — X_tail에 lsb 포트 전달



### 3. sweep_cap_bank.py 수정

- estimate_ibias_dac() 함수에 LSB 항 추가

### 4. 목표

- MSB=31 + LSB=23 근방에서 **f ≈ 2.4 GHz**, **swing > 100 mV** 달성

---

## 설계 파라미터 요약

| 파라미터 | 값 |
|---------|-----|
| 인덕터 L | 1.28 nH |
| 직렬 저항 Rs | 1.2 Ω (FastHenry 3턴 옥타곤) |
| 고정 커패시터 C_F | 1.72 pF (각 측) |
| MSB unit 커패시턴스 | 97 fF |
| LSB unit 커패시턴스 | 69 fF |
| 공진 주파수 | f = 1 / (2pi * sqrt(L/2 * C_each)) |
| Q @ 2.4 GHz | ≈ 16 |
| Rp @ 2.4 GHz | ≈ 307–311 Ω |
| VDD | 1.2 V |
| 목표 전력 | < 1 mW |

---

## 관련 파일

- tail_current_dac.cir
- lc_dco_top.cir
- sweep_cap_bank.py
