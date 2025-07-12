# TrueTone Development Setup Guide

## 🛠️ Developer Environment Setup

### Prerequisites

- **Python 3.12** (recommended for full compatibility)
- **Google Chrome** (latest version)
- **Git** for version control
- **Code Editor** (VS Code recommended)

### Project Structure

```
TrueTone/
├── chrome-extension/          # Chrome extension source
│   ├── manifest.json         # Extension manifest
│   ├── popup.html           # Extension UI
│   ├── popup.js             # UI logic
│   ├── content-script.js    # YouTube injection
│   ├── background.js        # Service worker
│   ├── styles.css           # Extension styling
│   └── icons/               # Extension icons
├── backend/                  # Python FastAPI backend
│   ├── main.py              # FastAPI server
│   ├── tts_mozilla_synthesis.py  # Voice synthesis module
│   ├── README_TTS.md        # TTS documentation
│   ├── routers/             # API endpoints
│   ├── services/            # Business logic
│   ├── models/              # Data models
│   └── utils/               # Helper functions
├── docs/                    # Documentation
├── tests/                   # Test suites
├── requirements.txt         # Python dependencies
├── setup.bat                # Windows setup script
└── start_backend.sh         # Backend startup script
```

### Development Environment Setup

#### 1. Clone and Setup

```bash
# Clone repository
git clone https://github.com/mpat247/TrueTone.git
cd TrueTone
```

#### 2. Environment Setup

##### Windows (Recommended)

```bash
# Run the setup script
setup.bat
```

##### Manual Setup (All Platforms)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# If you need microphone access, install PyAudio
pip install pipwin
pipwin install pyaudio
```

#### 3. Backend Development

```bash
# Start development server
./start_backend.sh

# Or manually:
cd backend
python main.py
```

The backend will be available at `http://localhost:8000`

**API Endpoints:**

- `GET /` - API information
- `GET /health` - Health check
- `GET /status` - System status
- `WebSocket /ws` - Real-time communication

#### 4. Chrome Extension Development

```bash
# Load extension in Chrome
# 1. Open chrome://extensions/
# 2. Enable Developer mode
# 3. Click "Load unpacked"
# 4. Select chrome-extension/ folder
```

**Extension Files:**

- `manifest.json` - Extension configuration
- `popup.html/js` - Extension UI and logic
- `content-script.js` - YouTube page injection
- `background.js` - Service worker for tab capture

### Development Workflow

#### Making Changes

1. **Backend Changes**: Server auto-reloads with `uvicorn --reload`
2. **Extension Changes**: Click "Reload" button in chrome://extensions/
3. **Testing**: Use browser dev tools and Python logging

#### Voice Synthesis Development

1. **TTS-Mozilla Module**: See `backend/README_TTS.md` for documentation
2. **Voice Cloning**: Test with sample audio files
3. **Integration**: Connect with translation service

#### Debugging

- **Chrome Extension**: Use Chrome DevTools (F12)
- **Backend**: Check console logs and `http://localhost:8000/status`
- **WebSocket**: Monitor connection in browser Network tab
- **TTS Module**: Use logging to debug voice synthesis

### Code Standards

#### Python (Backend)

- Use **Black** for code formatting
- Follow **PEP 8** style guidelines
- Type hints required for all functions
- Comprehensive docstrings for modules and functions

#### JavaScript (Extension)

- Use **ESLint** for code quality
- Follow modern ES6+ practices
- Maintain clean separation of concerns

### Dependency Management

- All dependencies are specified in `requirements.txt`
- Python 3.12 compatibility is maintained for all packages
- Use virtual environments for isolation

### Testing

- Unit tests with pytest
- Integration tests for API endpoints
- Manual testing for extension functionality

### Documentation

- Update documentation when adding new features
- Follow Markdown best practices
- Keep API documentation up to date

### Common Issues and Solutions

#### PyAudio Installation

If you encounter issues installing PyAudio:

**Windows**:

```bash
pip install pipwin
pipwin install pyaudio
```

**macOS**:

```bash
brew install portaudio
pip install pyaudio
```

**Linux**:

```bash
sudo apt-get install python3-pyaudio
```

#### TTS-Mozilla Setup

If you encounter issues with TTS-Mozilla:

1. Ensure you have Python 3.12
2. Check for GPU compatibility if using CUDA
3. See detailed troubleshooting in `backend/README_TTS.md`

---

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Chrome Extension Developer Guide](https://developer.chrome.com/docs/extensions/mv3/)
- [TTS-Mozilla Documentation](https://github.com/mozilla/TTS)
- [Whisper Documentation](https://github.com/openai/whisper)

---

**Happy developing with TrueTone!**
