# Complete Hardware Bill of Materials (BOM) & Ordering Guide
## Internet-Independent V2V Communication & SCADA Safety Monitoring System
**Compliant with MoRTH AIS-230 Mandate Architecture | STM32 ARM Cortex-M Ecosystem**

---

## 1. Executive Hardware Architecture Overview

This project replaces the prototype ESP32 architecture with an industrial-grade **STM32 Microcontroller Ecosystem**. Because standard STM32 chips (such as the STM32F103C8T6 Blue Pill or STM32F411CEU6 Black Pill) do not contain built-in 2.4GHz Wi-Fi or Bluetooth, dedicated high-performance RF transceivers, orientation sensors, and power management modules are integrated.

### Key Architectural Shifts:
1. **Microcontroller**: Transitioned from ESP32 to **STM32 (ARM Cortex-M)** for deterministic real-time hardware execution, multi-channel hardware USART/SPI/I2C buses, and automotive-grade reliability.
2. **RF Wireless Mesh**: Replaced ESP-NOW with the **Semtech SX1280 / SX1281 2.4GHz RF Transceiver**. It operates on the worldwide license-free 2.4GHz ISM band with high-speed FLRC mode (up to 1.3 Mbps) and 2.4GHz LoRa modulation, delivering sub-3ms latency, multi-kilometer range, zero cellular dependency, and zero SIM card recurring costs.
3. **Orientation Sensing (New Feature)**: Added 9-DOF / 6-DOF Inertial Measurement Units (IMUs) via I2C to provide **Absolute Heading/Yaw (0–360°)** even when stationary, **Pitch (road gradient/slope)**, **Roll (rollover hazard/lateral tilt)**, and dynamic G-force collision detection.

---

## 2. Complete Master Bill of Materials (BOM)

To build and validate a **2-Vehicle + 1-Stationary Laptop Gateway (RSU)** setup, use the itemized ordering list below:

