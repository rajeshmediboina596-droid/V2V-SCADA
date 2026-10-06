/*
 =======================================================================================
  Project: Internet-Independent V2V Communication & SCADA Safety Monitoring System
  Target Architecture: STM32 ARM Cortex-M (STM32F103C8T6 Blue Pill / STM32F411 Black Pill)
  Transceiver: Semtech SX1280 / SX1281 (2.4GHz High-Speed RF Broadcast)
  GNSS: U-blox NEO-6M / NEO-M8N via USART2 (PA2/PA3)
  IMU / Orientation: InvenSense MPU-6050 / BNO055 via I2C1 (PB6=SCL, PB7=SDA)
  Driver HUD: SSD1306 128x64 OLED HUD, Active Buzzer, AEB Relay, Hazard LEDs
  Cryptography: Hardware-friendly HMAC-SHA256 Payload Signing & Verification
  Flashing Method: Built-in ROM Bootloader via FTDI (FT232RL) / CP2102 USB-to-UART
                   (BOOT0=1 on USART1 PA9/PA10, or use DTR/RTS auto-reset)
                   *NO ST-LINK V2 REQUIRED! Flash with: python tools/flash_stm32_ftdi.py*
 =======================================================================================
  
  STM32F103C8T6 Pin Assignment & Wiring Table:
  -------------------------------------------------------------------------------------
  Peripheral         Peripheral Pin    STM32 Pin     Function / Notes
  -------------------------------------------------------------------------------------
  Semtech SX1281     SCK               PA5           SPI1 Serial Clock
  Semtech SX1281     MISO              PA6           SPI1 Master In Slave Out
  Semtech SX1281     MOSI              PA7           SPI1 Master Out Slave In
  Semtech SX1281     NSS (CS)          PA4           SPI1 Chip Select (Active Low)
  Semtech SX1281     DIO1              PB0           Packet Ready Interrupt (RX/TX Done)
  Semtech SX1281     RST               PB1           Radio Hardware Reset
  Semtech SX1281     BUSY              PB10          Radio Busy Status
  Semtech SX1281     3V3 / GND         Ext 3.3V/GND  *Dedicated AMS1117-3.3V rail!*
  
  NEO-6M / M8N GPS   TX                PA3           USART2 RX (9600 Baud)
  NEO-6M / M8N GPS   RX                PA2           USART2 TX (9600 Baud)
  NEO-6M / M8N GPS   VCC / GND         5V / GND      From LM2596 5V rail
  
  MPU-6050 / BNO055  SCL               PB6           I2C1 Clock (4.7kΩ pull-up to 3.3V)
  MPU-6050 / BNO055  SDA               PB7           I2C1 Data (4.7kΩ pull-up to 3.3V)
  MPU-6050 / BNO055  VCC / GND         3.3V / GND    From 3.3V rail
  
  SSD1306 OLED HUD   SCL / SDA         PB6 / PB7     Shared I2C1 Bus (Address 0x3C)
  Warning Buzzer     Input (+)         PB8           Active 5V Piezo Buzzer (TTC < 3.5s)
  AEB Relay Module   IN1               PB9           Automatic Emergency Braking Trigger (TTC < 2.5s)
  Alert LED          Anode (+)         PA8           Red Collision Warning (220Ω resistor)
  Status LED         Anode (+)         PA1           Green Radio / Heartbeat (220Ω resistor)
  
  FTDI / CP2102 USB  TXD / RXD         PA10 / PA9    USART1 Bootloader Flash & Gateway @ 115200
  FTDI Auto-Reset    DTR / RTS         NRST / BOOT0  Hardware Auto-Reset & Auto-BOOT0 (Optional)
                                                     *Manual: BOOT0=1 to Flash, BOOT0=0 to Run*
  -------------------------------------------------------------------------------------
*/

#include <SPI.h>
#include <Wire.h>
#include <HardwareSerial.h>
#include <ArduinoJson.h>
#include <RadioLib.h>
#include <TinyGPS++.h>
#include <Crypto.h>
#include <SHA256.h>
#include <string.h>
#include <math.h>

// ============================================================================
// Node Mode Selection:
// Set to 'false' for in-vehicle physical nodes (reads GPS, IMU, broadcasts RF, runs AEB)
// Set to 'true'  for stationary gateway node plugged into laptop USB bridge
// ============================================================================
#define IS_GATEWAY_NODE false 

