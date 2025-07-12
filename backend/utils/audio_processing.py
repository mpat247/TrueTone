"""
Audio Processing Utilities
Core audio processing functions for TrueTone backend.
"""

import numpy as np
import logging
from scipy import signal
from typing import Dict, Any, Tuple, Optional
import io

logger = logging.getLogger(__name__)


class AudioProcessor:
    """Core audio processing utilities for standardization and format conversion"""
    
    def __init__(self):
        # Standard audio parameters for ML models
        self.target_sample_rate = 16000  # 16kHz is optimal for most speech models
        self.target_channels = 1  # Mono audio
        self.target_dtype = np.float32
        
        # Audio quality thresholds
        self.min_rms_threshold = 1e-6  # Minimum RMS to consider as valid audio
        self.max_clip_ratio = 0.01  # Maximum acceptable clipping ratio
        
        logger.info(f"AudioProcessor initialized - Target: {self.target_sample_rate}Hz, {self.target_channels} channel(s)")
    
    def standardize_audio(self, audio_data: np.ndarray, orig_sample_rate: int, 
                         target_sample_rate: Optional[int] = None) -> np.ndarray:
        """Standardize audio format for ML processing"""
        if target_sample_rate is None:
            target_sample_rate = self.target_sample_rate
        
        try:
            # Convert to float32 if needed
            if audio_data.dtype != self.target_dtype:
                audio_data = audio_data.astype(self.target_dtype)
            
            # Ensure mono (convert stereo to mono if needed)
            if len(audio_data.shape) > 1:
                audio_data = self.stereo_to_mono(audio_data)
            
            # Resample if sample rate doesn't match
            if orig_sample_rate != target_sample_rate:
                audio_data = self.resample_audio(audio_data, orig_sample_rate, target_sample_rate)
            
            # Normalize audio
            audio_data = self.normalize_audio(audio_data)
            
            # Apply basic filtering
            audio_data = self.apply_basic_filters(audio_data, target_sample_rate)
            
            return audio_data
            
        except Exception as e:
            logger.error(f"Error standardizing audio: {str(e)}")
            raise
    
    def resample_audio(self, audio_data: np.ndarray, orig_rate: int, target_rate: int) -> np.ndarray:
        """Resample audio to target sample rate using high-quality resampling"""
        if orig_rate == target_rate:
            return audio_data
        
        try:
            # Calculate resampling ratio
            ratio = target_rate / orig_rate
            
            # Use scipy's resample_poly for high-quality resampling
            # This uses polyphase filtering which is better than simple interpolation
            if ratio > 1:
                # Upsampling
                up_factor = int(ratio) if ratio == int(ratio) else target_rate
                down_factor = orig_rate if ratio == int(ratio) else orig_rate
                resampled = signal.resample_poly(audio_data, up_factor, down_factor)
            else:
                # Downsampling
                down_factor = int(1/ratio) if 1/ratio == int(1/ratio) else orig_rate
                up_factor = target_rate if 1/ratio == int(1/ratio) else target_rate
                resampled = signal.resample_poly(audio_data, up_factor, down_factor)
            
            logger.debug(f"Resampled audio from {orig_rate}Hz to {target_rate}Hz")
            return resampled.astype(self.target_dtype)
            
        except Exception as e:
            logger.error(f"Error resampling audio: {str(e)}")
            # Fallback to simple resampling
            return self._simple_resample(audio_data, orig_rate, target_rate)
    
    def _simple_resample(self, audio_data: np.ndarray, orig_rate: int, target_rate: int) -> np.ndarray:
        """Simple resampling fallback method"""
        ratio = target_rate / orig_rate
        new_length = int(len(audio_data) * ratio)
        
        # Use numpy interpolation as fallback
        x_old = np.linspace(0, 1, len(audio_data))
        x_new = np.linspace(0, 1, new_length)
        resampled = np.interp(x_new, x_old, audio_data)
        
        logger.warning(f"Used simple resampling fallback from {orig_rate}Hz to {target_rate}Hz")
        return resampled.astype(self.target_dtype)
    
    def stereo_to_mono(self, stereo_data: np.ndarray) -> np.ndarray:
        """Convert stereo audio to mono using intelligent mixing"""
        try:
            if len(stereo_data.shape) == 1:
                return stereo_data  # Already mono
            
            if stereo_data.shape[1] == 1:
                return stereo_data.flatten()  # Single channel
            
            if stereo_data.shape[1] == 2:
                # Standard stereo - mix channels with equal weight
                mono = np.mean(stereo_data, axis=1)
                return mono.astype(self.target_dtype)
            
            # Multi-channel audio - use first channel or mix all
            if stereo_data.shape[1] > 2:
                logger.warning(f"Multi-channel audio detected ({stereo_data.shape[1]} channels), mixing to mono")
                mono = np.mean(stereo_data, axis=1)
                return mono.astype(self.target_dtype)
            
            # Fallback for unexpected shapes
            return stereo_data.flatten().astype(self.target_dtype)
            
        except Exception as e:
            logger.error(f"Error converting stereo to mono: {str(e)}")
            # Fallback - try to use first channel if possible
            if len(stereo_data.shape) > 1 and stereo_data.shape[1] > 0:
                return stereo_data[:, 0].astype(self.target_dtype)
            else:
                return stereo_data.flatten().astype(self.target_dtype)
    
    def normalize_audio(self, audio_data: np.ndarray, method: str = 'peak', 
                       target_level: float = 0.95) -> np.ndarray:
        """Normalize audio using specified method"""
        try:
            if len(audio_data) == 0:
                return audio_data
            
            if method == 'peak':
                # Peak normalization
                peak = np.max(np.abs(audio_data))
                if peak > 0:
                    normalized = audio_data / peak * target_level
                else:
                    normalized = audio_data
            
            elif method == 'rms':
                # RMS normalization
                rms = np.sqrt(np.mean(audio_data ** 2))
                if rms > self.min_rms_threshold:
                    target_rms = target_level * 0.3  # More conservative for RMS
                    normalized = audio_data / rms * target_rms
                else:
                    normalized = audio_data
            
            else:
                logger.warning(f"Unknown normalization method: {method}, using peak")
                return self.normalize_audio(audio_data, 'peak', target_level)
            
            # Ensure we don't exceed the target level
            normalized = np.clip(normalized, -target_level, target_level)
            
            return normalized.astype(self.target_dtype)
            
        except Exception as e:
            logger.error(f"Error normalizing audio: {str(e)}")
            return audio_data
    
    def apply_basic_filters(self, audio_data: np.ndarray, sample_rate: int) -> np.ndarray:
        """Apply basic audio filters for preprocessing"""
        try:
            filtered = audio_data.copy()
            
            # High-pass filter to remove DC offset and low-frequency noise
            # Cutoff at 80Hz to preserve speech fundamentals
            filtered = self.highpass_filter(filtered, sample_rate, cutoff=80)
            
            # Light low-pass filter to reduce high-frequency noise
            # Cutoff at 8kHz (Nyquist for 16kHz sampling)
            if sample_rate > 16000:
                filtered = self.lowpass_filter(filtered, sample_rate, cutoff=8000)
            
            return filtered
            
        except Exception as e:
            logger.error(f"Error applying basic filters: {str(e)}")
            return audio_data
    
    def highpass_filter(self, audio_data: np.ndarray, sample_rate: int, 
                       cutoff: float, order: int = 5) -> np.ndarray:
        """Apply highpass filter"""
        try:
            nyquist = sample_rate / 2
            normal_cutoff = cutoff / nyquist
            
            if normal_cutoff >= 1.0:
                logger.warning(f"Highpass cutoff frequency too high: {cutoff}Hz for {sample_rate}Hz sample rate")
                return audio_data
            
            # Use signal.butter with proper error handling
            filter_result = signal.butter(order, normal_cutoff, btype='high', analog=False)
            if filter_result is None:
                logger.warning("Failed to create highpass filter")
                return audio_data
            
            # Handle different return types from signal.butter
            if isinstance(filter_result, tuple) and len(filter_result) >= 2:
                b, a = filter_result[0], filter_result[1]
                filtered = signal.filtfilt(b, a, audio_data)
                return filtered.astype(self.target_dtype)
            else:
                logger.warning("Unexpected filter result format")
                return audio_data
            
        except Exception as e:
            logger.error(f"Error applying highpass filter: {str(e)}")
            return audio_data
    
    def lowpass_filter(self, audio_data: np.ndarray, sample_rate: int, 
                      cutoff: float, order: int = 5) -> np.ndarray:
        """Apply lowpass filter"""
        try:
            nyquist = sample_rate / 2
            normal_cutoff = cutoff / nyquist
            
            if normal_cutoff >= 1.0:
                logger.warning(f"Lowpass cutoff frequency too high: {cutoff}Hz for {sample_rate}Hz sample rate")
                return audio_data
            
            # Use signal.butter with proper error handling
            filter_result = signal.butter(order, normal_cutoff, btype='low', analog=False)
            if filter_result is None:
                logger.warning("Failed to create lowpass filter")
                return audio_data
            
            # Handle different return types from signal.butter
            if isinstance(filter_result, tuple) and len(filter_result) >= 2:
                b, a = filter_result[0], filter_result[1]
                filtered = signal.filtfilt(b, a, audio_data)
                return filtered.astype(self.target_dtype)
            else:
                logger.warning("Unexpected filter result format")
                return audio_data
            
        except Exception as e:
            logger.error(f"Error applying lowpass filter: {str(e)}")
            return audio_data
    
    def detect_audio_format(self, audio_data: bytes) -> Dict[str, Any]:
        """Detect audio format from raw bytes"""
        try:
            # Try different format interpretations
            formats = [
                ('float32', np.float32),
                ('int16', np.int16),
                ('int32', np.int32),
                ('float64', np.float64)
            ]
            
            best_format = None
            best_score = 0
            
            for format_name, dtype in formats:
                try:
                    # Try to interpret as this format
                    samples = np.frombuffer(audio_data, dtype=dtype)
                    
                    if len(samples) == 0:
                        continue
                    
                    # Convert to float32 for analysis
                    if dtype != np.float32:
                        if dtype == np.int16:
                            float_samples = samples.astype(np.float32) / 32768.0
                        elif dtype == np.int32:
                            float_samples = samples.astype(np.float32) / 2147483648.0
                        else:
                            float_samples = samples.astype(np.float32)
                    else:
                        float_samples = samples
                    
                    # Score based on reasonable audio characteristics
                    score = self._score_audio_format(float_samples)
                    
                    if score > best_score:
                        best_score = score
                        best_format = {
                            'format': format_name,
                            'dtype': dtype,
                            'samples': len(samples),
                            'score': score
                        }
                        
                except Exception:
                    continue
            
            if best_format:
                logger.debug(f"Detected audio format: {best_format['format']} (score: {best_format['score']:.2f})")
                return best_format
            else:
                # Default fallback
                return {
                    'format': 'float32',
                    'dtype': np.float32,
                    'samples': len(audio_data) // 4,
                    'score': 0.0
                }
                
        except Exception as e:
            logger.error(f"Error detecting audio format: {str(e)}")
            return {
                'format': 'float32',
                'dtype': np.float32,
                'samples': len(audio_data) // 4,
                'score': 0.0
            }
    
    def _score_audio_format(self, audio_samples: np.ndarray) -> float:
        """Score audio format interpretation based on characteristics"""
        if len(audio_samples) == 0:
            return 0.0
        
        score = 0.0
        
        # Check if values are in reasonable range for audio
        max_val = np.max(np.abs(audio_samples))
        if 0.001 <= max_val <= 1.0:
            score += 50  # Good range for normalized audio
        elif max_val <= 100:
            score += 25  # Reasonable range
        
        # Check for reasonable dynamic range
        if max_val > 0:
            rms = np.sqrt(np.mean(audio_samples ** 2))
            dynamic_range = 20 * np.log10(max_val / max(rms, 1e-6))
            if 10 <= dynamic_range <= 60:  # Reasonable dynamic range for speech
                score += 25
        
        # Check for non-zero variance (not silence or constant)
        variance = np.var(audio_samples)
        if variance > 1e-6:
            score += 15
        
        # Check for reasonable zero crossing rate
        if len(audio_samples) > 1:
            zero_crossings = np.sum(np.diff(np.signbit(audio_samples)))
            zcr = zero_crossings / (len(audio_samples) - 1)
            if 0.01 <= zcr <= 0.3:  # Reasonable for speech
                score += 10
        
        return score
    
    def get_audio_metadata(self, audio_data: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """Extract metadata from audio data"""
        try:
            if len(audio_data) == 0:
                return {'error': 'Empty audio data'}
            
            # Basic properties
            duration = len(audio_data) / sample_rate
            rms = np.sqrt(np.mean(audio_data ** 2))
            peak = np.max(np.abs(audio_data))
            
            # Dynamic range
            dynamic_range = 20 * np.log10(peak / max(rms, 1e-6))
            
            # Zero crossing rate
            zero_crossings = np.sum(np.diff(np.signbit(audio_data)))
            zcr = zero_crossings / (len(audio_data) - 1) if len(audio_data) > 1 else 0
            
            # Clipping detection
            clip_count = np.sum(np.abs(audio_data) >= 0.99)
            clip_ratio = clip_count / len(audio_data)
            
            return {
                'duration': duration,
                'samples': len(audio_data),
                'sample_rate': sample_rate,
                'rms_level': float(rms),
                'peak_level': float(peak),
                'dynamic_range_db': float(dynamic_range),
                'zero_crossing_rate': float(zcr),
                'clipping_detected': clip_ratio > self.max_clip_ratio,
                'clipping_ratio': float(clip_ratio),
                'is_silence': rms < self.min_rms_threshold
            }
            
        except Exception as e:
            logger.error(f"Error extracting audio metadata: {str(e)}")
            return {'error': str(e)}
