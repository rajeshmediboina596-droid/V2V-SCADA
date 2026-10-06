import serial
import serial.tools.list_ports
import paho.mqtt.client as mqtt
import json
import time
import sys
import os

# Add parent directory to sys.path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from backend.config import (
    SERIAL_PORT, SERIAL_BAUDRATE, MQTT_BROKER, MQTT_PORT,
    MQTT_TOPIC_TELEMETRY, MQTT_TOPIC_GATEWAY, MQTT_USERNAME,
    MQTT_PASSWORD, MQTT_USE_TLS, MQTT_CA_CERT, MQTT_CLIENT_CERT,
    MQTT_CLIENT_KEY, MQTT_SECURITY_MODE
)
from backend.mqtt_client import publish_or_dispatch

mqtt_connected = False

def on_connect(client, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        print(f"[Gateway Bridge] Connected to Mosquitto MQTT Broker! (Mode: {MQTT_SECURITY_MODE})")
    else:
        mqtt_connected = False
        print(f"[Gateway Bridge] MQTT connect failed (rc={rc})")

def find_serial_port(preferred_port: str) -> str:
    """Find preferred port or auto-detect CP2102/USB serial port."""
    ports = list(serial.tools.list_ports.comports())
    if not ports:
        return preferred_port

    # Check if preferred port exists
    for p in ports:
        if p.device.upper() == preferred_port.upper():
            return p.device

    # Search for known USB-to-UART bridge signatures (CP2102, FTDI, CH340, STM)
    for p in ports:
        desc = (p.description or "").lower()
        hwid = (p.hwid or "").lower()
        if any(chip in desc or chip in hwid for chip in ["cp210", "ch340", "ftdi", "uart", "serial", "stm"]):
            print(f"[Gateway Bridge] Auto-detected hardware USB serial port: {p.device} ({p.description})")
            return p.device

    # Fallback to first available port
    return ports[0].device

def main():
    global mqtt_connected
    client = mqtt.Client(client_id="STM32_Gateway_Serial_Bridge")
    client.on_connect = on_connect

    if MQTT_USERNAME and MQTT_PASSWORD:
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

    if MQTT_USE_TLS and MQTT_CA_CERT and os.path.exists(MQTT_CA_CERT):
        try:
            client.tls_set(
                ca_certs=MQTT_CA_CERT,
                certfile=MQTT_CLIENT_CERT if os.path.exists(MQTT_CLIENT_CERT) else None,
                keyfile=MQTT_CLIENT_KEY if os.path.exists(MQTT_CLIENT_KEY) else None
            )
            print("[Gateway Bridge] TLS enabled for secure MQTT transport.")
        except Exception as e:
            print(f"[Gateway Bridge] TLS setup warning: {e}")

    print(f"[Gateway Bridge] Checking MQTT Broker at {MQTT_BROKER}:{MQTT_PORT}...")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 10)
        client.loop_start()
    except Exception as e:
        print(f"[Gateway Bridge] Note: MQTT broker not reachable ({e}).")
        print("[Gateway Bridge] Operating in Autonomous Direct-Dispatch Mode (No external broker required).")

    packets_forwarded = 0
    last_health_broadcast = 0.0

    target_port = find_serial_port(SERIAL_PORT)
    print(f"[Gateway Bridge] Opening STM32 Serial Port {target_port} @ {SERIAL_BAUDRATE} baud...")

    while True:
        ser = None
        try:
            target_port = find_serial_port(SERIAL_PORT)
            ser = serial.Serial(target_port, SERIAL_BAUDRATE, timeout=1.0)
            print(f"[Gateway Bridge] Serial port {target_port} active. Listening for 2.4GHz RF traffic from SX1281...")

            while True:
                now = time.time()
                # Broadcast gateway health heartbeat every 3 seconds
                if now - last_health_broadcast >= 3.0:
                    health_payload = {
                        "node_id": "RSU-GATEWAY-01",
                        "status": "Online",
                        "port": target_port,
                        "baud": SERIAL_BAUDRATE,
                        "rf_frequency": "2.4GHz FLRC/LoRa (SX1281)",
                        "packets_rx": packets_forwarded,
                        "timestamp": int(now)
                    }
                    publish_or_dispatch(MQTT_TOPIC_GATEWAY, json.dumps(health_payload))
                    last_health_broadcast = now

                if ser.in_waiting > 0:
                    raw_line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if raw_line:
                        # Basic JSON validation before publishing
                        if raw_line.startswith('{') and raw_line.endswith('}'):
                            publish_or_dispatch(MQTT_TOPIC_TELEMETRY, raw_line)
                            packets_forwarded += 1
                            print(f"[RF -> SCADA #{packets_forwarded}]: {raw_line[:80]}...")
                        else:
                            # Debug/Status message from STM32 firmware
                            print(f"[STM32 Debug]: {raw_line}")

                time.sleep(0.005)

        except serial.SerialException as se:
            print(f"[Serial Warning]: Port {target_port} unavailable ({se}). Retrying in 3s...")
            try:
                offline_payload = {
                    "node_id": "RSU-GATEWAY-01",
                    "status": "Disconnected",
                    "port": target_port,
                    "packets_rx": packets_forwarded,
                    "timestamp": int(time.time())
                }
                publish_or_dispatch(MQTT_TOPIC_GATEWAY, json.dumps(offline_payload))
            except Exception:
                pass
            time.sleep(3.0)
        except KeyboardInterrupt:
            print("\n[Gateway Bridge] Stopping serial bridge...")
            break
        except Exception as e:
            print(f"[Gateway Bridge Error]: {e}")
            time.sleep(2.0)
        finally:
            if ser and ser.is_open:
                ser.close()

    try:
        client.loop_stop()
        client.disconnect()
    except Exception:
        pass
    print("[Gateway Bridge] Clean shutdown complete.")

if __name__ == "__main__":
    main()
