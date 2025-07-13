#!/usr/bin/env python3
"""
TrueTone Audio Streaming Service
Handles efficient audio streaming with compression and error recovery
"""

import asyncio
import logging
import time
import json
import struct
import hashlib
from typing import Dict, Optional, List, Callable, Any, Tuple
from dataclasses import dataclass
from collections import deque
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class AudioPacket:
    """Audio packet with metadata"""
    sequence_number: int
    timestamp: float
    data: bytes
    checksum: str
    is_compressed: bool = False
    compression_ratio: float = 1.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'sequence_number': self.sequence_number,
            'timestamp': self.timestamp,
            'data_size': len(self.data),
            'checksum': self.checksum,
            'is_compressed': self.is_compressed,
            'compression_ratio': self.compression_ratio
        }

class AudioCompressor:
    """Handle audio compression for efficient transmission"""
    
    def __init__(self):
        # Import the compression utility
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(__file__)))
        from utils.audio_compression import AudioCompressionUtils
        self.compression_utils = AudioCompressionUtils()
        self.compression_enabled = True
        self.adaptive_compression = True
        
    def compress_audio(self, audio_data: bytes, network_conditions: Dict[str, float] = None) -> Tuple[bytes, float, str]:
        """Compress audio data with adaptive algorithm selection"""
        if not self.compression_enabled or len(audio_data) < 1024:
            return audio_data, 1.0, 'none'
        
        try:
            # Adapt compression settings if network conditions provided
            if network_conditions and self.adaptive_compression:
                self.compression_utils.adapt_compression_settings(
                    network_conditions.get('speed', 5.0),
                    network_conditions.get('latency', 100.0),
                    network_conditions.get('cpu_usage', 50.0)
                )
            
            # Compress audio
            compressed_data, compression_ratio, was_compressed, algorithm = self.compression_utils.compress_audio_data(audio_data)
            
            if was_compressed:
                logger.debug(f"Audio compressed: {len(audio_data)} -> {len(compressed_data)} bytes ({compression_ratio:.2f} ratio, {algorithm})")
                return compressed_data, compression_ratio, algorithm
            else:
                return audio_data, 1.0, 'none'
                
        except Exception as e:
            logger.warning(f"Compression failed: {e}")
            return audio_data, 1.0, 'none'
    
    def decompress_audio(self, compressed_data: bytes) -> bytes:
        """Decompress audio data"""
        try:
            decompressed_data, was_compressed = self.compression_utils.decompress_audio_data(compressed_data)
            if was_compressed:
                logger.debug(f"Audio decompressed: {len(compressed_data)} -> {len(decompressed_data)} bytes")
            return decompressed_data
        except Exception as e:
            logger.error(f"Decompression failed: {e}")
            raise
    
    def get_compression_info(self) -> Dict[str, Any]:
        """Get compression algorithm information"""
        return self.compression_utils.get_compression_stats()
    
    def enable_adaptive_compression(self, enabled: bool = True):
        """Enable or disable adaptive compression"""
        self.adaptive_compression = enabled
        logger.info(f"Adaptive compression {'enabled' if enabled else 'disabled'}")
    
    def set_compression_algorithm(self, algorithm: str):
        """Set preferred compression algorithm"""
        if algorithm in ['lz4', 'zlib', 'flac', 'none']:
            if algorithm == 'none':
                self.compression_enabled = False
            else:
                self.compression_enabled = True
                self.compression_utils.preferred_algorithm = algorithm
            logger.info(f"Compression algorithm set to: {algorithm}")
        else:
            logger.warning(f"Unknown compression algorithm: {algorithm}")
    
    def adapt_compression_level(self, network_speed: float, latency: float):
        """Adapt compression level based on network conditions"""
        
        # Adjust based on latency
        if latency > 200:  # > 200ms
            self.compression_level = min(self.compression_level + 2, 9)

