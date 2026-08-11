# Vehicle-to-Vehicle (V2V) Communication & SCADA System

## 1. System Overview
This project is an advanced IoT-based V2V (Vehicle-to-Vehicle) and V2I (Vehicle-to-Infrastructure) communication platform. It acts as a real-time SCADA dashboard for tracking physical vehicles, processing 10Hz high-speed telemetry, verifying cryptographic signatures to prevent cyber-attacks, and predicting collisions using Haversine physics and Machine Learning.

---

## 2. IoT Hardware Requirements
To deploy this system onto physical vehicles (the "Original Vehicles"), each vehicle acts as an IoT Edge Node. You will need the following hardware components per vehicle:

1. **Microcontroller**: **ESP32 Development Board**
   * *Why*: Powerful dual-core processor, built-in Wi-Fi/Bluetooth, and fast enough to handle HMAC-SHA256 cryptographic signing at 10Hz.
2. **GNSS/GPS Module**: **U-blox NEO-M8N** (or NEO-6M)
   * *Why*: High-precision satellite tracking to grab accurate Latitude, Longitude, and Speed data.
3. **Communication Protocol**: **ESP-NOW (Built-in to ESP32)**
   * *Why*: We have eliminated the 4G/LTE cellular requirement. ESP-NOW allows the microcontrollers to blast data directly to each other peer-to-peer over radio waves (2.4GHz) up to 200 meters. **No internet, no SIM cards, and zero network latency.**
   * *(Alternative)*: **LoRa SX1278** modules can be added if you need multi-kilometer range, but at a lower update frequency.
4. **IMU Sensor (Optional)**: **MPU6050 (Accelerometer & Gyroscope)**
   * *Why*: Dead-reckoning fallback if GPS signal is lost in tunnels, and to provide high-resolution heading/yaw data.
5. **Feedback Interfaces**: 
   * **OLED Display (SSD1306)**: To show the driver their connection status and nearby vehicle count.
   * **Buzzer / LEDs**: To physically sound an alarm when the dashboard triggers an Automatic Emergency Braking (AEB) alert.
6. **Power Supply**: 12V to 5V Buck Converter to power the ESP32 directly from the vehicle's battery.

### Exact Shopping List (For a 2-Vehicle Test)
To run a real-world test with 2 cars while viewing the data on your laptop, you need **three** ESP32 nodes (2 for the cars, 1 for the laptop).

**For the 2 Vehicles:**
* **2x** ESP32 Development Boards
* **2x** U-blox NEO-M8N (or NEO-6M) GPS Modules
* **2x** 12V to 5V Buck Converters
* *(Optional)* **2x** OLED Displays + Buzzers

**For the Command Center (Laptop RSU):**
* **1x** bare ESP32 Development Board (Plugs into laptop via USB to receive wireless signals from the cars)

---

## 3. Full System Architecture (Offline & Internet-Free)

### Edge Layer (Physical Vehicles - V2V)
* The ESP32 gathers GPS data (Lat, Lon, Speed, Heading).
* It constructs a JSON payload and generates an **HMAC-SHA256 Signature**.
* **Internet-Free Broadcasting**: The ESP32 broadcasts this payload blindly into the air using the **ESP-NOW** protocol. 
* **Edge Physics**: The collision math is executed *directly on the vehicle's ESP32*. If it intercepts an ESP-NOW broadcast from another vehicle, it instantly calculates the Haversine distance. If a collision is imminent, the ESP32 triggers its own buzzer/brakes in under 3 milliseconds.

### Roadside Unit Layer (V2I Bridge)
* To keep the SCADA dashboard functional without internet, a stationary **Roadside Unit (RSU)** is constructed.
* This is a standalone ESP32 plugged into the command center laptop via USB.
* It listens to the ESP-NOW broadcasts from passing vehicles and forwards the JSON data over the USB Serial cable to the laptop.

