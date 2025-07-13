#!/usr/bin/env python3
"""
TrueTone Backend - FastAPI Server
Main entry point for the TrueTone voice-preserving translation service.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import json
import logging
from typing import Dict, Any, List, Optional
import asyncio
import base64
import time

# Import our audio services
from services.audio_capture import AudioCaptureService
from services.audio_streaming import AudioStreamingService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import services
from services.audio_capture import AudioCaptureService
from services.audio_streaming import AudioStreamingService
from services.audio_pipeline import AudioPipelineService
from utils.audio_processing import AudioProcessor
from models.audio_metadata import AudioMetadata, AudioFormat, AudioChunk

# Create FastAPI app
app = FastAPI(
    title="TrueTone API",
    description="Voice-preserving YouTube translation backend with real-time audio streaming",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active WebSocket connections and their services
active_connections: Dict[str, Dict[str, Any]] = {}

@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "message": "TrueTone API is running",
        "version": "1.0.0",
        "features": [
            "Real-time audio capture from YouTube",
            "Efficient audio streaming with compression",
            "Adaptive quality management",
            "Network condition monitoring",
            "Audio format conversion and optimization"
        ],
        "endpoints": {
            "health": "/health",
            "websocket": "/ws",
            "status": "/status",
            "connection_stats": "/stats/{connection_id}"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for the Chrome extension"""
    return {
        "status": "healthy",
        "service": "TrueTone Backend",
        "version": "1.0.0",
        "timestamp": time.time(),
        "active_connections": len(active_connections),
        "services_status": {
            "audio_capture": "ready",
            "audio_streaming": "ready",
            "compression": "ready"
        }
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Enhanced WebSocket endpoint for real-time audio streaming"""
    await websocket.accept()
    connection_id = f"conn_{len(active_connections)}_{int(time.time())}"
    
    # Initialize services for this connection
    audio_capture = AudioCaptureService()
    audio_streaming = AudioStreamingService()
    
    # Store connection and services
    active_connections[connection_id] = {
        'websocket': websocket,
        'audio_capture': audio_capture,
        'audio_streaming': audio_streaming,
        'connected_at': time.time(),
        'last_activity': time.time()
    }
    
    logger.info(f"New WebSocket connection: {connection_id}")
    
    # Initialize session variables
    session_id = None
    audio_metadata = None
    
    try:
        # Send welcome message with connection info
        await websocket.send_text(json.dumps({
            "type": "connection_established",
            "message": "Connected to TrueTone backend",
            "connection_id": connection_id,
            "server_time": time.time(),
            "features": {
                "audio_capture": True,
                "audio_streaming": True,
                "compression": True,
                "quality_monitoring": True,
                "adaptive_buffering": True
            }
        }))
        
        # Set up streaming service with WebSocket
        audio_streaming.set_websocket(websocket)
        
        while True:
            # Receive data from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            # Update last activity
            active_connections[connection_id]['last_activity'] = time.time()
            
            message_type = message.get('type')
            logger.debug(f"[{connection_id}] Received message type: {message_type}")
            
            if message_type == "audio_chunk":
                await handle_audio_chunk(websocket, message, audio_capture, audio_streaming)
            elif message_type == "audio_config":
                await handle_audio_config(websocket, message, audio_capture)
            elif message_type == "stream_control":
                await handle_stream_control(websocket, message, audio_capture, audio_streaming)
            elif message_type == "quality_check":
                await handle_quality_check(websocket, message, audio_capture)
            elif message_type == "sync_request":
                await handle_sync_request(websocket, message, audio_streaming)
            elif message_type == "stats_request":
                await handle_stats_request(websocket, message, audio_capture, audio_streaming)
            else:
                # Echo back unknown messages for debugging
                await websocket.send_text(json.dumps({
                    "type": "echo",
                    "original": message,
                    "server_time": time.time()
                }))
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
        await cleanup_connection(connection_id)
    except Exception as e:
        logger.error(f"WebSocket error [{connection_id}]: {e}")
        await cleanup_connection(connection_id)

async def cleanup_connection(connection_id: str):
    """Clean up connection and associated services"""
    if connection_id in active_connections:
        try:
            connection_info = active_connections[connection_id]
            audio_capture = connection_info['audio_capture']
            audio_streaming = connection_info['audio_streaming']
            
            # Stop services
            await audio_capture.stop_capture()
            audio_streaming.stop_streaming()
            
            # Remove connection
            del active_connections[connection_id]
            logger.info(f"Cleaned up connection: {connection_id}")
            
        except Exception as e:
            logger.error(f"Error cleaning up connection {connection_id}: {e}")

async def handle_audio_chunk(websocket: WebSocket, message: Dict[str, Any], 
                           audio_capture: AudioCaptureService, 
                           audio_streaming: AudioStreamingService):
    """Handle incoming audio chunk from client"""
    try:
        # Extract audio data
        audio_data_b64 = message.get("data", "")
        if not audio_data_b64:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": "No audio data provided"
            }))
            return
        
        # Decode base64 audio data
        try:
            audio_data = base64.b64decode(audio_data_b64)
        except Exception as e:
            await websocket.send_text(json.dumps({
                "type": "error",
                "message": f"Invalid audio data encoding: {str(e)}"
            }))
            return
        
        # Extract metadata
        metadata = {
            'sample_rate': message.get('sampleRate', 16000),
            'channels': message.get('channels', 1),
            'timestamp': message.get('timestamp', time.time()),
            'sequence': message.get('sequence', 0),
            'chunk_size': len(audio_data)
        }
        
        # Process through audio capture service
        success = await audio_capture.process_audio_chunk(audio_data, metadata)
        
        if success:
            # Get buffer statistics
            buffer_stats = audio_capture.get_buffer_stats()
            
            # Convert numpy types to Python types for JSON serialization
            def convert_numpy_types(obj):
                if isinstance(obj, dict):
                    return {k: convert_numpy_types(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [convert_numpy_types(v) for v in obj]
                elif hasattr(obj, 'item'):  # numpy scalar
                    return obj.item()
                elif hasattr(obj, 'tolist'):  # numpy array
                    return obj.tolist()
                else:
                    return obj
            
            buffer_stats = convert_numpy_types(buffer_stats)
            
            # Send acknowledgment with buffer status
            await websocket.send_text(json.dumps({
                "type": "audio_chunk_processed",
                "status": "success",
                "sequence": metadata['sequence'],
                "buffer_stats": buffer_stats,
                "server_time": time.time()
            }))
        else:
            await websocket.send_text(json.dumps({
                "type": "audio_chunk_processed",
                "status": "failed",
                "sequence": metadata['sequence'],
                "message": "Failed to process audio chunk"
            }))
            
    except Exception as e:
        logger.error(f"Error handling audio chunk: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Audio chunk processing error: {str(e)}"
        }))

async def handle_audio_config(websocket: WebSocket, message: Dict[str, Any], 
                            audio_capture: AudioCaptureService):
    """Handle audio configuration updates"""
    try:
        config = message.get("config", {})
        
        # Start or reconfigure audio capture
        if config.get("action") == "start":
            success = await audio_capture.start_capture(config)
            status = "started" if success else "failed"
        elif config.get("action") == "stop":
            await audio_capture.stop_capture()
            status = "stopped"
        else:
            status = "configured"
        
        response = {
            "type": "audio_config_response",
            "status": status,
            "config": config,
            "server_time": time.time()
        }
        
        await websocket.send_text(json.dumps(response))
        logger.info(f"Stopped session {session_id}")
        
    except Exception as e:
        logger.error(f"Error handling audio config: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Audio config error: {str(e)}"
        }))

async def handle_stream_control(websocket: WebSocket, message: Dict[str, Any],
                              audio_capture: AudioCaptureService,
                              audio_streaming: AudioStreamingService):
    """Handle stream control commands"""
    try:
        command = message.get("command", "")
        
        if command == "start_streaming":
            audio_streaming.start_streaming()
            status = "streaming_started"
        elif command == "stop_streaming":
            audio_streaming.stop_streaming()
            status = "streaming_stopped"
        elif command == "pause_streaming":
            # Could implement pause functionality
            status = "streaming_paused"
        elif command == "resume_streaming":
            # Could implement resume functionality
            status = "streaming_resumed"
        else:
            status = "unknown_command"
        
        await websocket.send_text(json.dumps({
            "type": "stream_control_response",
            "command": command,
            "status": status,
            "server_time": time.time()
        }))
        
    except Exception as e:
        logger.error(f"Error handling stream control: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Stream control error: {str(e)}"
        }))

async def handle_quality_check(websocket: WebSocket, message: Dict[str, Any],
                             audio_capture: AudioCaptureService):
    """Handle audio quality check requests"""
    try:
        # Get current quality metrics and recommendations
        quality_info = audio_capture.quality_monitor.get_recommendations()
        buffer_stats = audio_capture.get_buffer_stats()
        
        response = {
            "type": "quality_check_response",
            "quality_metrics": quality_info.get('metrics', {}),
            "recommendations": quality_info.get('recommendations', []),
            "buffer_stats": buffer_stats,
            "server_time": time.time()
        }
        
        await websocket.send_text(json.dumps(response))
        
    except Exception as e:
        logger.error(f"Error handling quality check: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Quality check error: {str(e)}"
        }))

async def handle_sync_request(websocket: WebSocket, message: Dict[str, Any],
                            audio_streaming: AudioStreamingService):
    """Handle clock synchronization requests"""
    try:
        client_timestamp = message.get("client_time", time.time())
        server_timestamp = time.time()
        
        # Update synchronizer
        audio_streaming.synchronizer.sync_clocks(client_timestamp, server_timestamp)
        
        response = {
            "type": "sync_response",
            "client_time": client_timestamp,
            "server_time": server_timestamp,
            "offset": audio_streaming.synchronizer.client_server_offset,
            "jitter_estimate": audio_streaming.synchronizer.estimate_jitter()
        }
        
        await websocket.send_text(json.dumps(response))
        logger.info(f"Updated config for session {session_id}")
        
    except Exception as e:
        logger.error(f"Error handling sync request: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Sync request error: {str(e)}"
        }))

async def handle_stats_request(websocket: WebSocket, message: Dict[str, Any],
                             audio_capture: AudioCaptureService,
                             audio_streaming: AudioStreamingService):
    """Handle statistics requests"""
    try:
        stats_type = message.get("stats_type", "all")
        
        response = {
            "type": "stats_response",
            "stats_type": stats_type,
            "server_time": time.time()
        }
        
        if stats_type in ["all", "capture"]:
            response["capture_stats"] = audio_capture.get_buffer_stats()
        
        if stats_type in ["all", "streaming"]:
            response["streaming_stats"] = audio_streaming.get_streaming_stats()
        
        if stats_type in ["all", "system"]:
            import psutil
            response["system_stats"] = {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "connections": len(active_connections)
            }
        
        await websocket.send_text(json.dumps(response))
        
    except Exception as e:
        logger.error(f"Error handling stats request: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Stats request error: {str(e)}"
        }))

async def process_audio_data(websocket: WebSocket, session_id: str, message: Dict[str, Any]):
    """Process incoming audio data from Chrome extension"""
    try:
        if not audio_pipeline_service:
            raise Exception("Audio pipeline service not initialized")
            
        audio_data = message.get("data", [])
        source_metadata = {
            "url": message.get("sourceUrl"),
            "language": message.get("language", "unknown"),
            "timestamp": message.get("timestamp", time.time())
        }
        
        logger.info(f"Processing audio chunk: {len(audio_data)} samples for session {session_id}")
        
        # Process through the audio pipeline
        result = await audio_pipeline_service.process_audio_chunk(
            session_id, 
            audio_data, 
            source_metadata
        )
        
        # Send response back to client
        response = {
            "type": "audio_processed",
            "session_id": session_id,
            "result": result
        }
        
        await websocket.send_text(json.dumps(response))
        
    except Exception as e:
        logger.error(f"Error processing audio data: {e}")
        await websocket.send_text(json.dumps({
            "type": "audio_error",
            "session_id": session_id,
            "status": "error",
            "message": f"Audio processing error: {str(e)}"
        }))

@app.get("/status")
async def get_status():
    """Get current system status"""
    try:
        import psutil
        system_stats = {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_usage": psutil.disk_usage('/').percent
        }
    except:
        system_stats = {"error": "System stats unavailable"}
    
    connection_details = {}
    for conn_id, conn_info in active_connections.items():
        connection_details[conn_id] = {
            "connected_at": conn_info.get('connected_at', 0),
            "last_activity": conn_info.get('last_activity', 0),
            "duration": time.time() - conn_info.get('connected_at', time.time())
        }
    
    return {
        "active_connections": len(active_connections),
        "connection_details": connection_details,
        "system_stats": system_stats,
        "services_status": {
            "audio_capture": "operational",
            "audio_streaming": "operational", 
            "compression": "operational"
        },
        "uptime": time.time(),
        "version": "1.0.0"
    }

@app.get("/stats/{connection_id}")
async def get_connection_stats(connection_id: str):
    """Get detailed statistics for a specific connection"""
    if connection_id not in active_connections:
        return JSONResponse(
            status_code=404,
            content={"error": f"Connection {connection_id} not found"}
        )
    
    try:
        conn_info = active_connections[connection_id]
        audio_capture = conn_info['audio_capture']
        audio_streaming = conn_info['audio_streaming']
        
        return {
            "connection_id": connection_id,
            "connection_info": {
                "connected_at": conn_info.get('connected_at', 0),
                "last_activity": conn_info.get('last_activity', 0),
                "duration": time.time() - conn_info.get('connected_at', time.time())
            },
            "capture_stats": audio_capture.get_buffer_stats(),
            "streaming_stats": audio_streaming.get_streaming_stats(),
            "timestamp": time.time()
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to get stats: {str(e)}"}
        )

if __name__ == "__main__":
    logger.info("Starting TrueTone Backend Server...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
