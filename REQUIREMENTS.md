# TrueTone Requirements Specification

## 📄 Project Overview

TrueTone is a Chrome extension + Python backend system that enables real-time translation of YouTube videos into a user-selected target language, while preserving the original speaker's voice characteristics (pitch, tone, rhythm).

## 🎯 Objectives

- Capture YouTube audio in real-time from any open tab
- Transcribe speech to text using Whisper (locally or via server)
- Translate transcribed text to target language using HuggingFace models
- Clone original speaker's voice to synthesize translated speech
- Play back translated, voice-preserved audio in sync with original video

## 🧩 System Components

### 3.1 Chrome Extension (Frontend)

- Injects into YouTube tabs
- Captures tab audio (Web Audio API)
- Provides UI to:
  - Enable/disable translation
  - Select target language
  - Adjust volume/sync
  - Toggle speaker cloning on/off
- Sends audio to backend via WebSocket or REST

### 3.2 Python Backend (FastAPI)

- Receives audio stream
- Runs transcription (Whisper)
- Translates text using HuggingFace models
- Performs voice cloning
- Synthesizes translated speech (TTS-Mozilla + voice clone)
- Streams audio back to extension

### 3.3 ML Models

| Task          | Model                 | Tool                                            |
| ------------- | --------------------- | ----------------------------------------------- |
| Transcription | Whisper (base/medium) | `whisper`                                       |
| Translation   | mBART, NLLB, M2M100   | `transformers`                                  |
| TTS           | Under evaluation      | TBD (evaluating Python 3.12 compatible options) |

## 📐 Architecture Flow

```
[YouTube Tab]
   |
[Chrome Extension]
   ├─> Captures audio
   └─> Sends audio chunks to FastAPI backend

[FastAPI Backend]
   ├─> Transcribe (Whisper)
   ├─> Translate (HuggingFace)
   ├─> Voice Cloning & TTS (TTS-Mozilla)
   └─> Stream translated audio back

[Chrome Extension]
   └─> Plays translated audio over muted or dimmed original audio
```

## ⚙️ Functional Requirements

### 5.1 Audio Capture

- Real-time tab audio capture
- Compatible with YouTube player
- Adjustable buffer size (e.g., 2–5 seconds)

### 5.2 Transcription

- Segment audio stream into chunks
- Use Whisper for accurate, multilingual transcription
- Output timestamps for each segment

### 5.3 Translation

- Use transformer-based models
- Maintain formatting and casing
- Match translated segment duration to original

### 5.4 Voice Cloning + TTS

- Extract voice characteristics from original speech
- Implement voice cloning for natural-sounding translation
- Output must sync closely with video timeline
- TTS solution must support Python 3.12
- Support for cross-lingual voice preservation

### 5.5 Playback and UI

- Overlay translated audio
- Let user toggle between original/translated audio
- Sync translated audio to video using timestamps

## 🔒 Non-Functional Requirements

- Low latency: end-to-end lag < 3s for smooth UX
- Cross-browser support (Chrome; future: Firefox)
- Works offline if all models are bundled (future goal)
- Scalable architecture (modular pipelines)
- Maintain original voice quality above 85% similarity

## 🧪 Testing Plan

| Component     | Test Type      | Metric                           |
| ------------- | -------------- | -------------------------------- |
| Audio Capture | Functional     | Latency, buffering errors        |
| Transcription | Accuracy Test  | WER (Word Error Rate)            |
| Translation   | BLEU / Quality | Language correctness             |
| Voice Cloning | Similarity     | Perceived voice similarity       |
| Playback Sync | Integration    | Audio/video drift tolerance < 1s |

## 📁 Dependencies

The following dependencies are required and specified in requirements.txt:

### Core Backend

- `fastapi`, `uvicorn`, `websockets`
- `python-multipart`, `python-dotenv`, `pydantic`

### Audio Processing

- `numpy`, `soundfile`, `librosa`, `resampy`
- `webrtcvad`, `ffmpeg-python`

### ML Models

- `torch`, `torchaudio`
- `transformers`, `sentencepiece`
- `openai-whisper`

### Voice Synthesis

- TBD (evaluating options for Python 3.12 compatibility)

### Optional Dependencies

- `pyaudio` (for microphone input if needed)

## 🔄 Future Enhancements

- Subtitle generation with original + translated captions
- Support for multi-speaker separation
- Integration with Twitch, Vimeo, or custom HTML5 players
- Offline mode using quantized models
- i18n UI for global users

## 🔚 Deliverables

- Chrome extension (`.zip` or GitHub repo)
- FastAPI backend service (`main.py`)
- Voice synthesis module (`tts_mozilla_synthesis.py`)
- Preconfigured models and sample audio
- Usage guide and comprehensive documentation

---

**Project**: TrueTone  
**Version**: v1.0.5  
**Last Updated**: July 6, 2025