| # | Component Name | Recommended Model / Spec | Interface | Logic / VCC | Car 1 | Car 2 | Gateway Node | Total to Order | Ordering / Search Keyword |
|:---:|:---|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| **1** | **Microcontroller Board** | **STM32F103C8T6 (Blue Pill)** *(or STM32F411CEU6 Black Pill)* | SWD / USB | 3.3V (5V in) | 1 | 1 | 1 | **3 pcs** | `STM32F103C8T6 Blue Pill` or `STM32F411CEU6 Black Pill` |
| **2** | **2.4GHz RF Transceiver** | **Semtech SX1280 / SX1281** (EBYTE E28-2G4M27S or Waveshare) | SPI | 3.3V | 1 | 1 | 1 | **3 pcs** | `SX1280 2.4GHz LoRa module` / `E28-2G4M20S` |
| **3** | **2.4GHz RF Antennas** | 2.4GHz 3dBi–5dBi Dipole Rubber Duck + IPEX to SMA Cable | RF / SMA | Passive | 1 | 1 | 1 | **3 pcs** | `2.4GHz SMA Antenna IPEX U.FL pigtail` |
| **4** | **GNSS / GPS Receiver** | **U-blox NEO-M8N** (Preferred 10Hz) or **NEO-6M** | UART (9600) | 3.3V / 5V | 1 | 1 | - | **2 pcs** | `U-blox NEO-M8N GPS Module with Ceramic Antenna` |
| **5** | **Orientation Sensor (Primary)** | **Bosch BNO055 9-DOF Absolute Orientation Sensor** | I2C (0x28) | 3.3V / 5V | 1 | 1 | - | **2 pcs** | `BNO055 9-DOF absolute orientation breakout` |
| **5b** | **Orientation Sensor (Budget Alt)** | **InvenSense MPU-6050 6-DOF IMU** | I2C (0x68) | 3.3V / 5V | *(Optional)* | *(Optional)* | - | *(Alt)* | `MPU-6050 3-axis gyro accelerometer module` |
| **6** | **In-Cockpit Display** | **0.96" or 1.3" I2C OLED Display (SSD1306 / SH1106, 128x64)** | I2C (0x3C) | 3.3V / 5V | 1 | 1 | - | **2 pcs** | `0.96 inch I2C OLED display 128x64 blue/white` |
| **7** | **Acoustic Warning Buzzer** | **5V Active Piezo Buzzer Module** (High Decibel >85dB) | GPIO | 3.3V–5V | 1 | 1 | - | **2 pcs** | `5V active buzzer module for Arduino` |
| **8** | **Visual Status LEDs** | 5mm Diffused LEDs (Red, Yellow, Green) + 220Ω Resistors | GPIO | 3.3V | 1 set | 1 set | 1 set | **3 sets** | `5mm LED kit Red Green Yellow with resistors` |
| **9** | **AEB Simulation Relay** | **5V 1-Channel Relay Module (Optocoupler-Isolated)** | GPIO | 5V | 1 | 1 | - | **2 pcs** | `5V 1 channel relay module optocoupler` |
| **10** | **Automotive Buck Converter** | **LM2596 DC-DC Step-Down Regulator (12V/24V to 5V 3A)** | Terminal | 4V–40V in | 1 | 1 | - | **2 pcs** | `LM2596 DC-DC buck converter module with display` |
| **11** | **Dedicated 3.3V LDO Rail** | **AMS1117-3.3V Power Supply Module (800mA–1A)** | Pin Header | 5V to 3.3V | 1 | 1 | 1 | **3 pcs** | `AMS1117 3.3V power supply step down module` |
| **12** | **PC Gateway & Flashing Bridge** | **CP2102 or FT232RL USB-to-TTL UART Serial Converter** | USB / UART | 3.3V / 5V | - | - | 1 | **1 pc** | `CP2102 USB to TTL UART serial converter module` |
| **13** | **Field Battery Pack (Portable)** | 18650 3.7V 2500–3000mAh Li-ion Cells + 18650 Holder | DC | 3.7V | 1 | 1 | - | **2 sets** | `18650 3.7V battery with single cell holder` |
| **14** | **Li-ion Charger & Protection** | **TP4056 Type-C USB 5V 1A Li-ion Charger with DW01A** | USB-C | 5V in | 1 | 1 | - | **2 pcs** | `TP4056 Type-C with battery protection circuit` |
| **15** | **DC Boost Converter** | **MT3608 2A Step-Up Boost Module (3.7V to 5V)** | Terminal | 2V–24V in | 1 | 1 | - | **2 pcs** | `MT3608 DC-DC step up boost converter` |
| **16** | **Prototyping Breadboards** | Solderless 830-Point Breadboard (or FR4 Perfboard 7x9cm) | - | - | 1 | 1 | 1 | **3 pcs** | `830 point solderless breadboard` |
| **17** | **Dupont Jumper Wires** | 120 pcs Combo Pack (40 M-M, 40 M-F, 40 F-F, 20cm length) | - | - | - | - | - | **1 combo** | `Dupont wire jumper cables 40 pin M-M M-F F-F` |
| **18** | **Passives & Filter Kit** | 4.7kΩ Resistors (I2C pullups), 100µF & 0.1µF Caps, In-line Fuse | - | - | - | - | - | **1 kit** | `Electrolytic capacitor and 1/4W resistor kit` |

---

## 3. Sensor Deep Dive: Selecting the Orientation Sensor

Orientation sensing is essential for vehicular edge safety under **AIS-230** requirements:

| Comparison Metric | Bosch BNO055 (Recommended) | InvenSense MPU-6050 (Standard Budget) |
|:---|:---|:---|
| **Degrees of Freedom (DOF)** | **9-DOF** (3-axis Accel + 3-axis Gyro + 3-axis Magnetometer) | **6-DOF** (3-axis Accel + 3-axis Gyro) |
| **Internal Processor** | 32-bit ARM Cortex-M0 on-chip running BSX3.0 FusionLib | Digital Motion Processor (DMP) |
| **Absolute Heading (Yaw)** | **Yes (0–360° True North Compass)** with zero long-term drift | No magnetometer (Yaw drifts over time without GPS) |
| **Pitch & Roll Output** | Direct Euler angles & Quaternions via I2C registers | Derived via Complementary/Kalman filter or DMP |
| **STM32 Processing Load** | **Near Zero**: Direct register reads in 2 milliseconds | Requires floating point math or complex DMP library |
| **Automotive Relevance** | Perfect for stationary vehicle heading, tilt, and rollover | Suitable for relative turning rates and impact G-force |
| **Recommended Choice** | **Primary choice for production & final demo** | Cost-effective bench alternative |

