// TrueTone Chrome Extension - Background Script (Service Worker)
console.log("TrueTone background script loaded");

class TrueToneBackground {
  constructor() {
    this.activeStream = null;
    this.capturedTabId = null;
    this.setupMessageListener();
    this.setupTabCapture();
  }

  setupMessageListener() {
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      console.log("Background received message:", request);

      switch (request.action) {
        case "getCurrentTabId":
          this.getCurrentTabId().then((tabId) => {
            sendResponse({ tabId });
          });
          return true; // Keep message channel open for async response

        case "startTabCapture":
          this.startTabCapture(sender.tab.id)
            .then((stream) => {
              sendResponse({ success: true, stream });
            })
            .catch((error) => {
              sendResponse({ success: false, error: error.message });
            });
          return true;

        case "stopTabCapture":
          this.stopTabCapture();
          sendResponse({ success: true });
          break;

        default:
          sendResponse({ success: false, error: "Unknown action" });
      }
    });
  }

  async getCurrentTabId() {
    try {
      const [tab] = await chrome.tabs.query({
        active: true,
        currentWindow: true,
      });
      return tab.id;
    } catch (error) {
      console.error("Error getting current tab ID:", error);
      return null;
    }
  }

  async startTabCapture(tabId) {
    try {
      // Stop any existing capture
      this.stopTabCapture();

      console.log("Starting tab capture for tab:", tabId);
      console.log("Available Chrome APIs:", {
        tabCapture: !!chrome.tabCapture,
        tabCaptureCapture: !!(chrome.tabCapture && chrome.tabCapture.capture),
        permissions: chrome.runtime.getManifest().permissions,
      });

      // Check if tabCapture API is available
      if (!chrome.tabCapture) {
        throw new Error("chrome.tabCapture API not available");
      }

      if (!chrome.tabCapture.capture) {
        throw new Error("chrome.tabCapture.capture function not available");
      }

      // For Manifest V3, we need to use chrome.tabCapture.capture
      // The tab needs to be active for this to work
      let stream;

      // First, ensure the tab is active
      console.log("Making tab active...");
      await chrome.tabs.update(tabId, { active: true });

      // Small delay to ensure tab is active
      await new Promise((resolve) => setTimeout(resolve, 300));

      console.log("Attempting to capture tab audio...");

      // Now try to capture the tab
      stream = await new Promise((resolve, reject) => {
        chrome.tabCapture.capture(
          {
            audio: true,
            video: false,
          },
          (capturedStream) => {
            console.log("tabCapture.capture callback called");
            console.log("chrome.runtime.lastError:", chrome.runtime.lastError);
            console.log("capturedStream:", capturedStream);

            if (chrome.runtime.lastError) {
              reject(new Error(chrome.runtime.lastError.message));
            } else if (!capturedStream) {
              reject(new Error("No stream returned from tabCapture.capture"));
            } else {
              resolve(capturedStream);
            }
          }
        );
      });

      if (!stream) {
        throw new Error("Tab capture failed - no stream returned");
      }

      console.log("Tab capture started successfully for tab:", tabId);

      // Store the stream for later cleanup
      this.activeStream = stream;
      this.capturedTabId = tabId;

      // Analyze audio format
      this.detectAudioFormat(stream);

      return stream;
    } catch (error) {
      console.error("Error starting tab capture:", error);
      throw error;
    }
  }

  detectAudioFormat(stream) {
    // Create a temporary audio context to analyze the stream
    const audioContext = new AudioContext();
    const source = audioContext.createMediaStreamSource(stream);
    const analyzer = audioContext.createAnalyser();

    analyzer.fftSize = 2048;
    source.connect(analyzer);

    // Get format details
    const format = {
      sampleRate: audioContext.sampleRate,
      channels: 1, // Tab capture is typically mono
      bitDepth: 32, // Float32 data
    };

    console.log("Detected audio format:", format);

    // Clean up analyzer after a short time (we just need the initial reading)
    setTimeout(() => {
      source.disconnect();
      audioContext
        .close()
        .catch((err) => console.error("Error closing audio context:", err));
    }, 1000);

    return format;
  }

  stopTabCapture() {
    if (this.activeStream) {
      // Stop all tracks in the stream
      this.activeStream.getTracks().forEach((track) => {
        track.stop();
        console.log(`Stopped track: ${track.kind} (${track.id})`);
      });

      this.activeStream = null;
      this.capturedTabId = null;
      console.log("Tab capture stopped and resources cleaned up");
    }
  }

  setupTabCapture() {
    // Listen for tab updates to restart capture if needed
    chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
      if (
        changeInfo.status === "complete" &&
        tab.url &&
        tab.url.includes("youtube.com")
      ) {
        console.log("YouTube tab updated:", tabId);

        // Check if the video changed on an already-captured tab
        if (this.activeStream && this.capturedTabId === tabId) {
          console.log(
            "Detected video change on active tab, notifying content script"
          );

          // Notify content script about the change
          chrome.tabs
            .sendMessage(tabId, {
              action: "videoChanged",
              tabId: tabId,
            })
            .catch((err) => {
              console.error("Error notifying content script:", err);
            });
        }
      }
    });

    // Listen for tab closure to clean up resources
    chrome.tabs.onRemoved.addListener((tabId) => {
      if (this.capturedTabId === tabId) {
        console.log("Captured tab closed, stopping capture");
        this.stopTabCapture();
      }
    });
  }
}

// Initialize background script
new TrueToneBackground();
