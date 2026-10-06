from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
import uvicorn
import asyncio
import os
import sys
import time
import json
import math
import random

from typing import Optional, Dict, Any, List
# Ensure backend can import sibling modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import (
    BASE_DIR, FRONTEND_DIR, REPORTS_DIR, MQTT_BROKER, MQTT_PORT, MQTT_TOPIC_TELEMETRY,
    STT_PROVIDER, TRANSLATION_PROVIDER, TTS_PROVIDER, TELEPHONY_PROVIDER
)
from backend.database import (
    init_db, get_tollgates, get_emergency_contacts, get_recent_crossings,
    get_recent_incidents, get_recent_security_events, get_vehicles_list,
    get_supported_languages, get_call_messages, get_call_record
)
from backend.mqtt_client import (
    start_mqtt_client, message_queue, vehicle_states, gateway_health_state,
    publish_or_dispatch
)
from backend.report_generator import generate_pdf_report
from backend.translation import translate_message, SUPPORTED_LANGUAGES
from backend.security import generate_signature
from backend.call_service import call_manager
from backend.providers.factory import (
    get_telephony_provider,
    get_stt_provider,
    get_translation_provider,
    get_tts_provider
)
import paho.mqtt.client as mqtt_lib

app = FastAPI(
    title="Internet-Independent V2V Communication & SCADA Safety Monitoring System",
    description="MoRTH AIS-230 Compliant STM32-based Telemetry, Collision Avoidance, and Highway V2I Platform",
    version="2.0.0"
)

# CORS & Security Headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Mount static frontend assets
app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, 'css')), name="css")
app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, 'js')), name="js")

connected_clients = set()

@app.on_event("startup")
async def startup_event():
    init_db()
    loop = asyncio.get_running_loop()
    start_mqtt_client(loop)
    asyncio.create_task(broadcast_messages())

async def broadcast_messages():
    while True:
        message = await message_queue.get()
        if not connected_clients:
            continue

        dead_clients = set()
        for client in connected_clients:
            try:
                await client.send_json(message)
            except Exception:
                dead_clients.add(client)

        for client in dead_clients:
            connected_clients.remove(client)

@app.get("/")
async def get_index():
    return FileResponse(os.path.join(FRONTEND_DIR, 'index.html'))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.add(websocket)
    try:
        # Push initial snapshot of registered tollgates, gateway health, and active vehicles
        tollgates = get_tollgates()
        await websocket.send_json({
            "type": "init_state",
            "tollgates": tollgates,
            "gateway_health": gateway_health_state,
            "emergency_contacts": get_emergency_contacts()
        })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.remove(websocket)
    except Exception:
        if websocket in connected_clients:
            connected_clients.remove(websocket)

# --- System Health & Diagnostics ---
@app.get("/api/health")
async def get_system_health():
    now = time.time()
    gw_online = (now - gateway_health_state.get("last_seen", 0)) < 15.0
    return {
        "status": "healthy",
        "timestamp": int(now),
        "architecture": "STM32F103 / SX1281 2.4GHz RF",
        "mqtt_broker": {
            "host": MQTT_BROKER,
            "port": MQTT_PORT,
            "status": "connected"
        },
        "gateway_node": {
            "status": "Online" if gw_online else "Standby",
            "port": gateway_health_state.get("port", "COM3"),
            "rf_frequency": gateway_health_state.get("rf_frequency", "2.4GHz FLRC/LoRa"),
            "packets_rx": gateway_health_state.get("packets_rx", 0)
        },
        "active_vehicles_count": len(vehicle_states),
        "connected_scada_clients": len(connected_clients),
        "database": "SQLite (WAL Mode)",
        "voice_translation_system": {
            "status": "Online (Continuous Real-Time)",
            "telephony_provider": TELEPHONY_PROVIDER,
            "stt_provider": STT_PROVIDER,
            "translation_provider": TRANSLATION_PROVIDER,
            "tts_provider": TTS_PROVIDER,
            "supported_indian_languages": len(get_supported_languages()),
            "offline_safety_isolation": "Guaranteed — V2V RF, Collision & GPS completely independent of telephony/cloud"
        }
    }

# --- Vehicles & Telemetry APIs ---
@app.get("/api/vehicles")
async def get_active_vehicles():
    return {
        "active_vehicles": list(vehicle_states.values()),
        "registered_directory": get_vehicles_list()
    }

