# V2V-SCADA Physical Hardware Validation Plan & Test Protocol

## Overview & Honesty Principles
This test plan specifies the exact physical testing procedures required to validate the V2V-SCADA edge hardware on the laboratory bench and test track.

In strict compliance with engineering integrity:
- **No hardware measurements are fabricated or simulated.**
- All `MEASURED RESULT` fields remain blank (`[PENDING PHYSICAL HARDWARE TEST]`) until physical bench equipment (oscilloscope, spectrum analyzer, serial logger, GPS simulator) is connected to actual silicon.
- All tests are marked as `PENDING PHYSICAL TEST`.

---

## Physical Hardware Validation Protocol Matrix

### Test 1: STM32 Microcontroller Boot & Clock Initialization
- **METHOD**: Connect STM32F103C8T6 node to 3.3V power bench supply with FTDI / ST-Link probe. Monitor 8 MHz HSE crystal oscillation and 72 MHz PLL lock on oscilloscope. Observe green status LED (`PA1`) boot sequence and 115200 baud USB UART banner.
- **EXPECTED RESULT**: Node boots cleanly within $< 200\text{ ms}$; serial banner `"STM32 V2V / AIS-230 Communication Node Starting"` emitted at 115200 baud; status LED transitions to solid ON.
- **MEASURED RESULT**: ________________________________________
- **STATUS**: **PENDING PHYSICAL TEST**

---

### Test 2: GNSS Signal Acquisition & Cold Start Time-To-First-Fix (TTFF)
- **METHOD**: Power node outdoors with clear line-of-sight to sky. Monitor NMEA sentence stream on USART2 (`PA3/RX`). Measure elapsed time from cold boot to first valid fix sentence (`$GPRMC` or `$GPGGA` fix status `A`).
- **EXPECTED RESULT**: Valid 2D/3D fix obtained within $< 45\text{ seconds}$ from cold start; coordinates match physical survey benchmark within $\pm 2.5\text{ meters}$.
- **MEASURED RESULT**: ________________________________________
- **STATUS**: **PENDING PHYSICAL TEST**

---

### Test 3: GNSS Sustained Update Rate & Jitter
- **METHOD**: Configure GNSS module for 10 Hz binary/NMEA output. Log sentence arrival timestamps via logic analyzer on `PA3/RX` over a 10-minute continuous run.
- **EXPECTED RESULT**: Sustained sentence delivery at $10.0\text{ Hz} \pm 5\%$ with inter-arrival delta of $100\text{ ms} \pm 10\text{ ms}$; zero dropped NMEA frames.
- **MEASURED RESULT**: ________________________________________
- **STATUS**: **PENDING PHYSICAL TEST**

---

### Test 4: MPU-6050 I2C Register Read & Accelerometer Calibration
- **METHOD**: Query MPU-6050 `WHO_AM_I` register (`0x75`) at 400 kHz Fast-Mode I2C. Tilt node through calibrated $\pm 15^\circ$ angles along pitch and roll axes. Log sensor fusion angle calculations.
- **EXPECTED RESULT**: `WHO_AM_I` returns `0x68`; static level position reports pitch $0.0^\circ \pm 1.0^\circ$ and roll $0.0^\circ \pm 1.0^\circ$; dynamic response follows physical tilt without I2C bus lockup.
- **MEASURED RESULT**: ________________________________________
- **STATUS**: **PENDING PHYSICAL TEST**

---

### Test 5: Semtech SX1281 2.4 GHz Transceiver Initialization & SPI Integrity
- **METHOD**: Inspect high-speed SPI1 bus transactions (`SCK`, `MISO`, `MOSI`, `NSS`) on digital storage oscilloscope during `radio.begin(2400.0, 812.5, 7, 5, 12, 10)`. Verify register readback from SX1281 silicon.
- **EXPECTED RESULT**: `radio.begin()` returns `RADIOLIB_ERR_NONE` (`0`); SPI signals show clean 10 MHz edges without ringing; SX1281 transitions into continuous RX listening mode.
- **MEASURED RESULT**: ________________________________________
- **STATUS**: **PENDING PHYSICAL TEST**

---

### Test 6: Over-the-Air Packet Integrity & CRC Check
- **METHOD**: Deploy two physical nodes (Node A transmitting at 10 Hz, Node B receiving). Log received packet payloads on Node B serial port. Compare raw payload strings against transmitted packets.
- **EXPECTED RESULT**: 100% payload integrity on received frames; hardware CRC confirms zero bit flips in received JSON payloads over a 1,000-packet bench burst.
- **MEASURED RESULT**: ________________________________________
- **STATUS**: **PENDING PHYSICAL TEST**

---

### Test 7: Hardware-Level HMAC-SHA256 Verification & Rejection
- **METHOD**: Transmit signed valid packets from Node A. In Node B firmware, observe verification pass rate. Then inject a single modified byte into transmitted latitude string from an unauthorized RF emitter.
- **EXPECTED RESULT**: Legitimate packets verify successfully with `generateHMACSignature`; tampered packets trigger `[SECURITY WARNING] Dropped spoofed RF packet` and are discarded without AEB relay activation.
- **MEASURED RESULT**: ________________________________________
- **STATUS**: **PENDING PHYSICAL TEST**

---