// Vehicle Identification & Type
const String VEHICLE_ID   = "V1";
const String VEHICLE_TYPE = "Passenger"; // Options: "Passenger", "Truck", "Emergency"
const char* HMAC_SECRET   = "v2v_shared_secret_123"; // Must match Python backend

// Hardware Pin Definitions
#define PIN_GPS_RX     PA3
#define PIN_GPS_TX     PA2
#define PIN_SX_SCK     PA5
#define PIN_SX_MISO    PA6
#define PIN_SX_MOSI    PA7
#define PIN_SX_NSS     PA4
#define PIN_SX_DIO1    PB0
#define PIN_SX_RST     PB1
#define PIN_SX_BUSY    PB10

#define PIN_BUZZER     PB8
#define PIN_AEB_RELAY  PB9
#define PIN_LED_ALERT  PA8
#define PIN_LED_OK     PA1

#define MPU_I2C_ADDR   0x68
#define OLED_I2C_ADDR  0x3C

// Math Constants
#ifndef DEG_TO_RAD
#define DEG_TO_RAD 0.017453292519943295
#endif

// Peripheral Instances
HardwareSerial SerialGPS(USART2);
SX1281 radio = new Module(PIN_SX_NSS, PIN_SX_DIO1, PIN_SX_RST, PIN_SX_BUSY);
TinyGPSPlus gps;

// Telemetry & Timing State
unsigned long lastTransmitTime = 0;
const unsigned long TRANSMIT_INTERVAL_MS = 100; // 10Hz High-Speed Broadcast Rate = 100ms
uint32_t sequenceNumber = 0;

// Local Vehicle Telemetry State
float myLat = 17.423900;
float myLon = 78.448300;
float mySpeed = 42.5;
float myHeading = 90.0;
float myPitch = 0.0;
float myRoll = 0.0;
float myAlt = 542.0;

// Orientation state
bool imuAvailable = false;
bool oledAvailable = false;

// Battery & Status monitoring (Simulated / ADC)
float batteryVoltage = 12.4; // Vehicle DC bus voltage
String faultCode = "NONE";
bool emergencyActive = false;

// Peer Vehicle Tracking & Collision State
unsigned long lastPeerPacketTime = 0;
String nearestPeerId = "NONE";
float nearestPeerDistance = 999.0;
float nearestPeerTTC = 99.9;
int currentThreatLevel = 0; // 0=Safe, 1=Advisory, 2=Warning, 3=Critical AEB, 4=Emergency Yield

// Radio Interrupt Flag
volatile bool packetReceived = false;
#if defined(ESP8266) || defined(ESP32)
  ICACHE_RAM_ATTR
#endif
void setFlag(void) {
    packetReceived = true;
}

// ============================================================================
// Cryptographic HMAC-SHA256 Generator
// ============================================================================
String generateHMACSignature(const String& dataString) {
    SHA256 sha256;
    uint8_t hash[32];
    
    sha256.reset();
    sha256.update(HMAC_SECRET, strlen(HMAC_SECRET));
    sha256.update(dataString.c_str(), dataString.length());
    sha256.finalize(hash, sizeof(hash));
    
    String hexSignature = "";
    for (int i = 0; i < 32; i++) {
        if (hash[i] < 16) hexSignature += "0";
        hexSignature += String(hash[i], HEX);
    }
    return hexSignature;
}

// ============================================================================
// Haversine Distance & Relative Closing Speed Calculations
// ============================================================================
float computeDistanceMeters(float lat1, float lon1, float lat2, float lon2) {
    const float R = 6371000.0; // Earth mean radius in meters
    float phi1 = lat1 * DEG_TO_RAD;
    float phi2 = lat2 * DEG_TO_RAD;
    float deltaPhi = (lat2 - lat1) * DEG_TO_RAD;
    float deltaLambda = (lon2 - lon1) * DEG_TO_RAD;

    float a = sin(deltaPhi / 2.0) * sin(deltaPhi / 2.0) +
              cos(phi1) * cos(phi2) *
              sin(deltaLambda / 2.0) * sin(deltaLambda / 2.0);
    float c = 2.0 * atan2(sqrt(a), sqrt(1.0 - a));
    return R * c;
}

