"""
Audio Processing Utilities for TrueTone
Handles audio format standardization, resampling, normalization, and conversion.
"""

import numpy as np
import soundfile as sf
import librosa
import logging
from typing import Tuple, Optional, Dict, Any
from dataclasses import dataclass
from pathlib import Path
import warnings

# Suppress librosa warnings for cleaner output
warnings.filterwarnings("ignore", category=UserWarning, module="librosa")

logger = logging.getLogger(__name__)

@dataclass
class AudioMetadata:
    """Audio metadata tracking throughout pipeline"""
    sample_rate: int
    channels: int
    duration: float
    bit_depth: int
    format: str
    quality_score: float = 0.0
    processing_steps: list = None
    
    def __post_init__(self):
        if self.processing_steps is None:
            self.processing_steps = []

class AudioProcessor:
    """
    Comprehensive audio processing for TrueTone pipeline.
    Handles format standardization, resampling, normalization, and quality control.
    """
    
    # Standard configurations for ML models
    WHISPER_SAMPLE_RATE = 16000  # Optimal for Whisper
    TTS_SAMPLE_RATE = 22050      # Optimal for TTS models
    HIGH_QUALITY_SAMPLE_RATE = 44100  # For high-quality processing
    
    def __init__(self, target_sample_rate: int = WHISPER_SAMPLE_RATE):
        """
        Initialize audio processor with target configuration.
        
        Args:
            target_sample_rate: Target sample rate for processing
        """
        self.target_sample_rate = target_sample_rate
        self.processing_stats = {
            'total_processed': 0,
            'resampling_operations': 0,
            'normalization_operations': 0,
            'format_conversions': 0,
            'quality_improvements': 0
        }
        
        logger.info(f"AudioProcessor initialized with target sample rate: {target_sample_rate}Hz")
    
    def detect_audio_properties(self, audio_data: np.ndarray, sample_rate: int) -> AudioMetadata:
        """
        Detect and analyze audio properties.
        
        Args:
            audio_data: Raw audio data
            sample_rate: Original sample rate
            
        Returns:
            AudioMetadata object with detected properties
        """
        try:
            # Ensure audio is 1D for analysis
            if len(audio_data.shape) > 1:
                audio_mono = np.mean(audio_data, axis=1)
            else:
                audio_mono = audio_data
            
            # Calculate basic properties
            duration = len(audio_mono) / sample_rate
            channels = 1 if len(audio_data.shape) == 1 else audio_data.shape[1]
            
            # Estimate bit depth from data type
            bit_depth_map = {
                np.int16: 16,
                np.int32: 24,
                np.float32: 32,
                np.float64: 64
            }
            bit_depth = bit_depth_map.get(audio_data.dtype, 16)
            
            # Calculate quality score based on various metrics
            quality_score = self._calculate_quality_score(audio_mono, sample_rate)
            
            metadata = AudioMetadata(
                sample_rate=sample_rate,
                channels=channels,
                duration=duration,
                bit_depth=bit_depth,
                format="numpy_array",
                quality_score=quality_score
            )
            
            logger.debug(f"Audio properties detected: {metadata}")
            return metadata
            
        except Exception as e:
            logger.error(f"Error detecting audio properties: {e}")
            # Return default metadata
            return AudioMetadata(
                sample_rate=sample_rate,
                channels=1,
                duration=0.0,
                bit_depth=16,
                format="unknown",
                quality_score=0.0
            )
    
    def _calculate_quality_score(self, audio_data: np.ndarray, sample_rate: int) -> float:
        """
        Calculate audio quality score based on various metrics.
        
        Args:
            audio_data: Mono audio data
            sample_rate: Sample rate
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        try:
            if len(audio_data) == 0:
                return 0.0
            
            # Calculate various quality metrics
            
            # 1. Dynamic range (higher is better)
            dynamic_range = np.max(audio_data) - np.min(audio_data)
            dynamic_score = min(dynamic_range / 0.5, 1.0)  # Normalize to 0-1
            
            # 2. RMS energy (presence of signal)
            rms = np.sqrt(np.mean(audio_data ** 2))
            energy_score = min(rms / 0.1, 1.0)  # Normalize to 0-1
            
            # 3. Zero crossing rate (measure of spectral content)
            zcr = librosa.feature.zero_crossing_rate(audio_data, frame_length=2048, hop_length=512)[0]
            zcr_score = 1.0 - min(np.mean(zcr) / 0.3, 1.0)  # Lower ZCR often better for speech
            
            # 4. Spectral centroid (frequency content quality)
            spectral_centroids = librosa.feature.spectral_centroid(y=audio_data, sr=sample_rate)[0]
            centroid_score = min(np.mean(spectral_centroids) / (sample_rate / 4), 1.0)
            
            # 5. Sample rate score (higher sample rates generally better)
            sr_score = min(sample_rate / 44100, 1.0)
            
            # Weighted combination of scores
            quality_score = (
                dynamic_score * 0.25 +
                energy_score * 0.25 +
                zcr_score * 0.2 +
                centroid_score * 0.15 +
                sr_score * 0.15
            )
            
            return float(np.clip(quality_score, 0.0, 1.0))
            
        except Exception as e:
            logger.warning(f"Error calculating quality score: {e}")
            return 0.5  # Default moderate quality score
    
    def standardize_sample_rate(self, audio_data: np.ndarray, original_sr: int, 
                              target_sr: Optional[int] = None) -> Tuple[np.ndarray, int]:
        """
        Resample audio to target sample rate using high-quality algorithms.
        
        Args:
            audio_data: Input audio data
            original_sr: Original sample rate
            target_sr: Target sample rate (uses instance default if None)
            
        Returns:
            Tuple of (resampled_audio, target_sample_rate)
        """
        if target_sr is None:
            target_sr = self.target_sample_rate
        
        if original_sr == target_sr:
            logger.debug(f"No resampling needed, already at {target_sr}Hz")
            return audio_data, target_sr
        
        try:
            logger.debug(f"Resampling from {original_sr}Hz to {target_sr}Hz")
            
            # Use librosa's high-quality resampling with anti-aliasing
            resampled_audio = librosa.resample(
                audio_data, 
                orig_sr=original_sr, 
                target_sr=target_sr,
                res_type='kaiser_best'  # Highest quality resampling
            )
            
            self.processing_stats['resampling_operations'] += 1
            logger.debug(f"Resampling completed: {len(audio_data)} -> {len(resampled_audio)} samples")
            
            return resampled_audio, target_sr
            
        except Exception as e:
            logger.error(f"Error during resampling: {e}")
            # Return original audio if resampling fails
            return audio_data, original_sr
    
    def convert_to_mono(self, audio_data: np.ndarray) -> np.ndarray:
        """
        Convert stereo/multi-channel audio to mono using intelligent mixing.
        
        Args:
            audio_data: Input audio data (can be mono or multi-channel)
            
        Returns:
            Mono audio data
        """
        if len(audio_data.shape) == 1:
            logger.debug("Audio is already mono")
            return audio_data
        
        if len(audio_data.shape) == 2:
            if audio_data.shape[1] == 1:
                # Single channel in 2D array
                return audio_data.flatten()
            elif audio_data.shape[1] == 2:
                # Stereo to mono conversion
                logger.debug("Converting stereo to mono")
                mono_audio = np.mean(audio_data, axis=1)
                return mono_audio
            else:
                # Multi-channel to mono
                logger.debug(f"Converting {audio_data.shape[1]}-channel audio to mono")
                mono_audio = np.mean(audio_data, axis=1)
                return mono_audio
        
        logger.warning(f"Unexpected audio shape: {audio_data.shape}")
        return audio_data.flatten()
    
    def normalize_audio(self, audio_data: np.ndarray, method: str = 'peak',
                       target_level: float = 0.8) -> np.ndarray:
        """
        Normalize audio using various methods.
        
        Args:
            audio_data: Input audio data
            method: Normalization method ('peak', 'rms', 'lufs')
            target_level: Target normalization level
            
        Returns:
            Normalized audio data
        """
        try:
            if len(audio_data) == 0:
                return audio_data
            
            if method == 'peak':
                # Peak normalization
                max_val = np.max(np.abs(audio_data))
                if max_val > 0:
                    normalized_audio = audio_data * (target_level / max_val)
                else:
                    normalized_audio = audio_data
                    
            elif method == 'rms':
                # RMS normalization
                rms = np.sqrt(np.mean(audio_data ** 2))
                if rms > 0:
                    normalized_audio = audio_data * (target_level / rms)
                else:
                    normalized_audio = audio_data
                    
            else:
                logger.warning(f"Unknown normalization method: {method}, using peak")
                return self.normalize_audio(audio_data, 'peak', target_level)
            
            # Prevent clipping
            normalized_audio = np.clip(normalized_audio, -1.0, 1.0)
            
            self.processing_stats['normalization_operations'] += 1
            logger.debug(f"Audio normalized using {method} method")
            
            return normalized_audio
            
        except Exception as e:
            logger.error(f"Error during normalization: {e}")
            return audio_data
    
    def apply_audio_filtering(self, audio_data: np.ndarray, sample_rate: int,
                            high_pass_freq: float = 80.0,
                            low_pass_freq: Optional[float] = None) -> np.ndarray:
        """
        Apply basic audio filtering to improve quality.
        
        Args:
            audio_data: Input audio data
            sample_rate: Sample rate
            high_pass_freq: High-pass filter frequency (Hz)
            low_pass_freq: Low-pass filter frequency (Hz), None to disable
            
        Returns:
            Filtered audio data
        """
        try:
            filtered_audio = audio_data.copy()
            
            # High-pass filter to remove low-frequency noise
            if high_pass_freq > 0:
                from scipy.signal import butter, filtfilt
                nyquist = sample_rate / 2
                high_pass_norm = high_pass_freq / nyquist
                
                if high_pass_norm < 1.0:
                    b, a = butter(2, high_pass_norm, btype='high')
                    filtered_audio = filtfilt(b, a, filtered_audio)
                    logger.debug(f"Applied high-pass filter at {high_pass_freq}Hz")
            
            # Low-pass filter if specified
            if low_pass_freq and low_pass_freq > 0:
                from scipy.signal import butter, filtfilt
                nyquist = sample_rate / 2
                low_pass_norm = low_pass_freq / nyquist
                
                if low_pass_norm < 1.0:
                    b, a = butter(2, low_pass_norm, btype='low')
                    filtered_audio = filtfilt(b, a, filtered_audio)
                    logger.debug(f"Applied low-pass filter at {low_pass_freq}Hz")
            
            return filtered_audio
            
        except ImportError:
            logger.warning("scipy not available for filtering, skipping")
            return audio_data
        except Exception as e:
            logger.warning(f"Error during filtering: {e}")
            return audio_data
    
    def process_audio_chunk(self, audio_data: np.ndarray, sample_rate: int,
                          normalize: bool = True, filter_audio: bool = True) -> Tuple[np.ndarray, AudioMetadata]:
        """
        Complete audio processing pipeline for a single chunk.
        
        Args:
            audio_data: Raw audio data
            sample_rate: Original sample rate
            normalize: Whether to normalize audio
            filter_audio: Whether to apply filtering
            
        Returns:
            Tuple of (processed_audio, metadata)
        """
        try:
            # Detect original properties
            original_metadata = self.detect_audio_properties(audio_data, sample_rate)
            
            # Start processing
            processed_audio = audio_data.copy()
            processing_steps = ["input"]
            
            # Convert to mono if needed
            if len(processed_audio.shape) > 1:
                processed_audio = self.convert_to_mono(processed_audio)
                processing_steps.append("mono_conversion")
            
            # Resample to target sample rate
            processed_audio, final_sr = self.standardize_sample_rate(
                processed_audio, sample_rate, self.target_sample_rate
            )
            if final_sr != sample_rate:
                processing_steps.append(f"resampled_to_{final_sr}Hz")
            
            # Apply filtering
            if filter_audio:
                processed_audio = self.apply_audio_filtering(processed_audio, final_sr)
                processing_steps.append("filtered")
            
            # Normalize audio
            if normalize:
                processed_audio = self.normalize_audio(processed_audio, method='peak', target_level=0.8)
                processing_steps.append("normalized")
            
            # Create final metadata
            final_metadata = self.detect_audio_properties(processed_audio, final_sr)
            final_metadata.processing_steps = processing_steps
            
            # Update stats
            self.processing_stats['total_processed'] += 1
            if final_metadata.quality_score > original_metadata.quality_score:
                self.processing_stats['quality_improvements'] += 1
            
            logger.debug(f"Audio chunk processed: {len(processing_steps)} steps, "
                        f"quality {original_metadata.quality_score:.2f} -> {final_metadata.quality_score:.2f}")
            
            return processed_audio, final_metadata
            
        except Exception as e:
            logger.error(f"Error in audio processing pipeline: {e}")
            # Return original audio with basic metadata
            metadata = AudioMetadata(
                sample_rate=sample_rate,
                channels=1,
                duration=len(audio_data) / sample_rate,
                bit_depth=16,
                format="error_fallback",
                quality_score=0.0,
                processing_steps=["error"]
            )
            return audio_data, metadata
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return self.processing_stats.copy()
    
    def reset_stats(self):
        """Reset processing statistics."""
        for key in self.processing_stats:
            self.processing_stats[key] = 0
        logger.info("Processing statistics reset")

# Utility functions for common operations
def load_audio_file(file_path: str, target_sr: int = 16000) -> Tuple[np.ndarray, int, AudioMetadata]:
    """
    Load audio file and return processed data with metadata.
    
    Args:
        file_path: Path to audio file
        target_sr: Target sample rate
        
    Returns:
        Tuple of (audio_data, sample_rate, metadata)
    """
    try:
        # Load audio file
        audio_data, original_sr = sf.read(file_path)
        
        # Process with AudioProcessor
        processor = AudioProcessor(target_sample_rate=target_sr)
        processed_audio, metadata = processor.process_audio_chunk(audio_data, original_sr)
        
        logger.info(f"Audio file loaded and processed: {file_path}")
        return processed_audio, target_sr, metadata
        
    except Exception as e:
        logger.error(f"Error loading audio file {file_path}: {e}")
        raise

def save_processed_audio(audio_data: np.ndarray, sample_rate: int, 
                        output_path: str, metadata: Optional[AudioMetadata] = None):
    """
    Save processed audio to file with metadata.
    
    Args:
        audio_data: Processed audio data
        sample_rate: Sample rate
        output_path: Output file path
        metadata: Optional metadata to include
    """
    try:
        # Ensure output directory exists
        output_dir = Path(output_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Save audio file
        sf.write(output_path, audio_data, sample_rate)
        
        # Save metadata if provided
        if metadata:
            metadata_path = Path(output_path).with_suffix('.json')
            import json
            metadata_dict = {
                'sample_rate': metadata.sample_rate,
                'channels': metadata.channels,
                'duration': metadata.duration,
                'bit_depth': metadata.bit_depth,
                'format': metadata.format,
                'quality_score': metadata.quality_score,
                'processing_steps': metadata.processing_steps
            }
            with open(metadata_path, 'w') as f:
                json.dump(metadata_dict, f, indent=2)
        
        logger.info(f"Processed audio saved: {output_path}")
        
    except Exception as e:
        logger.error(f"Error saving processed audio: {e}")
        raise

if __name__ == "__main__":
    # Example usage and testing
    logging.basicConfig(level=logging.DEBUG)
    
    # Create test audio processor
    processor = AudioProcessor(target_sample_rate=16000)
    
    # Test with synthetic audio
    test_audio = np.random.normal(0, 0.1, 44100)  # 1 second of noise at 44.1kHz
    
    processed_audio, metadata = processor.process_audio_chunk(test_audio, 44100)
    
    print(f"Original: {len(test_audio)} samples at 44100Hz")
    print(f"Processed: {len(processed_audio)} samples at {metadata.sample_rate}Hz")
    print(f"Quality score: {metadata.quality_score:.3f}")
    print(f"Processing steps: {metadata.processing_steps}")
    print(f"Stats: {processor.get_processing_stats()}")
