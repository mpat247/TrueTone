"""
Audio Streaming Service
Handles WebSocket audio streaming and network optimization for TrueTone.
"""

import asyncio
import json
import logging
import time
import zlib
from typing import Dict, Any, Optional, List, Callable
import numpy as np
from io import BytesIO

logger = logging.getLogger(__name__)


class AudioStreamingService:
    """Service for handling audio streaming over WebSocket connections"""
    
    def __init__(self, audio_processor):
        self.audio_processor = audio_processor
        self.connections = {}
        self.compression_enabled = True
        self.compression_level = 6  # zlib compression level (1-9)
        
        # Network monitoring
        self.network_stats = {
            'total_bytes_sent': 0,
            'total_bytes_received': 0,
            'total_messages_sent': 0,
            'total_messages_received': 0,
            'average_latency': 0.0,
            'packet_loss_rate': 0.0
        }
        
        # Adaptive streaming parameters
        self.adaptive_config = {
            'chunk_size_base': 4096,
            'chunk_size_min': 1024,
            'chunk_size_max': 8192,
            'latency_threshold_high': 300,  # ms
            'latency_threshold_low': 100,   # ms
            'packet_loss_threshold': 0.05   # 5%
        }
        
        logger.info("AudioStreamingService initialized")
    
    def register_connection(self, client_id: str, websocket, config: Dict[str, Any]) -> str:
        """Register a new WebSocket connection"""
        connection_info = {
            'websocket': websocket,
            'client_id': client_id,
            'connected_at': time.time(),
            'config': config,
            'last_ping': time.time(),
            'latency_history': [],
            'sent_messages': 0,
            'received_messages': 0,
            'bytes_sent': 0,
            'bytes_received': 0,
            'packet_loss_count': 0,
            'current_chunk_size': self.adaptive_config['chunk_size_base'],
            'sequence_number': 0,
            'pending_acks': {}  # Track messages waiting for acknowledgment
        }
        
        self.connections[client_id] = connection_info
        logger.info(f"Registered streaming connection for client {client_id}")
        
        return client_id
    
    def unregister_connection(self, client_id: str):
        """Unregister a WebSocket connection"""
        if client_id in self.connections:
            del self.connections[client_id]
            logger.info(f"Unregistered streaming connection for client {client_id}")
    
    async def send_audio_chunk(self, client_id: str, audio_data: np.ndarray, 
                              metadata: Dict[str, Any]) -> bool:
        """Send an audio chunk to a client with optimizations"""
        if client_id not in self.connections:
            logger.error(f"Client {client_id} not found in connections")
            return False
        
        connection = self.connections[client_id]
        websocket = connection['websocket']
        
        try:
            # Prepare audio data for transmission
            processed_data = await self._prepare_audio_for_transmission(
                audio_data, connection['config']
            )
            
            # Create message with metadata
            message = {
                'type': 'audio',
                'sequence': connection['sequence_number'],
                'timestamp': time.time() * 1000,
                'metadata': metadata,
                'compression': self.compression_enabled,
                'chunk_size': len(processed_data)
            }
            
            # Send metadata first
            await websocket.send_text(json.dumps(message))
            
            # Compress data if enabled
            if self.compression_enabled:
                compressed_data = zlib.compress(processed_data, self.compression_level)
                await websocket.send_bytes(compressed_data)
                
                # Update compression stats
                compression_ratio = len(compressed_data) / len(processed_data)
                logger.debug(f"Compression ratio: {compression_ratio:.2f}")
            else:
                await websocket.send_bytes(processed_data)
            
            # Update connection stats
            connection['sent_messages'] += 1
            connection['bytes_sent'] += len(processed_data)
            connection['sequence_number'] += 1
            connection['pending_acks'][message['sequence']] = time.time()
            
            # Update global stats
            self.network_stats['total_messages_sent'] += 1
            self.network_stats['total_bytes_sent'] += len(processed_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending audio chunk to client {client_id}: {str(e)}")
            return False
    
    async def handle_acknowledgment(self, client_id: str, ack_data: Dict[str, Any]):
        """Handle acknowledgment from client"""
        if client_id not in self.connections:
            return
        
        connection = self.connections[client_id]
        sequence = ack_data.get('sequence')
        
        if sequence in connection['pending_acks']:
            # Calculate latency
            sent_time = connection['pending_acks'][sequence]
            latency = (time.time() - sent_time) * 1000  # Convert to ms
            
            # Update latency history
            connection['latency_history'].append(latency)
            if len(connection['latency_history']) > 50:  # Keep last 50 measurements
                connection['latency_history'].pop(0)
            
            # Remove from pending acks
            del connection['pending_acks'][sequence]
            
            # Update average latency
            avg_latency = sum(connection['latency_history']) / len(connection['latency_history'])
            self.network_stats['average_latency'] = avg_latency
            
            # Adaptive chunk size adjustment
            await self._adjust_chunk_size(client_id, latency)
            
            logger.debug(f"Received ACK for sequence {sequence}, latency: {latency:.1f}ms")
    
    async def _adjust_chunk_size(self, client_id: str, latency: float):
        """Adjust chunk size based on network conditions"""
        connection = self.connections[client_id]
        current_size = connection['current_chunk_size']
        
        if latency > self.adaptive_config['latency_threshold_high']:
            # High latency - reduce chunk size
            new_size = max(
                self.adaptive_config['chunk_size_min'],
                int(current_size * 0.8)
            )
        elif latency < self.adaptive_config['latency_threshold_low']:
            # Low latency - increase chunk size for efficiency
            new_size = min(
                self.adaptive_config['chunk_size_max'],
                int(current_size * 1.2)
            )
        else:
            # Latency is acceptable - no change
            return
        
        if new_size != current_size:
            connection['current_chunk_size'] = new_size
            logger.info(f"Adjusted chunk size for client {client_id}: {current_size} -> {new_size}")
    
    async def _prepare_audio_for_transmission(self, audio_data: np.ndarray, 
                                            config: Dict[str, Any]) -> bytes:
        """Prepare audio data for network transmission"""
        # Ensure audio is in the correct format
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)
        
        # Apply any necessary preprocessing
        processed_audio = await self._apply_transmission_preprocessing(audio_data, config)
        
        # Convert to bytes
        return processed_audio.tobytes()
    
    async def _apply_transmission_preprocessing(self, audio_data: np.ndarray, 
                                             config: Dict[str, Any]) -> np.ndarray:
        """Apply preprocessing optimized for transmission"""
        # Normalize audio to prevent clipping
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            audio_data = audio_data / max_val * 0.95
        
        # Apply light compression/limiting if needed
        # This could include dynamic range compression for better transmission
        compressed_audio = self._apply_dynamic_range_compression(audio_data)
        
        return compressed_audio
    
    def _apply_dynamic_range_compression(self, audio_data: np.ndarray, 
                                       threshold: float = 0.7, ratio: float = 4.0) -> np.ndarray:
        """Apply dynamic range compression to improve transmission quality"""
        # Simple compressor implementation
        compressed = audio_data.copy()
        
        # Find samples above threshold
        above_threshold = np.abs(compressed) > threshold
        
        # Apply compression to samples above threshold
        if np.any(above_threshold):
            # Calculate compression amount
            excess = np.abs(compressed[above_threshold]) - threshold
            compressed_excess = excess / ratio
            
            # Apply compression while preserving sign
            compressed[above_threshold] = np.sign(compressed[above_threshold]) * (threshold + compressed_excess)
        
        return compressed
    
    async def handle_incoming_audio(self, client_id: str, audio_data: bytes, 
                                  metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming audio data from client"""
        if client_id not in self.connections:
            return {'status': 'error', 'message': 'Client not found'}
        
        connection = self.connections[client_id]
        
        try:
            # Decompress if needed
            if metadata.get('compression', False):
                audio_data = zlib.decompress(audio_data)
            
            # Convert to numpy array
            audio_np = np.frombuffer(audio_data, dtype=np.float32)
            
            # Validate audio data
            if len(audio_np) == 0:
                raise ValueError("Empty audio data received")
            
            # Update connection stats
            connection['received_messages'] += 1
            connection['bytes_received'] += len(audio_data)
            
            # Update global stats
            self.network_stats['total_messages_received'] += 1
            self.network_stats['total_bytes_received'] += len(audio_data)
            
            # Send acknowledgment
            await self._send_acknowledgment(client_id, metadata)
            
            return {
                'status': 'success',
                'audio_data': audio_np,
                'metadata': metadata,
                'connection_stats': {
                    'latency': connection['latency_history'][-1] if connection['latency_history'] else 0,
                    'chunk_size': connection['current_chunk_size']
                }
            }
            
        except Exception as e:
            logger.error(f"Error handling incoming audio from client {client_id}: {str(e)}")
            return {'status': 'error', 'message': str(e)}
    
    async def _send_acknowledgment(self, client_id: str, metadata: Dict[str, Any]):
        """Send acknowledgment for received audio"""
        if client_id not in self.connections:
            return
        
        connection = self.connections[client_id]
        websocket = connection['websocket']
        
        try:
            ack_message = {
                'type': 'ack',
                'sequence': metadata.get('sequence', 0),
                'timestamp': metadata.get('timestamp', time.time() * 1000),
                'received_at': time.time() * 1000
            }
            
            await websocket.send_text(json.dumps(ack_message))
            
        except Exception as e:
            logger.error(f"Error sending acknowledgment to client {client_id}: {str(e)}")
    
    def get_connection_stats(self, client_id: str) -> Optional[Dict[str, Any]]:
        """Get statistics for a specific connection"""
        if client_id not in self.connections:
            return None
        
        connection = self.connections[client_id]
        
        return {
            'client_id': client_id,
            'connected_at': connection['connected_at'],
            'uptime': time.time() - connection['connected_at'],
            'messages_sent': connection['sent_messages'],
            'messages_received': connection['received_messages'],
            'bytes_sent': connection['bytes_sent'],
            'bytes_received': connection['bytes_received'],
            'current_chunk_size': connection['current_chunk_size'],
            'average_latency': sum(connection['latency_history']) / len(connection['latency_history']) if connection['latency_history'] else 0,
            'pending_acks': len(connection['pending_acks']),
            'packet_loss_rate': connection['packet_loss_count'] / max(connection['sent_messages'], 1)
        }
    
    def get_global_stats(self) -> Dict[str, Any]:
        """Get global streaming statistics"""
        return {
            'network_stats': self.network_stats,
            'total_connections': len(self.connections),
            'active_connections': list(self.connections.keys()),
            'adaptive_config': self.adaptive_config,
            'compression_enabled': self.compression_enabled
        }
    
    async def optimize_streaming_parameters(self):
        """Continuously optimize streaming parameters based on network conditions"""
        while True:
            try:
                # Calculate global packet loss rate
                total_sent = self.network_stats['total_messages_sent']
                total_lost = sum(conn['packet_loss_count'] for conn in self.connections.values())
                
                if total_sent > 0:
                    global_loss_rate = total_lost / total_sent
                    self.network_stats['packet_loss_rate'] = global_loss_rate
                    
                    # Adjust compression if packet loss is high
                    if global_loss_rate > self.adaptive_config['packet_loss_threshold']:
                        if not self.compression_enabled:
                            self.compression_enabled = True
                            logger.info("Enabled compression due to high packet loss")
                    else:
                        if self.compression_enabled and global_loss_rate < 0.01:
                            # Disable compression if packet loss is very low
                            self.compression_enabled = False
                            logger.info("Disabled compression due to low packet loss")
                
                # Clean up old pending acknowledgments (timeout after 5 seconds)
                current_time = time.time()
                for connection in self.connections.values():
                    expired_acks = [
                        seq for seq, sent_time in connection['pending_acks'].items()
                        if current_time - sent_time > 5.0
                    ]
                    
                    for seq in expired_acks:
                        del connection['pending_acks'][seq]
                        connection['packet_loss_count'] += 1
                
                await asyncio.sleep(10)  # Run optimization every 10 seconds
                
            except Exception as e:
                logger.error(f"Error in streaming optimization: {str(e)}")
                await asyncio.sleep(10)
