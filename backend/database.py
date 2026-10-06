import os
import sqlite3
import json
import queue
import threading
from datetime import datetime
from backend.config import DB_PATH

WRITE_QUEUE = queue.Queue(maxsize=10000)
_writer_thread = None
_writer_lock = threading.Lock()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

def _write_batch(entries):
    if not entries:
        return

    import time
    t0 = time.perf_counter()
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    cursor = conn.cursor()
    try:
        telemetry_rows = []
        incident_rows = []
        crossing_rows = []
        security_rows = []
        vehicle_updates = []

        for entry_type, data in entries:
            if entry_type == 'telemetry':
                telemetry_rows.append(data)
            elif entry_type == 'incident':
                incident_rows.append(data)
            elif entry_type == 'crossing':
                crossing_rows.append(data)
            elif entry_type == 'security':
                security_rows.append(data)
            elif entry_type == 'vehicle_upsert':
                vehicle_updates.append(data)

        if telemetry_rows:
            cursor.executemany('''
                INSERT INTO telemetry (
                    vehicle_id, timestamp, seq, lat, lon, alt, speed_kmph,
                    heading_deg, pitch_deg, roll_deg, yaw_deg, battery_level,
                    fault_code, emergency_status, rf_rssi, raw_payload
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', telemetry_rows)

        if incident_rows:
            cursor.executemany('''
                INSERT INTO incidents (
                    vehicle_a, vehicle_b, distance, closing_speed, risk_level, ttc_seconds
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', incident_rows)

        if crossing_rows:
            cursor.executemany('''
                INSERT INTO tollgate_crossings (
                    vehicle_id, tollgate_id, speed_kmph, status
                ) VALUES (?, ?, ?, ?)
            ''', crossing_rows)

        if security_rows:
            cursor.executemany('''
                INSERT INTO security_events (
                    event_type, source_id, details, raw_payload
                ) VALUES (?, ?, ?, ?)
            ''', security_rows)

        if vehicle_updates:
            cursor.executemany('''
                INSERT INTO vehicles (vehicle_id, vehicle_type, first_seen, last_seen, status, battery_level)
                VALUES (?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?)
                ON CONFLICT(vehicle_id) DO UPDATE SET
                    last_seen=CURRENT_TIMESTAMP,
                    status=excluded.status,
                    battery_level=excluded.battery_level
            ''', vehicle_updates)

        conn.commit()
        try:
            from backend.metrics import metrics
            metrics.database_write.record((time.perf_counter() - t0) * 1000.0)
        except Exception:
            pass
    except Exception as e:
        print(f"[DB Error in batch write]: {e}")
    finally:
        conn.close()

def _write_worker():
    while True:
        try:
            entries = [WRITE_QUEUE.get()]
            while len(entries) < 200:
                try:
                    entries.append(WRITE_QUEUE.get_nowait())
                except queue.Empty:
                    break
            _write_batch(entries)
        except Exception as e:
            print(f"[DB Writer Thread Error]: {e}")

def _start_write_worker():
    global _writer_thread
    with _writer_lock:
        if _writer_thread is None or not _writer_thread.is_alive():
            _writer_thread = threading.Thread(target=_write_worker, name='v2v-db-writer', daemon=True)
            _writer_thread.start()

def _enqueue(entry_type, data):
    try:
        WRITE_QUEUE.put_nowait((entry_type, data))
    except queue.Full:
        pass

def init_db():
    os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('PRAGMA journal_mode=WAL')
    cursor.execute('PRAGMA synchronous=NORMAL')

    # 1. Vehicles Directory
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS vehicles (
        vehicle_id TEXT PRIMARY KEY,
        vehicle_type TEXT DEFAULT 'Passenger',
        first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'Active',
        battery_level REAL DEFAULT 100.0,
        registered_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 2. Complete High-Rate Telemetry Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS telemetry (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id TEXT NOT NULL,
        timestamp INTEGER NOT NULL,
        seq INTEGER DEFAULT 0,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        alt REAL DEFAULT 0.0,
        speed_kmph REAL NOT NULL,
        heading_deg REAL NOT NULL,
        pitch_deg REAL DEFAULT 0.0,
        roll_deg REAL DEFAULT 0.0,
        yaw_deg REAL DEFAULT 0.0,
        battery_level REAL DEFAULT 100.0,
        fault_code TEXT DEFAULT 'NONE',
        emergency_status INTEGER DEFAULT 0,
        rf_rssi INTEGER DEFAULT -45,
        raw_payload TEXT,
        received_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_telem_veh_time ON telemetry(vehicle_id, timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_telem_received_at ON telemetry(received_at)')

    # Automatic schema migration for telemetry table if created with older schema
    cursor.execute("PRAGMA table_info(telemetry)")
    existing_telem_cols = {col[1] for col in cursor.fetchall()}
    _telem_col_defs = {
        'seq': 'INTEGER DEFAULT 0',
        'alt': 'REAL DEFAULT 0.0',
        'pitch_deg': 'REAL DEFAULT 0.0',
        'roll_deg': 'REAL DEFAULT 0.0',
        'yaw_deg': 'REAL DEFAULT 0.0',
        'battery_level': 'REAL DEFAULT 100.0',
        'fault_code': "TEXT DEFAULT 'NONE'",
        'emergency_status': 'INTEGER DEFAULT 0',
        'rf_rssi': 'INTEGER DEFAULT -45',
        'raw_payload': 'TEXT',
        'received_at': 'DATETIME DEFAULT CURRENT_TIMESTAMP'
    }
    for col_name, col_def in _telem_col_defs.items():
        if col_name not in existing_telem_cols:
            try:
                cursor.execute(f"ALTER TABLE telemetry ADD COLUMN {col_name} {col_def}")
            except Exception as e:
                pass

    # 3. Incidents / Collision Warnings
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS incidents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_a TEXT NOT NULL,
        vehicle_b TEXT NOT NULL,
        distance REAL NOT NULL,
        closing_speed REAL NOT NULL,
        risk_level INTEGER NOT NULL,
        ttc_seconds REAL DEFAULT 0.0,
        incident_time DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_incidents_time ON incidents(incident_time)')

    # Automatic schema migration for incidents table
    cursor.execute("PRAGMA table_info(incidents)")
    existing_incident_cols = {col[1] for col in cursor.fetchall()}
    if 'ttc_seconds' not in existing_incident_cols:
        try:
            cursor.execute("ALTER TABLE incidents ADD COLUMN ttc_seconds REAL DEFAULT 0.0")
        except Exception:
            pass

    # 4. Highway Routes
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS routes (
        route_id TEXT PRIMARY KEY,
        highway_name TEXT NOT NULL,
        route_name TEXT NOT NULL,
        start_point TEXT,
        end_point TEXT,
        coordinates_json TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 5. Highway Tollgates
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tollgates (
        tollgate_id TEXT PRIMARY KEY,
        tollgate_name TEXT NOT NULL,
        highway_name TEXT NOT NULL,
        lat REAL NOT NULL,
        lon REAL NOT NULL,
        detection_radius_m REAL DEFAULT 500.0,
        toll_phone TEXT,
        emergency_phone TEXT,
        nearby_hospital TEXT,
        nearby_police TEXT,
        direction TEXT,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 6. Tollgate Crossings
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tollgate_crossings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vehicle_id TEXT NOT NULL,
        tollgate_id TEXT NOT NULL,
        crossing_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        speed_kmph REAL,
        status TEXT DEFAULT 'Crossed',
        notified INTEGER DEFAULT 1
    )''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_crossings_veh_toll ON tollgate_crossings(vehicle_id, tollgate_id)')

    # 7. Cyber-Security Events (Intrusions, Replays, Spoofs)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS security_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_type TEXT NOT NULL,
        source_id TEXT,
        details TEXT,
        raw_payload TEXT,
        detected_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 8. Highway Emergency Contacts Directory
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS emergency_contacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category TEXT NOT NULL,
        service_name TEXT NOT NULL,
        phone_number TEXT NOT NULL,
        location TEXT,
        highway TEXT
    )''')

    # 9. Supported Indian Languages Directory
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS supported_languages (
        code TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        native_name TEXT NOT NULL,
        bcp47 TEXT NOT NULL,
        script TEXT,
        is_active INTEGER DEFAULT 1
    )''')

    # 10. Call Sessions
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS call_sessions (
        call_id TEXT PRIMARY KEY,
        vehicle_id TEXT,
        tollgate_id TEXT,
        driver_lang TEXT DEFAULT 'te',
        operator_lang TEXT DEFAULT 'hi',
        status TEXT DEFAULT 'ACTIVE',
        start_time DATETIME DEFAULT CURRENT_TIMESTAMP,
        end_time DATETIME,
        emergency_info_shared INTEGER DEFAULT 0,
        incident_type TEXT DEFAULT 'General Inquiry',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_calls_veh ON call_sessions(vehicle_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_calls_toll ON call_sessions(tollgate_id)')

    # 11. Call Participants
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS call_participants (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        call_id TEXT NOT NULL,
        role TEXT NOT NULL,
        language TEXT NOT NULL,
        channel_info TEXT,
        joined_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 12. Translation Sessions & Messages
    cursor.execute("PRAGMA table_info(translation_sessions)")
    existing_cols = [col[1] for col in cursor.fetchall()]
    if existing_cols and "call_id" not in existing_cols:
        cursor.execute("DROP TABLE translation_sessions")

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS translation_sessions (
        session_id TEXT PRIMARY KEY,
        call_id TEXT,
        driver_lang TEXT NOT NULL,
        operator_lang TEXT NOT NULL,
        status TEXT DEFAULT 'ACTIVE',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS translation_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        call_id TEXT NOT NULL,
        session_id TEXT,
        sender_role TEXT NOT NULL,
        source_lang TEXT NOT NULL,
        detected_lang TEXT,
        target_lang TEXT NOT NULL,
        original_text TEXT NOT NULL,
        translated_text TEXT NOT NULL,
        confidence REAL DEFAULT 1.0,
        engine TEXT DEFAULT 'hybrid',
        status TEXT DEFAULT 'Delivered',
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_trans_msg_call ON translation_messages(call_id)')

    # 13. Translation & Voice Call Audit Events
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS translation_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        call_id TEXT,
        event_type TEXT NOT NULL,
        details TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 14. Communication Logs
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS communication_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        channel TEXT NOT NULL,
        source TEXT NOT NULL,
        destination TEXT NOT NULL,
        message TEXT NOT NULL,
        status TEXT DEFAULT 'Delivered',
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    # 11. Gateway Status & Health
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS gateway_status (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        node_id TEXT NOT NULL,
        rf_frequency TEXT DEFAULT '2.4GHz FLRC/LoRa',
        packets_forwarded INTEGER DEFAULT 0,
        last_heartbeat DATETIME DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'Online'
    )''')

    # 12. System Events Log
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS system_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        event_category TEXT NOT NULL,
        description TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')

    conn.commit()

    # Pre-seed initial Highway Tollgates and Emergency Contacts if empty
    cursor.execute("SELECT COUNT(*) FROM tollgates")
    if cursor.fetchone()[0] == 0:
        _seed_initial_data(cursor)
        conn.commit()

    # Pre-seed Supported Indian Languages if empty
    cursor.execute("SELECT COUNT(*) FROM supported_languages")
    if cursor.fetchone()[0] == 0:
        _seed_languages(cursor)
        conn.commit()

    conn.close()
    _start_write_worker()
    print("[DB] Initialized SQLite schema with 14 tables and WAL mode enabled.")

def _seed_languages(cursor):
    languages_data = [
        ("te", "Telugu", "తెలుగు", "te-IN", "Telugu", 1),
        ("hi", "Hindi", "हिन्दी", "hi-IN", "Devanagari", 1),
        ("ta", "Tamil", "தமிழ்", "ta-IN", "Tamil", 1),
        ("kn", "Kannada", "ಕನ್ನಡ", "kn-IN", "Kannada", 1),
        ("ml", "Malayalam", "മലയാളം", "ml-IN", "Malayalam", 1),
        ("mr", "Marathi", "मराठी", "mr-IN", "Devanagari", 1),
        ("bn", "Bengali", "বাংলা", "bn-IN", "Bengali", 1),
        ("gu", "Gujarati", "ગુજરાતી", "gu-IN", "Gujarati", 1),
        ("pa", "Punjabi", "ਪੰਜਾਬੀ", "pa-IN", "Gurmukhi", 1),
        ("or", "Odia", "ଓଡ଼ିଆ", "or-IN", "Odia", 1),
        ("as", "Assamese", "অসমীয়া", "as-IN", "Bengali", 1),
        ("en", "English", "English", "en-IN", "Latin", 1)
    ]
    cursor.executemany('''
        INSERT OR IGNORE INTO supported_languages (code, name, native_name, bcp47, script, is_active)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', languages_data)

def _seed_initial_data(cursor):
    _seed_languages(cursor)
    # Highway Tollgates
    tollgates_data = [
        (
            "TG-DEMO",
            "Jubilee Hills SCADA Smart Toll Plaza",
            "NH-65 Bypass",
            17.4270, 78.4450,
            250.0,
            "+91-40-23548888",
            "1033 (NHAI Emergency)",
            "KIMS Hospitals Begumpet (+91-40-44885000)",
            "Panjagutta Police Station (+91-40-27853500)",
            "Bidirectional"
        ),
        (
            "TG-001",
            "Patancheru Toll Plaza",
            "NH-65 (Hyderabad - Pune)",
            17.5338, 78.2644,
            600.0,
            "+91-40-23001234",
            "1033 (NHAI Helpline)",
            "Patancheru Government Area Hospital (+91-40-23114400)",
            "Patancheru Police Station (100)",
            "North-West"
        ),
        (
            "TG-002",
            "Korlapahad Toll Plaza",
            "NH-65 (Hyderabad - Vijayawada)",
            17.2150, 79.4820,
            600.0,
            "+91-8682-274111",
            "1033 (NHAI Helpline)",
            "Nalgonda District Hospital (+91-8682-244300)",
            "Nalgonda Traffic Police (100)",
            "Eastbound"
        ),
        (
            "TG-003",
            "Raikal Toll Plaza (Shadnagar)",
            "NH-44 (Hyderabad - Bangalore)",
            17.0655, 78.2248,
            600.0,
            "+91-8548-251200",
            "1033 (NHAI Helpline)",
            "Community Health Centre Shadnagar (+91-8548-252108)",
            "Shadnagar PS (100)",
            "Southbound"
        )
    ]
    cursor.executemany('''
        INSERT INTO tollgates (
            tollgate_id, tollgate_name, highway_name, lat, lon, detection_radius_m,
            toll_phone, emergency_phone, nearby_hospital, nearby_police, direction
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', tollgates_data)

    # Highway Emergency Contacts
    contacts_data = [
        ("National Highway Helpline", "NHAI 24x7 Emergency", "1033", "All National Highways", "National"),
        ("National Emergency", "All-in-One Emergency Response", "112", "Nationwide", "National"),
        ("Police Emergency", "Highway Traffic Patrol", "100", "State Highways & NH", "Regional"),
        ("Ambulance Service", "Emergency Medical Response", "108", "Statewide Trauma Care", "Regional"),
        ("Women Safety Helpline", "National Women Helpline", "1091", "Nationwide", "National"),
        ("Disaster Management", "NDMA Emergency Ops", "1078", "National Highways", "National"),
    ]
    cursor.executemany('''
        INSERT INTO emergency_contacts (service_name, category, phone_number, location, highway)
        VALUES (?, ?, ?, ?, ?)
    ''', contacts_data)

# --- Logging API Helpers ---
def log_telemetry(payload):
    vid = payload.get('vehicle_id')
    v_type = payload.get('vehicle_type', 'Passenger')
    battery = payload.get('battery_level', 95.0)

    # Upsert vehicle directory
    _enqueue('vehicle_upsert', (vid, v_type, 'Active', battery))

    # Queue telemetry row
    _enqueue('telemetry', (
        vid,
        payload.get('timestamp', int(datetime.now().timestamp())),
        payload.get('seq', 0),
        payload.get('lat', 0.0),
        payload.get('lon', 0.0),
        payload.get('alt', 0.0),
        payload.get('speed_kmph', 0.0),
        payload.get('heading_deg', 0.0),
        payload.get('pitch_deg', 0.0),
        payload.get('roll_deg', 0.0),
        payload.get('yaw_deg', 0.0),
        battery,
        payload.get('fault_code', 'NONE'),
        1 if payload.get('emergency_status') else 0,
        payload.get('rf_rssi', -45),
        json.dumps(payload)
    ))

def log_incident(v_a, v_b, distance, closing_speed, risk_level, ttc=0.0):
    _enqueue('incident', (v_a, v_b, distance, closing_speed, risk_level, ttc))

def log_tollgate_crossing(vehicle_id, tollgate_id, speed_kmph):
    _enqueue('crossing', (vehicle_id, tollgate_id, speed_kmph, 'Crossed'))

def log_security_event(event_type, source_id, details, raw_payload=""):
    _enqueue('security', (event_type, source_id, details, str(raw_payload)))

def log_translation(session_id, source_lang, target_lang, speaker_type, original, translated):
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO translation_sessions (
                session_id, source_lang, target_lang, speaker_type, original_text, translated_text
            ) VALUES (?, ?, ?, ?, ?, ?)
        ''', (session_id, source_lang, target_lang, speaker_type, original, translated))
        conn.commit()
    finally:
        conn.close()

def prune_old_telemetry(retention_hours: int = 48) -> int:
    """
    Prunes telemetry rows older than the specified retention window (default 48h)
    to prevent unbounded SQLite file growth during continuous testing.
    Returns the count of pruned rows.
    """
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM telemetry WHERE received_at < datetime('now', '-' || ? || ' hours')",
            (retention_hours,)
        )
        deleted = cursor.rowcount
        conn.commit()
        return deleted
    except Exception as e:
        print(f"[DB Retention Cleanup Error]: {e}")
        return 0
    finally:
        conn.close()

# --- Query Helpers ---
def get_recent_incidents(limit=50):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM incidents ORDER BY id DESC LIMIT ?', (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def get_recent_security_events(limit=50):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM security_events ORDER BY id DESC LIMIT ?', (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def get_tollgates():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tollgates ORDER BY tollgate_id ASC')
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def get_emergency_contacts():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM emergency_contacts ORDER BY id ASC')
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def get_recent_crossings(limit=50):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.*, t.tollgate_name, t.highway_name, t.toll_phone, t.emergency_phone
            FROM tollgate_crossings c
            JOIN tollgates t ON c.tollgate_id = t.tollgate_id
            ORDER BY c.id DESC LIMIT ?
        ''', (limit,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def get_vehicles_list():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM vehicles ORDER BY last_seen DESC')
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

# --- Voice Call & Multi-Indian-Language Translation Helpers ---
def get_supported_languages():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT code, name, native_name, bcp47, script, is_active FROM supported_languages WHERE is_active = 1 ORDER BY code ASC')
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def create_call_record(call_id, vehicle_id, tollgate_id, driver_lang="te", operator_lang="hi", incident_type="General Emergency", emergency_info_shared=0):
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO call_sessions (
                call_id, vehicle_id, tollgate_id, driver_lang, operator_lang,
                status, start_time, emergency_info_shared, incident_type
            ) VALUES (?, ?, ?, ?, ?, 'ACTIVE', CURRENT_TIMESTAMP, ?, ?)
            ON CONFLICT(call_id) DO UPDATE SET
                status='ACTIVE',
                driver_lang=excluded.driver_lang,
                operator_lang=excluded.operator_lang,
                emergency_info_shared=excluded.emergency_info_shared,
                incident_type=excluded.incident_type
        ''', (call_id, vehicle_id, tollgate_id, driver_lang, operator_lang, emergency_info_shared, incident_type))
        conn.commit()
    finally:
        conn.close()

def update_call_status(call_id, status, end_time=None, emergency_info_shared=None):
    conn = get_db_connection()
    try:
        if end_time and emergency_info_shared is not None:
            conn.execute('UPDATE call_sessions SET status = ?, end_time = CURRENT_TIMESTAMP, emergency_info_shared = ? WHERE call_id = ?', (status, emergency_info_shared, call_id))
        elif end_time:
            conn.execute('UPDATE call_sessions SET status = ?, end_time = CURRENT_TIMESTAMP WHERE call_id = ?', (status, call_id))
        elif emergency_info_shared is not None:
            conn.execute('UPDATE call_sessions SET status = ?, emergency_info_shared = ? WHERE call_id = ?', (status, emergency_info_shared, call_id))
        else:
            conn.execute('UPDATE call_sessions SET status = ? WHERE call_id = ?', (status, call_id))
        conn.commit()
    finally:
        conn.close()

def get_call_record(call_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT c.*, t.tollgate_name, t.highway_name, t.toll_phone, t.emergency_phone
            FROM call_sessions c
            LEFT JOIN tollgates t ON c.tollgate_id = t.tollgate_id
            WHERE c.call_id = ?
        ''', (call_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def add_call_participant(call_id, role, language, channel_info="WebRTC"):
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO call_participants (call_id, role, language, channel_info)
            VALUES (?, ?, ?, ?)
        ''', (call_id, role, language, channel_info))
        conn.commit()
    finally:
        conn.close()

def get_call_participants(call_id):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM call_participants WHERE call_id = ? ORDER BY id ASC', (call_id,))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def create_translation_session(session_id, call_id, driver_lang, operator_lang):
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO translation_sessions (session_id, call_id, driver_lang, operator_lang, status)
            VALUES (?, ?, ?, ?, 'ACTIVE')
            ON CONFLICT(session_id) DO UPDATE SET
                driver_lang=excluded.driver_lang,
                operator_lang=excluded.operator_lang
        ''', (session_id, call_id, driver_lang, operator_lang))
        conn.commit()
    finally:
        conn.close()

def log_call_message(call_id, session_id, sender_role, source_lang, detected_lang, target_lang, original_text, translated_text, confidence=1.0, engine="hybrid", status="Delivered"):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO translation_messages (
                call_id, session_id, sender_role, source_lang, detected_lang, target_lang,
                original_text, translated_text, confidence, engine, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (call_id, session_id, sender_role, source_lang, detected_lang, target_lang, original_text, translated_text, confidence, engine, status))
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()

def get_call_messages(call_id, limit=100):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM translation_messages
            WHERE call_id = ?
            ORDER BY id ASC
            LIMIT ?
        ''', (call_id, limit))
        return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def log_translation_event(call_id, event_type, details):
    conn = get_db_connection()
    try:
        conn.execute('''
            INSERT INTO translation_events (call_id, event_type, details)
            VALUES (?, ?, ?)
        ''', (call_id, event_type, str(details)))
        conn.commit()
    finally:
        conn.close()

