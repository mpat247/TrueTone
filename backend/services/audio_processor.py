#!/usr/bin/env python3
"""
Audio Processor - Audio Processing and Analysis
Handles audio capture, processing, transcription, and voice analysis
"""

import logging
import asyncio
import io
import time
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import base64

logger = logging.getLogger(__name__)

class AudioProcessor:
    """Handles audio processing for TrueTone"""
    
    def __init__(self):
        self.sample_rate = 16000  # Standard rate for speech processing
        self.model_manager = None  # Will be injected
        
    def set_model_manager(self, model_manager):
        """Set reference to model manager"""
        self.model_manager = model_manager
    
    async def analyze_audio(self, audio_bytes: bytes, format: str = "wav", sample_rate: int = 44100) -> Dict[str, Any]:
        """Analyze audio for basic characteristics"""
        try:
            # Convert audio bytes to numpy array
            audio_data = await self._load_audio_from_bytes(audio_bytes, format, sample_rate)
            
            if audio_data is None:
                return {"error": "Failed to load audio data"}
            
            # Basic audio analysis
            duration = len(audio_data) / sample_rate
            channels = 1 if len(audio_data.shape) == 1 else audio_data.shape[1]
            
            # Voice activity detection (simple energy-based)
            voice_detected, confidence = await self._detect_voice_activity(audio_data)
            
            analysis = {
                "duration": duration,
                "sample_rate": sample_rate,
                "channels": channels,
                "format": format,
                "voice_detected": voice_detected,
                "confidence": confidence,
                "audio_quality": await self._assess_audio_quality(audio_data, sample_rate)
            }
            
            return analysis
        
        except Exception as e:
            logger.error(f"Error analyzing audio: {e}")
            return {"error": str(e)}
    
    async def process_uploaded_audio(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Process uploaded audio file"""
        try:
            # Determine format from filename
            format = Path(filename).suffix.lower().lstrip('.')
            if format not in ['wav', 'mp3', 'flac', 'm4a']:
                return {"error": f"Unsupported audio format: {format}"}
            
            # Analyze the audio
            analysis = await self.analyze_audio(content, format)
            
            # Store audio for processing if needed
            audio_id = await self._store_audio_temp(content, filename)
            
            result = {
                "audio_id": audio_id,
                "filename": filename,
                "format": format,
                "analysis": analysis,
                "status": "processed"
            }
            
            return result
        
        except Exception as e:
            logger.error(f"Error processing uploaded audio: {e}")
            return {"error": str(e)}
    
    async def transcribe_audio(self, audio_bytes: bytes, format: str = "wav", sample_rate: int = 16000) -> Dict[str, Any]:
        """Transcribe audio using Whisper"""
        try:
            if not self.model_manager:
                return {"error": "Model manager not available"}
            
            # Get Whisper model
            whisper_model = self.model_manager.get_model("whisper")
            if not whisper_model:
                return {"error": "Whisper model not loaded"}
            
            # Load and preprocess audio
            audio_data = await self._load_audio_from_bytes(audio_bytes, format, sample_rate)
            if audio_data is None:
                return {"error": "Failed to load audio data"}
            
            # Transcribe with Whisper
            result = await self._transcribe_with_whisper(whisper_model, audio_data)
            
            return result
        
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return {"error": str(e)}
    
    async def create_voice_profile(self, audio_bytes: bytes, format: str = "wav", sample_rate: int = 16000) -> Dict[str, Any]:
        """Create voice embedding profile using Resemblyzer"""
        try:
            if not self.model_manager:
                return {"error": "Model manager not available"}
            
            # Get Resemblyzer model
            resemblyzer_model = self.model_manager.get_model("resemblyzer")
            if not resemblyzer_model:
                return {"error": "Resemblyzer model not loaded"}
            
            # Load and preprocess audio
            audio_data = await self._load_audio_from_bytes(audio_bytes, format, sample_rate)
            if audio_data is None:
                return {"error": "Failed to load audio data"}
            
            # Create voice embedding
            embedding = await self._create_voice_embedding(resemblyzer_model, audio_data, sample_rate)
            
            profile = {
                "embedding": embedding.tolist() if embedding is not None else None,
                "embedding_size": len(embedding) if embedding is not None else 0,
                "audio_duration": len(audio_data) / sample_rate,
                "sample_rate": sample_rate,
                "created_at": time.time()
            }
            
            return profile
        
        except Exception as e:
            logger.error(f"Error creating voice profile: {e}")
            return {"error": str(e)}
    
    async def get_status(self) -> Dict[str, Any]:
        """Get audio processing system status"""
        return {
            "audio_processor": "ready",
            "sample_rate": self.sample_rate,
            "supported_formats": ["wav", "mp3", "flac", "m4a"],
            "model_manager_available": self.model_manager is not None
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for audio processing system"""
        try:
            healthy = True
            details = {
                "audio_processor": "operational",
                "model_manager": self.model_manager is not None
            }
            
            # Check if essential models are available
            if self.model_manager:
                whisper_available = self.model_manager.get_model("whisper") is not None
                resemblyzer_available = self.model_manager.get_model("resemblyzer") is not None
                
                details.update({
                    "whisper_model": whisper_available,
                    "resemblyzer_model": resemblyzer_available
                })
                
                if not (whisper_available or resemblyzer_available):
                    healthy = False
            else:
                healthy = False
            
            return {"healthy": healthy, **details}
        
        except Exception as e:
            logger.error(f"Error in audio health check: {e}")
            return {"healthy": False, "error": str(e)}
    
    async def _load_audio_from_bytes(self, audio_bytes: bytes, format: str, target_sample_rate: int) -> Optional[np.ndarray]:
        """Load audio from bytes and convert to numpy array"""
        try:
            # This is a simplified version - in practice, you'd use librosa or soundfile
            # For MVP, we'll implement basic WAV loading
            if format.lower() == "wav":
                return await self._load_wav_from_bytes(audio_bytes, target_sample_rate)
            else:
                # For other formats, we'd need librosa/soundfile
                logger.warning(f"Format {format} not yet supported, treating as WAV")
                return await self._load_wav_from_bytes(audio_bytes, target_sample_rate)
        
        except Exception as e:
            logger.error(f"Error loading audio from bytes: {e}")
            return None
    
    async def _load_wav_from_bytes(self, wav_bytes: bytes, target_sample_rate: int) -> Optional[np.ndarray]:
        """Simple WAV loader from bytes"""
        try:
            # This is a very basic WAV parser for MVP
            # In production, use soundfile or librosa
            
            # Skip WAV header (44 bytes for standard WAV)
            if len(wav_bytes) < 44:
                return None
            
            audio_data = wav_bytes[44:]  # Skip header
            
            # Convert to 16-bit integers
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Convert to float32 and normalize
            audio_array = audio_array.astype(np.float32) / 32768.0
            
            return audio_array
        
        except Exception as e:
            logger.error(f"Error loading WAV from bytes: {e}")
            return None
    
    async def _detect_voice_activity(self, audio_data: np.ndarray) -> Tuple[bool, float]:
        """Simple voice activity detection based on energy"""
        try:
            # Calculate RMS energy
            rms_energy = np.sqrt(np.mean(audio_data ** 2))
            
            # Simple threshold-based detection
            energy_threshold = 0.01  # Adjustable threshold
            voice_detected = rms_energy > energy_threshold
            
            # Confidence based on how much above threshold
            confidence = min(rms_energy / energy_threshold, 1.0) if voice_detected else 0.0
            
            return voice_detected, confidence
        
        except Exception as e:
            logger.error(f"Error in voice activity detection: {e}")
            return False, 0.0
    
    async def _assess_audio_quality(self, audio_data: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """Assess basic audio quality metrics"""
        try:
            # Calculate signal-to-noise ratio (simplified)
            signal_power = np.mean(audio_data ** 2)
            
            # Estimate noise (bottom 10% of energy windows)
            window_size = sample_rate // 10  # 100ms windows
            windows = [audio_data[i:i+window_size] for i in range(0, len(audio_data) - window_size, window_size)]
            window_powers = [np.mean(window ** 2) for window in windows]
            noise_power = np.percentile(window_powers, 10)
            
            snr = 10 * np.log10(signal_power / max(noise_power, 1e-10))
            
            # Basic quality assessment
            quality = "good" if snr > 10 else "fair" if snr > 5 else "poor"
            
            return {
                "snr_db": snr,
                "quality": quality,
                "signal_power": signal_power,
                "estimated_noise_power": noise_power
            }
        
        except Exception as e:
            logger.error(f"Error assessing audio quality: {e}")
            return {"quality": "unknown", "error": str(e)}
    
    async def _transcribe_with_whisper(self, whisper_model, audio_data: np.ndarray) -> Dict[str, Any]:
        """Transcribe audio using Whisper model"""
        try:
            # Whisper expects audio at 16kHz
            if hasattr(whisper_model, 'transcribe'):
                result = whisper_model.transcribe(audio_data)
                
                return {
                    "text": result.get("text", ""),
                    "language": result.get("language", "unknown"),
                    "segments": result.get("segments", []),
                    "confidence": getattr(result, 'confidence', 0.0)
                }
            else:
                return {"error": "Invalid Whisper model"}
        
        except Exception as e:
            logger.error(f"Error in Whisper transcription: {e}")
            return {"error": str(e)}
    
    async def _create_voice_embedding(self, resemblyzer_model, audio_data: np.ndarray, sample_rate: int) -> Optional[np.ndarray]:
        """Create voice embedding using Resemblyzer"""
        try:
            if hasattr(resemblyzer_model, 'embed_utterance'):
                # Resample to 16kHz if needed (Resemblyzer requirement)
                if sample_rate != 16000:
                    # Simple resampling (in production, use proper resampling)
                    ratio = 16000 / sample_rate
                    new_length = int(len(audio_data) * ratio)
                    audio_data = np.interp(np.linspace(0, len(audio_data), new_length), np.arange(len(audio_data)), audio_data)
                
                embedding = resemblyzer_model.embed_utterance(audio_data)
                return embedding
            else:
                logger.error("Invalid Resemblyzer model")
                return None
        
        except Exception as e:
            logger.error(f"Error creating voice embedding: {e}")
            return None
    
    async def _store_audio_temp(self, content: bytes, filename: str) -> str:
        """Store audio temporarily and return ID"""
        try:
            # Generate simple ID based on hash and timestamp
            import hashlib
            audio_hash = hashlib.md5(content).hexdigest()[:8]
            audio_id = f"{int(time.time())}_{audio_hash}"
            
            # In production, store to temp directory or cloud storage
            # For MVP, we'll just return the ID
            logger.info(f"Audio stored with ID: {audio_id}")
            
            return audio_id
        
        except Exception as e:
            logger.error(f"Error storing audio: {e}")
            return "unknown"