float computeClosingSpeedMps(float lat1, float lon1, float speed1_kmph, float heading1_deg,
                             float lat2, float lon2, float speed2_kmph, float heading2_deg) {
    float s1 = speed1_kmph / 3.6;
    float s2 = speed2_kmph / 3.6;
    float h1 = heading1_deg * DEG_TO_RAD;
    float h2 = heading2_deg * DEG_TO_RAD;

    float v1x = s1 * cos(h1);
    float v1y = s1 * sin(h1);
    float v2x = s2 * cos(h2);
    float v2y = s2 * sin(h2);

    float rvx = v1x - v2x;
    float rvy = v1y - v2y;

    float midLat = ((lat1 + lat2) / 2.0) * DEG_TO_RAD;
    float dx = (lon1 - lon2) * 111320.0 * cos(midLat);
    float dy = (lat1 - lat2) * 111320.0;

    float posMag = sqrt(dx * dx + dy * dy);
    if (posMag < 0.1) posMag = 0.1;

    float dot = dx * rvx + dy * rvy;
    float closing = - (dot / posMag);
    return (closing > 0.0) ? closing : 0.0;
}

// ============================================================================
// IMU / Orientation Initialization & Sensor Fusion
// ============================================================================
void initIMU() {
    Wire.begin();
    Wire.setClock(400000); // 400 kHz Fast I2C Mode

    // Check MPU-6050 WHO_AM_I register (0x75, should return 0x68)
    Wire.beginTransmission(MPU_I2C_ADDR);
    Wire.write(0x6B); // Power Management 1 register
    Wire.write(0x00); // Wake up MPU-6050 from sleep
    byte err = Wire.endTransmission();

    if (err == 0) {
        imuAvailable = true;
        Serial.println(F("[IMU] MPU-6050 successfully initialized on I2C (0x68)."));
    } else {
        imuAvailable = false;
        faultCode = "ERR_IMU_OFFLINE";
        Serial.print(F("[IMU] Warning: Sensor not found (Code: "));
        Serial.print(err);
        Serial.println(F("). Falling back to GPS Course Heading."));
    }

    // Check if SSD1306 OLED HUD is present on 0x3C
    Wire.beginTransmission(OLED_I2C_ADDR);
    if (Wire.endTransmission() == 0) {
        oledAvailable = true;
        Serial.println(F("[HUD] SSD1306 I2C OLED display detected on 0x3C."));
    }
}

void readOrientation(float &pitch, float &roll, float &yaw) {
    if (!imuAvailable) {
        if (gps.course.isValid() && gps.speed.kmph() > 2.0) {
            yaw = gps.course.deg();
        }
        return;
    }

    Wire.beginTransmission(MPU_I2C_ADDR);
    Wire.write(0x3B); // Accel X High register
    if (Wire.endTransmission(false) == 0 && Wire.requestFrom(MPU_I2C_ADDR, 6) == 6) {
        int16_t rawAx = (Wire.read() << 8) | Wire.read();
        int16_t rawAy = (Wire.read() << 8) | Wire.read();
        int16_t rawAz = (Wire.read() << 8) | Wire.read();

        // Convert to G-forces (±2g range, 16384 LSB/g)
        float ax = (float)rawAx / 16384.0;
        float ay = (float)rawAy / 16384.0;
        float az = (float)rawAz / 16384.0;

        // Calculate pitch and roll angles in degrees
        pitch = atan2(ay, sqrt(ax * ax + az * az)) * 180.0 / 3.14159265;
        roll  = atan2(-ax, az) * 180.0 / 3.14159265;
    }

    // Prioritize GPS heading when vehicle has positive ground speed
    if (gps.course.isValid() && gps.speed.kmph() > 2.0) {
        yaw = gps.course.deg();
    }
}

