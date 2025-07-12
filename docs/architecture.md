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
│                 │    │                  │    │  │  TTS-Mozilla│ │
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
  "content_scripts": [{ "matches": ["https://*.youtube.com/*"] }],
  "background": { "service_worker": "background.js" },
  "action": { "default_popup": "popup.html" }
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

#### 3. ML Pipeline Components

- **Whisper Integration** (planned)

  - **Purpose**: Speech-to-text transcription
  - **Implementation**: OpenAI Whisper model
  - **Features**: Multilingual support, timestamps

- **Translation Service** (planned)

  - **Purpose**: Text translation
  - **Implementation**: HuggingFace transformer models
  - **Features**: Multiple language pairs, formatting preservation

- **Voice Synthesis Module** (planned)
  - **Purpose**: Text-to-speech with voice cloning
  - **Implementation**: Evaluating TTS solutions for Python 3.12
  - **Features**: Voice preservation, multilingual synthesis
  - **Status**: ⏳ Under evaluation

### Voice Synthesis Architecture

#### TTS-Mozilla Integration

```
┌───────────────┐      ┌───────────────┐      ┌───────────────┐
│  Source Text  │──────▶  Translation  │──────▶ Target Text   │
└───────────────┘      └───────────────┘      └───────┬───────┘
                                                     │
┌───────────────┐                                    │
│ Voice Sample  │                                    │
│    Audio      │────────────────┐                   │
└───────────────┘                │                   │
                                 ▼                   ▼
                         ┌───────────────┐    ┌───────────────┐
                         │ Voice Cloning │    │ TTS-Mozilla   │
                         │   Process     │◀───│  XTTS v2      │
                         └───────┬───────┘    └───────────────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │  Synthesized  │
                         │    Audio      │
                         └───────────────┘
```

#### Voice Cloning Process

1. **Voice Sample Input**: Audio sample of the original speaker
2. **Voice Characteristics Extraction**: Extract speaker identity
3. **Text Processing**: Prepare translated text for synthesis
4. **Speech Synthesis**: Generate audio with cloned voice
5. **Audio Output**: Translated speech with preserved voice characteristics

## 🔄 Data Flow

### End-to-End Translation Process

1. **Audio Capture**: Chrome extension captures YouTube audio
2. **WebSocket Transmission**: Audio sent to backend in chunks
3. **Transcription**: Whisper converts speech to text
4. **Translation**: Text translated to target language
5. **Voice Cloning**: Speaker's voice characteristics extracted
6. **TTS Synthesis**: Translated text converted to speech with original voice
7. **Audio Return**: Synthesized audio sent back to extension
8. **Playback**: Extension plays translated audio in sync with video

### State Management

- **Extension State**: Managed via Chrome storage API
- **Backend State**: Session management for active connections
- **ML Models**: Loaded and cached for efficient processing
- **Audio Buffers**: Circular buffers for continuous streaming

## 🔒 Security Considerations

- **Data Privacy**: All processing happens locally
- **Authentication**: WebSocket connections authenticated
- **CORS**: Proper configuration for cross-origin requests
- **Error Handling**: Graceful failure modes

## 🚀 Scalability Design

- **Modular Architecture**: Components can be scaled independently
- **Asynchronous Processing**: Non-blocking I/O for all operations
- **Model Optimization**: Quantized models for efficiency
- **Caching**: Intelligent caching of frequently used data
- **Distributed Potential**: Design allows for future distribution

## 📋 Technical Specifications

- **Frontend**: HTML5, CSS3, JavaScript (ES6+)
- **Backend**: Python 3.12, FastAPI, WebSockets
- **ML Models**: Whisper, HuggingFace Transformers, TTS-Mozilla
- **Audio Processing**: PyAudio, librosa, TTS-Mozilla
- **Protocol**: WebSocket for real-time, REST for config

---

This architecture is designed to be modular, extensible, and optimized for real-time voice-preserving translation.
