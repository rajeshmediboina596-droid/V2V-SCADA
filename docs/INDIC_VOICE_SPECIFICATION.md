# Multi-Indian-Language Voice Dispatch & Emergency Audio Specification

## 1. Overview
The V2V-SCADA platform integrates a multi-lingual driver-to-tollgate voice communications subsystem designed for multilingual highway environments across Indian corridors.

```
+---------------------------------------------------------------------------------------+
|  DRIVER HUD CONSOLE (WebRTC / Audio Streaming)                                         |
|  - Continuous Speech-to-Text (STT)                                                    |
|  - Automatic Script / Language Detection across 12 Indian Languages                   |
+---------------------------------------------------------------------------------------+
                                          |
                                          v
+---------------------------------------------------------------------------------------+
|  MULTI-TIER INDIC TRANSLATION ENGINE (backend/providers/translation.py)               |
|  - Tier 1: Emergency Automotive Phrase Lexicon (sub-5ms offline match)                |
|  - Tier 2: Neural Hybrid Translation Engine (Indic-to-Indic / English bridge)         |
|  - Tier 3: Offline Graceful Fallback Phrase Engine                                    |
+---------------------------------------------------------------------------------------+
                                          |
                                          v
+---------------------------------------------------------------------------------------+
|  SCADA DISPATCH CONSOLE                                                               |
|  - Real-time Bidirectional Text & Audio Stream                                         |
|  - Synthesized Speech Output (TTS) in Local Language                                  |
|  - Optional Privacy-Preserving Telemetry Dossier Share Modal                          |
+---------------------------------------------------------------------------------------+
```

## 2. Supported Languages (12 Regional Languages)
1. Telugu (`te`)
2. Hindi (`hi`)
3. Tamil (`ta`)
4. Kannada (`kn`)
5. Malayalam (`ml`)
6. Marathi (`mr`)
7. Bengali (`bn`)
8. Gujarati (`gu`)
9. Punjabi (`pa`)
10. Odia (`or`)
11. Assamese (`as`)
12. English (`en`)

## 3. Provider Abstraction Architecture (`backend/providers/`)
All voice services are configured through extensible interfaces in `backend/providers/`:
- `TelephonyProvider`: `WebRTCTelephonyProvider`, `TwilioTelephonyProvider`, `MockTelephonyProvider`.
- `SpeechToTextProvider`: `BrowserWebSpeechSTTProvider`, `GoogleSTTProvider`, `MockSTTProvider`.
- `TranslationProvider`: `MultiIndianTranslationEngine`.
- `TextToSpeechProvider`: `BrowserWebSpeechTTSProvider`, `GTTSProvider`, `MockTTSProvider`.

## 4. Privacy & Telemetry Dossier Sharing
Drivers can choose to transmit their telemetry state during emergency voice calls. The payload includes:
- Vehicle ID
- GPS Coordinates & Elevation
- Highway ID & Nearest Tollgate
- Emergency Status & Incident Type
Confirmation is required prior to sharing.
