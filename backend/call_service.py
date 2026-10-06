import time
import uuid
import json
import asyncio
from typing import Dict, Any, Optional, Set
from fastapi import WebSocket

from backend.database import (
    create_call_record,
    update_call_status,
    get_call_record,
    add_call_participant,
    get_call_participants,
    create_translation_session,
    log_call_message,
    get_call_messages,
    log_translation_event,
    get_tollgates
)
from backend.providers.factory import (
    get_telephony_provider,
    get_stt_provider,
    get_translation_provider,
    get_tts_provider
)
from backend.mqtt_client import vehicle_states

class CallManager:
    """
    Central Coordinator for Voice Calls, WebRTC/WebSocket Media,
    and Real-Time Multi-Indian-Language Translation.
    """

    def __init__(self):
        self.active_calls: Dict[str, Dict[str, Any]] = {}
        self.call_sockets: Dict[str, Set[WebSocket]] = {}
        self.lock = asyncio.Lock()

    def register_socket(self, call_id: str, ws: WebSocket):
        if call_id not in self.call_sockets:
            self.call_sockets[call_id] = set()
        self.call_sockets[call_id].add(ws)

    def unregister_socket(self, call_id: str, ws: WebSocket):
        if call_id in self.call_sockets and ws in self.call_sockets[call_id]:
            self.call_sockets[call_id].remove(ws)
            if not self.call_sockets[call_id]:
                del self.call_sockets[call_id]

    async def broadcast_to_call(self, call_id: str, message: Dict[str, Any]):
        sockets = self.call_sockets.get(call_id, set())
        dead_sockets = set()
        for ws in list(sockets):
            try:
                await ws.send_json(message)
            except Exception:
                dead_sockets.add(ws)
        for dead in dead_sockets:
            if dead in sockets:
                sockets.remove(dead)

    async def start_call(
        self,
        vehicle_id: str,
        tollgate_id: str,
        driver_lang: str = "te",
        operator_lang: str = "hi",
        incident_type: str = "General Emergency",
        emergency_info_shared: bool = False
    ) -> Dict[str, Any]:
        """
        Initiates a continuous emergency voice call between driver and tollgate operator.
        """
        async with self.lock:
            call_id = f"CALL-{int(time.time())}-{uuid.uuid4().hex[:4].upper()}"
            session_id = f"SES-{call_id}"

            # Look up vehicle telemetry
            v_telemetry = vehicle_states.get(vehicle_id, {})
            v_lat = v_telemetry.get("lat", 17.4239)
            v_lon = v_telemetry.get("lon", 78.4483)

            # Look up tollgate information
            tollgate_info = None
            for tg in get_tollgates():
                if tg["tollgate_id"] == tollgate_id:
                    tollgate_info = tg
                    break

            if not tollgate_info:
                tollgate_info = {
                    "tollgate_id": tollgate_id,
                    "tollgate_name": "Highway Smart Toll Plaza",
                    "highway_name": "NH-65 Highway Corridor",
                    "toll_phone": "+91-40-23548888",
                    "emergency_phone": "1033"
                }

            # Persist call in database
            create_call_record(
                call_id=call_id,
                vehicle_id=vehicle_id,
                tollgate_id=tollgate_id,
                driver_lang=driver_lang,
                operator_lang=operator_lang,
                incident_type=incident_type,
                emergency_info_shared=1 if emergency_info_shared else 0
            )

            # Add initial participants
            add_call_participant(call_id, "Driver", driver_lang, "In-Vehicle SCADA Mic")
            add_call_participant(call_id, "Tollgate Operator", operator_lang, "Toll Plaza Intercom")

            # Create translation session
            create_translation_session(session_id, call_id, driver_lang, operator_lang)

            # Connect voice communication channel via TelephonyProvider
            telephony = get_telephony_provider()
            telephony_res = await telephony.initiate_call(
                call_id=call_id,
                caller_id=vehicle_id,
                recipient_id=tollgate_info.get("toll_phone", "1033"),
                metadata={
                    "vehicle_id": vehicle_id,
                    "tollgate_id": tollgate_id,
                    "incident_type": incident_type,
                    "driver_lang": driver_lang,
                    "operator_lang": operator_lang
                }
            )

            # Log audit event
            log_translation_event(call_id, "CALL_START", f"Call started for {vehicle_id} -> {tollgate_id}")

            call_data = {
                "call_id": call_id,
                "session_id": session_id,
                "status": "CALL ACTIVE",
                "vehicle_id": vehicle_id,
                "tollgate_id": tollgate_id,
                "tollgate_name": tollgate_info.get("tollgate_name", "Toll Plaza"),
                "highway_name": tollgate_info.get("highway_name", "NH-65"),
                "toll_phone": tollgate_info.get("toll_phone", ""),
                "driver_lang": driver_lang,
                "operator_lang": operator_lang,
                "incident_type": incident_type,
                "emergency_info_shared": emergency_info_shared,
                "vehicle_location": f"{v_lat:.4f}° N, {v_lon:.4f}° E",
                "start_time": time.time(),
                "muted": False,
                "telephony_status": telephony_res.get("status", "ACTIVE")
            }

            self.active_calls[call_id] = call_data
            return call_data

    async def end_call(self, call_id: str, reason: str = "Call Completed Normally") -> Dict[str, Any]:
        """Terminates active voice call and archives records."""
        async with self.lock:
            active = self.active_calls.pop(call_id, None)
            duration_sec = 0.0
            if active:
                duration_sec = round(time.time() - active.get("start_time", time.time()), 1)

            # Update DB
            update_call_status(call_id, "ENDED", end_time=time.time())

            # Notify telephony provider
            telephony = get_telephony_provider()
            await telephony.terminate_call(call_id, reason=reason)

            # Log event
            log_translation_event(call_id, "CALL_END", f"Call ended. Duration: {duration_sec}s. Reason: {reason}")

            response = {
                "status": "CALL ENDED",
                "call_id": call_id,
                "duration_sec": duration_sec,
                "reason": reason
            }

            # Broadcast call termination to any listeners
            await self.broadcast_to_call(call_id, {
                "type": "call_ended",
                "data": response
            })

            return response

    async def get_call_summary(self, call_id: str) -> Optional[Dict[str, Any]]:
        record = get_call_record(call_id)
        if not record:
            return None

        participants = get_call_participants(call_id)
        messages = get_call_messages(call_id, limit=100)

        active = self.active_calls.get(call_id)
        v_telemetry = vehicle_states.get(record.get("vehicle_id", ""), {})

        return {
            "call_id": call_id,
            "status": "CALL ACTIVE" if active else record.get("status", "ENDED"),
            "vehicle_id": record.get("vehicle_id"),
            "tollgate_id": record.get("tollgate_id"),
            "tollgate_name": record.get("tollgate_name"),
            "highway_name": record.get("highway_name"),
            "driver_lang": record.get("driver_lang"),
            "operator_lang": record.get("operator_lang"),
            "incident_type": record.get("incident_type"),
            "emergency_info_shared": bool(record.get("emergency_info_shared", 0)),
            "start_time": record.get("start_time"),
            "end_time": record.get("end_time"),
            "participants": participants,
            "messages": messages,
            "vehicle_telemetry": {
                "speed_kmph": v_telemetry.get("speed_kmph", 0),
                "heading_deg": v_telemetry.get("heading_deg", 0),
                "lat": v_telemetry.get("lat", 17.4239),
                "lon": v_telemetry.get("lon", 78.4483),
                "emergency_status": v_telemetry.get("emergency_status", 0)
            }
        }

    async def process_speech_turn(
        self,
        call_id: str,
        sender_role: str,
        text: str,
        source_lang: str,
        target_lang: str,
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Translates real-time speech from driver or tollgate operator.
        Performs Auto-Language Detection -> Translation -> TTS Synthesis -> Audio Dispatch.
        """
        translation_eng = get_translation_provider()
        tts_eng = get_tts_provider()

        # 1. Translate utterance
        trans_res = await translation_eng.translate(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang
        )

        detected_lang = trans_res.get("detected_lang", source_lang)
        translated_text = trans_res.get("translated_text", text)
        engine_used = trans_res.get("engine", "hybrid")
        confidence = trans_res.get("confidence", 1.0)

        # 2. Synthesize speech for destination speaker
        tts_res = await tts_eng.synthesize_speech(
            text=translated_text,
            language=target_lang
        )

        # 3. Store message in database
        msg_id = log_call_message(
            call_id=call_id,
            session_id=session_id or f"SES-{call_id}",
            sender_role=sender_role,
            source_lang=source_lang,
            detected_lang=detected_lang,
            target_lang=target_lang,
            original_text=text,
            translated_text=translated_text,
            confidence=confidence,
            engine=engine_used,
            status="Delivered"
        )

        payload = {
            "type": "speech_turn",
            "data": {
                "message_id": msg_id,
                "call_id": call_id,
                "sender_role": sender_role,
                "source_lang": source_lang,
                "detected_lang": detected_lang,
                "target_lang": target_lang,
                "original_text": text,
                "translated_text": translated_text,
                "confidence": confidence,
                "engine": engine_used,
                "tts": tts_res,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }

        # 4. Broadcast live translation to both participants
        await self.broadcast_to_call(call_id, payload)
        return payload["data"]

    async def share_incident_dossier(self, call_id: str) -> Dict[str, Any]:
        """
        Shares verified vehicular incident telemetry with tollgate operator with driver confirmation.
        """
        record = get_call_record(call_id)
        if not record:
            return {"status": "error", "message": "Call not found"}

        vid = record.get("vehicle_id", "DEMO-1")
        telem = vehicle_states.get(vid, {})

        dossier = {
            "vehicle_id": vid,
            "gps_position": {
                "lat": telem.get("lat", 17.4239),
                "lon": telem.get("lon", 78.4483),
                "alt": telem.get("alt", 540.0)
            },
            "speed_kmph": telem.get("speed_kmph", 0.0),
            "heading_deg": telem.get("heading_deg", 0.0),
            "pitch_deg": telem.get("pitch_deg", 0.0),
            "roll_deg": telem.get("roll_deg", 0.0),
            "highway": record.get("highway_name", "NH-65 Corridor"),
            "nearest_tollgate": record.get("tollgate_name", "Toll Plaza"),
            "incident_type": record.get("incident_type", "Road Incident"),
            "emergency_status": "ACTIVE SOS" if telem.get("emergency_status") else "NORMAL",
            "collision_risk": "HIGH TTC ALARM" if telem.get("emergency_status") else "LOW",
            "battery_level": telem.get("battery_level", 95.0),
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
        }

        update_call_status(call_id, status="ACTIVE", emergency_info_shared=1)
        log_translation_event(call_id, "INCIDENT_SHARED", json.dumps(dossier))

        event = {
            "type": "incident_dossier_shared",
            "call_id": call_id,
            "dossier": dossier
        }
        await self.broadcast_to_call(call_id, event)
        return {
            "status": "transmitted",
            "transmission_status": "transmitted",
            "dossier": dossier,
            "telemetry_snapshot": dossier
        }

# Singleton instance
call_manager = CallManager()
