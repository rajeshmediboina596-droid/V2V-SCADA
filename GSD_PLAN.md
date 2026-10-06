# GSD_PLAN.md — V2V-SCADA End-to-End Engineering Validation & Reliability

## Phase Objective
Prove internal consistency, telemetry contract uniformity, collision physics determinism, failure recovery resilience, observability, and hardware integration readiness for the V2V-SCADA platform.

---

## 4-Pillar Pipeline Architecture
- **GSD Core**: Spec-driven, milestone-tracked development lifecycle.
- **Roo Code Modes**:
  - *Architect Mode*: Contract specifications, requirements matrix, hardware specs.
  - *Code Mode*: Surgical implementation of contract guards, physics edge cases, instrumentation.
  - *Test Mode*: Deterministic unit/integration suites (Phase 4, 5, 6, 8, 13).
- **Ralph Loop**: Continuous feedback loop using `progress.txt` and `GSD_PLAN.md`.
- **Code Rabbit Gate**: Automated quality, security, and edge-case audit before completion.

---

## Milestone Breakdown & Checklist

- [x] **Phase 0 — Inspect Current State**
  - [x] Verify Git tree and latest commit.
  - [x] Execute baseline test suites (`pytest`, `test_voice_call_system.py`).
  - [x] Create `GSD_PLAN.md` and `progress.txt`.

- [ ] **Phase 1 — Technical Requirements Matrix**
  - [ ] Create `docs/REQUIREMENTS_MATRIX.md` covering all 21 subsystems.
  - [ ] Classify each capability: `IMPLEMENTED`, `AUTOMATED TESTED`, `SIMULATED`, `PHYSICALLY VALIDATED`, `NOT VERIFIED`.
  - [ ] Explicitly identify hardware testing gaps.

- [ ] **Phase 2 — End-to-End Telemetry Packet Trace**
  - [ ] Trace fields: `vehicle_id`, `vehicle_type`, `timestamp`, `seq`, `lat`, `lon`, `alt`, `speed_kmph`, `heading_deg`, `pitch_deg`, `roll_deg`, `yaw_deg`, `battery_level`, `emergency_status`, `rf_status`, `fault_code`, `signature`.
  - [ ] Inspect STM32 firmware, serialization, Python backend, Pydantic model, SQLite schema, WebSocket broadcast, and frontend Leaflet/HUD rendering.
  - [ ] Identify and reconcile any naming, unit, or type discrepancies.

- [ ] **Phase 3 — Canonical Telemetry Contract**
  - [ ] Author `docs/CANONICAL_TELEMETRY_CONTRACT.md`.
  - [ ] Enforce field boundaries, units, canonical string format, and timestamp/sequence semantics.
  - [ ] Add contract verification tests in test suite.

- [ ] **Phase 4 — Collision Engine Validation**
  - [ ] Implement 16 deterministic kinematic scenarios in `tests/test_collision_scenarios.py`.
  - [ ] Verify distance, closing speed, TTC, risk level, and emergency preemption.
  - [ ] Document mathematical formulas and relative-motion prototype assumptions.

- [ ] **Phase 5 — Failure & Recovery Matrix**
  - [ ] Implement failure recovery behaviors and tests for GNSS loss, IMU failure, MQTT drops, DB offline, and corrupted payloads.
  - [ ] Validate fail-safe AEB demonstration relay state (default LOW, no spurious triggers).

- [ ] **Phase 6 — MQTT Reliability**
  - [ ] Verify client reconnection loops, non-blocking fallback dispatch, QoS, and authenticated modes.

- [ ] **Phase 7 — Performance Instrumentation**
  - [ ] Add lightweight runtime profiling (pipeline latency, collision calculation time, DB batch latency) without blocking event loop.
  - [ ] Tag all numbers as `DESIGN TARGET`, `MEASURED`, or `NOT MEASURED`.

- [ ] **Phase 8 — Security Regression Gate**
  - [ ] Implement automated regression tests for field tampering, out-of-order sequences, path traversal, and malicious payloads.

- [ ] **Phase 9 — Observability & Diagnostics**
  - [ ] Enhance diagnostic logging with proper levels (`INFO`, `WARNING`, `ERROR`) without exposing secrets or flooding logs.

- [ ] **Phase 10 — SCADA Dashboard Reliability**
  - [ ] Ensure frontend flags stale vehicles (>15s), handles WebSocket reconnects cleanly, and distinguishes `LIVE`, `STALE`, `DISCONNECTED`.

- [ ] **Phase 11 — Database Integrity & Reliability**
  - [ ] Verify SQLite indexes, WAL checkpointing, duplicate prevention, and prune/retention routines.

- [ ] **Phase 12 — Hardware Interface Specification**
  - [ ] Author `docs/HARDWARE_INTERFACE_SPEC.md` documenting STM32, GNSS, MPU6050, SX1281, OLED, Buzzer, and Relay.

- [ ] **Phase 13 — Simulator Realism & Preset Scenarios**
  - [ ] Enhance `stm32/simulator.py` with deterministic collision scenarios (head-on, crossing, ambulance pass, geofence breach).

- [ ] **Phase 14 — CI Quality Gate**
  - [ ] Create `.github/workflows/ci.yml` running syntax checks, pytest, and security regression gates.

- [ ] **Phase 15 — Low-Value Feature Review**
  - [ ] Audit repository and report classifications: `CORE`, `SUPPORTING`, `OPTIONAL`, `DEMO`, `LOW-VALUE`.

- [ ] **Phase 16 — Hardware Validation Plan**
  - [ ] Author `docs/HARDWARE_VALIDATION_PLAN.md` with 17 concrete physical test protocols and unpopulated measurement fields.

- [ ] **Phase 17 — Final Verification & Commit**
  - [ ] Run full test suite, lint, compile, and live sanity checks.
  - [ ] Commit with message: `test: validate V2V telemetry and end-to-end system reliability`.
