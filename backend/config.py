import os
import sys
from pathlib import Path

# ==============================================================================
# Base Directories & Filesystem Paths
# ==============================================================================
BASE_DIR = Path(__file__).resolve().parent.parent
BACKEND_DIR = Path(__file__).resolve().parent
DATABASE_DIR = BASE_DIR / "database"
REPORTS_DIR = BASE_DIR / "reports"
FRONTEND_DIR = BASE_DIR / "frontend"

DATABASE_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

# ==============================================================================
# Environment & Deployment Mode
# ==============================================================================
# ENVIRONMENT: 'development', 'test', 'production'
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

# DEMO_MODE: When true, enables relaxed replay tolerances for synthetic demonstrations.
# When false, strict production cryptographic & anti-replay checks are enforced.
DEMO_MODE = os.getenv("DEMO_MODE", "true").lower() in ("true", "1", "yes")

# ==============================================================================
# Cryptographic & Security Configuration
# ==============================================================================
# The shared HMAC secret used for telemetry packet signing and verification.
# In production, this must be set via an environment variable.
_raw_hmac_secret = os.getenv("HMAC_SECRET")

# Known insecure placeholder strings
_INSECURE_SECRETS = (
    "v2v_shared_secret_123",
    "CHANGE_ME_TO_A_RANDOM_SECRET",
    "secret",
    "password",
    "123456",
    ""
)

if ENVIRONMENT == "production":
    if not _raw_hmac_secret or _raw_hmac_secret in _INSECURE_SECRETS:
        raise RuntimeError(
            "[SECURITY CRITICAL] Application startup aborted: HMAC_SECRET is missing or set to an "
            "insecure placeholder in production mode. Set a strong random secret via the HMAC_SECRET "
            "environment variable (e.g. openssl rand -hex 32)."
        )
    HMAC_SECRET = _raw_hmac_secret.encode("utf-8")
else:
    # Development / Demo mode fallback
    if not _raw_hmac_secret or _raw_hmac_secret in _INSECURE_SECRETS:
        # Development fallback with clear notice (never print secret in logs)
        _raw_hmac_secret = "v2v_demo_secret_development_only"
    HMAC_SECRET = _raw_hmac_secret.encode("utf-8")

# Anti-Replay: Allowed timestamp divergence window (seconds)
REPLAY_TOLERANCE_SECONDS = int(os.getenv("REPLAY_TOLERANCE_SECONDS", "30"))

# Maximum number of vehicle IDs tracked in memory for sequence anti-replay
MAX_TRACKED_VEHICLES = int(os.getenv("MAX_TRACKED_VEHICLES", "1000"))

# API Authentication & Role-Based Access Control
# In DEMO_MODE, API auth is optional (default false) to allow frictionless demonstration.
# In SECURE/PRODUCTION mode, API auth is enforced (default true).
API_AUTH_ENABLED = os.getenv(
    "API_AUTH_ENABLED",
    "false" if DEMO_MODE else "true"
).lower() in ("true", "1", "yes")

API_ADMIN_KEY = os.getenv("API_ADMIN_KEY", "admin_secret_key_demo" if DEMO_MODE else "")
API_OPERATOR_KEY = os.getenv("API_OPERATOR_KEY", "operator_secret_key_demo" if DEMO_MODE else "")
API_VIEWER_KEY = os.getenv("API_VIEWER_KEY", "viewer_secret_key_demo" if DEMO_MODE else "")

if ENVIRONMENT == "production" and API_AUTH_ENABLED:
    if not API_ADMIN_KEY or API_ADMIN_KEY in _INSECURE_SECRETS:
        raise RuntimeError(
            "[SECURITY CRITICAL] Application startup aborted: API_ADMIN_KEY is missing or set to an "
            "insecure placeholder in production mode with API_AUTH_ENABLED=true. Set a strong secret key."
        )

# CORS Allowed Origins (Comma-separated string of trusted origin URLs)
_cors_origins_raw = os.getenv(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000"
)
CORS_ALLOWED_ORIGINS = [
    origin.strip() for origin in _cors_origins_raw.split(",") if origin.strip()
]

# ==============================================================================
# MQTT Broker Configuration (Demo vs Secure Mode)
# ==============================================================================
# MQTT_SECURITY_MODE: 'demo' (anonymous / local broker) or 'secure' (authenticated / TLS)
MQTT_SECURITY_MODE = os.getenv("MQTT_SECURITY_MODE", "demo").lower()

MQTT_BROKER = os.getenv("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
MQTT_USE_TLS = os.getenv("MQTT_USE_TLS", "false").lower() in ("true", "1", "yes")
MQTT_CA_CERT = os.getenv("MQTT_CA_CERT", "")
MQTT_CLIENT_CERT = os.getenv("MQTT_CLIENT_CERT", "")
MQTT_CLIENT_KEY = os.getenv("MQTT_CLIENT_KEY", "")

# Standard V2V MQTT Topic Hierarchy
MQTT_TOPIC_TELEMETRY = os.getenv("MQTT_TOPIC_TELEMETRY", "v2v/telemetry")
MQTT_TOPIC_ALERTS = os.getenv("MQTT_TOPIC_ALERTS", "v2v/alerts/#")
MQTT_TOPIC_COMMANDS = os.getenv("MQTT_TOPIC_COMMANDS", "v2v/commands")
MQTT_TOPIC_GATEWAY = os.getenv("MQTT_TOPIC_GATEWAY", "v2v/gateway/health")

# ==============================================================================
# Serial Hardware Gateway Settings
# ==============================================================================
SERIAL_PORT = os.getenv("SERIAL_PORT", "COM3")
SERIAL_BAUDRATE = int(os.getenv("SERIAL_BAUDRATE", "115200"))

# ==============================================================================
# Database Configuration
# ==============================================================================
DB_PATH = os.getenv("DB_PATH", str(DATABASE_DIR / "v2v_data.db"))

# ==============================================================================
# Central Safety & Physics Constants (TTC & Thresholds)
# ==============================================================================
TELEMETRY_RATE_HZ = 10                  # AIS-230 recommended broadcast frequency
TTC_CRITICAL_SECONDS = 2.5             # Critical imminent collision threshold (AEB trigger)
TTC_WARNING_SECONDS = 3.5              # Urgent collision warning threshold (audible alarm)
TTC_ADVISORY_SECONDS = 5.0             # Advisory threshold (visual cockpit caution)
EMERGENCY_PROXIMITY_METERS = 200.0     # Emergency vehicle preemption range (yield warning)
TOLLGATE_APPROACH_RADIUS_METERS = 500.0# Tollgate entry warning geofence radius
MAX_VALID_SPEED_KMPH = 250.0           # Physical upper bound for ground vehicle velocity

# Restricted Zone Geofence Coordinates (Hyderabad NH-65 Test Corridor)
RESTRICTED_ZONE = [
    (17.4245, 78.4460),
    (17.4245, 78.4530),
    (17.4190, 78.4530),
    (17.4190, 78.4460)
]

# ==============================================================================
# Voice Translation & Telephony Providers
# ==============================================================================
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
