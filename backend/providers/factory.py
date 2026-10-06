import os
from backend.config import STT_PROVIDER, TRANSLATION_PROVIDER, TTS_PROVIDER, TELEPHONY_PROVIDER
from backend.providers.base import (
    TelephonyProvider,
    SpeechToTextProvider,
    TranslationProvider,
    TextToSpeechProvider
)
from backend.providers.telephony import (
    WebRTCTelephonyProvider,
    MockTelephonyProvider,
    TwilioTelephonyProvider
)
from backend.providers.stt import (
    BrowserWebSpeechSTTProvider,
    MockSTTProvider,
    GoogleSTTProvider
)
from backend.providers.translation import MultiIndianTranslationEngine
from backend.providers.tts import (
    BrowserWebSpeechTTSProvider,
    MockTTSProvider,
    GTTSProvider
)

_telephony_instance = None
_stt_instance = None
_translation_instance = None
_tts_instance = None

def get_telephony_provider() -> TelephonyProvider:
    global _telephony_instance
    if _telephony_instance is None:
        choice = (TELEPHONY_PROVIDER or "webrtc_scada").lower()
        if choice in ("webrtc", "webrtc_scada", "browser"):
            _telephony_instance = WebRTCTelephonyProvider()
        elif choice in ("mock", "sim"):
            _telephony_instance = MockTelephonyProvider()
        elif choice in ("twilio", "pstn"):
            _telephony_instance = TwilioTelephonyProvider()
        else:
            _telephony_instance = WebRTCTelephonyProvider()
    return _telephony_instance

def get_stt_provider() -> SpeechToTextProvider:
    global _stt_instance
    if _stt_instance is None:
        choice = (STT_PROVIDER or "browser_speech").lower()
        if choice in ("browser", "browser_speech", "webspeech"):
            _stt_instance = BrowserWebSpeechSTTProvider()
        elif choice in ("mock", "sim"):
            _stt_instance = MockSTTProvider()
        elif choice in ("google", "whisper"):
            _stt_instance = GoogleSTTProvider()
        else:
            _stt_instance = BrowserWebSpeechSTTProvider()
    return _stt_instance

def get_translation_provider() -> TranslationProvider:
    global _translation_instance
    if _translation_instance is None:
        choice = (TRANSLATION_PROVIDER or "hybrid").lower()
        _translation_instance = MultiIndianTranslationEngine(mode=choice)
    return _translation_instance

def get_tts_provider() -> TextToSpeechProvider:
    global _tts_instance
    if _tts_instance is None:
        choice = (TTS_PROVIDER or "browser_speech").lower()
        if choice in ("browser", "browser_speech", "webspeech"):
            _tts_instance = BrowserWebSpeechTTSProvider()
        elif choice in ("mock", "sim"):
            _tts_instance = MockTTSProvider()
        elif choice in ("gtts", "cloud"):
            _tts_instance = GTTSProvider()
        else:
            _tts_instance = BrowserWebSpeechTTSProvider()
    return _tts_instance
