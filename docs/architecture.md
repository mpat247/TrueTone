# TrueTone Extension Architecture

## 🏗️ System Architecture Overview

### High-Level Architecture
```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   YouTube Tab   │    │  Chrome Extension │    │  FastAPI Backend │
│                 │    │                  │    │                 │
│  ┌───────────┐  │    │  ┌─────────────┐ │    │  ┌─────────────┐ │
│  │   Video   │  │    │  │   Popup UI  │ │    │  │  WebSocket  │ │
│  │   Player  │  │    │  │   Controls  │ │    │  │   Handler   │ │
│  └───────────┘  │    │  └─────────────┘ │    │  └─────────────┘ │
│                 │    │                  │    │                 │
│  ┌───────────┐  │    │  ┌─────────────┐ │    │  ┌─────────────┐ │
│  │   Audio   │━━━━━━━▶│  │  Content    │━━━━━━━▶│  │  ML Pipeline│ │
│  │   Stream  │  │    │  │  Script     │ │    │  │  Whisper    │ │
│  └───────────┘  │    │  └─────────────┘ │    │  │  Translation│ │
│                 │    │                  │    │  │  TTS/Voice  │ │
│  ┌───────────┐  │    │  ┌─────────────┐ │    │  └─────────────┘ │
│  │Translated │◀━━━━━━━│  │ Background  │◀━━━━━━━│                 │
│  │  Audio    │  │    │  │  Service    │ │    │  ┌─────────────┐ │
│  └───────────┘  │    │  └─────────────┘ │    │  │   Models    │ │
└─────────────────┘    └──────────────────┘    │  │   Storage   │ │
                                              │  └─────────────┘ │
                                              └─────────────────┘
```

## 🔧 Component Details

### Chrome Extension Components

#### 1. Manifest (manifest.json)
```json
{
  "manifest_version": 3,
  "permissions": ["activeTab", "tabCapture", "storage"],
  "host_permissions": ["https://*.youtube.com/*"],
  "content_scripts": [{"matches": ["https://*.youtube.com/*"]}],
  "background": {"service_worker": "background.js"},
  "action": {"default_popup": "popup.html"}
}
```

#### 2. Popup Interface (popup.html + popup.js)
- **Purpose**: User interface for extension controls
- **Features**:
  - Translation start/stop toggle
  - Target language selection
  - Volume control slider
  - Voice cloning toggle
  - Status indicators (YouTube/Backend connectivity)
- **Communication**: Sends messages to content script and background

#### 3. Content Script (content-script.js)
- **Purpose**: Injected into YouTube pages
- **Responsibilities**:
  - Detect YouTube video player
  - Capture audio from video
  - Create floating UI indicators
  - Handle WebSocket communication with backend
  - Manage translated audio playback
- **Permissions**: Access to YouTube DOM and Web Audio API

#### 4. Background Service Worker (background.js)
- **Purpose**: Handles extension lifecycle and tab management
- **Features**:
  - Tab capture API management
  - Cross-component message routing
  - Extension state persistence
  - Tab update monitoring

#### 5. Styling (styles.css)
- **Purpose**: Extension UI styling
- **Features**:
  - Gradient backgrounds (TrueTone branding)
  - Responsive design
  - YouTube overlay styling
  - Animation effects

### Backend Architecture

#### 1. FastAPI Server (main.py)
```python
app = FastAPI(title="TrueTone API", version="1.0.0")

# Key endpoints:
# GET /health - Health check
# GET /status - System status
# WebSocket /ws - Real-time communication
```

#### 2. WebSocket Handler
- **Purpose**: Real-time bidirectional communication
- **Features**:
  - Audio data streaming
  - Configuration updates
  - Status notifications
  - Error handling

#### 3. ML Pipeline (Future Implementation)
```
Audio Input → Whisper → Translation → Voice Cloning → TTS → Audio Output
```

## 🔄 Data Flow

