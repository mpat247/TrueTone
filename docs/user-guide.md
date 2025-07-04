# TrueTone Chrome Extension - User Guide

## 🎵 Getting Started with TrueTone

### What is TrueTone?
TrueTone is a Chrome extension that translates YouTube videos in real-time while preserving the original speaker's voice characteristics. Unlike traditional translation tools that change the voice completely, TrueTone maintains the speaker's pitch, tone, and rhythm.

### Installation
1. Download or clone the TrueTone project
2. Open Chrome and go to `chrome://extensions/`
3. Enable **"Developer mode"** (toggle in top-right)
4. Click **"Load unpacked"**
5. Select the `chrome-extension` folder
6. The 🎵 TrueTone icon will appear in your toolbar

### Using the Extension

#### 1. Basic Setup
- Navigate to any YouTube video
- Click the 🎵 TrueTone icon in your Chrome toolbar
- The extension popup will display with a beautiful gradient interface

#### 2. Extension Interface
The popup contains several sections:

**Status Indicators:**
- 🟢 **YouTube: Connected** - Extension detects YouTube page
- 🟢 **Backend: Connected** - Server is running and responsive
- 🔴 **Disconnected** - Service unavailable

**Translation Controls:**
- **Start/Stop Translation** - Main toggle for translation service
- **Target Language** - Select your desired translation language
- **Translation Volume** - Adjust the volume of translated audio
- **Voice Cloning** - Toggle to preserve original speaker's voice

#### 3. Language Support
Currently supported languages:
- Spanish (Español)
- French (Français)
- German (Deutsch)
- Italian (Italiano)
- Portuguese (Português)
- Russian (Русский)
- Chinese (中文)
- Japanese (日本語)
- Korean (한국어)
- Arabic (العربية)

#### 4. Using Translation
1. **Start the Backend**: Run `./start_backend.sh` in the project directory
2. **Open YouTube**: Navigate to any YouTube video
3. **Open Extension**: Click the 🎵 TrueTone icon
4. **Select Language**: Choose your target language from the dropdown
5. **Start Translation**: Click "Start Translation"
6. **Adjust Settings**: Use volume slider and voice cloning toggle as needed

### Features

#### Current Features (Phase 1)
- ✅ **YouTube Integration**: Automatically detects YouTube videos
- ✅ **Beautiful UI**: Gradient interface with intuitive controls
- ✅ **Language Selection**: Support for 10 major languages
- ✅ **Volume Control**: Adjustable translation audio volume
- ✅ **Voice Cloning Toggle**: Enable/disable voice preservation
- ✅ **Status Monitoring**: Real-time connection status indicators

#### Upcoming Features (Phase 2)
- 🔄 **Real-time Translation**: Live audio translation using Whisper
- 🔄 **Voice Preservation**: Maintain original speaker characteristics
- 🔄 **Audio Synthesis**: High-quality voice cloning with Coqui TTS
- 🔄 **Video Synchronization**: Perfect audio-video sync

### Troubleshooting

#### Extension Won't Load
- Ensure you're using Chrome (other browsers not yet supported)
- Check that Developer mode is enabled in `chrome://extensions/`
- Verify you selected the correct `chrome-extension` folder

#### Backend Connection Issues
- Make sure the backend server is running (`./start_backend.sh`)
- Check that no other service is using port 8000
- Verify your firewall allows connections to localhost:8000

#### YouTube Not Detected
- Refresh the YouTube page after installing the extension
- Ensure you're on a video page (not the YouTube homepage)
- Check that the extension has permission to access YouTube

### Technical Requirements
- **Chrome Browser**: Version 88 or higher (Manifest V3 support)
- **Python Backend**: Python 3.8+ (for backend functionality)
- **Memory**: At least 4GB RAM (for ML models when implemented)
- **Internet**: Required for YouTube access and model downloads

### Privacy & Security
- TrueTone processes audio locally (no data sent to external servers)
- Extension only accesses YouTube pages (no other site data)
- All translation processing happens on your machine
- No personal data is stored or transmitted

### Support
For issues or questions:
- Check the project documentation
- Review the development log in `/docs/dev-log.md`
- Submit issues on the GitHub repository

---

**Version**: 1.0.0 - Phase 1 Complete  
**Last Updated**: July 4, 2025
