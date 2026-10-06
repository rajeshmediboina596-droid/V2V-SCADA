from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class TelephonyProvider(ABC):
    """
    Abstract interface for real-time voice communications.
    Isolates in-browser WebRTC, local mock channels, and external PSTN/SIP providers (Twilio/Exotel).
    """

    @abstractmethod
    async def initiate_call(self, call_id: str, caller_id: str, recipient_id: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Initiate voice session between driver and tollgate operator/emergency center."""
        pass

    @abstractmethod
    async def terminate_call(self, call_id: str, reason: str = "User Ended") -> Dict[str, Any]:
        """Terminate active voice communication session."""
        pass

    @abstractmethod
    async def get_call_status(self, call_id: str) -> Dict[str, Any]:
        """Return real-time voice channel connectivity status."""
        pass


class SpeechToTextProvider(ABC):
    """
    Abstract interface for Speech-to-Text (STT) and Automatic Speech Recognition (ASR).
    Supports client-side Web Speech API streaming, mock simulation, and cloud ASR (Whisper/Google).
    """

    @abstractmethod
    async def transcribe_audio_chunk(self, audio_data: bytes, language_hint: Optional[str] = None) -> Dict[str, Any]:
        """Transcribe streaming or buffered audio chunk to text with language hint."""
        pass

    @abstractmethod
    async def detect_spoken_language(self, audio_data: bytes) -> str:
        """Detect the spoken language code from an audio stream or sample."""
        pass


class TranslationProvider(ABC):
    """
    Abstract interface for Multi-Indian-Language Translation Engine.
    Converts source language text to target language with auto-detection.
    """

    @abstractmethod
    async def translate(self, text: str, source_lang: str, target_lang: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Translates text from source_lang to target_lang.
        If source_lang == 'auto', performs automatic language detection first.
        """
        pass

    @abstractmethod
    async def detect_language(self, text: str) -> str:
        """Automatically identify Indian language code from text."""
        pass

    @abstractmethod
    def get_supported_languages(self) -> Dict[str, str]:
        """Return mapping of language code to display name."""
        pass


class TextToSpeechProvider(ABC):
    """
    Abstract interface for Text-to-Speech (TTS) audio synthesis.
    Outputs audio format or synthesis descriptors for remote playback.
    """

    @abstractmethod
    async def synthesize_speech(self, text: str, language: str, speaker_voice: Optional[str] = None) -> Dict[str, Any]:
        """Synthesize text into speech audio or browser playback tokens."""
        pass