### Test 8: Packet Error Rate (PER) vs Distance
- **METHOD**: Fix Node B (Gateway) at stationary base station. Move Node A along straight line-of-sight roadway in 100-meter increments up to 1,500 meters. Count received packets vs transmitted sequence numbers per position.
- **EXPECTED RESULT**: Packet delivery $> 99\%$ up to $500\text{ m}$; packet delivery $> 90\%$ up to $1000\text{ m}$ line-of-sight.
- **MEASURED RESULT**: ________________________________________
- **STATUS**: **PENDING PHYSICAL TEST**

---

### Test 9: Receiver Signal Strength Indicator (RSSI) & SNR Profiling
- **METHOD**: Query SX1281 `radio.getRSSI()` and `radio.getSNR()` on received packets at 10m, 50m, 200m, and 500m separations.
- **EXPECTED RESULT**: RSSI monotonically attenuates with distance in accordance with log-distance path loss model: $\sim -45\text{ dBm}$ at 10m, $\sim -75\text{ dBm}$ at 100m, $\sim -95\text{ dBm}$ at 500m.
- **MEASURED RESULT**: ________________________________________
- **STATUS**: **PENDING PHYSICAL TEST**

---

### Test 10: Maximum Usable RF Line-of-Sight Range
- **METHOD**: Increase separation along open test corridor until packet reception drops below $50\%$. Record GPS coordinates and calculate geodesic distance.
- **EXPECTED RESULT**: Usable communication range achieves between $1000\text{ m}$ and $2000\text{ m}$ with 10 dBm transmit power and 2.4 GHz dipole antennas.
- **MEASURED RESULT**: ________________________________________
- **STATUS**: **PENDING PHYSICAL TEST**

---

### Test 11: End-to-End Over-the-Air to SCADA Display Latency
- **METHOD**: Toggle GPIO pin on Node A immediately before RF transmission. Toggle GPIO pin on PC USB Gateway upon receiving packet. Measure delta on two-channel oscilloscope.
- **EXPECTED RESULT**: Over-the-air packet airtime $< 3.0\text{ ms}$; total edge-to-USB serial latency $< 8.0\text{ ms}$.
- **MEASURED RESULT**: ________________________________________
- **STATUS**: **PENDING PHYSICAL TEST**

---

### Test 12: Collision Warning (TTC) Audible & Visual Actuation
- **METHOD**: Broadcast telemetry simulating approaching peer vehicle ($V_{\text{close}} = 20\text{ m/s}$, Distance $= 50\text{ m}$, TTC $= 2.5\text{ s}$). Observe Node buzzer (`PB8`) and Alert LED (`PA8`).
- **EXPECTED RESULT**: Node transitions into Threat Level 2 / 3; buzzer sounds rapid warning cadence; alert LED illuminates continuously within $< 20\text{ ms}$ of packet ingest.
- **MEASURED RESULT**: ________________________________________
- **STATUS**: **PENDING PHYSICAL TEST**

---

### Test 13: Emergency Vehicle Preemption Siren Cadence
- **METHOD**: Broadcast telemetry from peer node with `emergency_status = 1` and `distance < 200m`.
- **EXPECTED RESULT**: Node immediately triggers Threat Level 4; buzzer produces alternating siren frequency; OLED HUD displays `"EMERGENCY YIELD"`.
- **MEASURED RESULT**: ________________________________________
- **STATUS**: **PENDING PHYSICAL TEST**

---

### Test 14: Geofence Workzone Breach Trigger
- **METHOD**: Simulate coordinates entering defined restricted workzone polygon.
- **EXPECTED RESULT**: Threat level 3 alert triggered; SCADA dashboard logs geofence violation and highlights vehicle marker in red.
- **MEASURED RESULT**: ________________________________________
- **STATUS**: **PENDING PHYSICAL TEST**

---

### Test 15: AEB Demonstration Relay Fail-Safe State Verification
- **METHOD**: Monitor voltage across relay coil driver pin (`PIN_AEB_RELAY`, `PB9`) with oscilloscope during:
  1. Microcontroller boot and reset
  2. Loss of RF signal (>2.5 seconds timeout)
  3. Receipt of malformed or invalidly signed packet
  4. Deliberate disconnection of GNSS or IMU sensors
- **EXPECTED RESULT**: Driver pin remains strictly $0.0\text{ V}$ (`LOW`) across all 4 failure modes. Relay coil never energizes unless verified Threat Level 3 (TTC $\le 2.5\text{ s}$) is actively maintained.
- **MEASURED RESULT**: ________________________________________
- **STATUS**: **PENDING PHYSICAL TEST**

---

### Test 16: DC Bus Power Supply Stability & Voltage Ripple
- **METHOD**: Power node via 12V automotive battery through DC-DC buck converter (LM2596 / MP1584 down to 3.3V). Measure 3.3V supply rail ripple during maximum RF transmit burst (10 dBm) on AC-coupled oscilloscope.
- **EXPECTED RESULT**: 3.3V rail voltage ripple remains $< 50\text{ mV}_{\text{p-p}}$; zero microcontroller resets or brownout events occur during RF TX transients.
- **MEASURED RESULT**: ________________________________________
- **STATUS**: **PENDING PHYSICAL TEST**

---

### Test 17: Automatic Recovery After RF Communication Loss
- **METHOD**: Place RF shielding box over Node A for 30 seconds to simulate complete tunnel RF dropout. Remove shielding and log reconnection time.
- **EXPECTED RESULT**: Node B auto-clears hazard status within 2.5 seconds of dropout; immediately upon shielding removal, packet ingest resumes without manual reboot or buffer stalls.
- **MEASURED RESULT**: ________________________________________
- **STATUS**: **PENDING PHYSICAL TEST**
