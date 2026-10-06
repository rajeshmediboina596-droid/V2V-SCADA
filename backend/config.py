import os
from pathlib import Path

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
DATABASE_DIR = BASE_DIR / "database"
REPORTS_DIR = BASE_DIR / "reports"
FRONTEND_DIR = BASE_DIR / "frontend"

DATABASE_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# Cryptographic and Security Settings
HMAC_SECRET = os.getenv("HMAC_SECRET", "v2v_shared_secret_123").encode("utf-8")
REPLAY_TOLERANCE_SECONDS = int(os.getenv("REPLAY_TOLERANCE_SECONDS", "30"))

# MQTT Settings
MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_TELEMETRY = os.getenv("MQTT_TOPIC_TELEMETRY", "v2v/telemetry")
MQTT_TOPIC_ALERTS = os.getenv("MQTT_TOPIC_ALERTS", "v2v/alerts/#")
MQTT_TOPIC_COMMANDS = os.getenv("MQTT_TOPIC_COMMANDS", "v2v/commands")
MQTT_TOPIC_GATEWAY = os.getenv("MQTT_TOPIC_GATEWAY", "v2v/gateway/health")

# Serial Gateway Settings
SERIAL_PORT = os.getenv("SERIAL_PORT", "COM3")
SERIAL_BAUDRATE = int(os.getenv("SERIAL_BAUDRATE", "115200"))

# Database Settings
DB_PATH = os.getenv("DB_PATH", str(DATABASE_DIR / "v2v_data.db"))

# Highway Geofence Zone (Lat, Lon)
RESTRICTED_ZONE = [
    (17.4245, 78.4460),
    (17.4245, 78.4530),
    (17.4190, 78.4530),
    (17.4190, 78.4460)
]

# Provider Configuration for Live Voice Translation & Telephony
# STT_PROVIDER: 'browser_speech', 'mock', 'google', 'whisper'
STT_PROVIDER = os.getenv("STT_PROVIDER", "browser_speech")

# TRANSLATION_PROVIDER: 'hybrid', 'lexicon_only', 'online_only', 'mock'
TRANSLATION_PROVIDER = os.getenv("TRANSLATION_PROVIDER", "hybrid")

# TTS_PROVIDER: 'browser_speech', 'mock', 'gtts'
TTS_PROVIDER = os.getenv("TTS_PROVIDER", "browser_speech")

# TELEPHONY_PROVIDER: 'webrtc_scada', 'mock', 'twilio', 'sip'
TELEPHONY_PROVIDER = os.getenv("TELEPHONY_PROVIDER", "webrtc_scada")

# Telephony Credentials (Optional - isolated behind provider interface)
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "+10000000000")

# Language Call Defaults
DEFAULT_DRIVER_LANG = os.getenv("DEFAULT_DRIVER_LANG", "te")      # Telugu
DEFAULT_OPERATOR_LANG = os.getenv("DEFAULT_OPERATOR_LANG", "hi")  # Hindi

