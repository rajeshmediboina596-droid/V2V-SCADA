"""
V2V-SCADA Provider Abstraction Layer
Modular interfaces for Telephony, Speech-to-Text, Translation, and Text-to-Speech.
"""
from backend.providers.base import (
    TelephonyProvider,
    SpeechToTextProvider,
    TranslationProvider,
    TextToSpeechProvider
)
from backend.providers.factory import (
    get_telephony_provider,
    get_stt_provider,
    get_translation_provider,
    get_tts_provider
)

__all__ = [
    "TelephonyProvider",
    "SpeechToTextProvider",
    "TranslationProvider",
    "TextToSpeechProvider",
    "get_telephony_provider",
    "get_stt_provider",
    "get_translation_provider",
    "get_tts_provider"
]
