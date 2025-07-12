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
                [User Controls]    [Whisper → Translation → TTS-Mozilla]
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
- **TTS solution** (evaluating options for Python 3.12)

### ML Models

| Component       | Model                 | Purpose                      |
| --------------- | --------------------- | ---------------------------- |
| Transcription   | Whisper (base/medium) | Speech-to-text               |
| Translation     | mBART/NLLB/M2M100     | Text translation             |
| Voice Synthesis | Under evaluation      | Voice synthesis with cloning |

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
│   ├── tts_mozilla_synthesis.py  # Voice synthesis module
│   ├── README_TTS.md          # TTS documentation
│   ├── models/
│   ├── services/
│   └── utils/
├── docs/                      # Documentation
├── tests/                     # Test suites
├── requirements.txt           # Python dependencies
├── setup.bat                  # Windows setup script
└── README.md                  # This file
```

## 🎯 Development Roadmap

### Phase 1: Foundation ✅ COMPLETED

- [x] Set up Chrome extension boilerplate
- [x] Create FastAPI backend structure
- [x] Implement basic audio capture
- [x] Set up WebSocket communication
- [x] Create extension UI and icons
- [x] Establish YouTube integration

### Phase 2: Core Pipeline (IN PROGRESS)

- [ ] Integrate Whisper for transcription
- [ ] Select and implement TTS solution
- [ ] Add translation service
- [ ] Complete end-to-end pipeline

### Phase 3: Integration (PLANNED)

- [ ] Real-time audio processing
- [ ] Synchronization with video
- [ ] UI/UX improvements
- [ ] Performance optimization

### Phase 4: Polish (PLANNED)

- [ ] Testing and debugging
- [ ] Documentation
- [ ] Deployment preparation

## 🚀 Getting Started

### Prerequisites

- Python 3.12
- Google Chrome browser
- Git (for development)

### Installation & Setup

#### 1. Clone the Repository

```bash
git clone https://github.com/mpat247/TrueTone.git
cd TrueTone
```

#### 2. Set Up the Backend

##### Windows

```bash
# Run the setup script
setup.bat
```

##### Manual Setup (All Platforms)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt

# If you need microphone access, install PyAudio
pip install pipwin
pipwin install pyaudio

# Start the backend server
cd backend
python main.py
```

The backend will be available at `http://localhost:8000`

#### 3. Load the Chrome Extension

1. Open Chrome and go to `chrome://extensions/`
2. Enable **"Developer mode"** (toggle in top-right)
3. Click **"Load unpacked"**
4. Select the `chrome-extension` folder from this project
5. The TrueTone extension should now appear in your toolbar

#### 4. Test the Extension

1. Go to any YouTube video
2. Click the 🎵 TrueTone extension icon
3. You should see the interface with translation controls
4. Try the translation controls (backend integration required for full functionality)

### Current Status

- ✅ **Chrome Extension**: Fully functional with UI and YouTube integration
- ✅ **Backend**: FastAPI server with WebSocket support
- ⏳ **Voice Synthesis**: Evaluating TTS solutions for Python 3.12
- ⏳ **ML Pipeline**: Whisper and Translation integration planning

## 🔮 Future Enhancements

- Multi-speaker support
- Offline mode with quantized models
- Support for other platforms (Twitch, Vimeo)
- Subtitle generation
- Multi-language UI

## 👥 Contributing

Contributions welcome! Please see our contributing guidelines.

## 📄 License

MIT License - see LICENSE file for details

---

**Author**: Manav Patel  
**Version**: v1.0.5  
**Last Updated**: July 6, 2025
