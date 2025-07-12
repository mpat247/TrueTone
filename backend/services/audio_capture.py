#!/usr/bin/env python3
"""
TrueTone Audio Capture Service
Handles audio capture, buffering, and quality management
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Callable, Any
import numpy as np
import soundfile as sf
import librosa
from collections import deque
import threading
import psutil

logger = logging.getLogger(__name__)

class AudioBuffer:
    """Circular buffer for continuous audio streaming with overflow protection"""
    
    def __init__(self, max_size: int = 1024 * 1024):  # 1MB default
        self.max_size = max_size
        self.buffer = deque(maxlen=max_size)
        self.lock = threading.Lock()
        self.overflow_count = 0
        self.total_written = 0
        self.total_read = 0
        
    def write(self, data: bytes) -> bool:
        """Write data to buffer with overflow protection"""
        with self.lock:
            if len(self.buffer) + len(data) > self.max_size:
                # Remove old data to make room
                overflow_size = len(self.buffer) + len(data) - self.max_size
                for _ in range(min(overflow_size, len(self.buffer))):
                    self.buffer.popleft()
                self.overflow_count += overflow_size
                logger.warning(f"Audio buffer overflow: {overflow_size} bytes dropped")
            
            self.buffer.extend(data)
            self.total_written += len(data)
            return True
    
    def read(self, size: int) -> bytes:
        """Read data from buffer"""
        with self.lock:
            if len(self.buffer) < size:
                # Return what we have
                data = bytes(self.buffer)
                self.buffer.clear()
            else:
                data = bytes([self.buffer.popleft() for _ in range(size)])
            
            self.total_read += len(data)
            return data
    
    def available(self) -> int:
        """Get available bytes in buffer"""
        with self.lock:
            return len(self.buffer)
    
    def clear(self):
        """Clear buffer"""
        with self.lock:
            self.buffer.clear()
    
    def get_stats(self) -> Dict[str, int]:
        """Get buffer statistics"""
        with self.lock:
            return {
                'size': len(self.buffer),
                'max_size': self.max_size,
                'overflow_count': self.overflow_count,
                'total_written': self.total_written,
                'total_read': self.total_read,
                'utilization': len(self.buffer) / self.max_size * 100
            }

class AudioQualityMonitor:
    """Monitor and optimize audio quality"""
    
    def __init__(self):
        self.sample_rate = None
        self.channels = None
        self.bit_depth = None
        self.quality_metrics = {}
        self.auto_adjustment_enabled = True
        
    def detect_format(self, audio_data: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """Detect audio format and quality metrics"""
        # Detect basic properties
        if len(audio_data.shape) == 1:
            channels = 1
        else:
            channels = audio_data.shape[1] if audio_data.shape[1] < audio_data.shape[0] else audio_data.shape[0]
        
        # Calculate quality metrics
        rms_level = np.sqrt(np.mean(audio_data**2))
        peak_level = np.max(np.abs(audio_data))
        dynamic_range = 20 * np.log10(peak_level / (rms_level + 1e-10))
        
        # Estimate SNR (simplified)
        signal_power = np.mean(audio_data**2)
        noise_floor = np.percentile(audio_data**2, 10)  # Estimate noise floor
        snr = 10 * np.log10(signal_power / (noise_floor + 1e-10))
        
        self.quality_metrics = {
            'sample_rate': sample_rate,
            'channels': channels,
            'rms_level': float(rms_level),
            'peak_level': float(peak_level),
            'dynamic_range': float(dynamic_range),
            'snr_estimate': float(snr),
            'clipping_detected': peak_level >= 0.99
        }
        
        return self.quality_metrics
    
    def optimize_for_ml(self, audio_data: np.ndarray, current_sr: int, target_sr: int = 16000) -> np.ndarray:
        """Optimize audio for ML model processing"""
        # Resample if needed
        if current_sr != target_sr:
            audio_data = librosa.resample(audio_data, orig_sr=current_sr, target_sr=target_sr)
        
        # Convert to mono if stereo
        if len(audio_data.shape) > 1:
            audio_data = librosa.to_mono(audio_data.T)
        
        # Normalize audio
        if np.max(np.abs(audio_data)) > 0:
            audio_data = audio_data / np.max(np.abs(audio_data)) * 0.9
        
        return audio_data
    
    def get_recommendations(self) -> Dict[str, str]:
        """Get quality improvement recommendations"""
        recommendations = []
        
        if self.quality_metrics.get('snr_estimate', 0) < 10:
            recommendations.append("Low SNR detected - consider noise reduction")
        
        if self.quality_metrics.get('clipping_detected', False):
            recommendations.append("Audio clipping detected - reduce input level")
        
        if self.quality_metrics.get('dynamic_range', 0) < 10:
            recommendations.append("Low dynamic range - check compression settings")
        
        return {'recommendations': recommendations, 'metrics': self.quality_metrics}

class AudioStreamManager:
    """Manage audio streaming with health monitoring and reconnection"""
    
    def __init__(self, max_reconnect_attempts: int = 5):
        self.is_active = False
        self.health_check_interval = 5.0  # seconds
        self.max_reconnect_attempts = max_reconnect_attempts
        self.reconnect_count = 0
        self.last_health_check = time.time()
        self.stream_callbacks = []
        self.error_callbacks = []
        self.health_monitor_task = None
        
    def add_stream_callback(self, callback: Callable):
        """Add callback for stream events"""
        self.stream_callbacks.append(callback)
    
    def add_error_callback(self, callback: Callable):
        """Add callback for error events"""
        self.error_callbacks.append(callback)
    
    def start_health_monitoring(self):
        """Start health monitoring task"""
        if self.health_monitor_task is None:
            self.health_monitor_task = asyncio.create_task(self._health_monitor_loop())
    
    def stop_health_monitoring(self):
        """Stop health monitoring task"""
        if self.health_monitor_task:
            self.health_monitor_task.cancel()
            self.health_monitor_task = None
    
    async def _health_monitor_loop(self):
        """Health monitoring loop"""
        while self.is_active:
            try:
                await asyncio.sleep(self.health_check_interval)
                
                # Check system resources
                memory_percent = psutil.virtual_memory().percent
                cpu_percent = psutil.cpu_percent()
                
                if memory_percent > 90:
                    logger.warning(f"High memory usage: {memory_percent}%")
                    await self._notify_callbacks('memory_warning', {'usage': memory_percent})
                
                if cpu_percent > 80:
                    logger.warning(f"High CPU usage: {cpu_percent}%")
                    await self._notify_callbacks('cpu_warning', {'usage': cpu_percent})
                
                self.last_health_check = time.time()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                await self._notify_error_callbacks('health_monitor_error', str(e))
    
    async def _notify_callbacks(self, event_type: str, data: Dict[str, Any]):
        """Notify stream callbacks"""
        for callback in self.stream_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_type, data)
                else:
                    callback(event_type, data)
            except Exception as e:
                logger.error(f"Callback error: {e}")
    
    async def _notify_error_callbacks(self, error_type: str, error_message: str):
        """Notify error callbacks"""
        for callback in self.error_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(error_type, error_message)
                else:
                    callback(error_type, error_message)
            except Exception as e:
                logger.error(f"Error callback error: {e}")
    
    def start_stream(self):
        """Start audio stream"""
        self.is_active = True
        self.start_health_monitoring()
        logger.info("Audio stream started")
    
    def stop_stream(self):
        """Stop audio stream"""
        self.is_active = False
        self.stop_health_monitoring()
        logger.info("Audio stream stopped")
    
    async def handle_reconnection(self, error: Exception):
        """Handle stream reconnection with exponential backoff"""
        if self.reconnect_count >= self.max_reconnect_attempts:
            logger.error(f"Max reconnection attempts reached: {self.max_reconnect_attempts}")
            await self._notify_error_callbacks('max_reconnects_reached', str(error))
            return False
        
        # Exponential backoff
        wait_time = min(2 ** self.reconnect_count, 30)  # Max 30 seconds
        self.reconnect_count += 1
        
        logger.info(f"Attempting reconnection {self.reconnect_count}/{self.max_reconnect_attempts} in {wait_time}s")
        await asyncio.sleep(wait_time)
        
        try:
            # Attempt to restart stream
            self.stop_stream()
            await asyncio.sleep(1)
            self.start_stream()
            
            # Reset reconnect count on success
            self.reconnect_count = 0
            await self._notify_callbacks('reconnection_success', {
                'attempt': self.reconnect_count,
                'wait_time': wait_time
            })
            return True
            
        except Exception as reconnect_error:
            logger.error(f"Reconnection failed: {reconnect_error}")
            await self._notify_error_callbacks('reconnection_failed', str(reconnect_error))
            return await self.handle_reconnection(reconnect_error)

class AudioCaptureService:
    """Main audio capture service coordinating all components"""
    
    def __init__(self):
        self.buffer = AudioBuffer()
        self.quality_monitor = AudioQualityMonitor()
        self.stream_manager = AudioStreamManager()
        self.is_capturing = False
        self.current_format = None
        
        # Setup callbacks
        self.stream_manager.add_error_callback(self._handle_stream_error)
        
    async def start_capture(self, config: Dict[str, Any]) -> bool:
        """Start audio capture with given configuration"""
        try:
            self.is_capturing = True
            self.stream_manager.start_stream()
            
            logger.info("Audio capture started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start audio capture: {e}")
            await self._handle_stream_error('capture_start_failed', str(e))
            return False
    
    async def stop_capture(self):
        """Stop audio capture"""
        self.is_capturing = False
        self.stream_manager.stop_stream()
        self.buffer.clear()
        logger.info("Audio capture stopped")
    
    async def process_audio_chunk(self, audio_data: bytes, metadata: Dict[str, Any]) -> bool:
        """Process incoming audio chunk"""
        try:
            # Write to buffer
            success = self.buffer.write(audio_data)
            
            if not success:
                logger.warning("Failed to write audio data to buffer")
                return False
            
            # Convert to numpy array for analysis
            try:
                audio_array = np.frombuffer(audio_data, dtype=np.float32)
                sample_rate = metadata.get('sample_rate', 44100)
                
                # Analyze quality
                quality_metrics = self.quality_monitor.detect_format(audio_array, sample_rate)
                
                # Optimize if needed
                if self.quality_monitor.auto_adjustment_enabled:
                    optimized_audio = self.quality_monitor.optimize_for_ml(
                        audio_array, sample_rate, target_sr=16000
                    )
                    # Could store optimized version for ML processing
                
            except Exception as analysis_error:
                logger.warning(f"Audio analysis failed: {analysis_error}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error processing audio chunk: {e}")
            await self._handle_stream_error('chunk_processing_failed', str(e))
            return False
    
    def get_audio_data(self, size: int) -> bytes:
        """Get audio data from buffer"""
        return self.buffer.read(size)
    
    def get_buffer_stats(self) -> Dict[str, Any]:
        """Get buffer statistics"""
        stats = self.buffer.get_stats()
        stats['quality_metrics'] = self.quality_monitor.quality_metrics
        stats['quality_recommendations'] = self.quality_monitor.get_recommendations()
        return stats
    
    async def _handle_stream_error(self, error_type: str, error_message: str):
        """Handle stream errors"""
        logger.error(f"Stream error [{error_type}]: {error_message}")
        
        # Attempt recovery based on error type
        if error_type in ['connection_lost', 'capture_start_failed']:
            await self.stream_manager.handle_reconnection(Exception(error_message))
        elif error_type in ['memory_warning', 'buffer_overflow']:
            # Clear buffer and reduce quality if needed
            self.buffer.clear()
            logger.info("Buffer cleared due to resource constraints")
    
    def handle_youtube_state_change(self, state: str, data: Dict[str, Any]):
        """Handle YouTube player state changes"""
        logger.info(f"YouTube player state changed: {state}")
        
        if state == 'paused':
            # Could pause processing to save resources
            logger.info("YouTube paused - reducing processing")
        elif state == 'playing':
            # Resume full processing
            logger.info("YouTube playing - resuming full processing")
        elif state == 'seeking':
            # Clear buffer on seek to avoid stale data
            self.buffer.clear()
            logger.info("YouTube seeking - buffer cleared")
        elif state == 'ad_started':
            # Could switch to ad-specific processing
            logger.info("Ad started - switching processing mode")
        elif state == 'ad_ended':
            # Resume normal processing
            logger.info("Ad ended - resuming normal processing")
