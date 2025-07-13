"""
Audio Pipeline Service for TrueTone
Integrates audio processing with the streaming pipeline for optimized ML processing.
"""

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List, Tuple, Callable
from dataclasses import dataclass, asdict
import numpy as np
from concurrent.futures import ThreadPoolExecutor
import threading
import queue

from .audio_capture import AudioCaptureManager
from .audio_streaming import AudioStreamingManager
from ..utils.audio_processing import AudioProcessor, AudioMetadata

logger = logging.getLogger(__name__)

@dataclass
class PipelineConfig:
    """Configuration for audio pipeline processing"""
    # Audio processing settings
    target_sample_rate: int = 16000  # Optimal for Whisper
    chunk_duration: float = 1.0      # Duration per processing chunk (seconds)
    overlap_duration: float = 0.1    # Overlap between chunks (seconds)
    max_buffer_size: int = 50        # Maximum number of chunks to buffer
    
    # Quality settings
    normalize_audio: bool = True
    apply_filtering: bool = True
    quality_threshold: float = 0.3   # Minimum quality score to process
    
    # Processing settings
    async_processing: bool = True
    max_workers: int = 2             # Number of processing threads
    processing_timeout: float = 5.0  # Max time to process a chunk
    
    # Pipeline optimization
    adaptive_quality: bool = True    # Adapt processing based on quality
    skip_silent_chunks: bool = True  # Skip chunks with low energy
    energy_threshold: float = 0.01   # Minimum energy to process

@dataclass
class ProcessedChunk:
    """Container for processed audio chunk with metadata"""
    chunk_id: int
    audio_data: np.ndarray
    metadata: AudioMetadata
    original_chunk_id: int
    processing_time: float
    timestamp: float
    quality_adjusted: bool = False

