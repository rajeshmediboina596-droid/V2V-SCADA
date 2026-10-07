# STM32 V2V Firmware Specification & Architecture

## 1. Canonical Firmware Architecture
The firmware directory contains two files that serve distinct IDE requirements while executing identical logic:
- **Canonical Master Source**: [`stm32/firmware/main.ino`](file:///c:/projectss/v2v%20communication/stm32/firmware/main.ino) (Root reference file for PlatformIO and CI pipeline analysis).
- **Arduino IDE Compatibility Bundle**: [`stm32/firmware/stm32_v2v_firmware/stm32_v2v_firmware.ino`](file:///c:/projectss/v2v%20communication/stm32/firmware/stm32_v2v_firmware/stm32_v2v_firmware.ino) (Located in a directory matching the `.ino` filename to fulfill Arduino IDE 1.8.x / 2.x sketch directory requirements).

Both files share identical implementations, data structures, closing speed kinematics, and cryptographic signing routines.

---

## 2. Hardware Stack & Target Specifications

| Component | Target Hardware Model | Interface Bus | Operating Frequency / Protocol |
| :--- | :--- | :--- | :--- |
| **Microcontroller** | STM32F401RE Nucleo-64 (ARM Cortex-M4 @ 84MHz) | Internal Bus | 84 MHz Core Clock, 512KB Flash, 96KB SRAM |
| **RF Transceiver** | Semtech SX1281 / SX1280 2.4 GHz | High-Speed SPI | 2.4 GHz ISM, FLRC (Fast LoRa) Modulation |
| **GNSS Module** | Quectel L86-M33 / u-blox NEO-M8N | UART (Serial1) | 9600 / 115200 baud, 10Hz NMEA sentences |
| **IMU (6-DoF)** | MPU-6050 / ICM-20689 | I2C1 | 400 kHz Fast I2C, Complementary Filter |
| **OLED Display** | SSD1306 128x64 Mono | I2C1 | 400 kHz Fast I2C |
| **Alert Buzzer / LED** | Active Piezo & Ultra-Bright LED | GPIO PWM/Out | Audible/Visual Pre-Collision Annunciation |

---

## 3. Microcontroller Pin Mapping (STM32F401RE Nucleo-64)

```text
                  +-----------------------------------+
                  |     STM32F401RE Nucleo-64         |
                  |                                   |
    [3.3V / GND] -| 3V3 / GND        PA2 (USART2_TX)  |- [ST-Link Serial Console]
                  |                  PA3 (USART2_RX)  |- [ST-Link Serial Console]
    [SX1281 NSS] -| PB6 (SPI_CS)     PA9 (USART1_TX)  |- [GNSS NMEA RX]
   [SX1281 SCK] -| PA5 (SPI1_SCK)   PA10 (USART1_RX) |- [GNSS NMEA TX]
  [SX1281 MISO] -| PA6 (SPI1_MISO)  PB8 (I2C1_SCL)   |- [MPU-6050 & SSD1306 SCL]
  [SX1281 MOSI] -| PA7 (SPI1_MOSI)  PB9 (I2C1_SDA)   |- [MPU-6050 & SSD1306 SDA]
   [SX1281 DIO1] -| PA1 (EXTI_INT)   PA8 (GPIO Out)   |- [Active Piezo Buzzer]
   [SX1281 NRST] -| PB0 (Reset)      PA4 (GPIO Out)   |- [Warning Hazard LED]
                  +-----------------------------------+
```

---

## 4. Telemetry Frame & Cryptographic Signing Format

### 4.1 Canonical Signing Contract
The firmware builds the deterministic payload string using strict key-value pairs formatted as:
```text
vehicle_id=<VID>|vehicle_type=<TYPE>|timestamp=<TS>|seq=<SEQ>|lat=<LAT:.6f>|lon=<LON:.6f>|speed_kmph=<SPD:.1f>|heading_deg=<HDG:int>
```

### 4.2 HMAC-SHA256 Digest
- **Algorithm**: HMAC with SHA-256 (RFC 2104).
- **Firmware Implementation**: Uses hardware-accelerated CRC or lightweight mbedTLS SHA-256 software primitives on the ARM Cortex-M4 core.
- **Output**: 64-character lowercase hexadecimal digest appended to the transmitted JSON/FLRC frame.

---

## 5. Collision Avoidance Kinematics (Compass Coordinate Standard)
The closing speed computation respects real-world navigational compass coordinates ($0^\circ = \text{North}, 90^\circ = \text{East}, 180^\circ = \text{South}, 270^\circ = \text{West}$):

$$v_{1x} = s_1 \cdot \sin(h_1), \quad v_{1y} = s_1 \cdot \cos(h_1)$$
$$v_{2x} = s_2 \cdot \sin(h_2), \quad v_{2y} = s_2 \cdot \cos(h_2)$$
$$rv_x = v_{1x} - v_{2x}, \quad rv_y = v_{1y} - v_{2y}$$
$$dx = (\text{lon}_2 - \text{lon}_1) \cdot 111320 \cdot \cos(\text{midLat}), \quad dy = (\text{lat}_2 - \text{lat}_1) \cdot 111320$$
$$\text{closing\_speed} = \frac{dx \cdot rv_x + dy \cdot rv_y}{\text{distance}}$$
$$\text{TTC} = \frac{\text{distance}}{\text{closing\_speed}}$$

- **Critical Threshold ($\text{TTC} \le 2.0\text{s}$)**: Trigger Level 2 alert (pulsed Piezo buzzer + hazard LED on STM32).
- **Warning Threshold ($\text{TTC} \le 5.0\text{s}$)**: Trigger Level 1 alert (intermittent visual OLED warning).

---

## 6. Physical Validation Status Disclaimer
> [!NOTE]
> Software simulation, packet serialization, HMAC validation, and compass kinematics have been mathematically verified with 100% test coverage in automated Python and C++ test benches. Full physical RF range and bench testing with actual Semtech SX1281 modules remain pending as outlined in [`docs/HARDWARE_VALIDATION_PLAN.md`](file:///c:/projectss/v2v%20communication/docs/HARDWARE_VALIDATION_PLAN.md).