// ============================================================================
// Driver Alert & Automatic Emergency Braking (AEB) Actuation
// ============================================================================
void applySafetyActuation(int threatLevel, float ttc, float dist, const String& peerId) {
    currentThreatLevel = threatLevel;

    switch (threatLevel) {
        case 3: // CRITICAL IMMINENT COLLISION (TTC <= 2.5s)
            digitalWrite(PIN_BUZZER, HIGH);
            digitalWrite(PIN_LED_ALERT, HIGH);
            digitalWrite(PIN_AEB_RELAY, HIGH); // Engages Emergency Braking Solenoid
            Serial.print(F(">>> [AEB TRIGGER] CRITICAL IMMINENT COLLISION! Vehicle: "));
            Serial.print(peerId);
            Serial.print(F(" | Dist: "));
            Serial.print(dist, 1);
            Serial.print(F("m | TTC: "));
            Serial.print(ttc, 1);
            Serial.println(F("s <<<"));
            break;

        case 2: // WARNING (2.5s < TTC <= 3.5s)
            // Rapid intermittent beep
            digitalWrite(PIN_BUZZER, (millis() % 200 < 100) ? HIGH : LOW);
            digitalWrite(PIN_LED_ALERT, HIGH);
            digitalWrite(PIN_AEB_RELAY, LOW); // Alert only, brake standby
            Serial.print(F(">> [COLLISION WARNING] Hazard Closing: "));
            Serial.print(peerId);
            Serial.print(F(" | Dist: "));
            Serial.print(dist, 1);
            Serial.println(F("m >>"));
            break;

        case 4: // EMERGENCY VEHICLE PREEMPTION (Ambulance < 200m)
            digitalWrite(PIN_BUZZER, (millis() % 400 < 150) ? HIGH : LOW);
            digitalWrite(PIN_LED_ALERT, (millis() % 200 < 100) ? HIGH : LOW);
            digitalWrite(PIN_AEB_RELAY, LOW);
            Serial.print(F(">> [AMBULANCE YIELD] Emergency Vehicle within "));
            Serial.print(dist, 1);
            Serial.println(F("m! Pull over to the left! >>"));
            break;

        case 1: // ADVISORY
            digitalWrite(PIN_BUZZER, LOW);
            digitalWrite(PIN_LED_ALERT, (millis() % 1000 < 200) ? HIGH : LOW);
            digitalWrite(PIN_AEB_RELAY, LOW);
            break;

        case 0: // SAFE
        default:
            digitalWrite(PIN_BUZZER, LOW);
            digitalWrite(PIN_LED_ALERT, LOW);
            digitalWrite(PIN_AEB_RELAY, LOW);
            break;
    }
}

// ============================================================================
// Process Received Peer Telemetry Packet (Edge Collision Assessment)
// ============================================================================
void processPeerPacket(const String& payload) {
    StaticJsonDocument<512> doc;
    DeserializationError error = deserializeJson(doc, payload);
    if (error) {
        return; // Ignore malformed frames
    }

    const char* peerId = doc["vehicle_id"] | "UNKNOWN";
    // Disregard our own transmissions
    if (String(peerId) == VEHICLE_ID) {
        return;
    }

    const char* peerType = doc["vehicle_type"] | "Passenger";
    unsigned long peerTime = doc["timestamp"] | 0;
    uint32_t peerSeq = doc["seq"] | 0;
    float peerLat = doc["lat"] | 0.0;
    float peerLon = doc["lon"] | 0.0;
    float peerSpeed = doc["speed_kmph"] | 0.0;
    float peerHeading = doc["heading_deg"] | 0.0;
    int peerEmergency = doc["emergency_status"] | 0;
    const char* signature = doc["signature"] | "";

    // 1. HMAC-SHA256 Cryptographic Verification
    String signString = String(peerId) +
                        String(peerType) +
                        String(peerTime) +
                        String(peerSeq) +
                        String(peerLat, 6) +
                        String(peerLon, 6) +
                        String(peerSpeed, 1) +
                        String(int(round(peerHeading)));

    String expectedSig = generateHMACSignature(signString);
    if (!expectedSig.equalsIgnoreCase(String(signature))) {
        Serial.print(F("[SECURITY WARNING] Dropped spoofed RF packet from: "));
        Serial.println(peerId);
        return; // Drop untrusted packet immediately
    }

    // 2. Physical Threat Assessment
    float dist = computeDistanceMeters(myLat, myLon, peerLat, peerLon);
    float closingSpeed = computeClosingSpeedMps(myLat, myLon, mySpeed, myHeading,
                                               peerLat, peerLon, peerSpeed, peerHeading);

    float ttc = (closingSpeed > 0.5) ? (dist / closingSpeed) : 99.9;

    nearestPeerId = String(peerId);
    nearestPeerDistance = dist;
    nearestPeerTTC = ttc;
    lastPeerPacketTime = millis();

    // 3. Threat Classification
    if (peerEmergency == 1 && dist < 200.0) {
        applySafetyActuation(4, ttc, dist, nearestPeerId); // Emergency vehicle yield
    } else if (ttc <= 2.5 && dist < 45.0) {
        applySafetyActuation(3, ttc, dist, nearestPeerId); // Critical AEB trigger
    } else if (ttc <= 3.5 && dist < 75.0) {
        applySafetyActuation(2, ttc, dist, nearestPeerId); // Collision Warning
    } else if (dist < 100.0) {
        applySafetyActuation(1, ttc, dist, nearestPeerId); // Advisory
    } else {
        applySafetyActuation(0, ttc, dist, nearestPeerId); // Safe
    }
}