### Translation Process Flow
1. **User Interaction**:
   - User clicks "Start Translation" in popup
   - Popup sends message to content script
   - Content script initiates WebSocket connection

2. **Audio Capture**:
   - Content script captures YouTube tab audio
   - Audio data chunked into processable segments
   - Chunks sent to backend via WebSocket

3. **Processing Pipeline** (Future):
   - Whisper transcribes audio to text
   - Translation model converts text to target language
   - Voice cloning preserves speaker characteristics
   - TTS generates translated audio

4. **Audio Playback**:
   - Backend streams translated audio back
   - Content script receives and plays translated audio
   - Original audio muted or dimmed

### Message Passing Architecture
```
Popup ←→ Content Script ←→ Background ←→ Backend
  ↓           ↓              ↓           ↓
 UI         YouTube        Tab         ML
State       Audio         Management   Pipeline
```

## 📡 Communication Protocols

### Chrome Extension Internal Communication
```javascript
// Popup to Content Script
chrome.tabs.sendMessage(tabId, {
  action: 'startTranslation',
  config: { language: 'es', volume: 80 }
});

// Content Script to Background
chrome.runtime.sendMessage({
  action: 'getCurrentTabId'
});
```

### WebSocket Communication
```javascript
// Client to Server
{
  "type": "audio",
  "data": [0.1, 0.2, 0.3, ...],
  "sampleRate": 44100,
  "config": {
    "targetLanguage": "es",
    "voiceCloning": true
  }
}

// Server to Client
{
  "type": "audio_processed",
  "data": [0.1, 0.2, 0.3, ...],
  "status": "success"
}
```

## 🛡️ Security Considerations

### Extension Security
- **Content Security Policy**: Strict CSP in manifest
- **Permissions**: Minimal required permissions
- **Origin Restrictions**: Only YouTube domains allowed
- **Data Validation**: Input sanitization for all user data

### Backend Security
- **CORS**: Configured for extension communication only
- **Input Validation**: All WebSocket messages validated
- **Rate Limiting**: Prevent abuse of audio processing
- **Local Processing**: No external API calls for sensitive data

## 🚀 Performance Considerations

### Chrome Extension Performance
- **Lazy Loading**: Components loaded only when needed
- **Memory Management**: Proper cleanup of audio contexts
- **DOM Manipulation**: Minimal YouTube DOM changes
- **Event Handling**: Efficient event delegation

### Backend Performance
- **Async Processing**: All I/O operations asynchronous
- **Model Caching**: ML models loaded once and cached
- **Resource Management**: Proper cleanup of audio resources
- **Streaming**: Real-time audio processing without buffering

## 🔧 Development Architecture

### Code Organization
```
├── chrome-extension/
│   ├── manifest.json      # Extension configuration
│   ├── popup/             # UI components
│   ├── content/           # YouTube integration
│   ├── background/        # Service worker
│   └── shared/            # Common utilities
├── backend/
│   ├── main.py            # FastAPI application
│   ├── routers/           # API endpoints
│   ├── services/          # Business logic
│   ├── models/            # Data models
│   └── utils/             # Helper functions
```

### Build Process
1. **Extension**: No build required (vanilla JS)
2. **Backend**: Virtual environment + pip dependencies
3. **Testing**: Manual testing + unit tests
4. **Deployment**: Extension packaging + server deployment

## 🔮 Future Architecture Enhancements

### Phase 2 Additions
- **Model Integration**: Whisper, Transformers, TTS
- **Audio Processing**: Real-time streaming pipeline
- **Caching**: Intelligent model and audio caching
- **Performance**: GPU acceleration for ML models

### Phase 3 Enhancements
- **Multi-language**: UI internationalization
- **Offline Mode**: Local model execution
- **Advanced Features**: Speaker separation, subtitle generation
- **Platform Support**: Firefox, Safari extensions

---

**Architecture Version**: 1.0.0 - Phase 1 Complete  
**Last Updated**: July 4, 2025