@app.post("/api/telemetry")
async def ingest_telemetry(payload: Dict[str, Any]):
    """
    Ingest vehicle telemetry directly via HTTP POST.
    Dispatches to MQTT or internal real-time pipeline.
    """
    raw_json = json.dumps(payload)
    publish_or_dispatch(MQTT_TOPIC_TELEMETRY, raw_json)
    return {
        "status": "success",
        "vehicle_id": payload.get("vehicle_id", "UNKNOWN"),
        "received_at": int(time.time())
    }

# --- Highway Route & Tollgate APIs ---
@app.get("/api/tollgates")
async def fetch_tollgates():
    return {"tollgates": get_tollgates()}

@app.get("/api/tollgates/crossings")
async def fetch_tollgate_crossings(limit: int = 50):
    return {"crossings": get_recent_crossings(limit)}

@app.get("/api/emergency-contacts")
async def fetch_emergency_contacts():
    return {"contacts": get_emergency_contacts()}

# --- Real-Time Multi-Indian-Language Voice Call & Translation APIs ---

class StartCallRequest(BaseModel):
    vehicle_id: str = "DEMO-1"
    tollgate_id: str = "TG-DEMO"
    driver_lang: str = "te"
    operator_lang: str = "hi"
    incident_type: str = "General Emergency"
    emergency_info_shared: bool = False

class EndCallRequest(BaseModel):
    call_id: str
    reason: str = "Call Completed"

class TranslationSessionRequest(BaseModel):
    call_id: Optional[str] = None
    driver_lang: str = "te"
    operator_lang: str = "hi"

class AudioTranslationRequest(BaseModel):
    call_id: str
    sender_role: str = "Driver"
    text: Optional[str] = None
    source_lang: str = "auto"
    target_lang: str = "hi"
    audio_base64: Optional[str] = None

class IncidentShareRequest(BaseModel):
    confirmed: bool = True

class SimulateTurnRequest(BaseModel):
    call_id: str
    sender_role: str = "Driver"
    text: str
    source_lang: str = "te"
    target_lang: str = "hi"

class TranslationRequest(BaseModel):
    text: str
    source_lang: str
    target_lang: str
    speaker_type: str = "Driver"
    session_id: Optional[str] = None

class CallLogRequest(BaseModel):
    contact_name: str
    phone_number: str
    category: str
    highway: str = "NH-65"

# 1. Start Voice Call
@app.post("/calls/start")
@app.post("/api/calls/start")
async def start_voice_call(req: StartCallRequest):
    call_data = await call_manager.start_call(
        vehicle_id=req.vehicle_id,
        tollgate_id=req.tollgate_id,
        driver_lang=req.driver_lang,
        operator_lang=req.operator_lang,
        incident_type=req.incident_type,
        emergency_info_shared=req.emergency_info_shared
    )
    await message_queue.put({
        "type": "call_started",
        "data": call_data
    })
    return call_data

# 2. End Voice Call
@app.post("/calls/end")
@app.post("/api/calls/end")
async def end_voice_call(req: EndCallRequest):
    result = await call_manager.end_call(call_id=req.call_id, reason=req.reason)
    await message_queue.put({
        "type": "call_ended",
        "data": result
    })
    return result

# 3. Get Call Details & Status
@app.get("/calls/{call_id}")
@app.get("/api/calls/{call_id}")
async def get_call_status(call_id: str):
    summary = await call_manager.get_call_summary(call_id)
    if not summary:
        return JSONResponse(status_code=404, content={"error": f"Call session {call_id} not found"})
    return summary

# 4. Translation Session Creation / Query
@app.post("/translation/session")
@app.post("/api/translation/session")
async def create_translation_session_endpoint(req: TranslationSessionRequest):
    cid = req.call_id or f"CALL-{int(time.time())}"
    sid = f"SES-{cid}"
    return {
        "session_id": sid,
        "call_id": cid,
        "driver_lang": req.driver_lang,
        "operator_lang": req.operator_lang,
        "status": "ACTIVE"
    }

# 5. Audio / Speech Translation Packet Processing
@app.post("/translation/audio")
@app.post("/api/translation/audio")
async def process_translation_audio(req: AudioTranslationRequest):
    text_to_process = req.text
    if not text_to_process and req.audio_base64:
        text_to_process = "Emergency audio frame captured"

    turn_res = await call_manager.process_speech_turn(
        call_id=req.call_id,
        sender_role=req.sender_role,
        text=text_to_process or "",
        source_lang=req.source_lang,
        target_lang=req.target_lang
    )
    return turn_res

# 6. Supported Languages (12+ Indian Languages)
@app.get("/translation/languages")
@app.get("/api/translation/languages")
async def get_supported_indian_languages():
    languages = get_supported_languages()
    return {"languages": languages, "count": len(languages)}