---

## 4. Microcontroller Comparison: Blue Pill vs Black Pill

| Parameter | STM32F103C8T6 (Blue Pill) | STM32F411CEU6 (Black Pill) - Recommended Upgrade |
|:---|:---|:---|
| **Architecture** | ARM Cortex-M3 (32-bit) | ARM Cortex-M4 with Hardware FPU (Floating Point Unit) |
| **Clock Frequency** | 72 MHz | **100 MHz** |
| **Flash Memory** | 64 KB / 128 KB | **512 KB** (4x more space for libraries) |
| **SRAM** | 20 KB | **128 KB** (6.4x more RAM for packet queues & ML) |
| **USB Interface** | Micro-USB (often requires custom bootloader) | **Native USB Type-C** (plug & play direct flashing) |
| **Hardware Math** | Software-emulated floating point | **Hardware Single-Precision FPU** (blazing fast Haversine & Quaternions) |
| **Pin Compatibility** | 40-pin DIP layout | Nearly pin-compatible 40-pin DIP layout |

> **Recommendation**: While both boards work with the provided firmware, the **STM32F411CEU6 Black Pill** is strongly recommended because its hardware Floating Point Unit (FPU) executes 10Hz Haversine physics, Quaternion rotations, and HMAC-SHA256 math with zero latency.

---

## 5. Critical Electrical & Power Engineering Guidelines

### ⚠️ Warning: The 3.3V Power Rail Brownout Trap
* The onboard 3.3V regulator on STM32 Blue Pill boards (RT9193 or clone) is rated for only **100mA–150mA**.
* The **SX1281 2.4GHz RF module consumes up to 100mA–120mA during TX peak bursts**.
* When combined with the U-blox GPS (45mA) and BNO055 (15mA), powering everything from the Bluepill's 3.3V pin will cause **instantaneous voltage sag, STM32 brownout resets, and corrupted RF packets**.
* **Mandatory Fix**: Use the dedicated **AMS1117-3.3V module** (rated for 800mA–1000mA). Feed 5V to the AMS1117, and connect its 3.3V output to the SX1281 `3V3` pin and sensors. Connect all Ground (`GND`) wires together.
* Solder a **100µF electrolytic capacitor** and a **0.1µF ceramic capacitor** in parallel directly across the SX1281 power pins to absorb transmission current spikes.

### Automotive 12V Installation
* Cars and commercial vehicles experience alternator spikes up to 18V–24V.
* Always place an **in-line 2A fast-blow automotive blade fuse** on the 12V input wire before the LM2596 buck converter.
* Set the LM2596 multi-turn potentiometer with a multimeter to verify **5.0V output** before plugging in any microcontroller!

---

## 6. Complete STM32 Hardware Pinout & Wiring Map

