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
- The extension popup will display with a gradient interface

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

1. **Start the Backend**:
   - On Windows: Run `setup.bat` to set up the environment first time
   - Then run: `cd backend && python main.py`
2. **Open YouTube**: Navigate to any YouTube video
3. **Open Extension**: Click the 🎵 TrueTone icon
4. **Select Language**: Choose your target language from the dropdown
5. **Start Translation**: Click "Start Translation"
6. **Adjust Settings**: Use volume slider and voice cloning toggle as needed

### Features

#### Current Features

- ✅ **YouTube Integration**: Automatically detects YouTube videos
- ✅ **Beautiful UI**: Gradient interface with intuitive controls
- ✅ **Language Selection**: Support for 10 major languages
- ✅ **Volume Control**: Adjustable translation audio volume
- ✅ **Voice Cloning Toggle**: Enable/disable voice preservation
- ✅ **Status Monitoring**: Real-time connection status indicators
- ✅ **Voice Synthesis**: TTS-Mozilla integration with voice cloning

#### Upcoming Features

- 🔄 **Real-time Translation**: Live audio translation using Whisper
- 🔄 **Full Voice Preservation**: Enhanced speaker characteristics preservation
- 🔄 **Video Synchronization**: Perfect audio-video sync
- 🔄 **Multilingual UI**: Interface in multiple languages

### Troubleshooting

#### Extension Won't Load

- Ensure you're using Chrome (other browsers not yet supported)
- Check that Developer mode is enabled in `chrome://extensions/`
- Verify you selected the correct `chrome-extension` folder

#### Backend Connection Issues

- Make sure the backend server is running (`cd backend && python main.py`)
- Check that no other service is using port 8000
- Verify your firewall allows connections to localhost:8000
- Ensure all dependencies are installed (`pip install -r requirements.txt`)

#### YouTube Not Detected

- Refresh the YouTube page after installing the extension
- Ensure you're on a video page (not the YouTube homepage)
- Check that the extension has permission to access YouTube

#### TTS Issues

- Ensure TTS-Mozilla is installed correctly
- Check that you have enough disk space for model downloads
- Verify Python 3.12 compatibility

### Technical Requirements

- **Chrome Browser**: Version 88 or higher (Manifest V3 support)
- **Python**: Version 3.12 recommended for full compatibility
- **RAM**: At least 4GB (8GB+ recommended for ML models)
- **Disk Space**: 2GB+ for ML models
- **Internet**: Required for YouTube access and initial model downloads

### Privacy & Security

- TrueTone processes audio locally (no data sent to external servers)
- Extension only accesses YouTube pages (no other site data)
- All translation processing happens on your machine
- Voice data is not stored permanently

### Voice Cloning Ethics

TrueTone's voice cloning feature is designed for personal use to enhance the experience of watching foreign language content. Please use this technology responsibly:

- Only use voice cloning for legitimate translation purposes
- Do not create misleading content with cloned voices
- Respect the intellectual property and persona rights of others

## Advanced Features

### Custom Voice Samples

For advanced users, you can use custom voice samples:

1. Record a clear audio sample of the speaker (5-10 seconds)
2. Save as a WAV file in the `backend/voice_samples` directory
3. Name it appropriately (e.g., `speaker_name.wav`)
4. Modify the `backend/tts_mozilla_synthesis.py` file to load your custom sample

### Performance Optimization

- Close unused browser tabs to free up memory
- Use a computer with a dedicated GPU for faster processing
- For slower machines, use the "Small" model option in settings

## Getting Help

If you encounter any issues not covered in this guide:

- Check the documentation in the `docs` folder
- See `backend/README_TTS.md` for TTS-specific guidance
- Create an issue on the GitHub repository

---

**TrueTone Version**: v1.0.5  
**Last Updated**: Current date