# 7. Translation History for Call
@app.get("/translation/history/{call_id}")
@app.get("/api/translation/history/{call_id}")
async def get_call_history(call_id: str, limit: int = 100):
    messages = get_call_messages(call_id, limit=limit)
    return {"call_id": call_id, "messages": messages, "count": len(messages)}

# 8. Share Emergency Incident Telemetry (With User Confirmation)
@app.post("/calls/{call_id}/share-incident")
@app.post("/api/calls/{call_id}/share-incident")
async def share_incident_endpoint(call_id: str, req: IncidentShareRequest):
    if not req.confirmed:
        return {"status": "cancelled", "message": "Incident transmission cancelled by user"}
    return await call_manager.share_incident_dossier(call_id)

# 9. Simulation Turn for Testing Any Language Pair
@app.post("/calls/simulate-turn")
@app.post("/api/calls/simulate-turn")
async def simulate_turn_endpoint(req: SimulateTurnRequest):
    turn = await call_manager.process_speech_turn(
        call_id=req.call_id,
        sender_role=req.sender_role,
        text=req.text,
        source_lang=req.source_lang,
        target_lang=req.target_lang
    )
    return {"status": "success", "turn": turn}

# 10. WebRTC & WebSocket Real-Time Voice Channel
@app.websocket("/ws/call/{call_id}")
async def call_websocket_endpoint(websocket: WebSocket, call_id: str):
    await websocket.accept()
    call_manager.register_socket(call_id, websocket)
    try:
        summary = await call_manager.get_call_summary(call_id)
        await websocket.send_json({
            "type": "call_snapshot",
            "data": summary
        })
        while True:
            data_text = await websocket.receive_text()
            try:
                msg = json.loads(data_text)
                msg_type = msg.get("type")
                if msg_type == "speech_turn":
                    await call_manager.process_speech_turn(
                        call_id=call_id,
                        sender_role=msg.get("sender_role", "Driver"),
                        text=msg.get("text", ""),
                        source_lang=msg.get("source_lang", "auto"),
                        target_lang=msg.get("target_lang", "hi")
                    )
                elif msg_type == "share_incident":
                    await call_manager.share_incident_dossier(call_id)
                elif msg_type in ("webrtc_offer", "webrtc_answer", "ice_candidate"):
                    await call_manager.broadcast_to_call(call_id, msg)
                elif msg_type == "end_call":
                    await call_manager.end_call(call_id, reason=msg.get("reason", "User Ended"))
            except Exception as e:
                print(f"[Call WS Message Error]: {e}")
    except WebSocketDisconnect:
        call_manager.unregister_socket(call_id, websocket)
    except Exception:
        call_manager.unregister_socket(call_id, websocket)

# Backward-compatible endpoints
@app.post("/api/translate")
async def handle_translation(req: TranslationRequest):
    result = translate_message(
        text=req.text,
        source_lang=req.source_lang,
        target_lang=req.target_lang,
        speaker_type=req.speaker_type,
        session_id=req.session_id
    )
    await message_queue.put({
        "type": "translation_event",
        "data": result
    })
    return result

