// TrueTone Chrome Extension - Background Script (Service Worker)
console.log('TrueTone background script loaded');

class TrueToneBackground {
  constructor() {
    this.activeCaptures = new Map(); // Track active captures
    this.captureRetryCount = new Map(); // Track retry attempts
    this.maxRetryAttempts = 3;
    
    this.setupMessageListener();
    this.setupTabCapture();
    this.setupTabEventListeners();
  }
  
  setupMessageListener() {
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      console.log('Background received message:', request);
      
      switch (request.action) {
        case 'getCurrentTabId':
          this.getCurrentTabId().then(tabId => {
            sendResponse({ tabId });
          }).catch(error => {
            console.error('Error getting tab ID:', error);
            sendResponse({ error: error.message });
          });
          return true; // Keep message channel open for async response
          
        case 'startTabCapture':
          this.startTabCapture(request.tabId, request.options).then(result => {
            sendResponse(result);
          }).catch(error => {
            console.error('Error starting tab capture:', error);
            sendResponse({ error: error.message });
          });
          return true;
          
        case 'stopTabCapture':
          this.stopTabCapture(request.tabId).then(result => {
            sendResponse(result);
          }).catch(error => {
            console.error('Error stopping tab capture:', error);
            sendResponse({ error: error.message });
          });
          return true;
          
        case 'checkCaptureStatus':
          this.checkCaptureStatus(request.tabId).then(status => {
            sendResponse({ status });
          });
          return true;
          
        case 'requestPermissions':
          this.requestTabCapturePermissions().then(granted => {
            sendResponse({ granted });
          });
          return true;
          
        default:
          sendResponse({ success: false, error: 'Unknown action' });
      }
    });
  }

  setupTabEventListeners() {
    // Listen for tab updates (URL changes, reloads, etc.)
    chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
      if (changeInfo.status === 'complete' && this.activeCaptures.has(tabId)) {
        console.log('Tab updated, checking if capture is still valid:', tabId);
        this.validateActiveCapture(tabId);
      }
    });

    // Listen for tab removal
    chrome.tabs.onRemoved.addListener((tabId) => {
      if (this.activeCaptures.has(tabId)) {
        console.log('Tab closed, cleaning up capture:', tabId);
        this.cleanupCapture(tabId);
      }
    });

    // Listen for tab activation
    chrome.tabs.onActivated.addListener((activeInfo) => {
      console.log('Tab activated:', activeInfo.tabId);
      // Could optimize capture based on active tab
    });
  }

  async validateActiveCapture(tabId) {
    try {
      const tab = await chrome.tabs.get(tabId);
      
      // Check if it's still a YouTube tab
      if (!tab.url.includes('youtube.com/watch')) {
        console.log('Tab is no longer a YouTube video, stopping capture');
        await this.stopTabCapture(tabId);
        return false;
      }
      
      // Check if capture is still active
      const captureInfo = await chrome.tabCapture.getCaptureInfo(tabId);
      if (!captureInfo || captureInfo.status !== 'active') {
        console.log('Capture is no longer active, attempting restart');
        await this.restartTabCapture(tabId);
      }
      
      return true;
    } catch (error) {
      console.error('Error validating capture:', error);
      return false;
    }
  }

  async restartTabCapture(tabId) {
    try {
      console.log('Restarting tab capture for tab:', tabId);
      
      // Stop existing capture
      await this.stopTabCapture(tabId);
      
      // Wait a moment before restarting
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Start new capture
      const result = await this.startTabCapture(tabId);
      
      if (result.success) {
        console.log('Tab capture restarted successfully');
        // Notify content script of restart
        chrome.tabs.sendMessage(tabId, {
          action: 'captureRestarted',
          streamId: result.streamId
        });
      }
      
      return result;
    } catch (error) {
      console.error('Error restarting tab capture:', error);
      return { success: false, error: error.message };
    }
  }
  
  async getCurrentTabId() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      if (!tab) {
        throw new Error('No active tab found');
      }
      
      // Verify it's a YouTube tab
      if (!tab.url.includes('youtube.com')) {
        throw new Error('Current tab is not YouTube');
      }
      
      return tab.id;
    } catch (error) {
      console.error('Error getting current tab ID:', error);
      throw error;
    }
  }
  
  async startTabCapture(tabId, options = {}) {
    try {
      console.log('Starting tab capture for tab:', tabId, 'with options:', options);
      
      // Check if we already have an active capture for this tab
      if (this.activeCaptures.has(tabId)) {
        const existingCapture = this.activeCaptures.get(tabId);
        console.log('Tab already has active capture:', existingCapture);
        return { success: true, streamId: existingCapture.streamId, existing: true };
      }
      
      // Check permissions first
      const hasPermission = await this.checkTabCapturePermissions();
      if (!hasPermission) {
        throw new Error('Tab capture permission not granted');
      }
      
      // Prepare capture options
      const captureOptions = {
        audio: true,
        video: false,
        audioConstraints: {
          mandatory: {
            chromeMediaSource: 'tab',
            chromeMediaSourceId: tabId.toString()
          },
          optional: [
            { echoCancellation: false },
            { googEchoCancellation: false },
            { googAutoGainControl: false },
            { googNoiseSuppression: false },
            { googHighpassFilter: false }
          ]
        },
        ...options
      };
      
      // Start capture
      const captureInfo = await new Promise((resolve, reject) => {
        chrome.tabCapture.capture(captureOptions, (stream) => {
          if (chrome.runtime.lastError) {
            reject(new Error(chrome.runtime.lastError.message));
            return;
          }
          
          if (!stream) {
            reject(new Error('Failed to capture tab audio stream'));
            return;
          }
          
          resolve({
            stream: stream,
            streamId: stream.id,
            options: captureOptions
          });
        });
      });
      
      // Store capture info
      this.activeCaptures.set(tabId, {
        streamId: captureInfo.streamId,
        stream: captureInfo.stream,
        startTime: Date.now(),
        options: captureOptions
      });
      
      // Reset retry count on success
      this.captureRetryCount.delete(tabId);
      
      console.log('Tab capture started successfully:', captureInfo.streamId);
      return { 
        success: true, 
        streamId: captureInfo.streamId,
        captureInfo: captureInfo
      };
      
    } catch (error) {
      console.error('Error starting tab capture:', error);
      
      // Handle retry logic
      const retryCount = this.captureRetryCount.get(tabId) || 0;
      if (retryCount < this.maxRetryAttempts) {
        console.log(`Retrying tab capture (attempt ${retryCount + 1}/${this.maxRetryAttempts})`);
        this.captureRetryCount.set(tabId, retryCount + 1);
        
        // Wait before retry with exponential backoff
        const delay = Math.min(1000 * Math.pow(2, retryCount), 5000);
        await new Promise(resolve => setTimeout(resolve, delay));
        
        return this.startTabCapture(tabId, options);
      }
      
      // Max retries reached
      this.captureRetryCount.delete(tabId);
      throw error;
    }
  }

  async stopTabCapture(tabId) {
    try {
      console.log('Stopping tab capture for tab:', tabId);
      
      const captureInfo = this.activeCaptures.get(tabId);
      if (!captureInfo) {
        console.log('No active capture found for tab:', tabId);
        return { success: true, message: 'No active capture' };
      }
      
      // Stop the stream
      if (captureInfo.stream) {
        captureInfo.stream.getTracks().forEach(track => {
          track.stop();
        });
      }
      
      // Clean up
      this.cleanupCapture(tabId);
      
      console.log('Tab capture stopped successfully');
      return { success: true };
      
    } catch (error) {
      console.error('Error stopping tab capture:', error);
      return { success: false, error: error.message };
    }
  }

  cleanupCapture(tabId) {
    this.activeCaptures.delete(tabId);
    this.captureRetryCount.delete(tabId);
    console.log('Cleaned up capture data for tab:', tabId);
  }

  async checkCaptureStatus(tabId) {
    try {
      if (!this.activeCaptures.has(tabId)) {
        return { active: false, message: 'No capture active' };
      }
      
      const captureInfo = await chrome.tabCapture.getCaptureInfo(tabId);
      
      if (!captureInfo) {
        // Capture info not found, clean up our records
        this.cleanupCapture(tabId);
        return { active: false, message: 'Capture not found' };
      }
      
      return {
        active: captureInfo.status === 'active',
        status: captureInfo.status,
        captureInfo: captureInfo,
        localInfo: this.activeCaptures.get(tabId)
      };
      
    } catch (error) {
      console.error('Error checking capture status:', error);
      return { active: false, error: error.message };
    }
  }

  async checkTabCapturePermissions() {
    return new Promise((resolve) => {
      chrome.permissions.contains({
        permissions: ['tabCapture']
      }, (result) => {
        resolve(result);
      });
    });
  }

  async requestTabCapturePermissions() {
    return new Promise((resolve) => {
      chrome.permissions.request({
        permissions: ['tabCapture']
      }, (granted) => {
        console.log('Tab capture permission granted:', granted);
        resolve(granted);
      });
    });
  }
      return streamId;
    } catch (error) {
      console.error('Error starting tab capture:', error);
      throw error;
    }
  }
  
  setupTabCapture() {
    // Listen for tab updates to restart capture if needed
    chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
      if (changeInfo.status === 'complete' && tab.url && tab.url.includes('youtube.com')) {
        console.log('YouTube tab updated:', tabId);
        // Notify content script if needed
      }
    });
  }
}

// Initialize background script
new TrueToneBackground();
