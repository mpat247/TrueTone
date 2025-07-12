#!/usr/bin/env python3
"""
Audio Pipeline Service
Orchestrates the complete audio processing workflow from capture to output.
"""

import asyncio
import logging
import time
from typing import Dict, List, Optional, Any, Callable
import json
import numpy as np

from models.audio_metadata import AudioMetadata, AudioChunk, AudioFormat, ProcessingStats
from services.audio_capture import AudioCaptureService
from services.audio_streaming import AudioStreamingService
from utils.audio_processing import AudioProcessor
from utils.audio_compression import AudioCompressor

logger = logging.getLogger(__name__)

class AudioPipelineService:
    """
    Main audio processing pipeline that coordinates all audio services.
    Handles the complete flow from raw audio input to processed output.
    """
    
    def __init__(self, 
                 audio_processor: AudioProcessor,
                 audio_capture: AudioCaptureService,
                 audio_streaming: AudioStreamingService):
        self.audio_processor = audio_processor
        self.audio_capture = audio_capture
        self.audio_streaming = audio_streaming
        self.audio_compressor = AudioCompressor()
        
        # Pipeline state
        self.is_running = False
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        self.processing_stats = ProcessingStats()
        
        # Processing callbacks
        self.on_audio_processed: Optional[Callable] = None
        self.on_translation_ready: Optional[Callable] = None
        self.on_error: Optional[Callable] = None
        
        # Configuration
        self.config = {
            "enable_compression": True,
            "compression_method": "adaptive",
            "target_sample_rate": 44100,
            "target_channels": 2,
            "enable_noise_reduction": True,
            "enable_normalization": True,
            "chunk_size": 1024,
            "max_sessions": 10,
            "session_timeout": 300  # 5 minutes
        }
    
    def update_config(self, new_config: Dict[str, Any]):
        """Update pipeline configuration"""
        self.config.update(new_config)
        logger.info(f"Pipeline config updated: {new_config}")
    
    def get_config(self) -> Dict[str, Any]:
        """Get current pipeline configuration"""
        return self.config.copy()
    
    async def start_session(self, session_id: str, metadata: AudioMetadata) -> bool:
        """Start a new audio processing session"""
        if len(self.active_sessions) >= self.config["max_sessions"]:
            logger.warning(f"Cannot start session {session_id}: max sessions reached")
            return False
        
        try:
            # Initialize session
            session_data = {
                "metadata": metadata,
                "start_time": time.time(),
                "last_activity": time.time(),
                "chunks_processed": 0,
                "total_samples": 0,
                "processing_errors": 0,
                "status": "active"
            }
            
            # Create capture session using existing API
            config = {
                "sample_rate": metadata.format.sample_rate,
                "channels": metadata.format.channels,
                "format": metadata.format.format.lower(),
                "buffer_size": metadata.chunk_size,
                "target_language": metadata.language,
                "voice_cloning": True
            }
            
            capture_session_id = self.audio_capture.create_session(session_id, config)
            session_data["capture_session_id"] = capture_session_id
            
            self.active_sessions[session_id] = session_data
            logger.info(f"Started audio pipeline session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error starting session {session_id}: {e}")
            return False
    
    async def stop_session(self, session_id: str) -> bool:
        """Stop an audio processing session"""
        if session_id not in self.active_sessions:
            logger.warning(f"Session {session_id} not found")
            return False
        
        try:
            session_data = self.active_sessions[session_id]
            
            # Stop capture session using existing API
            if "capture_session_id" in session_data:
                self.audio_capture.close_session(session_data["capture_session_id"])
            
            # Update stats
            session_data["status"] = "stopped"
            session_data["end_time"] = time.time()
            
            # Clean up session
            del self.active_sessions[session_id]
            
            logger.info(f"Stopped audio pipeline session {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping session {session_id}: {e}")
            return False
    
    async def process_audio_chunk(self, session_id: str, audio_data: List[float], 
                                source_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Process a single audio chunk through the complete pipeline"""
        if session_id not in self.active_sessions:
            raise ValueError(f"Session {session_id} not active")
        
        start_time = time.time()
        session_data = self.active_sessions[session_id]
        
        try:
            # Update session activity
            session_data["last_activity"] = time.time()
            session_data["chunks_processed"] += 1
            session_data["total_samples"] += len(audio_data)
            
            # Create audio chunk with metadata
            metadata = session_data["metadata"]
            metadata.timestamp = time.time()
            metadata.chunk_size = len(audio_data)
            metadata.source_url = source_metadata.get("url")
            metadata.language = source_metadata.get("language", "unknown")
            
            chunk = AudioChunk(
                data=audio_data,
                metadata=metadata,
                sequence_number=session_data["chunks_processed"]
            )
            
            # Step 1: Audio format standardization
            standardized_chunk = await self._standardize_audio(chunk)
            
            # Step 2: Quality analysis and enhancement
            enhanced_chunk = await self._enhance_audio(standardized_chunk)
            
            # Step 3: Compression (if enabled)
            if self.config["enable_compression"]:
                compressed_chunk = await self._compress_audio(enhanced_chunk)
            else:
                compressed_chunk = enhanced_chunk
            
            # Step 4: Streaming preparation
            streaming_data = await self._prepare_for_streaming(compressed_chunk)
            
            # Update processing stats
            processing_time = time.time() - start_time
            self.processing_stats.update_processing_time(processing_time)
            self.processing_stats.add_samples(len(audio_data))
            
            # Update session metadata
            session_data["processing_latency"] = processing_time
            
            # Prepare response
            response = {
                "status": "success",
                "session_id": session_id,
                "chunk_sequence": chunk.sequence_number,
                "processing_time": processing_time,
                "original_samples": len(audio_data),
                "processed_samples": len(compressed_chunk.data),
                "compression_ratio": compressed_chunk.metadata.compression_ratio,
                "quality_metrics": {
                    "peak_amplitude": compressed_chunk.metadata.peak_amplitude,
                    "rms_level": compressed_chunk.metadata.rms_level,
                    "snr": compressed_chunk.metadata.signal_to_noise_ratio
                },
                "streaming_data": streaming_data
            }
            
            # Call processing callback if set
            if self.on_audio_processed:
                await self.on_audio_processed(session_id, compressed_chunk, response)
            
            return response
            
        except Exception as e:
            session_data["processing_errors"] += 1
            self.processing_stats.add_error()
            logger.error(f"Error processing audio chunk for session {session_id}: {e}")
            
            # Call error callback if set
            if self.on_error:
                await self.on_error(session_id, e)
            
            raise
    
    async def _standardize_audio(self, chunk: AudioChunk) -> AudioChunk:
        """Standardize audio format and quality"""
        try:
            # Convert to numpy array for processing
            audio_np = np.array(chunk.data, dtype=np.float32)
            
            # Standardize format using existing API
            processed_audio = self.audio_processor.standardize_audio(
                audio_np,
                orig_sample_rate=chunk.metadata.format.sample_rate,
                target_sample_rate=self.config["target_sample_rate"]
            )
            
            # Convert stereo to mono if needed
            if chunk.metadata.format.channels == 2 and self.config["target_channels"] == 1:
                processed_audio = self.audio_processor.stereo_to_mono(processed_audio)
            
            # Update metadata
            chunk.data = processed_audio.tolist()
            chunk.metadata.format.sample_rate = self.config["target_sample_rate"]
            chunk.metadata.format.channels = self.config["target_channels"]
            
            return chunk
            
        except Exception as e:
            logger.error(f"Error standardizing audio: {e}")
            raise
    
    async def _enhance_audio(self, chunk: AudioChunk) -> AudioChunk:
        """Enhance audio quality with noise reduction and normalization"""
        try:
            audio_np = np.array(chunk.data, dtype=np.float32)
            
            # Apply basic filters for noise reduction if enabled
            if self.config["enable_noise_reduction"]:
                audio_np = self.audio_processor.apply_basic_filters(
                    audio_np, 
                    chunk.metadata.format.sample_rate
                )
            
            # Apply normalization if enabled
            if self.config["enable_normalization"]:
                audio_np = self.audio_processor.normalize_audio(audio_np)
            
            # Calculate quality metrics
            chunk.metadata.peak_amplitude = float(np.max(np.abs(audio_np)))
            chunk.metadata.rms_level = float(np.sqrt(np.mean(audio_np**2)))
            
            # Simple SNR estimation (placeholder)
            signal_power = np.mean(audio_np**2)
            noise_power = np.mean(audio_np[:100]**2)  # Estimate from first 100 samples
            chunk.metadata.signal_to_noise_ratio = float(10 * np.log10(signal_power / (noise_power + 1e-10)))
            
            chunk.data = audio_np.tolist()
            return chunk
            
        except Exception as e:
            logger.error(f"Error enhancing audio: {e}")
            raise
    
    async def _compress_audio(self, chunk: AudioChunk) -> AudioChunk:
        """Compress audio data for efficient transmission"""
        try:
            # Convert to numpy array for compression
            audio_np = np.array(chunk.data, dtype=np.float32)
            
            # Use existing compression API
            compressed_data, compression_metadata = self.audio_compressor.compress_audio(
                audio_np, 
                method=self.config["compression_method"]
            )
            
            # Calculate compression ratio
            compression_ratio = compression_metadata.get("compression_ratio", 1.0)
            chunk.metadata.compression_ratio = compression_ratio
            
            # For streaming, we'll keep the original data but store compression info
            # In a real implementation, you'd store the compressed data separately
            chunk.data = audio_np.tolist()
            
            # Update compression stats
            self.processing_stats.add_compression_stats(compression_ratio)
            
            return chunk
            
        except Exception as e:
            logger.error(f"Error compressing audio: {e}")
            raise
    
    async def _prepare_for_streaming(self, chunk: AudioChunk) -> Dict[str, Any]:
        """Prepare audio chunk for streaming"""
        try:
            # Prepare streaming data
            streaming_data = {
                "audio_data": chunk.data,
                "metadata": chunk.metadata.to_dict(),
                "sequence": chunk.sequence_number,
                "timestamp": chunk.timestamp,
                "format": {
                    "sample_rate": chunk.metadata.format.sample_rate,
                    "channels": chunk.metadata.format.channels,
                    "bit_depth": chunk.metadata.format.bit_depth
                }
            }
            
            return streaming_data
            
        except Exception as e:
            logger.error(f"Error preparing for streaming: {e}")
            raise
    
    async def cleanup_inactive_sessions(self):
        """Clean up inactive sessions that have timed out"""
        current_time = time.time()
        timeout = self.config["session_timeout"]
        
        inactive_sessions = []
        for session_id, session_data in self.active_sessions.items():
            if current_time - session_data["last_activity"] > timeout:
                inactive_sessions.append(session_id)
        
        for session_id in inactive_sessions:
            logger.info(f"Cleaning up inactive session {session_id}")
            await self.stop_session(session_id)
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific session"""
        if session_id not in self.active_sessions:
            return None
        
        session_data = self.active_sessions[session_id]
        return {
            "session_id": session_id,
            "status": session_data["status"],
            "start_time": session_data["start_time"],
            "last_activity": session_data["last_activity"],
            "chunks_processed": session_data["chunks_processed"],
            "total_samples": session_data["total_samples"],
            "processing_errors": session_data["processing_errors"],
            "uptime": time.time() - session_data["start_time"]
        }
    
    def get_all_sessions_info(self) -> List[Dict[str, Any]]:
        """Get information about all active sessions"""
        result = []
        for session_id in self.active_sessions.keys():
            session_info = self.get_session_info(session_id)
            if session_info is not None:
                result.append(session_info)
        return result
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get overall processing statistics"""
        return {
            "pipeline_stats": self.processing_stats.to_dict(),
            "active_sessions": len(self.active_sessions),
            "config": self.config
        }
    
    async def start_background_tasks(self):
        """Start background maintenance tasks"""
        self.is_running = True
        
        # Start session cleanup task
        asyncio.create_task(self._session_cleanup_task())
        
        logger.info("Audio pipeline background tasks started")
    
    async def stop_background_tasks(self):
        """Stop background maintenance tasks"""
        self.is_running = False
        
        # Stop all active sessions
        for session_id in list(self.active_sessions.keys()):
            await self.stop_session(session_id)
        
        logger.info("Audio pipeline background tasks stopped")
    
    async def _session_cleanup_task(self):
        """Background task to clean up inactive sessions"""
        while self.is_running:
            try:
                await self.cleanup_inactive_sessions()
                await asyncio.sleep(30)  # Check every 30 seconds
            except Exception as e:
                logger.error(f"Error in session cleanup task: {e}")
                await asyncio.sleep(60)  # Wait longer on error