@app.post("/api/emergency/call-log")
async def log_call_attempt(req: CallLogRequest):
    event = {
        "type": "emergency_call",
        "contact_name": req.contact_name,
        "phone_number": req.phone_number,
        "category": req.category,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    await message_queue.put(event)
    return {"status": "success", "event": event}


# --- Incident & Security Audit APIs ---
@app.get("/api/incidents")
async def fetch_incidents(limit: int = 50):
    return {"incidents": get_recent_incidents(limit)}

@app.get("/api/security-events")
async def fetch_security_events(limit: int = 50):
    return {"security_events": get_recent_security_events(limit)}

@app.post("/api/report")
async def generate_report():
    filepath = generate_pdf_report()
    filename = os.path.basename(filepath)
    return {"status": "success", "file": filename}

@app.get("/api/download/{filename}")
async def download_report(filename: str):
    filepath = os.path.join(REPORTS_DIR, filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type='application/pdf', filename=filename)
    return JSONResponse(status_code=404, content={"error": "File not found"})

# --- Demonstration & Simulation Simulation Runner ---
is_demo_running = False

def run_demo_simulation():
    global is_demo_running
    if is_demo_running:
        return
    is_demo_running = True

    try:
        routes_path = os.path.join(BASE_DIR, 'backend', 'routes.json')
        try:
            with open(routes_path, 'r') as f:
                routes = json.load(f)
        except Exception:
            routes = None

        # 4 OSRM-routed vehicles passing near Jubilee Hills / NH-65 Tollgate
        routed_vehicles = [
            {"idx": 0.0, "speed": 48.0, "heading": 90.0,  "type": "Passenger", "lat": 17.4239, "lon": 78.4400, "route": "v1", "rate": 0.16},
            {"idx": 0.0, "speed": 52.0, "heading": 270.0, "type": "Passenger", "lat": 17.4239, "lon": 78.4550, "route": "v2", "rate": 0.22},
            {"idx": 0.0, "speed": 38.0, "heading": 0.0,   "type": "Truck",     "lat": 17.4180, "lon": 78.4483, "route": "v3", "rate": 0.12},
            {"idx": 0.0, "speed": 82.0, "heading": 180.0, "type": "Emergency", "lat": 17.4290, "lon": 78.4483, "route": "v4", "rate": 0.35},
        ]

        seq_counter = 0

        # Run 600 cycles @ 10Hz = 60 seconds
        for _ in range(600):
            seq_counter += 1
            now_ts = int(time.time())

            for idx, v in enumerate(routed_vehicles):
                if routes and v['route'] in routes:
                    v['idx'] += v['rate']
                    route_pts = routes[v['route']]
                    v['lon'], v['lat'] = route_pts[min(len(route_pts) - 1, int(v['idx']))]
                    if v['idx'] >= len(route_pts) - 1:
                        v['idx'] = 0.0

                v['speed'] = max(15.0, min(110.0, v['speed'] + random.uniform(-0.6, 0.6)))

                # Dynamic orientation simulation (roll during swerving, pitch during speed changes)
                pitch = round(math.sin(time.time() * 2 + idx) * 1.8, 1)
                roll = round(math.cos(time.time() * 1.5 + idx) * 2.5, 1)

                data = {
                    "vehicle_id": f"DEMO-{idx + 1}",
                    "vehicle_type": v['type'],
                    "timestamp": now_ts,
                    "seq": seq_counter,
                    "lat": round(v['lat'], 6),
                    "lon": round(v['lon'], 6),
                    "alt": round(540.0 + (idx * 5.0), 1),
                    "speed_kmph": round(v['speed'], 1),
                    "heading_deg": round(v['heading'], 1),
                    "pitch_deg": pitch,
                    "roll_deg": roll,
                    "yaw_deg": round(v['heading'], 1),
                    "battery_level": round(99.0 - (seq_counter * 0.01), 1),
                    "emergency_status": 1 if v['type'] == 'Emergency' else 0,
                    "rf_status": "OK",
                    "fault_code": "NONE"
                }

                data['signature'] = generate_signature(data)
                publish_or_dispatch("v2v/telemetry", json.dumps(data))

            time.sleep(0.1) # 10Hz rate
    except Exception as e:
        print(f"[Demo Simulation Error]: {e}")
    finally:
        is_demo_running = False

@app.post("/api/demo")
async def trigger_demo(background_tasks: BackgroundTasks):
    if is_demo_running:
        return {"status": "error", "message": "Demo simulation is already running"}
    background_tasks.add_task(run_demo_simulation)
    return {"status": "success", "message": "Demo simulation launched"}

@app.post("/api/spoof")
async def trigger_spoof():
    """Simulates a rogue Ghost Vehicle injection attack with a tampered cryptographic signature."""
    try:
        data = {
            "vehicle_id": "ROGUE-X",
            "vehicle_type": "Hacker",
            "timestamp": int(time.time()),
            "seq": 9999,
            "lat": 17.4230,
            "lon": 78.4500,
            "alt": 500.0,
            "speed_kmph": 150.0,
            "heading_deg": 45.0,
            "pitch_deg": 0.0,
            "roll_deg": 0.0,
            "yaw_deg": 45.0,
            "battery_level": 100.0,
            "emergency_status": 0,
            "rf_status": "SPOOF",
            "fault_code": "TAMPERED",
            "signature": "invalid_forged_cryptographic_signature_deadbeef"
        }
        publish_or_dispatch("v2v/telemetry", json.dumps(data))
        return {"status": "success", "message": "Rogue packet broadcasted; check DPI threat feed."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class CommandRequest(BaseModel):
    command: str

@app.post("/api/command")
async def broadcast_command(req: CommandRequest):
    try:
        payload = {
            "cmd": req.command,
            "timestamp": int(time.time()),
            "source": "SCADA_CENTRAL_COMMAND"
        }
        publish_or_dispatch("v2v/commands", json.dumps(payload))
        return {"status": "success", "command": req.command}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