### Transport Layer (Local Network)
* A Python script reads the USB Serial data from the RSU and publishes it to a **Local MQTT Broker (Eclipse Mosquitto)** running entirely on the laptop's localhost.

### Backend Layer (FastAPI & Python)
* **MQTT Client (`mqtt_client.py`)**: Subscribes to the local MQTT broker to ingest the RSU data.
* **Security Module**: Instantly verifies the HMAC signature of every packet to detect spoofing.
* **AI/ML Integration**: Uses a Scikit-Learn `CollisionPredictor` model to evaluate data and generate analytics for the UI.
* **WebSocket Server (`main.py`)**: Streams the processed data to the frontend at 60 frames per second.

### Frontend Layer (SCADA Dashboard)
* **UI/UX**: Cyberpunk/SCADA aesthetic built with pure HTML/CSS/JS.
* **Mapping**: Leaflet.js with OSRM (Open Source Routing Machine) integration to physically snap vehicle paths to real-world curved roads.
* **Deep Packet Inspection (DPI)**: Real-time scrolling hex-feed of the encrypted MQTT payloads.

---

## 4. Problem Statements & Solutions

### 🔴 Problem 1: High Latency in Collision Avoidance
* **Statement**: Traditional HTTP REST APIs are too slow for fast-moving vehicles. If vehicles are moving at 100 km/h, a 1-second delay means they traveled 27 meters blind.
* **Solution**: Switched transport protocol to MQTT and WebSockets. The hardware publishes at 10Hz (every 0.1 seconds), and the backend calculates predictive trajectories looking 5 seconds into the future to alert drivers *before* they crash.

### 🔴 Problem 2: Cyber-Security & Data Spoofing
* **Statement**: Anyone can inject fake MQTT coordinates to trigger false collision alarms and bring traffic to a halt (Ghost Vehicle Attack).
* **Solution**: Implemented edge-level HMAC-SHA256 Cryptography. Every payload is uniquely signed using a secure key. The backend validates the signature in microseconds. Invalid payloads (like the "SPOOF ATTACK" button in the demo) are blocked, and a Cyber-Alert is raised on the DPI feed.

### 🔴 Problem 3: Inaccurate Visual Tracking (Off-roading)
* **Statement**: Map interpolation using simple trigonometry caused vehicles to visually drift in straight lines over buildings and parks between GPS updates.
* **Solution**: Integrated the **OSRM (Open Source Routing Machine)**. The engine queries the real-world road network and snaps the vehicle paths to the actual curves and corners of the street geometry for maximum SCADA realism.

---

## 5. Phase-by-Phase Implementation Plan

### Phase 1: IoT Hardware Setup
1. Wire the NEO-6M GPS and SIM7600G LTE modules to the ESP32.
2. Flash the `esp32/firmware/main.ino` firmware.
3. Test GPS locks and ensure the ESP32 is successfully publishing JSON payloads to the local/cloud MQTT broker.

### Phase 2: Backend Infrastructure & Security
1. Deploy the FastAPI backend and Python MQTT listener.
2. Implement the cryptographic signature verification function.
3. Build the Haversine distance calculator and link the Scikit-learn AI model for risk prediction.
4. Establish the WebSocket bridge to stream data continuously.

### Phase 3: Dashboard & Frontend Physics
1. Build the dark-themed CSS SCADA layout with live metrics (Latency, Speed Matrices, Active Threats).
2. Integrate Leaflet.js for the dynamic map.
3. Write the frontend `app.js` logic to render the radar blips, predictive trajectory lines, and geofence polygons.
4. Add the OSRM Road-Snapping logic to keep visual tracking hyper-realistic.

### Phase 4: Segregation & Testing
1. Implement the **LIVE FEED vs DEMO SIM** toggle to ensure hardware testing data never mixes with marketing demonstration data.
2. Run `esp32/simulator.py` to stress-test the backend with 10Hz data streams.
3. Run field tests with the physical ESP32 boards in actual vehicles to tune the AI model's sensitivity.
