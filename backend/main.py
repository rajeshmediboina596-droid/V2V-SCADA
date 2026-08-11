from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
import asyncio
import os
import sys

# Ensure backend can import other modules by adding project root to sys.path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.mqtt_client import start_mqtt_client, message_queue
from backend.database import init_db
from backend.report_generator import generate_pdf_report

app = FastAPI(title="V2V SCADA Dashboard")

# Security: CORS and Headers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, lock this down to specific domains
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

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, 'frontend')

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
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        connected_clients.remove(websocket)

@app.post("/api/report")
async def generate_report():
    filepath = generate_pdf_report()
    filename = os.path.basename(filepath)
    return {"status": "success", "file": filename}

@app.get("/api/download/{filename}")
async def download_report(filename: str):
    filepath = os.path.join(BASE_DIR, 'reports', filename)
    if os.path.exists(filepath):
        return FileResponse(filepath, media_type='application/pdf', filename=filename)
    return {"error": "File not found"}

import time
import json
import hmac
import hashlib
import paho.mqtt.client as mqtt_lib

is_demo_running = False

def run_demo_simulation():
    global is_demo_running
    if is_demo_running:
        return
    is_demo_running = True
    
    client = mqtt_lib.Client()
    try:
        client.connect("localhost", 1883, 60)
        
        # Load OSRM routes for road-snapping
        try:
            with open('backend/routes.json', 'r') as f:
                routes = json.load(f)
        except Exception as e:
            print(f"OSRM routes not found: {e}")
            routes = None

        v1 = {"idx": 0.0, "speed": 40, "heading": 90, "type": "Passenger"}
        v2 = {"idx": 0.0, "speed": 45, "heading": 270, "type": "Passenger"}
        v3 = {"idx": 0.0, "speed": 35, "heading": 0, "type": "Passenger"}
        v4 = {"idx": 0.0, "speed": 80, "heading": 180, "type": "Emergency"}
        
        # Fallback coords if no OSRM
        v1.update({"lat": 17.4239, "lon": 78.4400})
        v2.update({"lat": 17.4239, "lon": 78.4550})
        v3.update({"lat": 17.4180, "lon": 78.4483})
        v4.update({"lat": 17.4290, "lon": 78.4483})
        
        for i in range(600):
            dt = 0.1
            
            if routes:
                v1['idx'] += 0.15 # V1 speed
                v2['idx'] += 0.20 # V2 speed
                v3['idx'] += 0.12 # V3 speed
                v4['idx'] += 0.35 # V4 emergency high speed
                
                v1['lon'], v1['lat'] = routes['v1'][min(len(routes['v1'])-1, int(v1['idx']))]
                v2['lon'], v2['lat'] = routes['v2'][min(len(routes['v2'])-1, int(v2['idx']))]
                v3['lon'], v3['lat'] = routes['v3'][min(len(routes['v3'])-1, int(v3['idx']))]
                v4['lon'], v4['lat'] = routes['v4'][min(len(routes['v4'])-1, int(v4['idx']))]
            else:
                v1['lon'] += (v1['speed'] / 3600.0) * dt / 104.0
                v2['lon'] -= (v2['speed'] / 3600.0) * dt / 104.0
                v3['lat'] += (v3['speed'] / 3600.0) * dt / 111.0
                v4['lat'] -= (v4['speed'] / 3600.0) * dt / 111.0
            
            for idx, v in enumerate([v1, v2, v3, v4]):
                data = {
                    "vehicle_id": f"DEMO-{idx+1}",
                    "vehicle_type": v['type'],
                    "timestamp": int(time.time()),
                    "lat": round(v['lat'], 6),
                    "lon": round(v['lon'], 6),
                    "speed_kmph": round(v['speed'], 1),
                    "heading_deg": v['heading']
                }
                sign_str = f"{data['vehicle_id']}{data['vehicle_type']}{data['timestamp']}{data['lat']}{data['lon']}{data['speed_kmph']}{data['heading_deg']}"
                data['signature'] = hmac.new(b"v2v_shared_secret_123", sign_str.encode(), hashlib.sha256).hexdigest()
                
                client.publish("v2v/telemetry", json.dumps(data))
            time.sleep(0.1)
        client.disconnect()
    except Exception as e:
        print(f"Demo failed: {e}")
    finally:
        is_demo_running = False

@app.post("/api/demo")
async def trigger_demo(background_tasks: BackgroundTasks):
    if is_demo_running:
        return {"status": "error", "message": "Demo is already running"}
    background_tasks.add_task(run_demo_simulation)
    return {"status": "success"}

@app.post("/api/spoof")
async def trigger_spoof():
    client = mqtt_lib.Client()
    try:
        client.connect("localhost", 1883, 60)
        data = {
            "vehicle_id": "ROGUE-X",
            "vehicle_type": "Hacker",
            "timestamp": int(time.time()),
            "lat": 17.4230,
            "lon": 78.4500,
            "speed_kmph": 150.0,
            "heading_deg": 45,
            "signature": "invalid_fake_hacker_signature_99999"
        }
        client.publish("v2v/telemetry", json.dumps(data))
        client.disconnect()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

class CommandRequest(BaseModel):
    command: str

@app.post("/api/command")
async def broadcast_command(req: CommandRequest):
    client = mqtt_lib.Client()
    try:
        client.connect("localhost", 1883, 60)
        client.publish("v2v/commands", json.dumps({"cmd": req.command, "timestamp": int(time.time())}))
        client.disconnect()
        return {"status": "success"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