class AudioPipelineManager:
    """
    Manages the complete audio processing pipeline from capture to ML-ready output.
    Integrates audio capture, streaming, and processing with quality optimization.
    """
    
    def __init__(self, config: Optional[PipelineConfig] = None):
        """
        Initialize audio pipeline manager.
        
        Args:
            config: Pipeline configuration
        """
        self.config = config or PipelineConfig()
        
        # Initialize components
        self.audio_processor = AudioProcessor(target_sample_rate=self.config.target_sample_rate)
        self.capture_manager = AudioCaptureManager()
        self.streaming_manager = AudioStreamingManager()
        
        # Pipeline state
        self.is_running = False
        self.processed_chunks: queue.Queue = queue.Queue(maxsize=self.config.max_buffer_size)
        self.processing_stats = {
            'chunks_processed': 0,
            'chunks_skipped': 0,
            'processing_errors': 0,
            'quality_improvements': 0,
            'total_processing_time': 0.0,
            'average_chunk_time': 0.0
        }
        
        # Thread management
        self.processing_executor = ThreadPoolExecutor(max_workers=self.config.max_workers)
        self.pipeline_thread = None
        self.stop_event = threading.Event()
        
        # Callbacks for processed audio
        self.chunk_callbacks: List[Callable[[ProcessedChunk], None]] = []
        
        logger.info(f"AudioPipelineManager initialized with config: {self.config}")
    
    def add_chunk_callback(self, callback: Callable[[ProcessedChunk], None]):
        """Add callback for processed chunks."""
        self.chunk_callbacks.append(callback)
        logger.debug(f"Added chunk callback: {callback.__name__}")
    
    def remove_chunk_callback(self, callback: Callable[[ProcessedChunk], None]):
        """Remove chunk callback."""
        if callback in self.chunk_callbacks:
            self.chunk_callbacks.remove(callback)
            logger.debug(f"Removed chunk callback: {callback.__name__}")
    
    async def start_pipeline(self, websocket_url: str = "ws://localhost:8000/ws/audio") -> bool:
        """
        Start the complete audio pipeline.
        
        Args:
            websocket_url: WebSocket URL for streaming
            
        Returns:
            True if pipeline started successfully
        """
        try:
            if self.is_running:
                logger.warning("Pipeline is already running")
                return True
            
            logger.info("Starting audio pipeline...")
            
            # Start capture manager
            if not await self.capture_manager.start_capture():
                logger.error("Failed to start audio capture")
                return False
            
            # Start streaming manager
            if not await self.streaming_manager.connect(websocket_url):
                logger.error("Failed to connect streaming manager")
                await self.capture_manager.stop_capture()
                return False
            
            # Start processing pipeline
            self.is_running = True
            self.stop_event.clear()
            
            # Start pipeline thread
            self.pipeline_thread = threading.Thread(target=self._run_pipeline_loop, daemon=True)
            self.pipeline_thread.start()
            
            logger.info("Audio pipeline started successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error starting pipeline: {e}")
            await self.stop_pipeline()
            return False
    
    async def stop_pipeline(self):
        """Stop the audio pipeline."""
        try:
            if not self.is_running:
                return
            
            logger.info("Stopping audio pipeline...")
            
            # Signal stop
            self.is_running = False
            self.stop_event.set()
            
            # Wait for pipeline thread to finish
            if self.pipeline_thread and self.pipeline_thread.is_alive():
                self.pipeline_thread.join(timeout=5.0)
            
            # Stop components
            await self.capture_manager.stop_capture()
            await self.streaming_manager.disconnect()
            
            # Shutdown thread pool
            self.processing_executor.shutdown(wait=True, timeout=5.0)
            
            # Clear queues
            while not self.processed_chunks.empty():
                try:
                    self.processed_chunks.get_nowait()
                except queue.Empty:
                    break
            
            logger.info("Audio pipeline stopped")
            
        except Exception as e:
            logger.error(f"Error stopping pipeline: {e}")
    
    def _run_pipeline_loop(self):
        """Main pipeline processing loop (runs in separate thread)."""
        logger.info("Pipeline processing loop started")
        
        chunk_id = 0
        
        try:
            while self.is_running and not self.stop_event.is_set():
                try:
                    # Get raw audio chunk from capture manager
                    raw_chunk = self.capture_manager.get_next_chunk(timeout=0.1)
                    
                    if raw_chunk is None:
                        time.sleep(0.01)  # Brief pause if no data
                        continue
                    
                    # Extract audio data and metadata
                    audio_data = raw_chunk.get('audio_data')
                    sample_rate = raw_chunk.get('sample_rate', 44100)
                    timestamp = raw_chunk.get('timestamp', time.time())
                    
                    if audio_data is None or len(audio_data) == 0:
                        continue
                    
                    # Check if chunk should be skipped
                    if self.config.skip_silent_chunks and self._is_silent_chunk(audio_data):
                        self.processing_stats['chunks_skipped'] += 1
                        continue
                    
                    # Submit for async processing
                    if self.config.async_processing:
                        future = self.processing_executor.submit(
                            self._process_audio_chunk,
                            chunk_id, audio_data, sample_rate, timestamp
                        )
                        
                        # Handle future result (non-blocking)
                        def handle_result(fut):
                            try:
                                processed_chunk = fut.result(timeout=self.config.processing_timeout)
                                if processed_chunk:
                                    self._handle_processed_chunk(processed_chunk)
                            except Exception as e:
                                logger.error(f"Error processing chunk {chunk_id}: {e}")
                                self.processing_stats['processing_errors'] += 1
                        
                        future.add_done_callback(handle_result)
                    else:
                        # Synchronous processing
                        processed_chunk = self._process_audio_chunk(
                            chunk_id, audio_data, sample_rate, timestamp
                        )
                        if processed_chunk:
                            self._handle_processed_chunk(processed_chunk)
                    
                    chunk_id += 1
                    
                except Exception as e:
                    logger.error(f"Error in pipeline loop: {e}")
                    self.processing_stats['processing_errors'] += 1
                    time.sleep(0.1)  # Brief pause on error
        
        except Exception as e:
            logger.error(f"Fatal error in pipeline loop: {e}")
        
        finally:
            logger.info("Pipeline processing loop ended")
    
    def _is_silent_chunk(self, audio_data: np.ndarray) -> bool:
        """Check if audio chunk is silent or has very low energy."""
        try:
            if len(audio_data) == 0:
                return True
            
            # Calculate RMS energy
            rms_energy = np.sqrt(np.mean(audio_data ** 2))
            
            return rms_energy < self.config.energy_threshold
        except:
            return False
    
    def _process_audio_chunk(self, chunk_id: int, audio_data: np.ndarray, 
                           sample_rate: int, timestamp: float) -> Optional[ProcessedChunk]:
        """
        Process a single audio chunk.
        
        Args:
            chunk_id: Unique chunk identifier
            audio_data: Raw audio data
            sample_rate: Sample rate
            timestamp: Chunk timestamp
            
        Returns:
            ProcessedChunk if processing successful, None otherwise
        """
        start_time = time.time()
        
        try:
            # Process audio through pipeline
            processed_audio, metadata = self.audio_processor.process_audio_chunk(
                audio_data, 
                sample_rate,
                normalize=self.config.normalize_audio,
                filter_audio=self.config.apply_filtering
            )
            
            processing_time = time.time() - start_time
            
            # Check quality threshold
            quality_adjusted = False
            if metadata.quality_score < self.config.quality_threshold:
                if self.config.adaptive_quality:
                    # Try alternative processing for low quality audio
                    processed_audio, metadata = self.audio_processor.process_audio_chunk(
                        audio_data, 
                        sample_rate,
                        normalize=True,
                        filter_audio=True
                    )
                    quality_adjusted = True
                else:
                    logger.warning(f"Chunk {chunk_id} quality {metadata.quality_score:.3f} below threshold")
            
            # Create processed chunk
            processed_chunk = ProcessedChunk(
                chunk_id=chunk_id,
                audio_data=processed_audio,
                metadata=metadata,
                original_chunk_id=chunk_id,
                processing_time=processing_time,
                timestamp=timestamp,
                quality_adjusted=quality_adjusted
            )
            
            # Update statistics
            self.processing_stats['chunks_processed'] += 1
            self.processing_stats['total_processing_time'] += processing_time
            self.processing_stats['average_chunk_time'] = (
                self.processing_stats['total_processing_time'] / 
                max(self.processing_stats['chunks_processed'], 1)
            )
            
            if quality_adjusted:
                self.processing_stats['quality_improvements'] += 1
            
            logger.debug(f"Processed chunk {chunk_id}: "
                        f"{len(processed_audio)} samples, "
                        f"quality {metadata.quality_score:.3f}, "
                        f"time {processing_time:.3f}s")
            
            return processed_chunk
            
        except Exception as e:
            logger.error(f"Error processing chunk {chunk_id}: {e}")
            self.processing_stats['processing_errors'] += 1
            return None
    
    def _handle_processed_chunk(self, processed_chunk: ProcessedChunk):
        """Handle a successfully processed chunk."""
        try:
            # Add to processed chunks queue
            try:
                self.processed_chunks.put(processed_chunk, block=False)
            except queue.Full:
                # Remove oldest chunk if queue is full
                try:
                    self.processed_chunks.get_nowait()
                    self.processed_chunks.put(processed_chunk, block=False)
                    logger.warning("Processed chunk queue full, removed oldest chunk")
                except queue.Empty:
                    pass
            
            # Send to streaming manager for transmission
            asyncio.create_task(self._send_processed_chunk(processed_chunk))
            
            # Call registered callbacks
            for callback in self.chunk_callbacks:
                try:
                    callback(processed_chunk)
                except Exception as e:
                    logger.error(f"Error in chunk callback {callback.__name__}: {e}")
        
        except Exception as e:
            logger.error(f"Error handling processed chunk: {e}")
    
    async def _send_processed_chunk(self, processed_chunk: ProcessedChunk):
        """Send processed chunk via streaming manager."""
        try:
            # Prepare chunk data for transmission
            chunk_data = {
                'chunk_id': processed_chunk.chunk_id,
                'audio_data': processed_chunk.audio_data.tobytes(),
                'sample_rate': processed_chunk.metadata.sample_rate,
                'channels': processed_chunk.metadata.channels,
                'timestamp': processed_chunk.timestamp,
                'quality_score': processed_chunk.metadata.quality_score,
                'processing_time': processed_chunk.processing_time
            }
            
            # Send via streaming manager
            await self.streaming_manager.send_audio_chunk(chunk_data)
            
        except Exception as e:
            logger.error(f"Error sending processed chunk: {e}")
    
    def get_next_processed_chunk(self, timeout: float = 1.0) -> Optional[ProcessedChunk]:
        """
        Get next processed chunk from queue.
        
        Args:
            timeout: Maximum time to wait for chunk
            
        Returns:
            ProcessedChunk if available, None if timeout
        """
        try:
            return self.processed_chunks.get(timeout=timeout)
        except queue.Empty:
            return None
    
    def get_pipeline_stats(self) -> Dict[str, Any]:
        """Get comprehensive pipeline statistics."""
        stats = self.processing_stats.copy()
        
        # Add component stats
        stats.update({
            'capture_stats': self.capture_manager.get_capture_stats(),
            'streaming_stats': self.streaming_manager.get_streaming_stats(),
            'processing_queue_size': self.processed_chunks.qsize(),
            'is_running': self.is_running,
            'config': asdict(self.config)
        })
        
        return stats
    
    def update_config(self, **kwargs):
        """Update pipeline configuration dynamically."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                setattr(self.config, key, value)
                logger.info(f"Updated config {key} = {value}")
            else:
                logger.warning(f"Unknown config parameter: {key}")
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.stop_pipeline()

# Utility functions for pipeline management

async def create_pipeline(config: Optional[PipelineConfig] = None, 
                         websocket_url: str = "ws://localhost:8000/ws/audio") -> AudioPipelineManager:
    """
    Create and start an audio pipeline.
    
    Args:
        config: Pipeline configuration
        websocket_url: WebSocket URL for streaming
        
    Returns:
        Started AudioPipelineManager
    """
    pipeline = AudioPipelineManager(config)
    
    if await pipeline.start_pipeline(websocket_url):
        return pipeline
    else:
        raise RuntimeError("Failed to start audio pipeline")

def create_default_config(target_sample_rate: int = 16000, 
                         chunk_duration: float = 1.0) -> PipelineConfig:
    """Create default pipeline configuration."""
    return PipelineConfig(
        target_sample_rate=target_sample_rate,
        chunk_duration=chunk_duration,
        overlap_duration=0.1,
        max_buffer_size=50,
        normalize_audio=True,
        apply_filtering=True,
        quality_threshold=0.3,
        async_processing=True,
        max_workers=2,
        processing_timeout=5.0,
        adaptive_quality=True,
        skip_silent_chunks=True,
        energy_threshold=0.01
    )

if __name__ == "__main__":
    # Example usage
    import asyncio
    
    async def main():
        logging.basicConfig(level=logging.INFO)
        
        # Create pipeline with default config
        config = create_default_config()
        
        # Create and start pipeline
        async with AudioPipelineManager(config) as pipeline:
            # Add a simple callback to log processed chunks
            def log_chunk(chunk: ProcessedChunk):
                print(f"Processed chunk {chunk.chunk_id}: "
                      f"{len(chunk.audio_data)} samples, "
                      f"quality {chunk.metadata.quality_score:.3f}")
            
            pipeline.add_chunk_callback(log_chunk)
            
            # Start pipeline
            if await pipeline.start_pipeline():
                print("Pipeline started successfully")
                
                # Run for 10 seconds
                await asyncio.sleep(10)
                
                # Print final stats
                stats = pipeline.get_pipeline_stats()
                print(f"Final stats: {stats}")
            else:
                print("Failed to start pipeline")
    
    asyncio.run(main())
