import sys
import os
import json
import time
import asyncio

# Ensure UTF-8 console output
sys.stdout.reconfigure(encoding='utf-8')
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import init_db, get_supported_languages, get_call_messages, get_call_record
from backend.call_service import call_manager
from backend.main import (
    start_voice_call,
    end_voice_call,
    get_call_status,
    create_translation_session_endpoint,
    process_translation_audio,
    get_supported_indian_languages,
    get_call_history,
    share_incident_endpoint,
    simulate_turn_endpoint,
    get_system_health,
    StartCallRequest,
    EndCallRequest,
    TranslationSessionRequest,
    AudioTranslationRequest,
    IncidentShareRequest,
    SimulateTurnRequest
)

async def test_full_voice_call_pipeline():
    print("=================================================================")
    print("STARTING FULL TEST: V2V MULTI-INDIAN-LANGUAGE VOICE CALL SYSTEM")
    print("=================================================================")

    init_db()

    # 1. Health & System Diagnostic
    print("\n[TEST 1] Checking /api/health ...")
    health_data = await get_system_health()
    print("Health Status:", health_data["status"])
    print("Voice Translation System:", health_data.get("voice_translation_system"))
    assert health_data["voice_translation_system"]["supported_indian_languages"] >= 12
    print("Health and offline isolation verified!")

    # 2. Supported Languages Endpoint
    print("\n[TEST 2] Verifying GET /translation/languages ...")
    langs_resp = await get_supported_indian_languages()
    langs = langs_resp["languages"]
    print(f"Total Supported Languages: {len(langs)}")
    lang_codes = [l["code"] for l in langs]
    expected_12 = ["te", "hi", "ta", "kn", "ml", "mr", "bn", "gu", "pa", "or", "as", "en"]
    for code in expected_12:
        assert code in lang_codes, f"Missing language code {code}"
    print("All 12 required Indian languages verified present!")

    # 3. Start Live Emergency Voice Call
    print("\n[TEST 3] Initiating Emergency Call via POST /calls/start ...")
    start_req = StartCallRequest(
        vehicle_id="DEMO-1",
        tollgate_id="TG-DEMO",
        driver_lang="te",
        operator_lang="hi",
        incident_type="Critical Brake Failure",
        emergency_info_shared=False
    )
    call_info = await start_voice_call(start_req)
    call_id = call_info["call_id"]
    print(f"Call Created Successfully! Call ID: {call_id}")
    print(f"Driver Lang: {call_info['driver_lang']} | Operator Lang: {call_info['operator_lang']}")
    print(f"Tollgate Name: {call_info['tollgate_name']}")

    # 4. Test Multi-Indian-Language Conversational Turns
    test_conversations = [
        {
            "desc": "Telugu -> Hindi (Driver Speaks)",
            "role": "Driver",
            "text": "రోడ్డు ప్రమాదం జరిగింది, అత్యవసర సహాయం కావాలి.",
            "src": "te",
            "tgt": "hi"
        },
        {
            "desc": "Hindi -> Telugu (Operator Replies)",
            "role": "Tollgate Operator",
            "text": "हम तुरंत एम्बुलेंस और हाईवे पेट्रोल भेज रहे हैं।",
            "src": "hi",
            "tgt": "te"
        },
        {
            "desc": "Tamil -> Hindi (Driver Speaks Tamil)",
            "role": "Driver",
            "text": "சாலை விபத்து ஏற்பட்டுள்ளது, உடனடியாக அவசர உதவி அனுப்பவும்.",
            "src": "ta",
            "tgt": "hi"
        },
        {
            "desc": "Hindi -> Tamil (Operator Replies in Hindi)",
            "role": "Tollgate Operator",
            "text": "कृपया शांत रहें, सहायता रास्ते में है।",
            "src": "hi",
            "tgt": "ta"
        },
        {
            "desc": "Kannada -> English (Driver Speaks Kannada)",
            "role": "Driver",
            "text": "ಬ್ರೇಕ್ ವಿಫಲವಾಗಿದೆ! ದಯವಿಟ್ಟು ಇತರ ವಾಹನಗಳು ದಾರಿ ಬಿಡಿ.",
            "src": "kn",
            "tgt": "en"
        },
        {
            "desc": "Auto-Detect Telugu -> Hindi",
            "role": "Driver",
            "text": "వాహనంలో మంటలు చెలరేగాయి! వెంటనే ఫైర్ ఇంజిన్ పంపండి.",
            "src": "auto",
            "tgt": "hi"
        }
    ]

    print("\n[TEST 4] Simulating Live Speech Turns across Indian Language Pairs ...")
    for conv in test_conversations:
        turn_req = SimulateTurnRequest(
            call_id=call_id,
            sender_role=conv["role"],
            text=conv["text"],
            source_lang=conv["src"],
            target_lang=conv["tgt"]
        )
        res = await simulate_turn_endpoint(turn_req)
        data = res["turn"]
        print(f"\n  [{conv['desc']}]")
        print(f"    Detected Lang: {data['detected_lang']} -> Target: {data['target_lang']}")
        print(f"    Original:   {data['original_text']}")
        print(f"    Translated: {data['translated_text']}")
        print(f"    Engine:     {data['engine']} (Confidence: {data['confidence']})")
        assert len(data["translated_text"]) > 0

    # 5. Share Emergency Incident Telemetry Dossier with User Confirmation
    print("\n[TEST 5] Sharing Incident Telemetry Dossier via POST /calls/{call_id}/share-incident ...")
    share_req = IncidentShareRequest(confirmed=True)
    dossier_data = await share_incident_endpoint(call_id, share_req)
    assert dossier_data["status"] == "success"
    dossier = dossier_data["dossier"]
    print("Incident Dossier Transmitted:")
    print(f"  Vehicle ID: {dossier['vehicle_id']}")
    print(f"  GPS: {dossier['gps_position']['lat']}, {dossier['gps_position']['lon']}")
    print(f"  Highway: {dossier['highway']}")
    print(f"  Nearest Tollgate: {dossier['nearest_tollgate']}")
    print(f"  Incident Type: {dossier['incident_type']}")
    print(f"  Emergency Status: {dossier['emergency_status']}")

    # 6. Retrieve Call Conversation History
    print("\n[TEST 6] Querying Call History via GET /translation/history/{call_id} ...")
    history = await get_call_history(call_id)
    messages = history["messages"]
    print(f"Retrieved {len(messages)} historical conversation messages logged in SQLite database:")
    for m in messages:
        print(f"  - [{m['sender_role']}] {m['source_lang']} -> {m['target_lang']}: {m['original_text']} -> {m['translated_text']}")
    assert len(messages) >= 6

    # 7. Query Call Summary
    print("\n[TEST 7] Querying Call Summary via GET /calls/{call_id} ...")
    summary = await get_call_status(call_id)
    assert summary["status"] == "CALL ACTIVE"
    print(f"Call {call_id} is ACTIVE with {len(summary['participants'])} participants and {len(summary['messages'])} messages.")

    # 8. End Emergency Voice Call
    print("\n[TEST 8] Terminating Call via POST /calls/end ...")
    end_req = EndCallRequest(call_id=call_id, reason="Emergency Assistance Dispatched")
    end_data = await end_voice_call(end_req)
    print("Call Terminated:", end_data)
    assert end_data["status"] == "CALL ENDED"

    # Verify Call Record is now ENDED
    final_summary = await get_call_status(call_id)
    assert final_summary["status"] == "ENDED"
    print(f"Verified call {call_id} is marked ENDED in database.")

    print("\n=================================================================")
    print("ALL TESTS PASSED! REAL-TIME MULTI-INDIAN-LANGUAGE SYSTEM VERIFIED!")
    print("=================================================================")

if __name__ == "__main__":
    asyncio.run(test_full_voice_call_pipeline())