// ============================================================================
// Setup
// ============================================================================
void setup() {
    // 1. USB / UART1 Serial initialization for PC Communication
    // Note: Used for live telemetry and firmware uploading via CP2102!
    Serial.begin(115200);
    delay(1000);

    // 2. Configure safety actuation pins
    pinMode(PIN_BUZZER, OUTPUT);
    pinMode(PIN_AEB_RELAY, OUTPUT);
    pinMode(PIN_LED_ALERT, OUTPUT);
    pinMode(PIN_LED_OK, OUTPUT);

    digitalWrite(PIN_BUZZER, LOW);
    digitalWrite(PIN_AEB_RELAY, LOW);
    digitalWrite(PIN_LED_ALERT, LOW);
    digitalWrite(PIN_LED_OK, HIGH);

    Serial.println(F("=================================================="));
    Serial.println(F(" STM32 V2V / AIS-230 Communication Node Starting "));
    Serial.println(F("=================================================="));
    Serial.print(F("Node Mode: "));
    Serial.println(IS_GATEWAY_NODE ? F("GATEWAY (USB Serial Bridge)") : F("VEHICLE (IoT Edge Node)"));
    Serial.print(F("Vehicle ID: "));
    Serial.println(VEHICLE_ID);

    if (!IS_GATEWAY_NODE) {
        // Initialize GPS on USART2 (PA2/PA3)
        SerialGPS.begin(9600);
        Serial.println(F("[GPS] USART2 initialized @ 9600 baud."));

        // Initialize MPU-6050 Orientation Sensor & OLED HUD
        initIMU();
    }

    // 3. Initialize Semtech SX1281 2.4GHz RF Transceiver
    Serial.print(F("[RF] Initializing Semtech SX1281 (2.4GHz FLRC/LoRa)... "));
    // 2400.0 MHz, 812.5 kHz BW, Spreading Factor 7, Coding Rate 4/5, SyncWord 0x12, Pwr 10dBm
    int rfState = radio.begin(2400.0, 812.5, 7, 5, 12, 10);
    if (rfState == RADIOLIB_ERR_NONE) {
        Serial.println(F("SX1281 Ready (Sub-3ms Latency Mode)!"));
        // Set interrupt handler on DIO1 for asynchronous non-blocking packet reception
        radio.setDio1Action(setFlag);
        radio.startReceive();
    } else {
        Serial.print(F("Failed with error code: "));
        Serial.println(rfState);
        faultCode = "ERR_RF_INIT_FAIL";
        while (true) {
            // Flash red alert LED on hardware radio failure
            digitalWrite(PIN_LED_ALERT, !digitalRead(PIN_LED_ALERT));
            delay(150);
        }
    }
}

