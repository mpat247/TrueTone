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
- Runs transcription (Whisper or whisper.cpp)
- Translates text using HuggingFace models
- Runs speaker embedding (Resemblyzer)
- Synthesizes translated speech (Coqui TTS + voice clone)
- Streams audio back to extension

### 3.3 ML Models
| Task | Model | Tool |
|------|-------|------|
| Transcription | Whisper (base/medium) | `whisper` or `whisper.cpp` |
| Translation | mBART, NLLB, M2M100 | `transformers` |
| Voice Embedding | Resemblyzer | `resemblyzer` |
| TTS | Coqui TTS | `TTS` library (multi-speaker support) |

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
   ├─> Voice Embedding (Resemblyzer)
   ├─> TTS Synthesis (Coqui)
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
- Extract speaker embedding from original speech
- Use cloned voice to synthesize translated speech
- Output must sync closely with video timeline

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
| Component | Test Type | Metric |
|-----------|-----------|--------|
| Audio Capture | Functional | Latency, buffering errors |
| Transcription | Accuracy Test | WER (Word Error Rate) |
| Translation | BLEU / Quality | Language correctness |
| Voice Cloning | Similarity | Cosine similarity of embeddings |
| Playback Sync | Integration | Audio/video drift tolerance < 1s |

## 📁 Dependencies
- `fastapi`, `uvicorn`
- `whisper` or `whisper.cpp`
- `transformers`, `sentencepiece`
- `resampy`, `resemblyzer`
- `TTS` (Coqui)
- `pyaudio`, `ffmpeg`
- Chrome Extension APIs (Manifest v3)

## 🔄 Future Enhancements
- Subtitle generation with original + translated captions
- Support for multi-speaker separation
- Integration with Twitch, Vimeo, or custom HTML5 players
- Offline mode using quantized models
- i18n UI for global users

## 🔚 Deliverables
- Chrome extension (`.zip` or GitHub repo)
- FastAPI backend service (`main.py`)
- Preconfigured models and sample audio
- Usage guide and README.md

---

**Author**: Manav Patel  
**Project**: TrueTone  
**Version**: v1.0  
**Last Updated**: July 4, 2025
