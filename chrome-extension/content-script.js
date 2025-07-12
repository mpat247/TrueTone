// TrueTone Chrome Extension - Content Script
console.log("TrueTone content script loaded on:", window.location.href);

class TrueToneYouTube {
  constructor() {
    this.isTranslating = false;
    this.config = {
      targetLanguage: "es",
      volume: 80,
      voiceCloning: true,
    };

    this.audioContext = null;
    this.mediaStream = null;
    this.websocket = null;
    this.audioBuffer = null;
    this.bufferSize = 4096; // Default buffer size, will be adjusted dynamically
    this.audioProcessor = null;
    this.lastChunkTimestamp = 0;
    this.reconnectAttempts = 0;
    this.maxReconnectAttempts = 5;
    this.reconnectInterval = 2000; // ms
    this.networkStats = {
      packetsLost: 0,
      avgLatency: 0,
      chunksSent: 0,
    };

    this.setupMessageListener();
    this.detectYouTubePlayer();
    this.createUI();
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

        default:
          sendResponse({ success: false, error: "Unknown action" });
      }
    });
  }

  detectYouTubePlayer() {
    // Wait for YouTube player to load
    const checkForPlayer = () => {
      const player = document.querySelector("video");
      if (player) {
        console.log("YouTube player detected");
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
        if (
          mutation.type === "attributes" &&
          mutation.attributeName === "src"
        ) {
          console.log("New video detected");
          if (this.isTranslating) {
            this.restartTranslation();
          }
        }
      });
    });

    observer.observe(this.videoElement, {
      attributes: true,
      attributeFilter: ["src"],
    });
  }

  createUI() {
    // Create floating UI indicator
    const ui = document.createElement("div");
    ui.id = "truetone-indicator";
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
    this.uiElement = ui.querySelector("div");
    this.statusElement = ui.querySelector("#truetone-status");
  }

  showUI() {
    this.uiElement.style.display = "block";
  }

  hideUI() {
    this.uiElement.style.display = "none";
  }

  updateStatus(status) {
    this.statusElement.textContent = status;
  }

  async startTranslation() {
    console.log("Starting translation with config:", this.config);

    try {
      this.isTranslating = true;
      this.showUI();
      this.updateStatus("Starting...");

      // Connect to backend
      await this.connectToBackend();

      // Start audio capture
      await this.startAudioCapture();

      this.updateStatus("Translating");
    } catch (error) {
      console.error("Error starting translation:", error);
      this.updateStatus("Error");
      this.stopTranslation();
    }
  }

  async stopTranslation() {
    console.log("Stopping translation");

    this.isTranslating = false;
    this.hideUI();

    // Stop audio capture
    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((track) => track.stop());
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
    console.log("Restarting translation for new video");
    await this.stopTranslation();
    setTimeout(() => this.startTranslation(), 1000);
  }

  async connectToBackend() {
    return new Promise((resolve, reject) => {
      const backendUrl = "ws://localhost:8000/ws";
      this.updateStatus(`Connecting to backend...`);

      try {
        this.websocket = new WebSocket(backendUrl);

        this.websocket.onopen = () => {
          console.log("Connected to TrueTone backend");
          this.reconnectAttempts = 0; // Reset reconnect counter on successful connection

          // Send initial config to server
          this.websocket.send(
            JSON.stringify({
              type: "config",
              data: {
                targetLanguage: this.config.targetLanguage,
                voiceCloning: this.config.voiceCloning,
                clientId: this.getClientId(),
                audioFormat: {
                  sampleRate: this.audioContext
                    ? this.audioContext.sampleRate
                    : 44100,
                  channels: 1,
                  encoding: "float32",
                },
              },
            })
          );

          resolve();
        };

        this.websocket.onmessage = (event) => {
          try {
            // Handle different message types from the backend
            if (typeof event.data === "string") {
              const message = JSON.parse(event.data);

              switch (message.type) {
                case "translation":
                  // Handle translated text
                  console.log("Received translation:", message.data);
                  break;

                case "audio":
                  // Handle translated audio (metadata)
                  console.log("Received audio metadata:", message.data);
                  break;

                case "status":
                  // Update UI with status from backend
                  this.updateStatus(message.data.status);
                  break;

                case "error":
                  console.error("Backend error:", message.data);
                  this.updateStatus(`Error: ${message.data.message}`);
                  break;

                case "latency":
                  // Update network stats
                  this.networkStats.avgLatency = message.data.latency;
                  break;

                default:
                  console.log("Received message from backend:", message);
              }
            } else if (event.data instanceof Blob) {
              // Handle binary audio data
              this.handleTranslatedAudio(event.data);
            }
          } catch (error) {
            console.error("Error processing WebSocket message:", error);
          }
        };

        this.websocket.onerror = (error) => {
          console.error("WebSocket error:", error);
          this.updateStatus("Connection error");
          reject(error);
        };

        this.websocket.onclose = (event) => {
          console.log(
            `Disconnected from backend: ${event.code} ${event.reason}`
          );
          this.updateStatus("Disconnected");

          // Try to reconnect if this wasn't a normal closure and we're still translating
          if (
            this.isTranslating &&
            event.code !== 1000 &&
            event.code !== 1001
          ) {
            this.attemptReconnect();
          }
        };
      } catch (error) {
        console.error("Error creating WebSocket:", error);
        this.updateStatus("Connection failed");
        reject(error);
      }
    });
  }

  getClientId() {
    // Generate a unique client ID if none exists
    if (!this.clientId) {
      this.clientId =
        "truetone-" +
        Date.now() +
        "-" +
        Math.random().toString(36).substr(2, 9);
    }
    return this.clientId;
  }

  attemptReconnect() {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error("Maximum reconnection attempts reached");
      this.updateStatus("Connection failed");
      this.stopTranslation();
      return;
    }

    this.reconnectAttempts++;
    const delay =
      this.reconnectInterval * Math.pow(1.5, this.reconnectAttempts - 1);

    this.updateStatus(
      `Reconnecting (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`
    );
    console.log(
      `Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`
    );

    setTimeout(() => {
      if (this.isTranslating) {
        this.connectToBackend().catch((error) => {
          console.error("Reconnection failed:", error);
        });
      }
    }, delay);
  }

  handleTranslatedAudio(audioBlob) {
    // Create an audio element to play the translated audio
    const audioUrl = URL.createObjectURL(audioBlob);
    const audio = new Audio(audioUrl);

    // Set volume based on user preference
    audio.volume = this.config.volume / 100;

    // Clean up when done playing
    audio.onended = () => {
      URL.revokeObjectURL(audioUrl);
    };

    // Play the translated audio
    audio.play().catch((error) => {
      console.error("Error playing translated audio:", error);
    });
  }

  updateUI(state, message) {
    this.showUI();

    switch (state) {
      case "connecting":
        this.updateStatus("Connecting...");
        break;

      case "translating":
        this.updateStatus("Translating");
        break;

      case "error":
        this.updateStatus(`Error: ${message || "Unknown error"}`);
        break;

      default:
        this.updateStatus(state);
    }
  }

  async startAudioCapture() {
    try {
      this.updateStatus("Capturing audio...");

      // Request the background script to handle tab capture (necessary for Manifest V3)
      const response = await new Promise((resolve) => {
        chrome.runtime.sendMessage({ action: "startTabCapture" }, (result) => {
          resolve(result);
        });
      });

      if (!response || !response.success) {
        throw new Error(
          "Failed to capture tab audio: " + (response?.error || "Unknown error")
        );
      }

      // Get the stream from the background script
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: true,
      });

      // Set up audio processing
      await this.setupAudioProcessing();

      console.log("Audio capture started successfully");
    } catch (error) {
      console.error("Error starting audio capture:", error);
      this.updateStatus("Audio capture failed");
      throw error;
    }
  }

  async setupAudioProcessing() {
    // Create audio context with preferred sample rate for ML models
    this.audioContext = new AudioContext({
      sampleRate: 16000, // 16kHz is optimal for most speech recognition models
      latencyHint: "interactive",
    });

    // Initialize audio buffer
    this.setupAudioBuffer();

    // Create audio processor node
    const source = this.audioContext.createMediaStreamSource(this.mediaStream);

    // Create analyzer for audio quality monitoring
    const analyzer = this.audioContext.createAnalyser();
    analyzer.fftSize = 2048;
    source.connect(analyzer);

    // Set up audio processor
    const processor = this.audioContext.createScriptProcessor(4096, 1, 1);

    processor.onaudioprocess = (event) => {
      const inputBuffer = event.inputBuffer;
      const inputData = inputBuffer.getChannelData(0);

      // Add to our circular buffer
      this.audioBuffer.write(inputData);

      // Process and send audio to backend
      this.processAndSendAudio(inputData, this.audioContext.sampleRate);

      // Monitor audio quality
      this.monitorAudioQuality(analyzer);
    };

    source.connect(processor);
    processor.connect(this.audioContext.destination);
    this.audioProcessor = processor;

    console.log("Audio processing pipeline established");
  }

  setupAudioBuffer() {
    // Create a circular buffer for audio data
    const bufferSeconds = 5; // Store 5 seconds of audio
    const bufferSize = this.audioContext.sampleRate * bufferSeconds;

    this.audioBuffer = {
      buffer: new Float32Array(bufferSize),
      writePos: 0,
      readPos: 0,
      length: 0,
      capacity: bufferSize,

      write: function (data) {
        const available = this.capacity - this.length;
        if (data.length > available) {
          console.warn("Buffer overflow, dropping oldest data");
          // Move read position forward to make space
          this.readPos =
            (this.readPos + (data.length - available)) % this.capacity;
          this.length = Math.min(
            this.length - (data.length - available),
            this.capacity
          );
        }

        // Copy data to buffer
        for (let i = 0; i < data.length; i++) {
          this.buffer[(this.writePos + i) % this.capacity] = data[i];
        }

        this.writePos = (this.writePos + data.length) % this.capacity;
        this.length = Math.min(this.length + data.length, this.capacity);
      },

      read: function (size) {
        const available = this.length;
        const readSize = Math.min(size, available);

        if (readSize === 0) return new Float32Array(0);

        const result = new Float32Array(readSize);

        for (let i = 0; i < readSize; i++) {
          result[i] = this.buffer[(this.readPos + i) % this.capacity];
        }

        this.readPos = (this.readPos + readSize) % this.capacity;
        this.length -= readSize;

        return result;
      },

      clear: function () {
        this.writePos = 0;
        this.readPos = 0;
        this.length = 0;
      },
    };

    console.log(
      `Circular audio buffer created with ${bufferSeconds} seconds capacity`
    );
  }

  processAndSendAudio(audioData, sampleRate) {
    if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
      return; // Skip if websocket is not ready
    }

    // Calculate optimal chunk size based on network conditions
    const chunkSize = this.calculateOptimalChunkSize();

    // Prepare audio metadata
    const metadata = {
      type: "audio",
      format: "float32",
      sampleRate: sampleRate,
      channels: 1,
      timestamp: Date.now(),
      sequence: this.networkStats.chunksSent++,
      config: {
        targetLanguage: this.config.targetLanguage,
        voiceCloning: this.config.voiceCloning,
      },
    };

    // Convert float32 audio data to int16 for more efficient transmission
    const int16Data = new Int16Array(audioData.length);
    for (let i = 0; i < audioData.length; i++) {
      // Convert float32 (-1.0 to 1.0) to int16 (-32768 to 32767)
      int16Data[i] = Math.max(-32768, Math.min(32767, audioData[i] * 32767));
    }

    // Compress audio data
    this.compressAudioData(int16Data, metadata)
      .then((compressedData) => {
        // Send audio chunk with metadata
        this.sendAudioChunk(compressedData, metadata);
      })
      .catch((error) => {
        console.error("Error compressing audio:", error);
        // Fall back to sending uncompressed data
        this.sendAudioChunk(int16Data.buffer, metadata);
      });
  }

  async compressAudioData(audioData, metadata) {
    // In a real implementation, we would use Web Codecs API or a library
    // For this demo, we'll simulate compression by just returning the buffer
    // In production, you would use Opus or another audio codec

    // For now, we'll just return the array buffer
    return audioData.buffer;
  }

  sendAudioChunk(audioBuffer, metadata) {
    if (!this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
      return;
    }

    // First send the metadata as a JSON message
    this.websocket.send(JSON.stringify(metadata));

    // Then send the binary audio data
    this.websocket.send(audioBuffer);

    // Record timestamp for latency calculation
    this.lastChunkTimestamp = metadata.timestamp;
  }

  calculateOptimalChunkSize() {
    // Start with default size
    let chunkSize = 4096;

    // Adjust based on network conditions
    if (this.networkStats.avgLatency > 300) {
      // High latency, reduce chunk size
      chunkSize = 2048;
    } else if (this.networkStats.avgLatency < 100) {
      // Low latency, increase chunk size for efficiency
      chunkSize = 8192;
    }

    // Adjust based on packet loss
    if (this.networkStats.packetsLost > 2) {
      // Higher packet loss, reduce chunk size
      chunkSize = Math.max(1024, chunkSize / 2);
    }

    return chunkSize;
  }

  monitorAudioQuality(analyzer) {
    // Get frequency data
    const bufferLength = analyzer.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    analyzer.getByteFrequencyData(dataArray);

    // Calculate simple audio quality metrics
    let sum = 0;
    let peak = 0;

    for (let i = 0; i < bufferLength; i++) {
      sum += dataArray[i];
      peak = Math.max(peak, dataArray[i]);
    }

    const average = sum / bufferLength;

    // Detect silence or very low audio
    if (peak < 10) {
      console.warn("Low audio level detected");
    }

    // Log quality periodically (every 5 seconds)
    if (Date.now() % 5000 < 100) {
      console.log(
        `Audio quality metrics - Avg: ${average.toFixed(2)}, Peak: ${peak}`
      );
    }
  }

  async getCurrentTabId() {
    return new Promise((resolve) => {
      chrome.runtime.sendMessage({ action: "getCurrentTabId" }, (response) => {
        resolve(response.tabId);
      });
    });
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
