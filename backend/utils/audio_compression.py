#!/usr/bin/env python3
"""
TrueTone Audio Compression Utilities
Handles lossless audio compression for efficient transmission
"""

import logging
import struct
import zlib
import lz4.frame
from typing import Tuple, Optional, Union
import numpy as np
import soundfile as sf
from io import BytesIO

logger = logging.getLogger(__name__)

class AudioCompressionUtils:
    """Advanced audio compression utilities with multiple algorithms"""
    
    def __init__(self):
        self.compression_level = 6  # 1-9 for zlib
        self.min_size_threshold = 512  # Don't compress smaller chunks
        self.preferred_algorithm = 'lz4'  # 'lz4', 'zlib', 'flac'
        self.fallback_algorithm = 'zlib'
        
    def compress_audio_data(self, audio_data: bytes, algorithm: Optional[str] = None) -> Tuple[bytes, float, bool, str]:
        """
        Compress audio data using specified algorithm
        Returns: (compressed_data, compression_ratio, was_compressed, algorithm_used)
        """
        if len(audio_data) < self.min_size_threshold:
            return audio_data, 1.0, False, 'none'
        
        algorithm = algorithm or self.preferred_algorithm
        
        try:
            if algorithm == 'lz4':
                return self._compress_lz4(audio_data)
            elif algorithm == 'zlib':
                return self._compress_zlib(audio_data)
            elif algorithm == 'flac':
                return self._compress_flac(audio_data)
            else:
                logger.warning(f"Unknown compression algorithm: {algorithm}, using fallback")
                return self._compress_zlib(audio_data)
                
        except Exception as e:
            logger.warning(f"Compression with {algorithm} failed: {e}, trying fallback")
            try:
                return self._compress_zlib(audio_data)
            except Exception as fallback_error:
                logger.error(f"Fallback compression failed: {fallback_error}")
                return audio_data, 1.0, False, 'none'
    
    def _compress_lz4(self, audio_data: bytes) -> Tuple[bytes, float, bool, str]:
        """Compress using LZ4 (fast compression)"""
        compressed = lz4.frame.compress(audio_data, compression_level=4)
        compression_ratio = len(compressed) / len(audio_data)
        
        if compression_ratio < 0.9:  # At least 10% reduction for LZ4
            # Prepend original size and algorithm marker
            header = struct.pack('!BI', 1, len(audio_data))  # 1 = LZ4
            return header + compressed, compression_ratio, True, 'lz4'
        else:
            return audio_data, 1.0, False, 'none'
    
    def _compress_zlib(self, audio_data: bytes) -> Tuple[bytes, float, bool, str]:
        """Compress using zlib (balanced compression)"""
        compressed = zlib.compress(audio_data, level=self.compression_level)
        compression_ratio = len(compressed) / len(audio_data)
        
        if compression_ratio < 0.8:  # At least 20% reduction for zlib
            header = struct.pack('!BI', 2, len(audio_data))  # 2 = zlib
            return header + compressed, compression_ratio, True, 'zlib'
        else:
            return audio_data, 1.0, False, 'none'
    
    def _compress_flac(self, audio_data: bytes) -> Tuple[bytes, float, bool, str]:
        """Compress using FLAC (lossless audio compression)"""
        try:
            # Assume audio_data is float32 PCM data
            # Convert bytes to numpy array
            audio_array = np.frombuffer(audio_data, dtype=np.float32)
            
            # Write to FLAC in memory
            output_buffer = BytesIO()
            sf.write(output_buffer, audio_array, 16000, format='FLAC', subtype='PCM_16')
            compressed = output_buffer.getvalue()
            
            compression_ratio = len(compressed) / len(audio_data)
            
            if compression_ratio < 0.7:  # At least 30% reduction for FLAC
                header = struct.pack('!BI', 3, len(audio_data))  # 3 = FLAC
                return header + compressed, compression_ratio, True, 'flac'
            else:
                return audio_data, 1.0, False, 'none'
                
        except Exception as e:
            logger.warning(f"FLAC compression failed: {e}")
            return audio_data, 1.0, False, 'none'
    
    def decompress_audio_data(self, compressed_data: bytes) -> Tuple[bytes, bool]:
        """
        Decompress audio data, auto-detecting compression algorithm
        Returns: (decompressed_data, was_compressed)
        """
        if len(compressed_data) < 5:  # Too small to have compression header
            return compressed_data, False
        
        try:
            # Read algorithm marker and original size
            algorithm_id, original_size = struct.unpack('!BI', compressed_data[:5])
            compressed_payload = compressed_data[5:]
            
            if algorithm_id == 1:  # LZ4
                return self._decompress_lz4(compressed_payload, original_size)
            elif algorithm_id == 2:  # zlib
                return self._decompress_zlib(compressed_payload, original_size)
            elif algorithm_id == 3:  # FLAC
                return self._decompress_flac(compressed_payload, original_size)
            else:
                logger.warning(f"Unknown compression algorithm ID: {algorithm_id}")
                return compressed_data, False
                
        except Exception as e:
            logger.error(f"Decompression failed: {e}")
            return compressed_data, False
    
    def _decompress_lz4(self, compressed_data: bytes, original_size: int) -> Tuple[bytes, bool]:
        """Decompress LZ4 data"""
        try:
            decompressed = lz4.frame.decompress(compressed_data)
            if len(decompressed) == original_size:
                return decompressed, True
            else:
                logger.warning(f"LZ4 decompression size mismatch: {len(decompressed)} != {original_size}")
                return compressed_data, False
        except Exception as e:
            logger.error(f"LZ4 decompression failed: {e}")
            return compressed_data, False
    
    def _decompress_zlib(self, compressed_data: bytes, original_size: int) -> Tuple[bytes, bool]:
        """Decompress zlib data"""
        try:
            decompressed = zlib.decompress(compressed_data)
            if len(decompressed) == original_size:
                return decompressed, True
            else:
                logger.warning(f"zlib decompression size mismatch: {len(decompressed)} != {original_size}")
                return compressed_data, False
        except Exception as e:
            logger.error(f"zlib decompression failed: {e}")
            return compressed_data, False
    
    def _decompress_flac(self, compressed_data: bytes, original_size: int) -> Tuple[bytes, bool]:
        """Decompress FLAC data"""
        try:
            # Read FLAC from memory
            input_buffer = BytesIO(compressed_data)
            audio_array, sample_rate = sf.read(input_buffer, dtype='float32')
            
            # Convert back to bytes
            decompressed = audio_array.tobytes()
            
            if len(decompressed) == original_size:
                return decompressed, True
            else:
                logger.warning(f"FLAC decompression size mismatch: {len(decompressed)} != {original_size}")
                return compressed_data, False
                
        except Exception as e:
            logger.error(f"FLAC decompression failed: {e}")
            return compressed_data, False
    
    def adapt_compression_settings(self, network_speed: float, latency: float, cpu_usage: float):
        """Adapt compression settings based on network and system conditions"""
        # Choose algorithm based on conditions
        if cpu_usage > 80:  # High CPU usage
            self.preferred_algorithm = 'lz4'  # Fastest
        elif network_speed < 1.0:  # Slow network
            if cpu_usage < 50:  # Have CPU headroom
                self.preferred_algorithm = 'flac'  # Best compression
            else:
                self.preferred_algorithm = 'zlib'  # Balanced
        elif latency > 300:  # High latency
            self.preferred_algorithm = 'lz4'  # Minimize processing time
        else:
            self.preferred_algorithm = 'zlib'  # Default balanced
        
        # Adjust compression levels
        if self.preferred_algorithm == 'zlib':
            if network_speed < 2.0:
                self.compression_level = 9  # Maximum compression
            elif network_speed > 10.0:
                self.compression_level = 3  # Faster compression
            else:
                self.compression_level = 6  # Default
        
        logger.info(f"Adapted compression: algorithm={self.preferred_algorithm}, level={self.compression_level}")
    
    def get_compression_stats(self) -> dict:
        """Get compression algorithm capabilities and current settings"""
        return {
            'preferred_algorithm': self.preferred_algorithm,
            'fallback_algorithm': self.fallback_algorithm,
            'compression_level': self.compression_level,
            'min_size_threshold': self.min_size_threshold,
            'supported_algorithms': ['lz4', 'zlib', 'flac'],
            'algorithm_info': {
                'lz4': {'speed': 'fastest', 'compression': 'low', 'cpu': 'minimal'},
                'zlib': {'speed': 'medium', 'compression': 'medium', 'cpu': 'moderate'},
                'flac': {'speed': 'slowest', 'compression': 'highest', 'cpu': 'high'}
            }
        }
        
        try:
            # Extract original size from header
            if len(compressed_data) < 4:
                raise ValueError("Invalid compressed data format")
            
            original_size = struct.unpack('!I', compressed_data[:4])[0]
            compressed_content = compressed_data[4:]
            
            # Decompress
            decompressed = zlib.decompress(compressed_content)
            
            # Verify size
            if len(decompressed) != original_size:
                raise ValueError(f"Decompressed size mismatch: expected {original_size}, got {len(decompressed)}")
            
            return decompressed
            
        except Exception as e:
            logger.error(f"Audio decompression failed: {e}")
            raise
    
    def set_compression_level(self, level: int):
        """Set compression level (1-9)"""
        if 1 <= level <= 9:
            self.compression_level = level
        else:
            logger.warning(f"Invalid compression level {level}, using default")
    
    def estimate_compression_benefit(self, audio_data: bytes) -> float:
        """Estimate compression benefit without actually compressing"""
        if len(audio_data) < self.min_size_threshold:
            return 1.0  # No benefit
        
        # Simple heuristic based on data entropy
        # Higher entropy = less compressible
        try:
            # Count unique bytes
            unique_bytes = len(set(audio_data))
            entropy_estimate = unique_bytes / 256.0
            
            # Estimate compression ratio
            estimated_ratio = 0.3 + (entropy_estimate * 0.6)  # 0.3-0.9 range
            return estimated_ratio
            
        except Exception:
            return 0.8  # Conservative estimate
