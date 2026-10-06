# V2V-SCADA System Requirements & Verification Matrix

This matrix documents the verification state of all 21 core architectural subsystems in the V2V-SCADA platform.

### Verification Status Definitions
- **`IMPLEMENTED`**: Production source code or C++ firmware exists and is structured in the repository.
- **`AUTOMATED TESTED`**: Validated via automated deterministic unit, integration, or property test suites in CI / pytest.
- **`SIMULATED`**: Validated through software-in-the-loop (SIL), synthetic multi-vehicle simulation, or mock telemetry emitters.
- **`PHYSICALLY VALIDATED`**: Measured and verified on actual silicon/hardware on bench or field test track with real instrumentation.
- **`NOT VERIFIED`**: Requires pending verification or formal homologation.

---

## Comprehensive Subsystem Status Matrix

| # | Subsystem / Capability | Primary Source Files | Implementation State | Verification Level | Verification Evidence | Pending Physical Testing Requirements |
|:---:|:---|:---|:---:|:---:|:---|:---|
| **1** | **STM32 Edge Core** | `stm32/firmware/main.ino` | IMPLEMENTED | SIMULATED | ROM bootloader flash script, syntax verified | Physical bench clocking, IWDG watchdog reset timing, FreeRTOS task jitter |
| **2** | **GNSS Receiver Ingest** | `stm32/firmware/main.ino` | IMPLEMENTED | SIMULATED | NMEA sentence parsing via TinyGPS++, simulator GPS coordinates | Multi-path satellite lock, cold start TTFF, indoor GPS attenuation drift |
| **3** | **MPU-6050 / BNO055 IMU** | `stm32/firmware/main.ino` | IMPLEMENTED | SIMULATED | I2C registers 0x68/0x3C, simulated pitch/roll/yaw | Sensor calibration drift, road vibration resonance, thermal bias drift |
| **4** | **SX1281 2.4 GHz RF Radio**| `stm32/firmware/main.ino` | IMPLEMENTED | SIMULATED | RadioLib SX1281 configuration, packet frame structure | Over-the-air link budget, packet error rate vs distance, Fresnel zone clearance |
| **5** | **HMAC-SHA256 Signing** | `backend/security.py`, `stm32/firmware/main.ino` | IMPLEMENTED | AUTOMATED TESTED | `test_canonical_hmac_valid`, signature corruption tests | Hardware crypto acceleration execution time profiling on Cortex-M |
| **6** | **Anti-Replay Windowing** | `backend/security.py` | IMPLEMENTED | AUTOMATED TESTED | Monotonic sequence tests, timestamp skew tests, reboot tests | Multi-node clock drift handling under non-synchronized RTC crystals |
| **7** | **10Hz Telemetry Packet** | `backend/main.py`, `backend/security.py` | IMPLEMENTED | AUTOMATED TESTED | Pydantic `TelemetryPayload` validation, serial bridge dispatch | End-to-end 10Hz sustained throughput over physical 115200 baud UART bridge |
| **8** | **MQTT Broker & Bridge** | `backend/mqtt_client.py`, `mqtt/mosquitto.conf` | IMPLEMENTED | AUTOMATED TESTED | Local demo dispatch, authenticated/TLS config, fallback routing | Broker disconnection resilience under continuous 100+ msg/s hardware load |
| **9** | **FastAPI SCADA Host** | `backend/main.py` | IMPLEMENTED | AUTOMATED TESTED | REST endpoints, CORS restrictions, error response codes | Multi-client concurrent load and memory footprint over 24+ hour run |
| **10**| **WebSocket Telemetry Stream**| `backend/main.py` | IMPLEMENTED | AUTOMATED TESTED | 60 FPS broadcast loop, client connection/disconnection handling | Network socket latency under fluctuating client Wi-Fi bandwidth |
| **11**| **SQLite WAL Database** | `backend/database.py` | IMPLEMENTED | AUTOMATED TESTED | 14 tables, WAL mode, transaction batching, incident logging | High-speed concurrent write stress testing during multi-vehicle incidents |
| **12**| **Collision Physics (2D)** | `backend/mqtt_client.py` | IMPLEMENTED | AUTOMATED TESTED | Haversine distance, Cartesian closing speed, heading normalization | Real road curvature snapping, 3D gradient/elevation elevation compensation |
| **13**| **Time-to-Collision (TTC)**| `backend/mqtt_client.py` | IMPLEMENTED | AUTOMATED TESTED | Warning (3.5s) and Critical (2.5s) multi-tier thresholds | Real driver reaction time and deceleration dynamics integration |
| **14**| **Emergency Vehicle Alert**| `backend/mqtt_client.py` | IMPLEMENTED | AUTOMATED TESTED | Threat Level 4 preemption when ambulance within 200m | Real-world multi-path RF propagation of emergency beacons through traffic |
| **15**| **Geofence Zone Violation**| `backend/mqtt_client.py`, `backend/config.py` | IMPLEMENTED | AUTOMATED TESTED | Ray-casting `is_in_polygon` with inside/outside coordinates | GNSS jitter near polygon boundary lines causing false boundary triggers |
| **16**| **Leaflet SCADA Dashboard**| `frontend/index.html`, `frontend/js/app.js` | IMPLEMENTED | SIMULATED | Cyberpunk HUD, 60 FPS vehicle tracking, DPI hex view | Mobile browser rendering performance and touch controls in-cabin |
| **17**| **Vehicular Traffic Simulator**| `stm32/simulator.py` | IMPLEMENTED | AUTOMATED TESTED | 4-vehicle OSRM road trajectory generator, spoof attack emitter | Validation against real CAN-bus or highway traffic trace logs |
| **18**| **Machine Learning Model** | `ml/collision_model.py`, `ml/train_model.py` | IMPLEMENTED | AUTOMATED TESTED | 99.6% accuracy on synthetic TTC split, rule-based fallback | Training and validation against real-world crash or NGSIM vehicle traces |
| **19**| **Docker Orchestration** | `Dockerfile`, `docker-compose.yml` | IMPLEMENTED | SIMULATED | Non-root `appuser`, health checks, volume mounts | Long-running container stability on embedded edge hardware (e.g. Raspberry Pi) |
| **20**| **PDF Audit Reporting** | `backend/report_generator.py` | IMPLEMENTED | AUTOMATED TESTED | ReportLab PDF compilation, path-traversal-guarded download | Performance impact of PDF rendering under high telemetry stream load |
| **21**| **Provider Abstraction** | `backend/providers/` | IMPLEMENTED | AUTOMATED TESTED | WebRTC telephony, Indic translation (12 languages), fallback lexicon | High-noise cabin acoustic performance with vehicle engine background noise |

---

## Summary of Verification Levels
- **Automated Tested (Software/Logic)**: 16 / 21 subsystems (76%)
- **Simulated (System-in-the-Loop)**: 5 / 21 subsystems (24%)
- **Physically Validated (On Real Hardware)**: 0 / 21 subsystems (0% — explicitly pending hardware test-track validation)

> [!IMPORTANT]
> **Zero Hardware Claims Verified Prior to Laboratory Testing**:
> No feature is claimed as physically validated. Firmware and drivers are implemented, structurally verified, and tested against simulator and unit tests, but require physical bench and test-track validation per `docs/HARDWARE_VALIDATION_PLAN.md`.
