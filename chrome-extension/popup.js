// TrueTone Chrome Extension - Popup JavaScript
console.log('TrueTone popup loaded');

class TrueTonePopup {
  constructor() {
    this.isTranslating = false;
    this.isVoiceCloning = true;
    this.targetLanguage = 'es';
    this.volume = 80;
    
    this.initializeElements();
    this.setupEventListeners();
    this.checkYouTubeStatus();
    this.checkBackendStatus();
  }
  
  initializeElements() {
    this.elements = {
      translateToggle: document.getElementById('translate-toggle'),
      voiceCloneToggle: document.getElementById('voice-clone-toggle'),
      targetLanguage: document.getElementById('target-language'),
      volumeSlider: document.getElementById('volume-slider'),
      volumeValue: document.getElementById('volume-value'),
      youtubeStatus: document.getElementById('youtube-status'),
      youtubeText: document.getElementById('youtube-text'),
      backendStatus: document.getElementById('backend-status'),
      backendText: document.getElementById('backend-text')
    };
  }
  
  setupEventListeners() {
    // Translation toggle
    this.elements.translateToggle.addEventListener('click', () => {
      this.toggleTranslation();
    });
    
    // Voice cloning toggle
    this.elements.voiceCloneToggle.addEventListener('click', () => {
      this.toggleVoiceCloning();
    });
    
    // Language selection
    this.elements.targetLanguage.addEventListener('change', (e) => {
      this.targetLanguage = e.target.value;
      this.updateContentScript();
    });
    
    // Volume slider
    this.elements.volumeSlider.addEventListener('input', (e) => {
      this.volume = e.target.value;
      this.elements.volumeValue.textContent = `${this.volume}%`;
      this.updateContentScript();
    });
  }
  
  toggleTranslation() {
    this.isTranslating = !this.isTranslating;
    
    if (this.isTranslating) {
      this.elements.translateToggle.textContent = 'Stop Translation';
      this.elements.translateToggle.classList.add('active');
      this.startTranslation();
    } else {
      this.elements.translateToggle.textContent = 'Start Translation';
      this.elements.translateToggle.classList.remove('active');
      this.stopTranslation();
    }
  }
  
  toggleVoiceCloning() {
    this.isVoiceCloning = !this.isVoiceCloning;
    
    if (this.isVoiceCloning) {
      this.elements.voiceCloneToggle.textContent = 'Voice Cloning: ON';
      this.elements.voiceCloneToggle.classList.add('active');
    } else {
      this.elements.voiceCloneToggle.textContent = 'Voice Cloning: OFF';
      this.elements.voiceCloneToggle.classList.remove('active');
    }
    
    this.updateContentScript();
  }
  
  async startTranslation() {
    console.log('Starting translation...');
    
    try {
      // Get current active tab
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      
      if (!tab.url.includes('youtube.com')) {
        alert('Please open a YouTube video first!');
        this.toggleTranslation();
        return;
      }
      
      // Send message to content script
      await chrome.tabs.sendMessage(tab.id, {
        action: 'startTranslation',
        config: {
          targetLanguage: this.targetLanguage,
          volume: this.volume,
          voiceCloning: this.isVoiceCloning
        }
      });
      
      console.log('Translation started');
      
    } catch (error) {
      console.error('Error starting translation:', error);
      alert('Error starting translation. Please refresh the YouTube page and try again.');
      this.toggleTranslation();
    }
  }
  
  async stopTranslation() {
    console.log('Stopping translation...');
    
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      
      await chrome.tabs.sendMessage(tab.id, {
        action: 'stopTranslation'
      });
      
      console.log('Translation stopped');
      
    } catch (error) {
      console.error('Error stopping translation:', error);
    }
  }
  
  async updateContentScript() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      
      if (tab.url.includes('youtube.com')) {
        await chrome.tabs.sendMessage(tab.id, {
          action: 'updateConfig',
          config: {
            targetLanguage: this.targetLanguage,
            volume: this.volume,
            voiceCloning: this.isVoiceCloning
          }
        });
      }
    } catch (error) {
      console.error('Error updating content script:', error);
    }
  }
  
  async checkYouTubeStatus() {
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
      
      if (tab.url.includes('youtube.com')) {
        this.elements.youtubeStatus.classList.add('connected');
        this.elements.youtubeText.textContent = 'YouTube: Connected';
      } else {
        this.elements.youtubeStatus.classList.remove('connected');
        this.elements.youtubeText.textContent = 'YouTube: Not detected';
      }
    } catch (error) {
      console.error('Error checking YouTube status:', error);
    }
  }
  
  async checkBackendStatus() {
    try {
      const response = await fetch('http://localhost:8000/health');
      
      if (response.ok) {
        this.elements.backendStatus.classList.add('connected');
        this.elements.backendText.textContent = 'Backend: Connected';
      } else {
        throw new Error('Backend not responding');
      }
    } catch (error) {
      console.error('Backend connection error:', error);
      this.elements.backendStatus.classList.remove('connected');
      this.elements.backendText.textContent = 'Backend: Disconnected';
    }
  }
}

// Initialize popup when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
  new TrueTonePopup();
});
