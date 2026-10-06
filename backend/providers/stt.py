import asyncio
import time
from typing import Dict, Any, Optional
from backend.providers.base import SpeechToTextProvider

class BrowserWebSpeechSTTProvider(SpeechToTextProvider):
    """
    Standard in-browser Web Speech API STT provider.
    Transcribes spoken voice in real time with zero external server dependencies,
    streaming continuous partial and final transcripts for any of the 12 Indian languages.
    """

    async def transcribe_audio_chunk(self, audio_data: bytes, language_hint: Optional[str] = None) -> Dict[str, Any]:
        return {
            "status": "STREAMING",
            "provider": "Browser-WebSpeech-STT",
            "language_hint": language_hint or "auto",
            "bytes_received": len(audio_data) if audio_data else 0,
            "message": "Continuous streaming STT active via client audio interface."
        }

    async def detect_spoken_language(self, audio_data: bytes) -> str:
        # Client-side language detector passes detected BCP-47 tag
        return "auto"


class MockSTTProvider(SpeechToTextProvider):
    """
    Mock STT Provider for local demonstration and automated testing.
    Provides realistic highway emergency transcripts without a live microphone.
    """

    SAMPLE_UTTERANCES = {
        "te": [
            "రోడ్డు ప్రమాదం జరిగింది, అత్యవసర సహాయం పంపండి.",
            "బ్రేక్ విఫలమైంది! చుట్టుపక్కల వాహనాలు దయచేసి పక్కకు వెళ్లండి.",
            "టోల్‌గేట్ వద్ద సమస్య ఉంది, ఆపరేటర్ సహాయం కావాలి.",
            "టైరు పంక్చర్ అయింది, హైవే పెట్రోల్ సహాయం కావాలి."
        ],
        "hi": [
            "सड़क दुर्घटना हुई है, तत्काल आपातकालीन सहायता भेजें।",
            "ब्रेक फेल हो गया है! कृपया आसपास के वाहन रास्ता दें।",
            "टोल प्लाजा पर समस्या है, ऑपरेटर से बात करनी है।",
            "गाड़ी में आग लग गई है! कृपया तुरंत दमकल गाड़ी भेजें।"
        ],
        "ta": [
            "சாலை விபத்து ஏற்பட்டுள்ளது, உடனடியாக அவசர உதவி அனுப்பவும்.",
            "பிரேக் செயல் இழந்தது! சுற்றியுள்ள வாகனங்கள் விலகிச் செல்லவும்.",
            "சுங்கச்சாவடியில் சிக்கல் உள்ளது, ஆபரேட்டர் உதவி தேவை."
        ],
        "kn": [
            "ರಸ್ತೆ ಅಪಘಾತ ಸಂಭವಿಸಿದೆ, ತಕ್ಷಣ ತುರ್ತು ನೆರವು ಕಳುಹಿಸಿ.",
            "ಬ್ರೇಕ್ ವಿಫಲವಾಗಿದೆ! ದಯವಿಟ್ಟು ಇತರ ವಾಹನಗಳು ದಾರಿ ಬಿಡಿ."
        ],
        "en": [
            "Accident reported on NH-65 corridor, dispatch rescue team.",
            "Brake failure detected on vehicle, yielding to shoulder lane.",
            "Requesting toll booth clearance and operator support."
        ]
    }

    def __init__(self):
        self.counter = 0

    async def transcribe_audio_chunk(self, audio_data: bytes, language_hint: Optional[str] = "en") -> Dict[str, Any]:
        lang = language_hint or "en"
        samples = self.SAMPLE_UTTERANCES.get(lang, self.SAMPLE_UTTERANCES["en"])
        selected = samples[self.counter % len(samples)]
        self.counter += 1
        return {
            "transcript": selected,
            "confidence": 0.96,
            "is_final": True,
            "detected_lang": lang,
            "provider": "MockSTTProvider"
        }

    async def detect_spoken_language(self, audio_data: bytes) -> str:
        return "te"


class GoogleSTTProvider(SpeechToTextProvider):
    """
    Cloud Speech-to-Text provider stub (Whisper / Google Cloud Speech-to-Text v2).
    Isolates external ASR API so it can be swapped with self-hosted models (Vakyansh/AI4Bharat).
    """

    async def transcribe_audio_chunk(self, audio_data: bytes, language_hint: Optional[str] = None) -> Dict[str, Any]:
        return {
            "transcript": "Audio buffer received for cloud ASR",
            "confidence": 0.90,
            "is_final": True,
            "detected_lang": language_hint or "hi",
            "provider": "GoogleSTTProvider (Cloud Adapter)"
        }

    async def detect_spoken_language(self, audio_data: bytes) -> str:
        return "hi"
