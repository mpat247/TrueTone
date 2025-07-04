// TrueTone Chrome Extension - Background Script (Service Worker)
console.log('TrueTone background script loaded');

class TrueToneBackground {
  constructor() {
    this.setupMessageListener();
    this.setupTabCapture();
  }
  
  setupMessageListener() {
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      console.log('Background received message:', request);
      
      switch (request.action) {
        case 'getCurrentTabId':
          this.getCurrentTabId().then(tabId => {
            sendResponse({ tabId });
          });
          return true; // Keep message channel open for async response
          
        case 'startTabCapture':
          this.startTabCapture(request.tabId).then(streamId => {
            sendResponse({ streamId });
          });
          return true;
          
        default:
          sendResponse({ success: false, error: 'Unknown action' });
      }
    });
  }
  
  async getCurrentTabId() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      return tab.id;
    } catch (error) {
      console.error('Error getting current tab ID:', error);
      return null;
    }
  }
  
  async startTabCapture(tabId) {
    try {
      const streamId = await chrome.tabCapture.capture({
        audio: true,
        video: false
      });
      
      console.log('Tab capture started with stream ID:', streamId);
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
