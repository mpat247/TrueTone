# TrueTone Development Setup Guide

## 🛠️ Developer Environment Setup

### Prerequisites
- **Python 3.8+** (3.9+ recommended)
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
│   ├── routers/             # API endpoints
│   ├── services/            # Business logic
│   ├── models/              # Data models
│   └── utils/               # Helper functions
├── docs/                    # Documentation
├── tests/                   # Test suites
├── requirements.txt         # Python dependencies
└── start_backend.sh         # Backend startup script
```

### Development Environment Setup

#### 1. Clone and Setup
```bash
# Clone repository
git clone https://github.com/mpat247/TrueTone.git
cd TrueTone

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

#### 2. Backend Development
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

#### 3. Chrome Extension Development
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

#### Debugging
- **Chrome Extension**: Use Chrome DevTools (F12)
- **Backend**: Check console logs and `http://localhost:8000/status`
- **WebSocket**: Monitor connection in browser Network tab

### Code Standards

#### Python (Backend)
- Use **Black** for code formatting
- Follow **PEP 8** style guidelines
- Type hints recommended
- Docstrings for all functions

#### JavaScript (Extension)
- Use **modern ES6+** syntax
- Consistent variable naming (camelCase)
- Error handling for all async operations
- Comments for complex logic

### Testing

#### Backend Testing
```bash
# Run tests
pytest tests/

# Run with coverage
pytest --cov=backend tests/
```

#### Extension Testing
- Manual testing on various YouTube videos
- Check console for errors
- Verify WebSocket connections
- Test UI responsiveness

### Version Control

#### Commit Guidelines
```bash
# Commit format
git commit -m "Type: Brief description

- Detailed change 1
- Detailed change 2"

# Types: feat, fix, docs, style, refactor, test, chore
```

#### Branch Strategy
- `main` - Production ready code
- `develop` - Development integration
- `feature/*` - Feature branches
- `hotfix/*` - Bug fixes

### Deployment

#### Backend Deployment
```bash
# Production server
uvicorn backend.main:app --host 0.0.0.0 --port 8000

# With Docker (future)
docker build -t truetone-backend .
docker run -p 8000:8000 truetone-backend
```

#### Extension Packaging
```bash
# Create extension package
cd chrome-extension
zip -r truetone-extension.zip . -x "*.DS_Store"
```

### Troubleshooting

#### Common Issues
1. **Import Errors**: Ensure virtual environment is activated
2. **Port Conflicts**: Check if port 8000 is available
3. **Extension Errors**: Check manifest.json syntax
4. **WebSocket Issues**: Verify CORS settings

#### Debug Commands
```bash
# Check Python environment
python --version
pip list

# Check backend health
curl http://localhost:8000/health

# Check Chrome extension
# Go to chrome://extensions/ and check error messages
```

### Next Steps for Development

#### Phase 2 Implementation
1. **Whisper Integration**:
   ```bash
   pip install openai-whisper
   # Test with: whisper audio.wav --model base
   ```

2. **Translation Models**:
   ```bash
   pip install transformers torch
   # Test with: python -c "from transformers import pipeline; print('OK')"
   ```

3. **Voice Cloning**:
   ```bash
   pip install TTS resemblyzer
   # Test with: tts --help
   ```

#### Development Priorities
1. Audio capture from YouTube tabs
2. Real-time audio processing pipeline
3. Model integration and testing
4. Performance optimization
5. UI/UX improvements

---

**Happy coding! 🚀**