### 6.1 Hardware Subsystem Interconnect Block Diagram
```mermaid
graph TD
    subgraph POWER["Power Conditioning Subsystem"]
        V_BAT["Vehicle 12V / 3.7V Battery"] --> FUSE["2A Fuse"]
        FUSE --> BUCK["LM2596 Buck Converter (12V -> 5V)"]
        BUCK --> LDO["AMS1117-3.3V LDO Module (800mA)"]
    end

    subgraph MCU["STM32 MCU (STM32F103C8T6 / STM32F411CEU6)"]
        CORE["ARM Cortex-M Processing Core"]
        UART2_P["USART2 (PA2/PA3)"]
        SPI1_P["SPI1 (PA4-PA7, PB0, PB1, PB10)"]
        I2C1_P["I2C1 (PB6/PB7)"]
        GPIO_P["GPIO / PWM (PB8, PB9, PA8, PA1)"]
        UART1_P["USART1 (PA9/PA10)"]
    end

    subgraph SENSORS["Geolocation & Orientation Sensors"]
        GPS["U-blox NEO-M8N GNSS Module"]
        IMU["Bosch BNO055 9-DOF / MPU6050 Sensor"]
    end

    subgraph RF["Wireless Telemetry Subsystem"]
        SX1281["Semtech SX1281 2.4GHz RF Module"]
        ANT["2.4GHz 3-5dBi Dipole Antenna"]
    end

    subgraph ACTUATION["Cockpit HMI & AEB Safety Actuation"]
        OLED["SSD1306 0.96 inch I2C OLED Display"]
        BUZZER["5V Active Piezo Buzzer"]
        RELAY["5V 1-Channel AEB Relay Module"]
        LEDS["Status & Collision Warning LEDs"]
    end

    subgraph PROGRAMMING["Programming & Host Interface"]
        CP2102["CP2102 USB-to-UART Module (Dual-Role: Flashing & Gateway)"]
    end

    GPS -->|NMEA Serial @ 9600 Baud| UART2_P
    IMU -->|Euler Angles & Accelerations (I2C)| I2C1_P
    I2C1_P -->|Shared I2C Bus (0x3C)| OLED
    SX1281 <-->|High-Speed SPI1 Bus| SPI1_P
    SX1281 <--> ANT
    GPIO_P -->|PB8 Digital Trigger| BUZZER
    GPIO_P -->|PB9 Solenoid Trigger| RELAY
    GPIO_P -->|PA8 / PA1 Drive| LEDS
    UART1_P <-->|BOOT0=1 Flashing & 115200 Baud Bridge| CP2102

    LDO -.->|"Dedicated 3.3V Rail"| SX1281
    LDO -.->|"Dedicated 3.3V Rail"| IMU
    LDO -.->|"3.3V System VCC"| CORE
    BUCK -.->|"5V DC Power"| GPS
    BUCK -.->|"5V DC Power"| BUZZER
    BUCK -.->|"5V DC Power"| RELAY
```

### 6.2 Breadboard & Component Pin Mapping
The pinout below is optimized for both **STM32F103C8T6 (Blue Pill)** and **STM32F411 (Black Pill)** without pin conflicts:

```
                          ┌───────────────────────────┐
                          │   STM32F103C8T6 / F411    │
                          │        MICROCONTROLLER    │
                          └─────────────┬─────────────┘
                                        │
           ┌────────────────────────────┼────────────────────────────┐
           │ (USART2)                   │ (SPI1)                     │ (I2C1)
           ▼                            ▼                            ▼
  ┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
  │ U-blox NEO-M8N  │          │ Semtech SX1281  │          │ Bosch BNO055 /  │
  │   GPS Receiver  │          │   2.4GHz RF     │          │    MPU-6050     │
  ├─────────────────┤          ├─────────────────┤          ├─────────────────┤
  │ TX  ──► PA3(RX) │          │ SCK  ──► PA5    │          │ SCL ──► PB6     │
  │ RX  ◄── PA2(TX) │          │ MISO ◄── PA6    │          │ SDA ──► PB7     │
  │ VCC ──► 5V/3.3V │          │ MOSI ──► PA7    │          │ VCC ──► 3.3V    │
  │ GND ──► GND     │          │ NSS  ──► PA4    │          │ GND ──► GND     │
  └─────────────────┘          │ DIO1 ──► PB0    │          └─────────────────┘
                               │ RST  ──► PB1    │                   │ (Shared I2C)
                               │ BUSY ──► PB10   │                   ▼
                               │ 3V3  ──► Ext3V3 │          ┌─────────────────┐
                               │ GND  ──► GND    │          │ SSD1306 OLED    │
                               └─────────────────┘          │  128x64 HUD     │
                                                            ├─────────────────┤
                                                            │ SCL ──► PB6     │
                                                            │ SDA ──► PB7     │
                                                            │ VCC ──► 3.3V    │
                                                            │ GND ──► GND     │
                                                            └─────────────────┘
```

### Pin Assignment Table:

