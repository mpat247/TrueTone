// TrueTone Chrome Extension - Content Script
console.log('TrueTone content script loaded on:', window.location.href);

class TrueToneYouTube {
  constructor() {
    this.isTranslating = false;
    this.config = {
      targetLanguage: 'es',
      volume: 80,
      voiceCloning: true
    };
    
    this.audioContext = null;
    this.mediaStream = null;
    this.websocket = null;
    
    this.setupMessageListener();
    this.detectYouTubePlayer();
    this.createUI();
  }
  
  setupMessageListener() {
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      console.log('Content script received message:', request);
      
      switch (request.action) {
        case 'startTranslation':
          this.config = request.config;
          this.startTranslation();
          sendResponse({ success: true });
          break;
          
        case 'stopTranslation':
          this.stopTranslation();
          sendResponse({ success: true });
          break;
          
        case 'updateConfig':
          this.config = request.config;
          sendResponse({ success: true });
          break;
          
        default:
          sendResponse({ success: false, error: 'Unknown action' });
      }
    });
  }
  
  detectYouTubePlayer() {
    // Wait for YouTube player to load
    const checkForPlayer = () => {
      const player = document.querySelector('video');
      if (player) {
        console.log('YouTube player detected');
        this.videoElement = player;
        this.setupPlayerObserver();
      } else {
        setTimeout(checkForPlayer, 1000);
      }
    };
    
    checkForPlayer();
  }
  
  setupPlayerObserver() {
    // Observer for video changes (new video loads)
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === 'attributes' && mutation.attributeName === 'src') {
          console.log('New video detected');
          if (this.isTranslating) {
            this.restartTranslation();
          }
        }
      });
    });
    
    observer.observe(this.videoElement, {
      attributes: true,
      attributeFilter: ['src']
    });
  }
  
  createUI() {
    // Create floating UI indicator
    const ui = document.createElement('div');
    ui.id = 'truetone-indicator';
    ui.innerHTML = `
      <div style="
        position: fixed;
        top: 20px;
        right: 20px;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 10px 15px;
        border-radius: 20px;
        font-family: Arial, sans-serif;
        font-size: 14px;
        z-index: 9999;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        display: none;
      ">
        🎵 TrueTone: <span id="truetone-status">Ready</span>
      </div>
    `;
    
    document.body.appendChild(ui);
    this.uiElement = ui.querySelector('div');
    this.statusElement = ui.querySelector('#truetone-status');
  }
  
  showUI() {
    this.uiElement.style.display = 'block';
  }
  
  hideUI() {
    this.uiElement.style.display = 'none';
  }
  
  updateStatus(status) {
    this.statusElement.textContent = status;
  }
  
  async startTranslation() {
    console.log('Starting translation with config:', this.config);
    
    try {
      this.isTranslating = true;
      this.showUI();
      this.updateStatus('Starting...');
      
      // Connect to backend
      await this.connectToBackend();
      
      // Start audio capture
      await this.startAudioCapture();
      
      this.updateStatus('Translating');
      
    } catch (error) {
      console.error('Error starting translation:', error);
      this.updateStatus('Error');
      this.stopTranslation();
    }
  }
  
  async stopTranslation() {
    console.log('Stopping translation');
    
    this.isTranslating = false;
    this.hideUI();
    
    // Stop audio capture
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(track => track.stop());
      this.mediaStream = null;
    }
    
    // Close WebSocket
    if (this.websocket) {
      this.websocket.close();
      this.websocket = null;
    }
    
    // Close audio context
    if (this.audioContext) {
      this.audioContext.close();
      this.audioContext = null;
    }
  }
  
  async restartTranslation() {
    console.log('Restarting translation for new video');
    await this.stopTranslation();
    setTimeout(() => this.startTranslation(), 1000);
  }
  
  async connectToBackend() {
    return new Promise((resolve, reject) => {
      this.websocket = new WebSocket('ws://localhost:8000/ws');
      
      this.websocket.onopen = () => {
        console.log('Connected to TrueTone backend');
        resolve();
      };
      
      this.websocket.onmessage = (event) => {
        console.log('Received from backend:', event.data);
        // Handle translated audio data here
      };
      
      this.websocket.onerror = (error) => {
        console.error('WebSocket error:', error);
        reject(error);
      };
      
      this.websocket.onclose = () => {
        console.log('Disconnected from backend');
      };
    });
  }
  
  async startAudioCapture() {
    try {
      // Get current tab's audio stream
      const tabId = await this.getCurrentTabId();
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          mandatory: {
            chromeMediaSource: 'tab',
            chromeMediaSourceId: tabId
          }
        }
      });
      
      // Set up audio processing
      this.audioContext = new AudioContext();
      const source = this.audioContext.createMediaStreamSource(this.mediaStream);
      
      // Create audio processor
      const processor = this.audioContext.createScriptProcessor(4096, 1, 1);
      
      processor.onaudioprocess = (event) => {
        const inputBuffer = event.inputBuffer;
        const inputData = inputBuffer.getChannelData(0);
        
        // Send audio data to backend
        if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
          const audioData = Array.from(inputData);
          this.websocket.send(JSON.stringify({
            type: 'audio',
            data: audioData,
            sampleRate: this.audioContext.sampleRate,
            config: this.config
          }));
        }
      };
      
      source.connect(processor);
      processor.connect(this.audioContext.destination);
      
      console.log('Audio capture started');
      
    } catch (error) {
      console.error('Error starting audio capture:', error);
      throw error;
    }
  }
  
  async getCurrentTabId() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ action: 'getCurrentTabId' }, (response) => {
        resolve(response.tabId);
      });
    });
  }
}

// Initialize when page loads
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    new TrueToneYouTube();
  });
} else {
  new TrueToneYouTube();
}
