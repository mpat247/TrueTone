# 🎵 TrueTone: Voice-Preserving YouTube Translator

**Real-time YouTube video translation that preserves the original speaker's voice characteristics**

## 📋 Project Overview

TrueTone is a Chrome extension + Python backend system that enables real-time translation of YouTube videos into any target language while maintaining the original speaker's voice pitch, tone, and rhythm.

### ✨ Key Features
- Real-time audio capture from YouTube tabs
- Accurate transcription using Whisper
- High-quality translation with HuggingFace models
- Voice cloning to preserve speaker identity
- Synchronized translated audio playback

## 🏗️ System Architecture

```
[YouTube Tab] → [Chrome Extension] → [FastAPI Backend]
                      ↓                        ↓
                [Audio Capture]         [ML Pipeline]
                      ↓                        ↓
                [User Controls]    [Whisper → Translation → Voice Clone → TTS]
                      ↓                        ↓
                [Translated Audio] ← [Processed Audio Stream]
```

## 🔧 Technology Stack

### Frontend (Chrome Extension)
- **Manifest V3** for Chrome extension
- **Web Audio API** for real-time audio capture
- **WebSocket/REST** for backend communication
- **JavaScript/HTML/CSS** for UI

### Backend (Python)
- **FastAPI** for API server
- **Whisper** for speech transcription
- **HuggingFace Transformers** for translation
- **Resemblyzer** for voice embedding
- **Coqui TTS** for voice synthesis

### ML Models
| Component | Model | Purpose |
|-----------|--------|---------|
| Transcription | Whisper (base/medium) | Speech-to-text |
| Translation | mBART/NLLB/M2M100 | Text translation |
| Voice Embedding | Resemblyzer | Speaker characteristics |
| TTS | Coqui TTS | Voice synthesis |

## 📁 Project Structure

```
TrueTone/
├── chrome-extension/          # Chrome extension frontend
│   ├── manifest.json
│   ├── content-script.js
│   ├── popup.html
│   └── background.js
├── backend/                   # Python FastAPI backend
│   ├── main.py
│   ├── models/
│   ├── services/
│   └── utils/
├── docs/                      # Documentation
├── tests/                     # Test suites
├── requirements.txt           # Python dependencies
└── README.md                  # This file
```

## 🎯 Development Roadmap

### Phase 1: Foundation
- [ ] Set up Chrome extension boilerplate
- [ ] Create FastAPI backend structure
- [ ] Implement basic audio capture
- [ ] Set up WebSocket communication

### Phase 2: Core Pipeline
- [ ] Integrate Whisper for transcription
- [ ] Add translation service
- [ ] Implement voice embedding
- [ ] Set up TTS synthesis

### Phase 3: Integration
- [ ] Real-time audio processing
- [ ] Synchronization with video
- [ ] UI/UX improvements
- [ ] Performance optimization

### Phase 4: Polish
- [ ] Testing and debugging
- [ ] Documentation
- [ ] Deployment preparation

## 🚀 Getting Started

### Prerequisites
- Python 3.8+
- Node.js (for extension development)
- Chrome browser
- GPU recommended for ML models

### Installation
```bash
# Clone repository
git clone https://github.com/mpat247/TrueTone.git
cd TrueTone

# Install Python dependencies
pip install -r requirements.txt

# Set up Chrome extension
# (Load unpacked extension in Chrome developer mode)
```

## 🔮 Future Enhancements
- Multi-speaker support
- Offline mode with quantized models
- Support for other platforms (Twitch, Vimeo)
- Subtitle generation
- Multi-language UI

## 👥 Contributing
This project is in active development. Contributions welcome!

## 📄 License
MIT License - see LICENSE file for details

---

**Author**: Manav Patel  
**Version**: v1.0  
**Last Updated**: July 4, 2025
