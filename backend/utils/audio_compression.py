"""
Audio Compression Utilities
Handles audio compression for efficient network transmission.
"""

import numpy as np
import logging
import zlib
import gzip
from typing import Dict, Any, Tuple, Optional
import struct
import io

logger = logging.getLogger(__name__)


class AudioCompressor:
    """Audio compression utilities for network transmission"""
    
    def __init__(self):
        self.compression_methods = {
            'none': self._no_compression,
            'zlib': self._zlib_compression,
            'gzip': self._gzip_compression,
            'delta': self._delta_compression,
            'adaptive': self._adaptive_compression
        }
        
        # Compression parameters
        self.zlib_level = 6  # Compression level (1-9)
        self.delta_enabled = True
        self.adaptive_threshold = 0.7  # Switch to different compression if ratio > threshold
        
        logger.info("AudioCompressor initialized")
    
    def compress_audio(self, audio_data: np.ndarray, method: str = 'adaptive', 
                      metadata: Optional[Dict[str, Any]] = None) -> Tuple[bytes, Dict[str, Any]]:
        """Compress audio data using specified method"""
        try:
            if method not in self.compression_methods:
                logger.warning(f"Unknown compression method: {method}, using 'zlib'")
                method = 'zlib'
            
            # Convert numpy array to bytes
            audio_bytes = audio_data.astype(np.float32).tobytes()
            original_size = len(audio_bytes)
            
            # Apply compression
            compressed_bytes, compression_info = self.compression_methods[method](
                audio_bytes, metadata or {}
            )
            
            compressed_size = len(compressed_bytes)
            compression_ratio = compressed_size / original_size if original_size > 0 else 1.0
            
            # Prepare compression metadata
            result_metadata = {
                'method': method,
                'original_size': original_size,
                'compressed_size': compressed_size,
                'compression_ratio': compression_ratio,
                'samples': len(audio_data),
                'dtype': str(audio_data.dtype),
                **compression_info
            }
            
            logger.debug(f"Compressed audio: {original_size} -> {compressed_size} bytes "
                        f"(ratio: {compression_ratio:.3f}) using {method}")
            
            return compressed_bytes, result_metadata
            
        except Exception as e:
            logger.error(f"Error compressing audio: {str(e)}")
            # Return uncompressed data as fallback
            audio_bytes = audio_data.astype(np.float32).tobytes()
            return audio_bytes, {
                'method': 'none',
                'original_size': len(audio_bytes),
                'compressed_size': len(audio_bytes),
                'compression_ratio': 1.0,
                'error': str(e)
            }
    
    def decompress_audio(self, compressed_data: bytes, 
                        metadata: Dict[str, Any]) -> np.ndarray:
        """Decompress audio data using metadata information"""
        try:
            method = metadata.get('method', 'none')
            original_size = metadata.get('original_size', len(compressed_data))
            samples = metadata.get('samples', original_size // 4)
            
            # Decompress based on method
            if method == 'none':
                audio_bytes = compressed_data
            elif method == 'zlib':
                audio_bytes = zlib.decompress(compressed_data)
            elif method == 'gzip':
                audio_bytes = gzip.decompress(compressed_data)
            elif method == 'delta':
                audio_bytes = self._delta_decompression(compressed_data, metadata)
            elif method == 'adaptive':
                # Adaptive method stores the actual method used
                actual_method = metadata.get('actual_method', 'zlib')
                if actual_method == 'delta':
                    audio_bytes = self._delta_decompression(compressed_data, metadata)
                elif actual_method == 'zlib':
                    audio_bytes = zlib.decompress(compressed_data)
                elif actual_method == 'gzip':
                    audio_bytes = gzip.decompress(compressed_data)
                else:
                    audio_bytes = compressed_data
            else:
                logger.warning(f"Unknown decompression method: {method}")
                audio_bytes = compressed_data
            
            # Convert back to numpy array
            audio_array = np.frombuffer(audio_bytes, dtype=np.float32)
            
            # Validate size
            if len(audio_array) != samples:
                logger.warning(f"Size mismatch after decompression: "
                             f"expected {samples}, got {len(audio_array)}")
            
            return audio_array
            
        except Exception as e:
            logger.error(f"Error decompressing audio: {str(e)}")
            # Try to return raw data as float32
            try:
                return np.frombuffer(compressed_data, dtype=np.float32)
            except:
                # Return empty array as last resort
                return np.array([], dtype=np.float32)
    
    def _no_compression(self, audio_bytes: bytes, metadata: Dict[str, Any]) -> Tuple[bytes, Dict[str, Any]]:
        """No compression - return data as-is"""
        return audio_bytes, {'actual_method': 'none'}
    
    def _zlib_compression(self, audio_bytes: bytes, metadata: Dict[str, Any]) -> Tuple[bytes, Dict[str, Any]]:
        """Compress using zlib"""
        compressed = zlib.compress(audio_bytes, self.zlib_level)
        return compressed, {
            'actual_method': 'zlib',
            'zlib_level': self.zlib_level
        }
    
    def _gzip_compression(self, audio_bytes: bytes, metadata: Dict[str, Any]) -> Tuple[bytes, Dict[str, Any]]:
        """Compress using gzip"""
        compressed = gzip.compress(audio_bytes, compresslevel=self.zlib_level)
        return compressed, {
            'actual_method': 'gzip',
            'gzip_level': self.zlib_level
        }
    
    def _delta_compression(self, audio_bytes: bytes, metadata: Dict[str, Any]) -> Tuple[bytes, Dict[str, Any]]:
        """Delta compression - encode differences between samples"""
        try:
            # Convert bytes back to float32 array for delta encoding
            audio_array = np.frombuffer(audio_bytes, dtype=np.float32)
            
            if len(audio_array) == 0:
                return audio_bytes, {'actual_method': 'delta', 'delta_samples': 0}
            
            # Calculate deltas (differences between consecutive samples)
            deltas = np.diff(audio_array, prepend=audio_array[0])
            
            # Quantize deltas to reduce precision for better compression
            # Scale factor for quantization (higher = more compression, lower quality)
            scale_factor = 1000.0
            quantized_deltas = np.round(deltas * scale_factor).astype(np.int16)
            
            # Convert to bytes
            delta_bytes = quantized_deltas.tobytes()
            
            # Add header with first sample and scale factor
            header = struct.pack('!fd', audio_array[0], scale_factor)
            
            # Compress the delta data
            compressed_deltas = zlib.compress(delta_bytes, self.zlib_level)
            
            # Combine header and compressed deltas
            result = header + compressed_deltas
            
            return result, {
                'actual_method': 'delta',
                'delta_samples': len(audio_array),
                'scale_factor': scale_factor,
                'header_size': len(header)
            }
            
        except Exception as e:
            logger.error(f"Error in delta compression: {str(e)}")
            # Fallback to zlib
            return self._zlib_compression(audio_bytes, metadata)
    
    def _delta_decompression(self, compressed_data: bytes, metadata: Dict[str, Any]) -> bytes:
        """Decompress delta-encoded audio"""
        try:
            header_size = metadata.get('header_size', 16)  # 8 bytes float64 + 8 bytes double
            samples = metadata.get('delta_samples', 0)
            
            # Extract header
            header = compressed_data[:header_size]
            compressed_deltas = compressed_data[header_size:]
            
            # Unpack header
            first_sample, scale_factor = struct.unpack('!fd', header)
            
            # Decompress deltas
            delta_bytes = zlib.decompress(compressed_deltas)
            quantized_deltas = np.frombuffer(delta_bytes, dtype=np.int16)
            
            # Convert back to float deltas
            deltas = quantized_deltas.astype(np.float32) / scale_factor
            
            # Reconstruct audio by cumulative sum
            audio_array = np.empty(len(deltas), dtype=np.float32)
            audio_array[0] = first_sample
            
            for i in range(1, len(deltas)):
                audio_array[i] = audio_array[i-1] + deltas[i]
            
            return audio_array.tobytes()
            
        except Exception as e:
            logger.error(f"Error in delta decompression: {str(e)}")
            raise
    
    def _adaptive_compression(self, audio_bytes: bytes, metadata: Dict[str, Any]) -> Tuple[bytes, Dict[str, Any]]:
        """Adaptive compression - choose best method based on data characteristics"""
        try:
            # Try different methods and choose the best one
            methods_to_try = ['zlib', 'delta']
            best_method = 'zlib'
            best_compressed: bytes = audio_bytes
            best_ratio = 1.0
            best_info: Dict[str, Any] = {}
            
            for method in methods_to_try:
                try:
                    compressed, info = self.compression_methods[method](audio_bytes, metadata)
                    ratio = len(compressed) / len(audio_bytes)
                    
                    if compressed and ratio < best_ratio:
                        best_method = method
                        best_compressed = compressed
                        best_ratio = ratio
                        best_info = info
                        
                except Exception as e:
                    logger.debug(f"Method {method} failed: {str(e)}")
                    continue
            
            # If no method worked well, use no compression
            if best_ratio > self.adaptive_threshold:
                best_method = 'none'
                best_compressed = audio_bytes
                best_info = {'actual_method': 'none'}
            
            best_info['adaptive_choice'] = best_method
            best_info['adaptive_ratio'] = str(best_ratio)
            
            return best_compressed, best_info
            
        except Exception as e:
            logger.error(f"Error in adaptive compression: {str(e)}")
            return audio_bytes, {'actual_method': 'none', 'error': str(e)}
    
    def estimate_compression_ratio(self, audio_data: np.ndarray, method: str = 'zlib') -> float:
        """Estimate compression ratio without actually compressing"""
        try:
            if len(audio_data) == 0:
                return 1.0
            
            # Quick estimation based on audio characteristics
            if method == 'delta':
                # Delta compression works well with smooth signals
                if len(audio_data) > 1:
                    deltas = np.diff(audio_data)
                    delta_variance = np.var(deltas)
                    signal_variance = np.var(audio_data)
                    
                    if signal_variance > 0:
                        smoothness_ratio = delta_variance / signal_variance
                        # Smoother signals compress better with delta
                        estimated_ratio = 0.3 + (smoothness_ratio * 0.6)
                    else:
                        estimated_ratio = 0.5
                else:
                    estimated_ratio = 0.5
            
            elif method in ['zlib', 'gzip']:
                # General purpose compression - estimate based on entropy
                # Calculate rough entropy estimate
                unique_values = len(np.unique(audio_data.astype(np.int16)))
                max_possible_values = 65536  # int16 range
                
                if unique_values > 0:
                    entropy_ratio = unique_values / max_possible_values
                    # Higher entropy (more unique values) = worse compression
                    estimated_ratio = 0.4 + (entropy_ratio * 0.5)
                else:
                    estimated_ratio = 0.2  # Very compressible
            
            else:
                estimated_ratio = 1.0  # No compression
            
            return float(min(1.0, max(0.1, estimated_ratio)))
            
        except Exception as e:
            logger.error(f"Error estimating compression ratio: {str(e)}")
            return 0.7  # Conservative estimate
    
    def get_compression_stats(self) -> Dict[str, Any]:
        """Get compression statistics and performance info"""
        return {
            'available_methods': list(self.compression_methods.keys()),
            'default_method': 'adaptive',
            'zlib_level': self.zlib_level,
            'delta_enabled': self.delta_enabled,
            'adaptive_threshold': self.adaptive_threshold
        }