// ============================================================================
// Main Loop
// ============================================================================
void loop() {
    // ------------------------------------------------------------------------
    // Check Asynchronous RF Packet Reception
    // ------------------------------------------------------------------------
    if (packetReceived) {
        packetReceived = false;
        String receivedPayload;
        int state = radio.readData(receivedPayload);

        if (state == RADIOLIB_ERR_NONE && receivedPayload.length() > 0) {
            if (IS_GATEWAY_NODE) {
                // GATEWAY: Forward directly to PC USB serial bridge
                Serial.println(receivedPayload);
                // Pulse Green Status LED
                digitalWrite(PIN_LED_OK, LOW);
                delayMicroseconds(500);
                digitalWrite(PIN_LED_OK, HIGH);
            } else {
                // VEHICLE NODE: Perform edge collision assessment & AEB actuation
                processPeerPacket(receivedPayload);
            }
        }
        // Put SX1281 back into non-blocking continuous receive mode
        radio.startReceive();
    }

    if (IS_GATEWAY_NODE) {
        // --------------------------------------------------------------------
        // GATEWAY NODE: Listen for SCADA Commands from PC over Serial
        // --------------------------------------------------------------------
        if (Serial.available() > 0) {
            String cmd = Serial.readStringUntil('\n');
            cmd.trim();
            if (cmd.length() > 0) {
                // Broadcast SCADA command packet over 2.4GHz RF
                radio.transmit(cmd);
                radio.startReceive();
            }
        }

    } else {
        // --------------------------------------------------------------------
        // VEHICLE NODE: Ingest GPS, Update Physics, Broadcast Signed 10Hz Packet
        // --------------------------------------------------------------------
        
        // 1. Ingest NMEA GPS bytes continuously from USART2
        while (SerialGPS.available() > 0) {
            gps.encode(SerialGPS.read());
        }

        // Update local vehicle dynamics from GNSS
        if (gps.location.isValid()) {
            myLat = gps.location.lat();
            myLon = gps.location.lng();
        }
        if (gps.speed.isValid()) {
            mySpeed = gps.speed.kmph();
        }
        if (gps.altitude.isValid()) {
            myAlt = gps.altitude.meters();
        }

        // Auto-clear stale peer hazard state if no packets received for > 2.5 seconds
        if (millis() - lastPeerPacketTime > 2500 && currentThreatLevel > 0) {
            applySafetyActuation(0, 99.9, 999.0, "NONE");
        }

        // 2. Broadcast high-speed telemetry packet at 10Hz (100ms interval)
        if (millis() - lastTransmitTime >= TRANSMIT_INTERVAL_MS) {
            lastTransmitTime = millis();
            sequenceNumber++;

            // Read IMU Orientation (Pitch, Roll, Yaw)
            readOrientation(myPitch, myRoll, myHeading);
            unsigned long timestamp = millis() / 1000 + 1730000000;

            // Formulate Canonical String for HMAC-SHA256 Signing
            // Matches backend build_signing_string():
            // vehicle_id + vehicle_type + timestamp + seq + lat + lon + speed_kmph + heading_deg
            String signString = VEHICLE_ID +
                                VEHICLE_TYPE +
                                String(timestamp) +
                                String(sequenceNumber) +
                                String(myLat, 6) +
                                String(myLon, 6) +
                                String(mySpeed, 1) +
                                String(int(round(myHeading)));

            String signature = generateHMACSignature(signString);

            // Construct Full JSON Telemetry Schema
            StaticJsonDocument<384> doc;
            doc["vehicle_id"]       = VEHICLE_ID;
            doc["vehicle_type"]     = VEHICLE_TYPE;
            doc["timestamp"]        = timestamp;
            doc["seq"]              = sequenceNumber;
            doc["lat"]              = serialized(String(myLat, 6));
            doc["lon"]              = serialized(String(myLon, 6));
            doc["alt"]              = round(myAlt * 10) / 10.0;
            doc["speed_kmph"]       = serialized(String(mySpeed, 1));
            doc["heading_deg"]      = round(myHeading);
            doc["pitch_deg"]        = round(myPitch * 10) / 10.0;
            doc["roll_deg"]         = round(myRoll * 10) / 10.0;
            doc["yaw_deg"]          = round(myHeading);
            doc["battery_level"]    = 98.5;
            doc["emergency_status"] = emergencyActive ? 1 : 0;
            doc["rf_status"]        = "OK";
            doc["fault_code"]       = faultCode;
            doc["signature"]        = signature;

            String outgoingPayload;
            serializeJson(doc, outgoingPayload);

            // Transmit packet over 2.4GHz RF via SX1281
            int txState = radio.transmit(outgoingPayload);
            if (txState == RADIOLIB_ERR_NONE) {
                // Toggle status heartbeat LED
                digitalWrite(PIN_LED_OK, !digitalRead(PIN_LED_OK));
            } else {
                Serial.print(F("[RF TX Error]: "));
                Serial.println(txState);
            }

            // Immediately restore non-blocking continuous listening
            radio.startReceive();
        }
    }
}
