// TrueTone Chrome Extension - Content Script
console.log('TrueTone content script loaded on:', window.location.href);

class AudioCaptureManager {
  constructor() {
    this.isCapturing = false;
    this.audioContext = null;
    this.mediaStream = null;
    this.sourceNode = null;
    this.processorNode = null;
    this.audioBuffer = [];
    this.bufferSize = 4096;
    this.maxBufferSize = 1024 * 1024; // 1MB max buffer
    this.sampleRate = 44100;
    this.sequenceNumber = 0;
    this.lastChunkTime = 0;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.audioQualityMetrics = {
      averageLevel: 0,
      peakLevel: 0,
      clipCount: 0,
      silenceCount: 0
    };
  }

  async initializeAudioCapture(config = {}) {
    console.log('Initializing audio capture with config:', config);
    
    try {
      // Check for required permissions
      if (!this.checkPermissions()) {
        throw new Error('Required permissions not available');
      }

      // Get tab audio stream using Chrome API
      const constraints = {
        audio: {
          mandatory: {
            chromeMediaSource: 'tab',
            chromeMediaSourceId: await this.getCurrentTabId()
          }
        }
      };

      this.mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
      console.log('Media stream acquired:', this.mediaStream);

      // Setup audio context
      this.audioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: this.sampleRate
      });

      // Create audio source
      this.sourceNode = this.audioContext.createMediaStreamSource(this.mediaStream);
      
      // Create script processor for audio processing
      this.processorNode = this.audioContext.createScriptProcessor(this.bufferSize, 1, 1);
      
      // Setup audio processing callback
      this.processorNode.onaudioprocess = this.processAudioData.bind(this);
      
      // Connect audio nodes
      this.sourceNode.connect(this.processorNode);
      this.processorNode.connect(this.audioContext.destination);
      
      this.isCapturing = true;
      console.log('Audio capture initialized successfully');
      
      return true;
    } catch (error) {
      console.error('Failed to initialize audio capture:', error);
      await this.handleCaptureError(error);
      return false;
    }
  }

  checkPermissions() {
    // Check if tab capture API is available
    if (!chrome.tabCapture) {
      console.error('Tab capture API not available');
      return false;
    }
    
    // Check if getUserMedia is available
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      console.error('getUserMedia not available');
      return false;
    }
    
    return true;
  }

  async getCurrentTabId() {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ action: 'getCurrentTabId' }, (response) => {
        if (response && response.tabId) {
          resolve(response.tabId.toString());
        } else {
          reject(new Error('Could not get current tab ID'));
        }
      });
    });
  }

  processAudioData(audioProcessingEvent) {
    if (!this.isCapturing) return;

    const inputBuffer = audioProcessingEvent.inputBuffer;
    const inputData = inputBuffer.getChannelData(0); // Get mono channel
    
    // Convert Float32Array to regular array for processing
    const audioArray = Array.from(inputData);
    
    // Analyze audio quality
    this.analyzeAudioQuality(audioArray);
    
    // Add to buffer with overflow protection
    this.addToAudioBuffer(audioArray);
    
    // Send chunk if buffer is large enough or enough time has passed
    const currentTime = Date.now();
    if (this.audioBuffer.length >= this.bufferSize || 
        (currentTime - this.lastChunkTime) > 100) { // 100ms max delay
      this.sendAudioChunk();
    }
  }

  analyzeAudioQuality(audioData) {
    // Calculate RMS level
    const rmsLevel = Math.sqrt(audioData.reduce((sum, sample) => sum + sample * sample, 0) / audioData.length);
    
    // Calculate peak level
    const peakLevel = Math.max(...audioData.map(Math.abs));
    
    // Count clipping (samples at max level)
    const clipCount = audioData.filter(sample => Math.abs(sample) >= 0.99).length;
    
    // Count silence (very low levels)
    const silenceCount = audioData.filter(sample => Math.abs(sample) <= 0.01).length;
    
    // Update metrics with smoothing
    const alpha = 0.1; // Smoothing factor
    this.audioQualityMetrics.averageLevel = (1 - alpha) * this.audioQualityMetrics.averageLevel + alpha * rmsLevel;
    this.audioQualityMetrics.peakLevel = Math.max(this.audioQualityMetrics.peakLevel * 0.99, peakLevel);
    this.audioQualityMetrics.clipCount += clipCount;
    this.audioQualityMetrics.silenceCount += silenceCount;
  }

  addToAudioBuffer(audioData) {
    // Check buffer overflow
    if (this.audioBuffer.length + audioData.length > this.maxBufferSize) {
      console.warn('Audio buffer overflow, clearing old data');
      const overflow = this.audioBuffer.length + audioData.length - this.maxBufferSize;
      this.audioBuffer.splice(0, overflow);
    }
    
    this.audioBuffer.push(...audioData);
  }

  sendAudioChunk() {
    if (this.audioBuffer.length === 0 || !this.websocket) return;
    
    try {
      // Create audio chunk data
      const chunkData = {
        type: 'audio_chunk',
        sequence: this.sequenceNumber++,
        timestamp: Date.now(),
        sampleRate: this.sampleRate,
        channels: 1,
        data: this.audioBuffer.slice(), // Copy buffer
        quality: {
          averageLevel: this.audioQualityMetrics.averageLevel,
          peakLevel: this.audioQualityMetrics.peakLevel,
          hasClipping: this.audioQualityMetrics.clipCount > 0,
          isSilent: this.audioQualityMetrics.silenceCount > this.bufferSize * 0.9
        }
      };
      
      // Send via WebSocket
      if (this.websocket.readyState === WebSocket.OPEN) {
        this.websocket.send(JSON.stringify(chunkData));
      }
      
      // Clear buffer and reset metrics
      this.audioBuffer = [];
      this.lastChunkTime = Date.now();
      this.audioQualityMetrics.clipCount = 0;
      this.audioQualityMetrics.silenceCount = 0;
      
    } catch (error) {
      console.error('Error sending audio chunk:', error);
      this.handleStreamingError(error);
    }
  }

  async handleCaptureError(error) {
    console.error('Audio capture error:', error);
    
    if (error.name === 'NotAllowedError') {
      console.error('Microphone permission denied');
      // Could trigger permission request UI
    } else if (error.name === 'NotFoundError') {
      console.error('No audio device found');
    } else if (error.name === 'OverconstrainedError') {
      console.error('Audio constraints not supported');
      // Could try with relaxed constraints
      await this.retryWithRelaxedConstraints();
    }
    
    // Attempt recovery
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000); // Exponential backoff, max 30s
      console.log(`Retrying audio capture in ${delay}ms (attempt ${this.reconnectAttempts})`);
      setTimeout(() => this.initializeAudioCapture(), delay);
    }
  }

  async retryWithRelaxedConstraints() {
    try {
      console.log('Retrying with relaxed audio constraints');
      const relaxedConstraints = {
        audio: {
          mandatory: {
            chromeMediaSource: 'tab'
          }
        }
      };
      
      this.mediaStream = await navigator.mediaDevices.getUserMedia(relaxedConstraints);
      return true;
    } catch (error) {
      console.error('Relaxed constraints also failed:', error);
      return false;
    }
  }

  handleStreamingError(error) {
    console.error('Streaming error:', error);
    
    if (this.websocket) {
      if (this.websocket.readyState === WebSocket.CLOSED || 
          this.websocket.readyState === WebSocket.CLOSING) {
        console.log('WebSocket connection lost, attempting reconnection');
        this.reconnectWebSocket();
      }
    }
  }

  async reconnectWebSocket() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max WebSocket reconnection attempts reached');
      return;
    }
    
    this.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
    
    console.log(`Attempting WebSocket reconnection in ${delay}ms (attempt ${this.reconnectAttempts})`);
    
    setTimeout(async () => {
      try {
        await this.connectToBackend();
        this.reconnectAttempts = 0; // Reset on success
        console.log('WebSocket reconnection successful');
      } catch (error) {
        console.error('WebSocket reconnection failed:', error);
        this.reconnectWebSocket(); // Try again
      }
    }, delay);
  }

  async connectToBackend() {
    return new Promise((resolve, reject) => {
      try {
        this.websocket = new WebSocket('ws://localhost:8000/ws');
        
        this.websocket.onopen = () => {
          console.log('Connected to TrueTone backend');
          this.reconnectAttempts = 0;
          resolve();
        };
        
        this.websocket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            this.handleBackendMessage(data);
          } catch (error) {
            console.error('Error parsing backend message:', error);
          }
        };
        
        this.websocket.onerror = (error) => {
          console.error('WebSocket error:', error);
          reject(error);
        };
        
        this.websocket.onclose = (event) => {
          console.log('WebSocket connection closed:', event.code, event.reason);
          if (this.isCapturing) {
            this.reconnectWebSocket();
          }
        };
        
      } catch (error) {
        reject(error);
      }
    });
  }

  handleBackendMessage(data) {
    switch (data.type) {
      case 'translated_audio':
        this.playTranslatedAudio(data);
        break;
      case 'status_update':
        console.log('Backend status:', data.status);
        break;
      case 'error':
        console.error('Backend error:', data.message);
        break;
      case 'quality_feedback':
        this.adjustQualitySettings(data);
        break;
      default:
        console.log('Unknown message type:', data.type);
    }
  }

  adjustQualitySettings(qualityData) {
    // Adjust capture settings based on backend feedback
    if (qualityData.suggestedBufferSize && qualityData.suggestedBufferSize !== this.bufferSize) {
      console.log(`Adjusting buffer size from ${this.bufferSize} to ${qualityData.suggestedBufferSize}`);
      this.bufferSize = qualityData.suggestedBufferSize;
      
      // Recreate processor node with new buffer size
      if (this.processorNode) {
        this.processorNode.disconnect();
        this.processorNode = this.audioContext.createScriptProcessor(this.bufferSize, 1, 1);
        this.processorNode.onaudioprocess = this.processAudioData.bind(this);
        this.sourceNode.connect(this.processorNode);
        this.processorNode.connect(this.audioContext.destination);
      }
    }
  }

  playTranslatedAudio(audioData) {
    // This will be implemented in the next part (audio playback)
    console.log('Received translated audio:', audioData);
  }

  stopCapture() {
    console.log('Stopping audio capture');
    
    this.isCapturing = false;
    
    // Clean up audio nodes
    if (this.processorNode) {
      this.processorNode.disconnect();
      this.processorNode = null;
    }
    
    if (this.sourceNode) {
      this.sourceNode.disconnect();
      this.sourceNode = null;
    }
    
    // Close audio context
    if (this.audioContext && this.audioContext.state !== 'closed') {
      this.audioContext.close();
      this.audioContext = null;
    }
    
    // Stop media stream
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach(track => track.stop());
      this.mediaStream = null;
    }
    
    // Close WebSocket
    if (this.websocket) {
      this.websocket.close();
      this.websocket = null;
    }
    
    // Clear buffer
    this.audioBuffer = [];
    this.sequenceNumber = 0;
    this.reconnectAttempts = 0;
  }

  getAudioStats() {
    return {
      isCapturing: this.isCapturing,
      bufferSize: this.audioBuffer.length,
      maxBufferSize: this.maxBufferSize,
      sampleRate: this.sampleRate,
      sequenceNumber: this.sequenceNumber,
      reconnectAttempts: this.reconnectAttempts,
      qualityMetrics: { ...this.audioQualityMetrics },
      websocketState: this.websocket ? this.websocket.readyState : 'disconnected'
    };
  }
}

class TrueToneYouTube {
  constructor() {
    this.isTranslating = false;
    this.config = {
      targetLanguage: 'es',
      volume: 80,
      voiceCloning: true
    };
    
    this.audioCaptureManager = new AudioCaptureManager();
    this.playerStateObserver = null;
    
    this.setupMessageListener();
    this.detectYouTubePlayer();
    this.createUI();
    this.setupPlayerStateMonitoring();
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
          
        case 'getAudioStats':
          sendResponse({ stats: this.audioCaptureManager.getAudioStats() });
          break;
          
        default:
          sendResponse({ success: false, error: 'Unknown action' });
      }
    });
  }

  setupPlayerStateMonitoring() {
    // Monitor YouTube player state changes
    const video = document.querySelector('video');
    if (video) {
      video.addEventListener('play', () => this.handlePlayerStateChange('playing'));
      video.addEventListener('pause', () => this.handlePlayerStateChange('paused'));
      video.addEventListener('seeking', () => this.handlePlayerStateChange('seeking'));
      video.addEventListener('loadstart', () => this.handlePlayerStateChange('loading'));
      
      // Monitor for ad changes
      const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
          if (mutation.type === 'childList') {
            const adElement = document.querySelector('.video-ads');
            if (adElement) {
              this.handlePlayerStateChange('ad_playing');
            } else {
              this.handlePlayerStateChange('ad_ended');
            }
          }
        });
      });
      
      observer.observe(document.body, {
        childList: true,
        subtree: true
      });
      
      this.playerStateObserver = observer;
    }
  }

  handlePlayerStateChange(state) {
    console.log('YouTube player state changed:', state);
    
    if (this.isTranslating) {
      // Send state change to backend
      if (this.audioCaptureManager.websocket && 
          this.audioCaptureManager.websocket.readyState === WebSocket.OPEN) {
        this.audioCaptureManager.websocket.send(JSON.stringify({
          type: 'player_state_change',
          state: state,
          timestamp: Date.now()
        }));
      }
      
      // Handle specific state changes
      switch (state) {
        case 'seeking':
          // Clear audio buffer on seek to avoid stale data
          this.audioCaptureManager.audioBuffer = [];
          break;
        case 'paused':
          // Could reduce processing to save resources
          break;
        case 'playing':
          // Resume full processing
          break;
      }
    }
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