| Subsystem | Peripheral Pin | STM32 Pin | Logic Level | Function / Role |
|:---|:---|:---:|:---:|:---|
| **SX1281 RF** | SCK | **PA5** | 3.3V | SPI1 Serial Clock |
| **SX1281 RF** | MISO | **PA6** | 3.3V | SPI1 Master In Slave Out |
| **SX1281 RF** | MOSI | **PA7** | 3.3V | SPI1 Master Out Slave In |
| **SX1281 RF** | NSS (CS) | **PA4** | 3.3V | SPI1 Chip Select |
| **SX1281 RF** | DIO1 | **PB0** | 3.3V | RF Packet RX/TX Interrupt |
| **SX1281 RF** | RST | **PB1** | 3.3V | Radio Hardware Reset |
| **SX1281 RF** | BUSY | **PB10** | 3.3V | RF Busy Indicator Flag |
| **NEO-M8N GPS** | TX | **PA3** | 3.3V | USART2 RX (NMEA Sentence In) |
| **NEO-M8N GPS** | RX | **PA2** | 3.3V | USART2 TX (Configuration Out) |
| **BNO055 / MPU** | SCL | **PB6** | 3.3V | I2C1 Clock (4.7kΩ pull-up to 3.3V) |
| **BNO055 / MPU** | SDA | **PB7** | 3.3V | I2C1 Data (4.7kΩ pull-up to 3.3V) |
| **SSD1306 OLED** | SCL / SDA | **PB6 / PB7** | 3.3V | Shared I2C1 Bus (Address 0x3C) |
| **Audio Alert** | Active Buzzer | **PB8** | 3.3V / 5V | PWM/GPIO Alarm Trigger (TTC < 3s) |
| **Braking Relay** | In1 (AEB Relay) | **PB9** | 5V (Opto) | Simulates Emergency Brake Solenoid |
| **Visual Threat** | Red Alert LED | **PA8** | 3.3V (220Ω) | Active Collision Threat Warning |
| **Visual Status** | Green LED | **PA1** | 3.3V (220Ω) | RF Network Heartbeat / GPS Locked |
| **Gateway Bridge**| TX / RX (To PC) | **PA9 / PA10** | 3.3V | USART1 connected to CP2102 USB Bridge (Flashing & Data) |
| **Boot Jumpers**  | BOOT0 / BOOT1 | **Onboard** | 3.3V / GND | Set BOOT0=1 to Flash via CP2102, BOOT0=0 to Run |

---

## 7. Fast Procurement Checklist (Ready to Copy-Paste for Orders)

Copy this list directly into procurement portals:

```text
[ ] 3x STM32F103C8T6 Blue Pill (or STM32F411CEU6 Black Pill) Development Boards
[ ] 1x CP2102 (or FT232RL) USB to TTL UART serial converter module (Flashing + Gateway)
[ ] 3x Semtech SX1280 or SX1281 2.4GHz RF Transceiver Modules (e.g., EBYTE E28-2G4M20S)
[ ] 3x 2.4GHz 3dBi/5dBi Rubber Duck Antennas with IPEX (U.FL) to SMA female pigtails
[ ] 2x U-blox NEO-M8N GPS Modules with active ceramic patch antennas (SMA/IPEX)
[ ] 2x Bosch BNO055 9-Axis Absolute Orientation Sensor Breakout Boards (or MPU-6050)
[ ] 2x 0.96 inch I2C OLED Displays (SSD1306, 128x64, 4-pin)
[ ] 2x 5V Active Piezo Buzzer Modules (3-pin or 2-pin with driver)
[ ] 2x 5V 1-Channel Relay Modules with optocoupler isolation
[ ] 2x LM2596 DC-DC Buck Converters (12V to 5V Step-Down, 3A rated)
[ ] 3x AMS1117-3.3V Linear Voltage Regulator Modules (800mA max)
[ ] 2x 18650 3.7V 2500mAh Li-ion Batteries + 2x Single-Cell 18650 Battery Holders
[ ] 2x TP4056 Type-C USB 5V 1A Li-ion Battery Charger Modules with DW01A protection
[ ] 2x MT3608 2A DC-DC Step-Up Boost Converter Modules
[ ] 3x 830-Point Solderless Breadboards (or 7x9cm double-sided prototyping perfboards)
[ ] 1x Dupont Jumper Wires Combo Pack (120 pcs: 40 M-M, 40 M-F, 40 F-F)
[ ] 1x Electrolytic & Ceramic Capacitor Assortment (100uF, 10uF, 0.1uF)
[ ] 1x Metal Film Resistor Kit (including 220Ω, 330Ω, 4.7kΩ, 10kΩ)
[ ] 2x 5mm Diffused LED Sets (Red, Yellow, Green)
[ ] 2x In-line 2A Automotive Blade Fuse Holders with 2A fuses (for car 12V safety)
```
