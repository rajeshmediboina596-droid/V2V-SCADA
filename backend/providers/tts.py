import asyncio
from typing import Dict, Any, Optional
from backend.providers.base import TextToSpeechProvider

# Mapping language code to default BCP-47 speech synthesis tag
BCP47_MAPPING = {
    "te": "te-IN",
    "hi": "hi-IN",
    "ta": "ta-IN",
    "kn": "kn-IN",
    "ml": "ml-IN",
    "mr": "mr-IN",
    "bn": "bn-IN",
    "gu": "gu-IN",
    "pa": "pa-IN",
    "or": "or-IN",
    "as": "as-IN",
    "en": "en-IN"
}

class BrowserWebSpeechTTSProvider(TextToSpeechProvider):
    """
    Client-side Web Speech Synthesis (SpeechSynthesis API).
    Plays natural synthesized audio directly in the listener's ear/speaker in real time.
    """

    async def synthesize_speech(self, text: str, language: str, speaker_voice: Optional[str] = None) -> Dict[str, Any]:
        bcp47 = BCP47_MAPPING.get(language, "en-IN")
        return {
            "mode": "client_speech_synthesis",
            "text": text,
            "language": language,
            "bcp47": bcp47,
            "rate": 1.0,
            "pitch": 1.0,
            "provider": "Browser-SpeechSynthesis"
        }


class MockTTSProvider(TextToSpeechProvider):
    """
    Mock TTS Provider for automated CI/CD and simulation testing.
    """

    async def synthesize_speech(self, text: str, language: str, speaker_voice: Optional[str] = None) -> Dict[str, Any]:
        return {
            "mode": "mock_audio",
            "text": text,
            "language": language,
            "audio_duration_sec": round(len(text) * 0.08, 2),
            "provider": "MockTTSProvider"
        }


class GTTSProvider(TextToSpeechProvider):
    """
    gTTS (Google Text-to-Speech) adapter for server-side audio file delivery.
    """

    async def synthesize_speech(self, text: str, language: str, speaker_voice: Optional[str] = None) -> Dict[str, Any]:
        bcp47 = BCP47_MAPPING.get(language, "en-IN")
        return {
            "mode": "server_gtts_stream",
            "text": text,
            "language": language,
            "bcp47": bcp47,
            "provider": "GTTS-Cloud-Adapter"
        }
