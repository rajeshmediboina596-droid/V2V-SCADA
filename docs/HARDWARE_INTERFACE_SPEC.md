# V2V-SCADA Vehicle Edge Node Hardware Interface Specification

## 1. Edge Node Hardware Architecture Overview

The physical vehicle node is built around an ARM Cortex-M microcontroller executing the V2V edge firmware (`stm32/firmware/main.ino`). The node interfaces directly with sensors, RF communications, human-machine interface (HMI) peripherals, and an autonomous emergency braking demonstration relay.

```
Vehicle Node Architecture:
STM32F103C8T6 (ARM Cortex-M3 / 72 MHz)
├── GNSS Receiver (USART2: PA2/TX, PA3/RX)
├── MPU-6050 6-DOF IMU (I2C1: PB6/SCL, PB7/SDA @ 400 kHz)
├── Semtech SX1281 2.4 GHz Transceiver (SPI1: PA5/SCK, PA6/MISO, PA7/MOSI, PA4/NSS, PB0/DIO1, PB1/RST, PB10/BUSY)
├── SSD1306 0.96" OLED HUD (I2C1: PB6/SCL, PB7/SDA @ Addr 0x3C)
├── Audible Warning Buzzer (GPIO: PB8, PWM / Digital Output)
├── Visual Hazard LED Indicator (GPIO: PA8, Active High)
└── Prototype AEB Demo Relay (GPIO: PB9, Active High NPN Driver)
```

---

## 2. Component Interface Specifications

### A. STM32 Edge Core
- **Hardware**: STM32F103C8T6 (ARM Cortex-M3, 72 MHz, 64 KB Flash, 20 KB SRAM).
- **Purpose**: Real-time sensor fusion, HMAC-SHA256 edge signing, peer collision threat assessment, and safety actuation.
- **Expected Update Rate**: Main telemetry broadcast loop runs at 10 Hz ($100\text{ ms}$ interval); peer reception is interrupt-driven on SX1281 DIO1.
- **Failure Behavior**: On critical fault, illuminates Alert LED (`PA8`) and logs fault code (`fault_code`).
- **Software Dependency**: STM32 Arduino Core, `RadioLib`, `TinyGPSPlus`, `ArduinoJson`, `SHA256`.
- **Physical Validation Status**: **`SIMULATED`** (Firmware compiled; bench flashing script verified; bench clocking and IWDG watchdog timing pending hardware integration).

### B. GNSS Receiver Module
- **Hardware**: Neo-6M / Neo-M8N GNSS Module.
- **Purpose**: Geodetic positioning (latitude, longitude), ground speed, course over ground (heading), and altitude.
- **Physical Interface**: Hardware UART (USART2: `PA2/TX`, `PA3/RX` @ 9600 baud default).
- **Data Extracted**: Latitude ($\pm 90^\circ$, 6 decimals), Longitude ($\pm 180^\circ$, 6 decimals), Speed ($\text{km/h}$), Heading ($0-360^\circ$), Altitude ($\text{m}$).
- **Expected Update Rate**: 1 Hz to 10 Hz (sensor dependent; 9600–115200 baud).
- **Failure Behavior**: If satellite fix is lost (`gps.location.isValid() == false`), firmware holds last valid fix or halts broadcast; flags fallback to IMU course.
- **Software Dependency**: `TinyGPSPlus.h`.
- **Physical Validation Status**: **`SIMULATED`** (NMEA parsing verified; outdoor multipath and cold-start TTFF pending test-track validation).

### C. MPU-6050 6-Axis Motion Sensor
- **Hardware**: InvenSense MPU-6050 (3-axis Accelerometer + 3-axis Gyroscope).
- **Purpose**: Vehicle chassis dynamics (longitudinal pitch, transverse roll, and yaw rate).
- **Physical Interface**: I2C Bus (`PB6/SCL`, `PB7/SDA` @ 400 kHz Fast-Mode, Slave Address `0x68`).
- **Data Extracted**: Pitch angle ($-90^\circ \text{ to } +90^\circ$), Roll angle ($-90^\circ \text{ to } +90^\circ$).
- **Expected Update Rate**: 100 Hz internal DLPF sampled at 10 Hz main loop.
- **Failure Behavior**: If I2C initialization fails (`WHO_AM_I` mismatch), sets `imuAvailable = false`, flags `fault_code = "ERR_IMU_OFFLINE"`, and falls back to GNSS course heading without stopping telemetry.
- **Software Dependency**: `Wire.h`.
- **Physical Validation Status**: **`SIMULATED`** (Register read/write code verified; road vibration resonance and thermal bias drift pending physical vehicle testing).

### D. Semtech SX1281 2.4 GHz RF Transceiver
- **Hardware**: Semtech SX1281 Transceiver (2.4 GHz ISM band, FLRC / LoRa modulation).
- **Purpose**: Ultra-low-latency inter-vehicle telemetry broadcast and roadside gateway packet ingest.
- **Physical Interface**: High-Speed SPI1 (`PA5/SCK`, `PA6/MISO`, `PA7/MOSI`, `PA4/NSS`, `PB0/DIO1`, `PB1/RST`, `PB10/BUSY`).
- **RF Parameters (Design Target)**: 2400.0 MHz carrier, 812.5 kHz bandwidth, SF7, CR 4/5, SyncWord `0x12`, 10 dBm transmit power.
- **Expected Update Rate**: 10 Hz broadcast rate ($100\text{ ms}$ airtime slot).
- **Failure Behavior**: If `radio.begin()` fails, halts boot loop, blinks Alert LED at 3 Hz, sets `fault_code = "ERR_RF_INIT_FAIL"`.
- **Software Dependency**: `RadioLib.h`.
- **Physical Validation Status**: **`SIMULATED`** (Driver configuration verified; link budget, packet error rate vs distance, and Fresnel zone clearance pending test-track RF trials).

### E. SSD1306 0.96" I2C OLED HUD
- **Hardware**: SSD1306 $128 \times 64$ monochrome OLED.
- **Purpose**: In-cabin driver heads-up display showing vehicle speed, nearest peer distance, TTC, and active threat level.
- **Physical Interface**: I2C Bus (Shared `PB6/SCL`, `PB7/SDA` @ Address `0x3C`).
- **Expected Update Rate**: 10 Hz HUD refresh.
- **Failure Behavior**: If not present on I2C bus, firmware sets `oledAvailable = false` and continues normal headless operation without blocking.
- **Software Dependency**: `Wire.h` / `Adafruit_SSD1306.h`.
- **Physical Validation Status**: **`SIMULATED`** (I2C detection probe verified).

### F. Audible Warning Buzzer & Alert LED
- **Hardware**: Active Piezo Buzzer (`PB8`) and High-Intensity Alert LED (`PA8`).
- **Purpose**: Multi-tier driver acoustic and visual alarms:
  - Threat Level 1 (Advisory): 1 Hz visual pulse.
  - Threat Level 2 (Warning): Intermittent 5 Hz audible beep + solid LED.
  - Threat Level 3 (Critical AEB): Continuous high-pitch tone + solid LED.
  - Threat Level 4 (Emergency Yield): Dual-tone siren cadence.
- **Physical Interface**: GPIO Digital Outputs (`PB8`, `PA8`).
- **Failure Behavior**: Inactive by default (`LOW`); fails safe to silent during microcontroller reset.
- **Physical Validation Status**: **`SIMULATED`** (State logic verified in code).

### G. Prototype AEB Demonstration Relay
- **Hardware**: 5V Single-Channel Optocoupled Relay Module.
- **Purpose**: Physical actuation indicator representing Automatic Emergency Braking (AEB) engagement.
- **Physical Interface**: GPIO Digital Output (`PB9`, Active High).
- **Expected Update Rate**: Actuated on demand during Threat Level 3 (TTC $\le 2.5\text{ s}$ and Distance $< 45\text{ m}$).
- **Failure Behavior**: **Strictly Fail-Safe**: Defaults to `LOW` (De-energized) on startup, reset, sensor timeout (>2.5s), and security rejection.
- **Physical Validation Status**: **`SIMULATED`** (Actuation logic verified; bench relay click and bench load test pending).

> [!CAUTION]
> **Laboratory Safety Boundary**:
> The AEB relay is strictly a bench-level laboratory prototype indicator. It is NEVER to be wired into motor vehicle braking actuators without ISO 26262 ASIL-D certified hardware redundancy.