class AudioSynchronizer:
    """Handle audio synchronization with timestamps"""
    
    def __init__(self):
        self.client_server_offset = 0.0
        self.last_sync_time = 0.0
        self.sync_interval = 30.0  # Sync every 30 seconds
        self.max_jitter_buffer = 10  # Max packets to buffer for jitter
        self.jitter_buffer = deque(maxlen=self.max_jitter_buffer)
        
    def sync_clocks(self, client_timestamp: float, server_timestamp: float):
        """Synchronize client and server clocks"""
        self.client_server_offset = server_timestamp - client_timestamp
        self.last_sync_time = time.time()
        logger.info(f"Clock sync: offset = {self.client_server_offset:.3f}s")
    
    def needs_sync(self) -> bool:
        """Check if clock sync is needed"""
        return (time.time() - self.last_sync_time) > self.sync_interval
    
    def adjust_timestamp(self, client_timestamp: float) -> float:
        """Adjust client timestamp to server time"""
        return client_timestamp + self.client_server_offset
    
    def add_to_jitter_buffer(self, packet: AudioPacket):
        """Add packet to jitter buffer for reordering"""
        self.jitter_buffer.append(packet)
        
        # Sort buffer by sequence number
        sorted_buffer = sorted(self.jitter_buffer, key=lambda p: p.sequence_number)
        self.jitter_buffer.clear()
        self.jitter_buffer.extend(sorted_buffer)
    
    def get_next_packet(self) -> Optional[AudioPacket]:
        """Get next packet from jitter buffer"""
        if self.jitter_buffer:
            return self.jitter_buffer.popleft()
        return None
    
    def estimate_jitter(self) -> float:
        """Estimate network jitter"""
        if len(self.jitter_buffer) < 2:
            return 0.0
        
        timestamps = [p.timestamp for p in self.jitter_buffer]
        intervals = [timestamps[i+1] - timestamps[i] for i in range(len(timestamps)-1)]
        
        if intervals:
            mean_interval = sum(intervals) / len(intervals)
            variance = sum((x - mean_interval)**2 for x in intervals) / len(intervals)
            return variance ** 0.5
        
        return 0.0

class PacketManager:
    """Manage audio packet ordering and reconstruction"""
    
    def __init__(self):
        self.expected_sequence = 0
        self.received_packets = {}
        self.missing_packets = set()
        self.max_reorder_window = 10
        self.packet_timeout = 5.0  # 5 seconds
        
    def add_packet(self, packet: AudioPacket) -> List[AudioPacket]:
        """Add packet and return any complete sequences"""
        self.received_packets[packet.sequence_number] = {
            'packet': packet,
            'received_time': time.time()
        }
        
        # Check for missing packets
        if packet.sequence_number > self.expected_sequence:
            for seq in range(self.expected_sequence, packet.sequence_number):
                if seq not in self.received_packets:
                    self.missing_packets.add(seq)
        
        # Return complete sequence
        complete_packets = []
        while self.expected_sequence in self.received_packets:
            packet_info = self.received_packets.pop(self.expected_sequence)
            complete_packets.append(packet_info['packet'])
            self.missing_packets.discard(self.expected_sequence)
            self.expected_sequence += 1
        
        # Clean up old packets
        self._cleanup_old_packets()
        
        return complete_packets
    
    def get_missing_packets(self) -> List[int]:
        """Get list of missing packet sequence numbers"""
        return list(self.missing_packets)
    
    def _cleanup_old_packets(self):
        """Remove packets that have timed out"""
        current_time = time.time()
        expired_sequences = []
        
        for seq, packet_info in self.received_packets.items():
            if current_time - packet_info['received_time'] > self.packet_timeout:
                expired_sequences.append(seq)
        
        for seq in expired_sequences:
            self.received_packets.pop(seq, None)
            self.missing_packets.discard(seq)
    
    def reset(self):
        """Reset packet manager state"""
        self.expected_sequence = 0
        self.received_packets.clear()
        self.missing_packets.clear()

class NetworkMonitor:
    """Monitor network conditions and quality"""
    
    def __init__(self):
        self.packet_loss_rate = 0.0
        self.average_latency = 0.0
        self.bandwidth_estimate = 0.0
        self.quality_score = 1.0  # 0-1, higher is better
        self.connection_stable = True
        
        # Statistics
        self.packets_sent = 0
        self.packets_received = 0
        self.total_bytes_sent = 0
        self.total_bytes_received = 0
        self.latency_samples = deque(maxlen=100)
        
    def record_packet_sent(self, size: int):
        """Record a packet being sent"""
        self.packets_sent += 1
        self.total_bytes_sent += size
    
    def record_packet_received(self, size: int, latency: float):
        """Record a packet being received"""
        self.packets_received += 1
        self.total_bytes_received += size
        self.latency_samples.append(latency)
        
        # Update metrics
        self._update_metrics()
    
    def _update_metrics(self):
        """Update network quality metrics"""
        # Calculate packet loss rate
        if self.packets_sent > 0:
            self.packet_loss_rate = 1.0 - (self.packets_received / self.packets_sent)
        
        # Calculate average latency
        if self.latency_samples:
            self.average_latency = sum(self.latency_samples) / len(self.latency_samples)
        
        # Estimate bandwidth (simplified)
        if self.latency_samples:
            recent_latency = sum(list(self.latency_samples)[-10:]) / min(10, len(self.latency_samples))
            self.bandwidth_estimate = max(1.0, 100.0 / (recent_latency + 1))  # Rough estimate
        
        # Calculate quality score
        latency_score = max(0.0, 1.0 - (self.average_latency / 1000.0))  # 1s = 0 score
        loss_score = max(0.0, 1.0 - (self.packet_loss_rate * 10))  # 10% loss = 0 score
        self.quality_score = (latency_score + loss_score) / 2
        
        # Determine connection stability
        self.connection_stable = (
            self.packet_loss_rate < 0.05 and  # < 5% loss
            self.average_latency < 500 and    # < 500ms latency
            len(self.latency_samples) > 10    # Sufficient samples
        )
    
    def get_network_stats(self) -> Dict[str, Any]:
        """Get comprehensive network statistics"""
        return {
            'packet_loss_rate': self.packet_loss_rate,
            'average_latency': self.average_latency,
            'bandwidth_estimate': self.bandwidth_estimate,
            'quality_score': self.quality_score,
            'connection_stable': self.connection_stable,
            'packets_sent': self.packets_sent,
            'packets_received': self.packets_received,
            'total_bytes_sent': self.total_bytes_sent,
            'total_bytes_received': self.total_bytes_received
        }
    
    def should_adapt_quality(self) -> bool:
        """Check if quality adaptation is needed"""
        return (
            self.packet_loss_rate > 0.02 or  # > 2% loss
            self.average_latency > 300 or    # > 300ms latency
            self.quality_score < 0.7         # Low quality score
        )

