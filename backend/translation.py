import time
import uuid
import asyncio
from typing import Dict, Any, Optional
from backend.providers.translation import MultiIndianTranslationEngine, INDIAN_LANGUAGES, EMERGENCY_LEXICON
from backend.database import log_translation

SUPPORTED_LANGUAGES = {code: f"{data['name']} ({data['native']})" for code, data in INDIAN_LANGUAGES.items()}

_engine = MultiIndianTranslationEngine(mode="hybrid")

def translate_message(text: str, source_lang: str, target_lang: str, speaker_type: str = "Driver", session_id: str = None) -> dict:
    """
    Translates text across all supported Indian languages.
    Ensures zero internet dependency for critical communications.
    """
    if not session_id:
        session_id = f"SES-{int(time.time())}-{uuid.uuid4().hex[:6]}"

    try:
        # Run async translation in event loop or synchronously
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # In active loop, create task or run directly
                task = _engine.translate(text, source_lang, target_lang)
                res = asyncio.run_coroutine_threadsafe(task, loop).result(timeout=2.5)
            else:
                res = loop.run_until_complete(_engine.translate(text, source_lang, target_lang))
        except RuntimeError:
            res = asyncio.run(_engine.translate(text, source_lang, target_lang))

        translated = res.get("translated_text", text)
        engine_used = res.get("engine", "hybrid")
    except Exception as e:
        print(f"[Translation Engine Warning]: {e}")
        translated = text
        engine_used = "Offline Fallback"

    # Log to database for auditing
    try:
        log_translation(session_id, source_lang, target_lang, speaker_type, text, translated)
    except Exception as e:
        print(f"[Translation Log Error]: {e}")

    return {
        "session_id": session_id,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "speaker_type": speaker_type,
        "original_text": text,
        "translated_text": translated,
        "engine": engine_used,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }
