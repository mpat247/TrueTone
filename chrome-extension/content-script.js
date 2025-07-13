// TrueTone Chrome Extension - Content Script
console.log("TrueTone content script loaded on:", window.location.href);

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
    this.websocket = null;
    this.audioQualityMetrics = {
      averageLevel: 0,
      peakLevel: 0,
      clipCount: 0,
      silenceCount: 0,
    };
  }

  async initializeAudioCapture(config = {}) {
    console.log("Initializing audio capture with config:", config);

    try {
      // Check for required permissions
      if (!this.checkPermissions()) {
        throw new Error("Required permissions not available");
      }

      // Get tab audio stream using Chrome API
      const constraints = {
        audio: {
          mandatory: {
            chromeMediaSource: "tab",
            chromeMediaSourceId: await this.getCurrentTabId(),
          },
        },
      };

      this.mediaStream = await navigator.mediaDevices.getUserMedia(constraints);
      console.log("Media stream acquired:", this.mediaStream);

      // Setup audio context
      this.audioContext = new (window.AudioContext ||
        window.webkitAudioContext)({
        sampleRate: this.sampleRate,
      });

      // Create audio source
      this.sourceNode = this.audioContext.createMediaStreamSource(
        this.mediaStream
      );

      // Create script processor for audio processing
      this.processorNode = this.audioContext.createScriptProcessor(
        this.bufferSize,
        1,
        1
      );

      // Setup audio processing callback
      this.processorNode.onaudioprocess = this.processAudioData.bind(this);

      // Connect audio nodes
      this.sourceNode.connect(this.processorNode);
      this.processorNode.connect(this.audioContext.destination);

      this.isCapturing = true;

      // Start quality monitoring
      this.startQualityMonitoring();

      // Start periodic synchronization
      this.startPeriodicSync();

      console.log("Audio capture initialized successfully");

      return true;
    } catch (error) {
      console.error("Failed to initialize audio capture:", error);
      await this.handleCaptureError(error);
      return false;
    }
  }

  startQualityMonitoring() {
    // Monitor audio quality every 5 seconds
    this.qualityMonitorInterval = setInterval(() => {
      if (this.isCapturing) {
        this.requestQualityCheck();
      }
    }, 5000);
  }

  startPeriodicSync() {
    // Sync clocks every 30 seconds
    this.syncInterval = setInterval(() => {
      if (
        this.isCapturing &&
        this.websocket &&
        this.websocket.readyState === WebSocket.OPEN
      ) {
        this.requestClockSync();
      }
    }, 30000);
  }

  stopQualityMonitoring() {
    if (this.qualityMonitorInterval) {
      clearInterval(this.qualityMonitorInterval);
      this.qualityMonitorInterval = null;
    }

    if (this.syncInterval) {
      clearInterval(this.syncInterval);
      this.syncInterval = null;
    }
  }

  checkPermissions() {
    // Check if tab capture API is available
    if (!chrome.tabCapture) {
      console.error("Tab capture API not available");
      return false;
    }

    // Check if getUserMedia is available
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      console.error("getUserMedia not available");
      return false;
    }

    return true;
  }

  async getCurrentTabId() {
    return new Promise((resolve, reject) => {
      chrome.runtime.sendMessage({ action: "getCurrentTabId" }, (response) => {
        if (response && response.tabId) {
          resolve(response.tabId.toString());
        } else {
          reject(new Error("Could not get current tab ID"));
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
    if (
      this.audioBuffer.length >= this.bufferSize ||
      currentTime - this.lastChunkTime > 100
    ) {
      // 100ms max delay
      this.sendAudioChunk();
    }
  }

  analyzeAudioQuality(audioData) {
    // Calculate RMS level
    const rmsLevel = Math.sqrt(
      audioData.reduce((sum, sample) => sum + sample * sample, 0) /
        audioData.length
    );

    // Calculate peak level
    const peakLevel = Math.max(...audioData.map(Math.abs));

    // Count clipping (samples at max level)
    const clipCount = audioData.filter(
      (sample) => Math.abs(sample) >= 0.99
    ).length;

    // Count silence (very low levels)
    const silenceCount = audioData.filter(
      (sample) => Math.abs(sample) <= 0.01
    ).length;

    // Update metrics with smoothing
    const alpha = 0.1; // Smoothing factor
    this.audioQualityMetrics.averageLevel =
      (1 - alpha) * this.audioQualityMetrics.averageLevel + alpha * rmsLevel;
    this.audioQualityMetrics.peakLevel = Math.max(
      this.audioQualityMetrics.peakLevel * 0.99,
      peakLevel
    );
    this.audioQualityMetrics.clipCount += clipCount;
    this.audioQualityMetrics.silenceCount += silenceCount;
  }

  addToAudioBuffer(audioData) {
    // Check buffer overflow
    if (this.audioBuffer.length + audioData.length > this.maxBufferSize) {
      console.warn("Audio buffer overflow, clearing old data");
      const overflow =
        this.audioBuffer.length + audioData.length - this.maxBufferSize;
      this.audioBuffer.splice(0, overflow);
    }

    this.audioBuffer.push(...audioData);
  }

  sendAudioChunk() {
    if (this.audioBuffer.length === 0 || !this.websocket) return;

    try {
      // Convert audio buffer to Float32Array for proper encoding
      const audioFloat32 = new Float32Array(this.audioBuffer);

      // Convert to base64 for transmission
      const audioBytes = new Uint8Array(audioFloat32.buffer);
      const base64Audio = btoa(String.fromCharCode.apply(null, audioBytes));

      // Create audio chunk data matching backend protocol
      const chunkData = {
        type: "audio_chunk",
        sequence: this.sequenceNumber++,
        timestamp: Date.now(),
        sampleRate: this.sampleRate,
        channels: 1,
        data: base64Audio, // Base64 encoded audio data
        metadata: {
          bufferSize: this.audioBuffer.length,
          quality: {
            averageLevel: this.audioQualityMetrics.averageLevel,
            peakLevel: this.audioQualityMetrics.peakLevel,
            hasClipping: this.audioQualityMetrics.clipCount > 0,
            isSilent:
              this.audioQualityMetrics.silenceCount > this.bufferSize * 0.9,
            snrEstimate: this.calculateSNR(),
          },
          compression: {
            enabled: true,
            preferredAlgorithm: "lz4", // Fast compression for real-time
          },
        },
      };

      // Send via WebSocket
      if (this.websocket.readyState === WebSocket.OPEN) {
        this.websocket.send(JSON.stringify(chunkData));
        console.debug(
          `Sent audio chunk: ${this.audioBuffer.length} samples, sequence ${chunkData.sequence}`
        );
      }

      // Clear buffer and reset metrics
      this.audioBuffer = [];
      this.lastChunkTime = Date.now();
      this.audioQualityMetrics.clipCount = 0;
      this.audioQualityMetrics.silenceCount = 0;
    } catch (error) {
      console.error("Error sending audio chunk:", error);
      this.handleStreamingError(error);
    }
  }

  calculateSNR() {
    if (this.audioBuffer.length === 0) return 0;

    // Calculate signal power (RMS)
    const signalPower =
      this.audioBuffer.reduce((sum, sample) => sum + sample * sample, 0) /
      this.audioBuffer.length;

    // Estimate noise floor (10th percentile of squared samples)
    const sortedSquared = this.audioBuffer
      .map((s) => s * s)
      .sort((a, b) => a - b);
    const noiseFloor =
      sortedSquared[Math.floor(sortedSquared.length * 0.1)] || 1e-10;

    // Calculate SNR in dB
    return 10 * Math.log10(signalPower / noiseFloor);
  }

  async handleCaptureError(error) {
    console.error("Audio capture error:", error);

    if (error.name === "NotAllowedError") {
      console.error("Microphone permission denied");
    } else if (error.name === "NotFoundError") {
      console.error("No audio device found");
    } else if (error.name === "OverconstrainedError") {
      console.error("Audio constraints not supported");
      await this.retryWithRelaxedConstraints();
    }

    // Attempt recovery
    if (this.reconnectAttempts < this.maxReconnectAttempts) {
      this.reconnectAttempts++;
      const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);
      console.log(
        `Retrying audio capture in ${delay}ms (attempt ${this.reconnectAttempts})`
      );
      setTimeout(() => this.initializeAudioCapture(), delay);
    }
  }

  async retryWithRelaxedConstraints() {
    try {
      console.log("Retrying with relaxed audio constraints");
      const relaxedConstraints = {
        audio: {
          mandatory: {
            chromeMediaSource: "tab",
          },
        },
      };

      this.mediaStream = await navigator.mediaDevices.getUserMedia(
        relaxedConstraints
      );
      return true;
    } catch (error) {
      console.error("Relaxed constraints also failed:", error);
      return false;
    }
  }

  handleStreamingError(error) {
    console.error("Streaming error:", error);

    if (this.websocket) {
      if (
        this.websocket.readyState === WebSocket.CLOSED ||
        this.websocket.readyState === WebSocket.CLOSING
      ) {
        console.log("WebSocket connection lost, attempting reconnection");
        this.reconnectWebSocket();
      }
    }
  }

  async reconnectWebSocket() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error("Max WebSocket reconnection attempts reached");
      return;
    }

    this.reconnectAttempts++;
    const delay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), 30000);

    console.log(
      `Attempting WebSocket reconnection in ${delay}ms (attempt ${this.reconnectAttempts})`
    );

    setTimeout(async () => {
      try {
        await this.connectToBackend();
        this.reconnectAttempts = 0; // Reset on success
        console.log("WebSocket reconnection successful");
      } catch (error) {
        console.error("WebSocket reconnection failed:", error);
        this.reconnectWebSocket(); // Try again
      }
    }, delay);
  }

  async connectToBackend() {
    return new Promise((resolve, reject) => {
      try {
        this.websocket = new WebSocket("ws://localhost:8000/ws");

        this.websocket.onopen = () => {
          console.log("Connected to TrueTone backend");
          this.reconnectAttempts = 0;

          // Send initial configuration
          this.sendAudioConfig();

          // Request clock synchronization
          this.requestClockSync();

          resolve();
        };

        this.websocket.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            this.handleBackendMessage(data);
          } catch (error) {
            console.error("Error parsing backend message:", error);
          }
        };

        this.websocket.onerror = (error) => {
          console.error("WebSocket error:", error);
          reject(error);
        };

        this.websocket.onclose = (event) => {
          console.log("WebSocket connection closed:", event.code, event.reason);
          if (this.isCapturing) {
            this.reconnectWebSocket();
          }
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  sendAudioConfig() {
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      const configMessage = {
        type: "audio_config",
        config: {
          action: "start",
          sampleRate: this.sampleRate,
          channels: 1,
          bufferSize: this.bufferSize,
          format: "float32",
          compression: {
            enabled: true,
            preferredAlgorithm: "lz4",
          },
        },
      };

      this.websocket.send(JSON.stringify(configMessage));
      console.log("Sent audio configuration to backend");
    }
  }

  requestClockSync() {
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      const syncMessage = {
        type: "sync_request",
        client_time: Date.now() / 1000, // Convert to seconds
      };

      this.websocket.send(JSON.stringify(syncMessage));
      console.log("Requested clock synchronization");
    }
  }

  requestQualityCheck() {
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      const qualityMessage = {
        type: "quality_check",
        timestamp: Date.now(),
      };

      this.websocket.send(JSON.stringify(qualityMessage));
    }
  }

  requestStats() {
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      const statsMessage = {
        type: "stats_request",
        stats_type: "all",
        timestamp: Date.now(),
      };

      this.websocket.send(JSON.stringify(statsMessage));
    }
  }

  handleBackendMessage(data) {
    switch (data.type) {
      case "connection_established":
        console.log("Backend connection established:", data);
        this.serverTimeOffset = data.server_time - Date.now() / 1000;
        break;

      case "audio_chunk_processed":
        console.debug("Audio chunk processed:", data.sequence, data.status);
        if (data.buffer_stats) {
          this.handleBufferStats(data.buffer_stats);
        }
        break;

      case "audio_config_response":
        console.log("Audio config response:", data.status);
        if (data.status === "started") {
          console.log("Backend audio capture started successfully");
        }
        break;

      case "sync_response":
        console.log("Clock sync response:", data);
        this.serverTimeOffset = data.server_time - data.client_time;
        console.log(
          `Clock sync: offset = ${this.serverTimeOffset}s, jitter = ${data.jitter_estimate}ms`
        );
        break;

      case "quality_check_response":
        console.log("Quality check response:", data);
        this.handleQualityRecommendations(data);
        break;

      case "stats_response":
        console.log("Stats response:", data);
        this.handleStatsUpdate(data);
        break;

      case "translated_audio":
        this.playTranslatedAudio(data);
        break;

      case "stream_control_response":
        console.log("Stream control response:", data.command, data.status);
        break;

      case "error":
        console.error("Backend error:", data.message);
        this.handleBackendError(data);
        break;

      default:
        console.log("Unknown message type:", data.type, data);
    }
  }

  handleBufferStats(bufferStats) {
    // Monitor buffer health
    if (bufferStats.utilization > 80) {
      console.warn(
        "Backend buffer utilization high:",
        bufferStats.utilization + "%"
      );
      // Could reduce chunk size or increase send frequency
    }

    if (bufferStats.overflow_count > 0) {
      console.warn(
        "Backend buffer overflow detected:",
        bufferStats.overflow_count
      );
    }
  }

  handleQualityRecommendations(qualityData) {
    const recommendations = qualityData.recommendations || [];
    const metrics = qualityData.quality_metrics || {};

    console.log("Audio quality metrics:", metrics);

    recommendations.forEach((recommendation) => {
      console.log("Quality recommendation:", recommendation);
    });

    // Auto-adjust based on recommendations
    if (
      recommendations.includes("Low SNR detected - consider noise reduction")
    ) {
      // Could implement noise gating or filtering
      console.log("Implementing noise reduction measures");
    }

    if (
      recommendations.includes("Audio clipping detected - reduce input level")
    ) {
      // Could reduce gain or implement automatic gain control
      console.log("Reducing audio input level");
    }
  }

  handleStatsUpdate(statsData) {
    if (statsData.capture_stats) {
      console.log("Capture stats:", statsData.capture_stats);
    }

    if (statsData.streaming_stats) {
      console.log("Streaming stats:", statsData.streaming_stats);

      // Monitor network quality
      const networkStats = statsData.streaming_stats;
      if (networkStats.packet_loss_rate > 0.05) {
        console.warn(
          "High packet loss detected:",
          networkStats.packet_loss_rate
        );
        this.adaptToNetworkConditions(networkStats);
      }

      if (networkStats.average_latency > 300) {
        console.warn(
          "High latency detected:",
          networkStats.average_latency + "ms"
        );
        this.adaptToNetworkConditions(networkStats);
      }
    }
  }

  adaptToNetworkConditions(networkStats) {
    // Reduce buffer size for poor network conditions
    if (
      networkStats.packet_loss_rate > 0.05 ||
      networkStats.average_latency > 300
    ) {
      const newBufferSize = Math.max(1024, Math.floor(this.bufferSize * 0.8));
      if (newBufferSize !== this.bufferSize) {
        console.log(
          `Adapting buffer size: ${this.bufferSize} -> ${newBufferSize}`
        );
        this.bufferSize = newBufferSize;
        this.recreateProcessorNode();
      }
    }
  }

  recreateProcessorNode() {
    if (this.processorNode && this.sourceNode && this.audioContext) {
      // Disconnect old processor
      this.processorNode.disconnect();

      // Create new processor with updated buffer size
      this.processorNode = this.audioContext.createScriptProcessor(
        this.bufferSize,
        1,
        1
      );
      this.processorNode.onaudioprocess = this.processAudioData.bind(this);

      // Reconnect
      this.sourceNode.connect(this.processorNode);
      this.processorNode.connect(this.audioContext.destination);

      console.log(
        "Recreated processor node with buffer size:",
        this.bufferSize
      );
    }
  }

  handleBackendError(errorData) {
    console.error("Backend error:", errorData.message);

    // Handle specific error types
    if (errorData.message.includes("Audio chunk processing error")) {
      console.log("Attempting to resend audio configuration");
      this.sendAudioConfig();
    } else if (errorData.message.includes("decompression")) {
      console.log("Disabling compression due to backend error");
      // Could disable compression in next chunks
    }
  }

  adjustQualitySettings(qualityData) {
    // Adjust capture settings based on backend feedback
    if (
      qualityData.suggestedBufferSize &&
      qualityData.suggestedBufferSize !== this.bufferSize
    ) {
      console.log(
        `Adjusting buffer size from ${this.bufferSize} to ${qualityData.suggestedBufferSize}`
      );
      this.bufferSize = qualityData.suggestedBufferSize;

      // Recreate processor node with new buffer size
      if (this.processorNode) {
        this.processorNode.disconnect();
        this.processorNode = this.audioContext.createScriptProcessor(
          this.bufferSize,
          1,
          1
        );
        this.processorNode.onaudioprocess = this.processAudioData.bind(this);
        this.sourceNode.connect(this.processorNode);
        this.processorNode.connect(this.audioContext.destination);
      }
    }
  }

  playTranslatedAudio(audioData) {
    // This will be implemented in the next part (audio playback)
    console.log("Received translated audio:", audioData);
  }

  stopCapture() {
    console.log("Stopping audio capture");

    this.isCapturing = false;

    // Stop monitoring
    this.stopQualityMonitoring();

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
    if (this.audioContext && this.audioContext.state !== "closed") {
      this.audioContext.close();
      this.audioContext = null;
    }

    // Stop media stream
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
      this.mediaStream = null;
    }

    // Send stop command to backend
    if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
      this.websocket.send(
        JSON.stringify({
          type: "audio_config",
          config: { action: "stop" },
        })
      );
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
      websocketState: this.websocket
        ? this.websocket.readyState
        : "disconnected",
    };
  }
}

class TrueToneYouTube {
  constructor() {
    this.isTranslating = false;
    this.config = {
      targetLanguage: "es",
      volume: 80,
      voiceCloning: true,
    };

    this.audioCaptureManager = new AudioCaptureManager();
    this.playerStateObserver = null;
    this.qualityMonitorInterval = null;

    this.setupMessageListener();
    this.detectYouTubePlayer();
    this.createUI();
    this.setupPlayerStateMonitoring();
  }

  setupMessageListener() {
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      console.log("Content script received message:", request);

      switch (request.action) {
        case "startTranslation":
          this.config = request.config;
          this.startTranslation();
          sendResponse({ success: true });
          break;

        case "stopTranslation":
          this.stopTranslation();
          sendResponse({ success: true });
          break;

        case "updateConfig":
          this.config = request.config;
          sendResponse({ success: true });
          break;

        case "getAudioStats":
          sendResponse({ stats: this.audioCaptureManager.getAudioStats() });
          break;

        default:
          sendResponse({ success: false, error: "Unknown action" });
      }
    });
  }

  setupPlayerStateMonitoring() {
    // Monitor YouTube player state changes
    const video = document.querySelector("video");
    if (video) {
      video.addEventListener("play", () =>
        this.handlePlayerStateChange("playing")
      );
      video.addEventListener("pause", () =>
        this.handlePlayerStateChange("paused")
      );
      video.addEventListener("seeking", () =>
        this.handlePlayerStateChange("seeking")
      );
      video.addEventListener("loadstart", () =>
        this.handlePlayerStateChange("loading")
      );

      // Monitor for ad changes
      const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
          if (mutation.type === "childList") {
            const adElement = document.querySelector(".video-ads");
            if (adElement) {
              this.handlePlayerStateChange("ad_playing");
            } else {
              this.handlePlayerStateChange("ad_ended");
            }
          }
        });
      });

      observer.observe(document.body, {
        childList: true,
        subtree: true,
      });

      this.playerStateObserver = observer;
    }
  }

  handlePlayerStateChange(state) {
    console.log("YouTube player state changed:", state);

    if (this.isTranslating) {
      // Send state change to backend
      if (
        this.audioCaptureManager.websocket &&
        this.audioCaptureManager.websocket.readyState === WebSocket.OPEN
      ) {
        this.audioCaptureManager.websocket.send(
          JSON.stringify({
            type: "player_state_change",
            state: state,
            timestamp: Date.now(),
          })
        );
      }

      // Handle specific state changes
      switch (state) {
        case "seeking":
          // Clear audio buffer on seek to avoid stale data
          this.audioCaptureManager.audioBuffer = [];
          break;
        case "paused":
          // Could reduce processing to save resources
          break;
        case "playing":
          // Resume full processing
          break;
      }
    }
  }

  detectYouTubePlayer() {
    const checkForPlayer = () => {
      const player = document.querySelector(
        "#movie_player, .html5-video-player"
      );
      if (player) {
        console.log("YouTube player detected");
        this.playerElement = player;
        return true;
      }
      return false;
    };

    if (!checkForPlayer()) {
      // Wait for player to load
      const observer = new MutationObserver((mutations, obs) => {
        if (checkForPlayer()) {
          obs.disconnect();
        }
      });

      observer.observe(document.body, {
        childList: true,
        subtree: true,
      });
    }
  }

  createUI() {
    // Create floating UI element
    this.uiElement = document.createElement("div");
    this.uiElement.id = "truetone-ui";
    this.uiElement.style.cssText = `
      position: fixed;
      top: 100px;
      right: 20px;
      width: 250px;
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: white;
      padding: 15px;
      border-radius: 10px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.3);
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      font-size: 14px;
      z-index: 10000;
      display: none;
      backdrop-filter: blur(10px);
    `;

    this.uiElement.innerHTML = `
      <div style="margin-bottom: 10px;">
        <strong>🎵 TrueTone</strong>
        <button id="truetone-close" style="float: right; background: none; border: none; color: white; cursor: pointer; font-size: 16px;">×</button>
      </div>
      
      <div style="margin-bottom: 10px;">
        <div>Status: <span id="truetone-status">Ready</span></div>
        <div>Quality: <span id="truetone-quality">Good</span></div>
      </div>
      
      <div style="margin-bottom: 10px;">
        <div style="margin-bottom: 5px;">Language: ${
          this.config.targetLanguage
        }</div>
        <div style="margin-bottom: 5px;">Volume: ${this.config.volume}%</div>
        <div>Voice Cloning: ${this.config.voiceCloning ? "On" : "Off"}</div>
      </div>
      
      <div>
        <button id="truetone-toggle" style="
          background: rgba(255,255,255,0.2);
          border: 1px solid rgba(255,255,255,0.3);
          color: white;
          padding: 8px 16px;
          border-radius: 5px;
          cursor: pointer;
          width: 100%;
        ">Stop Translation</button>
      </div>
    `;

    document.body.appendChild(this.uiElement);

    // Add event listeners
    document.getElementById("truetone-close").addEventListener("click", () => {
      this.hideUI();
    });

    document.getElementById("truetone-toggle").addEventListener("click", () => {
      if (this.isTranslating) {
        this.stopTranslation();
      } else {
        this.startTranslation();
      }
    });

    // Store UI elements for easy access
    this.statusElement = document.getElementById("truetone-status");
    this.qualityElement = document.getElementById("truetone-quality");
    this.toggleButton = document.getElementById("truetone-toggle");
  }

  showUI() {
    this.uiElement.style.display = "block";
  }

  hideUI() {
    this.uiElement.style.display = "none";
  }

  updateStatus(status) {
    if (this.statusElement) {
      this.statusElement.textContent = status;
    }
  }

  updateQuality(quality) {
    if (this.qualityElement) {
      this.qualityElement.textContent = quality;

      // Color code quality
      const colors = {
        Excellent: "#4CAF50",
        Good: "#8BC34A",
        Fair: "#FFC107",
        Poor: "#FF9800",
        Bad: "#F44336",
      };

      this.qualityElement.style.color = colors[quality] || "white";
    }
  }

  async startTranslation() {
    console.log("Starting translation with config:", this.config);

    try {
      this.isTranslating = true;
      this.showUI();
      this.updateStatus("Connecting...");

      // Connect to backend
      await this.audioCaptureManager.connectToBackend();
      this.updateStatus("Initializing...");

      // Start audio capture
      const success = await this.audioCaptureManager.initializeAudioCapture(
        this.config
      );

      if (success) {
        this.updateStatus("Translating");
        this.toggleButton.textContent = "Stop Translation";

        // Start quality monitoring
        this.startQualityMonitoring();
      } else {
        throw new Error("Failed to initialize audio capture");
      }
    } catch (error) {
      console.error("Error starting translation:", error);
      this.updateStatus("Error");
      this.stopTranslation();
    }
  }

  startQualityMonitoring() {
    // Monitor audio quality every 2 seconds
    this.qualityMonitorInterval = setInterval(() => {
      const stats = this.audioCaptureManager.getAudioStats();

      if (stats.isCapturing) {
        const metrics = stats.qualityMetrics;
        let quality = "Good";

        if (metrics.averageLevel < 0.01) {
          quality = "Poor"; // Too quiet
        } else if (metrics.peakLevel >= 0.99) {
          quality = "Bad"; // Clipping
        } else if (metrics.averageLevel > 0.1) {
          quality = "Excellent"; // Good levels
        }

        this.updateQuality(quality);

        // Update status based on connection
        if (stats.websocketState === 1) {
          // WebSocket.OPEN
          this.updateStatus("Translating");
        } else {
          this.updateStatus("Reconnecting...");
        }
      }
    }, 2000);
  }

  async stopTranslation() {
    console.log("Stopping translation");

    this.isTranslating = false;

    // Stop quality monitoring
    if (this.qualityMonitorInterval) {
      clearInterval(this.qualityMonitorInterval);
      this.qualityMonitorInterval = null;
    }

    // Stop audio capture
    this.audioCaptureManager.stopCapture();

    // Update UI
    this.updateStatus("Stopped");
    this.toggleButton.textContent = "Start Translation";
    this.hideUI();
  }

  async restartTranslation() {
    console.log("Restarting translation for new video");
    await this.stopTranslation();
    setTimeout(() => this.startTranslation(), 1000);
  }
}

// Initialize when page loads
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    new TrueToneYouTube();
  });
} else {
  new TrueToneYouTube();
}