class AudioStreamingService:
    """Main audio streaming service"""
    
    def __init__(self):
        self.compressor = AudioCompressor()
        self.synchronizer = AudioSynchronizer()
        self.packet_manager = PacketManager()
        self.network_monitor = NetworkMonitor()
        
        self.sequence_number = 0
        self.chunk_size = 4096  # Default chunk size
        self.adaptive_chunk_sizing = True
        self.max_retry_attempts = 3
        
        # WebSocket connection state
        self.websocket = None
        self.connection_callbacks = []
        self.data_callbacks = []
        self.is_streaming = False
    
    def add_connection_callback(self, callback: Callable):
        """Add callback for connection events"""
        self.connection_callbacks.append(callback)
    
    def add_data_callback(self, callback: Callable):
        """Add callback for data events"""
        self.data_callbacks.append(callback)
    
    def set_websocket(self, websocket):
        """Set the WebSocket connection for streaming"""
        self.websocket = websocket
        logger.info("WebSocket connection set for audio streaming")
    
    def start_streaming(self):
        """Start the audio streaming service"""
        self.is_streaming = True
        logger.info("Audio streaming service started")
    
    def stop_streaming(self):
        """Stop the audio streaming service"""
        self.is_streaming = False
        self.websocket = None
        logger.info("Audio streaming service stopped")
    
    def is_streaming_active(self) -> bool:
        """Check if streaming is currently active"""
        return self.is_streaming and self.websocket is not None
    
    def calculate_optimal_chunk_size(self) -> int:
        """Calculate optimal chunk size based on network conditions"""
        if not self.adaptive_chunk_sizing:
            return self.chunk_size
        
        base_size = 4096
        
        # Adjust based on latency
        if self.network_monitor.average_latency > 200:
            base_size = 8192  # Larger chunks for high latency
        elif self.network_monitor.average_latency < 50:
            base_size = 2048  # Smaller chunks for low latency
        
        # Adjust based on packet loss
        if self.network_monitor.packet_loss_rate > 0.02:
            base_size = min(base_size, 2048)  # Smaller chunks for lossy networks
        
        # Adjust based on bandwidth
        if self.network_monitor.bandwidth_estimate < 1.0:
            base_size = min(base_size, 1024)  # Very small chunks for low bandwidth
        
        return base_size
    
    async def send_audio_chunk(self, audio_data: bytes, metadata: Dict[str, Any]) -> bool:
        """Send audio chunk with compression and error handling"""
        if not self.websocket:
            logger.error("No WebSocket connection available")
            return False
        
        try:
            # Update chunk size if adaptive
            if self.adaptive_chunk_sizing:
                self.chunk_size = self.calculate_optimal_chunk_size()
            
            # Compress if beneficial
            network_conditions = {
                'speed': self.network_monitor.bandwidth_estimate,
                'latency': self.network_monitor.average_latency,
                'cpu_usage': 50.0  # Could be obtained from system monitor
            }
            compressed_data, compression_ratio, algorithm = self.compressor.compress_audio(
                audio_data, network_conditions
            )
            
            # Create packet
            packet = AudioPacket(
                sequence_number=self.sequence_number,
                timestamp=time.time(),
                data=compressed_data,
                checksum=hashlib.md5(compressed_data).hexdigest(),
                is_compressed=algorithm != 'none',
                compression_ratio=compression_ratio
            )
            
            # Send packet
            packet_data = {
                'type': 'audio_packet',
                'packet': packet.to_dict(),
                'metadata': metadata,
                'algorithm': algorithm
            }
            
            await self.websocket.send(json.dumps(packet_data))
            
            # Update statistics
            self.network_monitor.record_packet_sent(len(compressed_data))
            self.sequence_number += 1
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send audio chunk: {e}")
            await self._handle_send_error(e)
            return False
    
    async def receive_audio_packet(self, packet_data: Dict[str, Any]) -> Optional[bytes]:
        """Receive and process audio packet"""
        try:
            # Create packet from data
            packet_info = packet_data['packet']
            packet = AudioPacket(
                sequence_number=packet_info['sequence_number'],
                timestamp=packet_info['timestamp'],
                data=b'',  # Will be received separately
                checksum=packet_info['checksum'],
                is_compressed=packet_info['is_compressed'],
                compression_ratio=packet_info['compression_ratio']
            )
            
            # Add to packet manager
            complete_packets = self.packet_manager.add_packet(packet)
            
            # Process complete packets
            if complete_packets:
                processed_data = b''
                for pkt in complete_packets:
                    if pkt.is_compressed:
                        audio_data = self.compressor.decompress_audio(pkt.data)
                    else:
                        audio_data = pkt.data
                    
                    processed_data += audio_data
                
                return processed_data
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to receive audio packet: {e}")
            return None
    
    async def handle_connection_loss(self):
        """Handle WebSocket connection loss with retry logic"""
        retry_count = 0
        
        while retry_count < self.max_retry_attempts:
            try:
                # Wait with exponential backoff
                wait_time = min(2 ** retry_count, 30)
                await asyncio.sleep(wait_time)
                
                # Attempt reconnection
                await self._reconnect_websocket()
                
                # Notify callbacks
                await self._notify_connection_callbacks('reconnected', {
                    'retry_count': retry_count,
                    'wait_time': wait_time
                })
                
                return True
                
            except Exception as e:
                retry_count += 1
                logger.warning(f"Reconnection attempt {retry_count} failed: {e}")
        
        # Max retries reached
        await self._notify_connection_callbacks('max_retries_reached', {
            'retry_count': retry_count
        })
        return False
    
    async def _reconnect_websocket(self):
        """Reconnect WebSocket connection"""
        # Reset state
        self.packet_manager.reset()
        self.sequence_number = 0
        
        # This would be implemented based on the specific WebSocket client
        # For now, just a placeholder
        logger.info("Attempting WebSocket reconnection...")
    
    async def _handle_send_error(self, error: Exception):
        """Handle send error with appropriate recovery"""
        if "connection" in str(error).lower():
            await self.handle_connection_loss()
        else:
            logger.error(f"Send error: {error}")
    
    async def _notify_connection_callbacks(self, event_type: str, data: Dict[str, Any]):
        """Notify connection callbacks"""
        for callback in self.connection_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_type, data)
                else:
                    callback(event_type, data)
            except Exception as e:
                logger.error(f"Connection callback error: {e}")
    
    async def _notify_data_callbacks(self, event_type: str, data: bytes):
        """Notify data callbacks"""
        for callback in self.data_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event_type, data)
                else:
                    callback(event_type, data)
            except Exception as e:
                logger.error(f"Data callback error: {e}")
    
    def get_streaming_stats(self) -> Dict[str, Any]:
        """Get comprehensive streaming statistics"""
        stats = self.network_monitor.get_network_stats()
        compression_info = self.compressor.get_compression_info()
        
        stats.update({
            'current_chunk_size': self.chunk_size,
            'sequence_number': self.sequence_number,
            'compression_info': compression_info,
            'sync_offset': self.synchronizer.client_server_offset,
            'jitter_estimate': self.synchronizer.estimate_jitter(),
            'missing_packets': len(self.packet_manager.get_missing_packets())
        })
        return stats
    
    def adapt_to_network_conditions(self):
        """Adapt streaming parameters to current network conditions"""
        if self.network_monitor.should_adapt_quality():
            # Reduce chunk size for poor network conditions
            if self.network_monitor.packet_loss_rate > 0.05:
                self.chunk_size = max(1024, self.chunk_size // 2)
            
            # Adapt compression based on conditions
            self.compressor.adapt_compression_level(
                self.network_monitor.bandwidth_estimate,
                self.network_monitor.average_latency
            )
            
            logger.info(f"Adapted to network conditions: "
                       f"chunk_size={self.chunk_size}, "
                       f"compression_algorithm={self.compressor.compression_utils.preferred_algorithm}")
