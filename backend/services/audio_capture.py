"""
Audio Capture Service
Handles audio capture and processing for the TrueTone backend.
"""

import numpy as np
import logging
from typing import Dict, Any, Optional, List
import asyncio
import time
from io import BytesIO

logger = logging.getLogger(__name__)


class AudioCaptureService:
    """Service for handling audio capture and initial processing"""
    
    def __init__(self, audio_processor):
        self.audio_processor = audio_processor
        self.active_sessions = {}
        self.session_buffers = {}
        
        # Audio quality monitoring
        self.quality_metrics = {
            'sample_rate_mismatches': 0,
            'format_errors': 0,
            'buffer_overflows': 0,
            'total_chunks_processed': 0
        }
        
        logger.info("AudioCaptureService initialized")
    
    def create_session(self, client_id: str, config: Dict[str, Any]) -> str:
        """Create a new audio capture session"""
        session_id = f"session_{client_id}_{int(time.time())}"
        
        session_config = {
            'client_id': client_id,
            'created_at': time.time(),
            'sample_rate': config.get('sample_rate', 44100),
            'channels': config.get('channels', 1),
            'format': config.get('format', 'float32'),
            'buffer_size': config.get('buffer_size', 4096),
            'target_language': config.get('target_language', 'en'),
            'voice_cloning': config.get('voice_cloning', True)
        }
        
        self.active_sessions[session_id] = session_config
        self.session_buffers[session_id] = []
        
        logger.info(f"Created audio capture session {session_id} for client {client_id}")
        return session_id
    
    def close_session(self, session_id: str):
        """Close an audio capture session and clean up resources"""
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]
        
        if session_id in self.session_buffers:
            del self.session_buffers[session_id]
        
        logger.info(f"Closed audio capture session {session_id}")
    
    async def process_audio_chunk(self, session_id: str, audio_data: bytes, 
                                metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Process an incoming audio chunk"""
        try:
            if session_id not in self.active_sessions:
                raise ValueError(f"Session {session_id} not found")
            
            session_config = self.active_sessions[session_id]
            
            # Extract metadata
            timestamp = metadata.get('timestamp', time.time() * 1000)
            sequence = metadata.get('sequence', 0)
            sample_rate = metadata.get('sampleRate', session_config['sample_rate'])
            audio_format = metadata.get('format', session_config['format'])
            
            # Convert audio data to numpy array
            audio_np = self._convert_audio_data(audio_data, audio_format)
            
            # Validate and process audio
            processed_audio = await self._validate_and_process_audio(
                audio_np, sample_rate, session_config
            )
            
            # Store in session buffer
            self.session_buffers[session_id].append({
                'audio': processed_audio,
                'timestamp': timestamp,
                'sequence': sequence,
                'metadata': metadata
            })
            
            # Keep buffer size manageable (max 10 seconds of audio)
            max_buffer_size = int(session_config['sample_rate'] * 10)
            current_buffer_size = sum(len(chunk['audio']) for chunk in self.session_buffers[session_id])
            
            if current_buffer_size > max_buffer_size:
                # Remove oldest chunks to make space
                while current_buffer_size > max_buffer_size and self.session_buffers[session_id]:
                    removed_chunk = self.session_buffers[session_id].pop(0)
                    current_buffer_size -= len(removed_chunk['audio'])
                
                self.quality_metrics['buffer_overflows'] += 1
            
            # Update metrics
            self.quality_metrics['total_chunks_processed'] += 1
            
            # Perform quality analysis
            quality_metrics = self._analyze_audio_quality(processed_audio, sample_rate)
            
            return {
                'status': 'success',
                'sequence': sequence,
                'timestamp': timestamp,
                'quality': quality_metrics,
                'buffer_size': len(self.session_buffers[session_id]),
                'processed_samples': len(processed_audio)
            }
            
        except Exception as e:
            logger.error(f"Error processing audio chunk for session {session_id}: {str(e)}")
            self.quality_metrics['format_errors'] += 1
            
            return {
                'status': 'error',
                'message': str(e),
                'sequence': metadata.get('sequence', 0),
                'timestamp': metadata.get('timestamp', time.time() * 1000)
            }
    
    def _convert_audio_data(self, audio_data: bytes, audio_format: str) -> np.ndarray:
        """Convert audio bytes to numpy array based on format"""
        try:
            if audio_format == 'float32':
                return np.frombuffer(audio_data, dtype=np.float32)
            elif audio_format == 'int16':
                return np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            elif audio_format == 'int32':
                return np.frombuffer(audio_data, dtype=np.int32).astype(np.float32) / 2147483648.0
            else:
                raise ValueError(f"Unsupported audio format: {audio_format}")
        except Exception as e:
            raise ValueError(f"Error converting audio data: {str(e)}")
    
    async def _validate_and_process_audio(self, audio_np: np.ndarray, 
                                        sample_rate: int, session_config: Dict[str, Any]) -> np.ndarray:
        """Validate and process audio data"""
        # Check for valid audio data
        if len(audio_np) == 0:
            raise ValueError("Empty audio data")
        
        # Check for NaN or infinite values
        if np.any(np.isnan(audio_np)) or np.any(np.isinf(audio_np)):
            logger.warning("Audio contains NaN or infinite values, cleaning...")
            audio_np = np.nan_to_num(audio_np, nan=0.0, posinf=1.0, neginf=-1.0)
        
        # Clip audio to valid range
        audio_np = np.clip(audio_np, -1.0, 1.0)
        
        # Standardize audio format if needed
        if sample_rate != session_config['sample_rate']:
            logger.warning(f"Sample rate mismatch: {sample_rate} vs {session_config['sample_rate']}")
            self.quality_metrics['sample_rate_mismatches'] += 1
            
            # Use audio processor to resample
            audio_np = self.audio_processor.resample_audio(
                audio_np, sample_rate, session_config['sample_rate']
            )
        
        # Apply basic audio enhancement
        audio_np = self._apply_audio_enhancement(audio_np)
        
        return audio_np
    
    def _apply_audio_enhancement(self, audio_np: np.ndarray) -> np.ndarray:
        """Apply basic audio enhancement filters"""
        # Normalize audio
        max_val = np.max(np.abs(audio_np))
        if max_val > 0:
            audio_np = audio_np / max_val * 0.95  # Leave some headroom
        
        # Simple high-pass filter to remove DC offset and low-frequency noise
        if len(audio_np) > 1:
            audio_np = np.diff(audio_np, prepend=audio_np[0])
        
        return audio_np
    
    def _analyze_audio_quality(self, audio_np: np.ndarray, sample_rate: int) -> Dict[str, float]:
        """Analyze audio quality metrics"""
        # Calculate RMS level
        rms = np.sqrt(np.mean(audio_np ** 2))
        
        # Calculate peak level
        peak = np.max(np.abs(audio_np))
        
        # Calculate zero crossing rate (rough measure of speech vs noise)
        zero_crossings = np.sum(np.diff(np.signbit(audio_np)))
        zcr = zero_crossings / (len(audio_np) - 1) if len(audio_np) > 1 else 0
        
        # Calculate spectral centroid (brightness measure)
        # This is a simplified version - in production, use FFT-based analysis
        spectral_centroid = np.mean(np.abs(np.gradient(audio_np)))
        
        return {
            'rms_level': float(rms),
            'peak_level': float(peak),
            'zero_crossing_rate': float(zcr),
            'spectral_centroid': float(spectral_centroid),
            'snr_estimate': float(20 * np.log10(rms) if rms > 0 else -60),  # Rough SNR estimate
            'clip_detected': bool(np.any(np.abs(audio_np) >= 0.99))
        }
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a session"""
        if session_id not in self.active_sessions:
            return None
        
        session_config = self.active_sessions[session_id]
        buffer_info = {
            'chunks': len(self.session_buffers.get(session_id, [])),
            'total_samples': sum(len(chunk['audio']) for chunk in self.session_buffers.get(session_id, [])),
            'duration_seconds': sum(len(chunk['audio']) for chunk in self.session_buffers.get(session_id, [])) / session_config['sample_rate']
        }
        
        return {
            'session_config': session_config,
            'buffer_info': buffer_info,
            'quality_metrics': self.quality_metrics
        }
    
    def get_buffered_audio(self, session_id: str, max_duration: float = 5.0) -> Optional[np.ndarray]:
        """Get buffered audio for a session"""
        if session_id not in self.session_buffers:
            return None
        
        chunks = self.session_buffers[session_id]
        if not chunks:
            return None
        
        session_config = self.active_sessions[session_id]
        max_samples = int(max_duration * session_config['sample_rate'])
        
        # Concatenate recent audio chunks
        audio_data = []
        total_samples = 0
        
        for chunk in reversed(chunks):  # Start from most recent
            if total_samples + len(chunk['audio']) > max_samples:
                break
            audio_data.insert(0, chunk['audio'])
            total_samples += len(chunk['audio'])
        
        if audio_data:
            return np.concatenate(audio_data)
        else:
            return None
