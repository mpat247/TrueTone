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
import time
import uuid
import os
import io
import numpy as np

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
    description="Voice-preserving YouTube translation backend",
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

# Store active WebSocket connections
active_connections: Dict[str, WebSocket] = {}

# Initialize services
audio_processor = None
audio_streaming_service = None
audio_capture_service = None
audio_pipeline_service = None

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global audio_processor, audio_streaming_service, audio_capture_service, audio_pipeline_service
    
    # Initialize audio processing utilities
    audio_processor = AudioProcessor()
    
    # Initialize services
    audio_streaming_service = AudioStreamingService(audio_processor)
    audio_capture_service = AudioCaptureService(audio_processor)
    
    # Initialize the main audio pipeline
    audio_pipeline_service = AudioPipelineService(
        audio_processor, 
        audio_capture_service, 
        audio_streaming_service
    )
    
    # Start background tasks
    await audio_pipeline_service.start_background_tasks()
    
    logger.info("TrueTone services initialized")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    global audio_pipeline_service
    
    if audio_pipeline_service:
        await audio_pipeline_service.stop_background_tasks()
    
    logger.info("TrueTone services shutdown complete")

@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "message": "TrueTone API is running",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "websocket": "/ws",
            "status": "/status",
            "sessions": "/sessions"
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
        "services": {
            "audio_processor": audio_processor is not None,
            "audio_streaming": audio_streaming_service is not None,
            "audio_capture": audio_capture_service is not None,
            "audio_pipeline": audio_pipeline_service is not None
        }
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time audio streaming"""
    await websocket.accept()
    connection_id = f"conn_{len(active_connections)}_{int(time.time())}"
    active_connections[connection_id] = websocket
    
    logger.info(f"New WebSocket connection: {connection_id}")
    
    # Initialize session variables
    session_id = None
    audio_metadata = None
    
    try:
        # Send welcome message
        await websocket.send_text(json.dumps({
            "type": "connection",
            "message": "Connected to TrueTone backend",
            "connection_id": connection_id
        }))
        
        while True:
            # Receive data from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            logger.info(f"Received message type: {message.get('type')}")
            
            if message.get("type") == "start_session":
                # Start new audio processing session
                session_id, audio_metadata = await start_audio_session(websocket, message)
                
            elif message.get("type") == "audio" and session_id:
                # Process audio data
                await process_audio_data(websocket, session_id, message)
                
            elif message.get("type") == "config" and session_id:
                # Update configuration
                await update_session_config(websocket, session_id, message)
                
            elif message.get("type") == "stop_session" and session_id:
                # Stop audio processing session
                await stop_audio_session(websocket, session_id)
                session_id = None
                audio_metadata = None
                
            else:
                # Echo back unknown messages for debugging
                await websocket.send_text(json.dumps({
                    "type": "echo",
                    "original": message,
                    "note": "Unknown message type or no active session"
                }))
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
        if connection_id in active_connections:
            del active_connections[connection_id]
        
        # Clean up session if active
        if session_id and audio_pipeline_service:
            await audio_pipeline_service.stop_session(session_id)
            
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if connection_id in active_connections:
            del active_connections[connection_id]
        
        # Clean up session if active
        if session_id and audio_pipeline_service:
            await audio_pipeline_service.stop_session(session_id)

async def start_audio_session(websocket: WebSocket, message: Dict[str, Any]) -> tuple[str, AudioMetadata]:
    """Start a new audio processing session"""
    try:
        if not audio_pipeline_service:
            raise Exception("Audio pipeline service not initialized")
            
        config = message.get("config", {})
        
        # Create audio metadata from config
        audio_format = AudioFormat(
            sample_rate=config.get("sampleRate", 44100),
            channels=config.get("channels", 2),
            bit_depth=config.get("bitDepth", 16),
            format="PCM",
            encoding="signed"
        )
        
        session_id = str(uuid.uuid4())
        audio_metadata = AudioMetadata(
            session_id=session_id,
            format=audio_format,
            source_url=config.get("sourceUrl"),
            source_type=config.get("sourceType", "youtube"),
            language=config.get("language", "unknown"),
            chunk_size=config.get("chunkSize", 1024)
        )
        
        # Start the session in the pipeline
        success = await audio_pipeline_service.start_session(session_id, audio_metadata)
        
        if success:
            response = {
                "type": "session_started",
                "session_id": session_id,
                "status": "success",
                "config": config
            }
            logger.info(f"Started session {session_id}")
        else:
            response = {
                "type": "session_error",
                "status": "error",
                "message": "Failed to start session"
            }
            logger.error(f"Failed to start session")
        
        await websocket.send_text(json.dumps(response))
        return session_id, audio_metadata
        
    except Exception as e:
        logger.error(f"Error starting audio session: {e}")
        await websocket.send_text(json.dumps({
            "type": "session_error",
            "status": "error",
            "message": f"Session start error: {str(e)}"
        }))
        raise

async def stop_audio_session(websocket: WebSocket, session_id: str):
    """Stop an audio processing session"""
    try:
        if not audio_pipeline_service:
            raise Exception("Audio pipeline service not initialized")
            
        success = await audio_pipeline_service.stop_session(session_id)
        
        response = {
            "type": "session_stopped",
            "session_id": session_id,
            "status": "success" if success else "error"
        }
        
        await websocket.send_text(json.dumps(response))
        logger.info(f"Stopped session {session_id}")
        
    except Exception as e:
        logger.error(f"Error stopping audio session: {e}")
        await websocket.send_text(json.dumps({
            "type": "session_error",
            "status": "error",
            "message": f"Session stop error: {str(e)}"
        }))

async def update_session_config(websocket: WebSocket, session_id: str, message: Dict[str, Any]):
    """Update session configuration"""
    try:
        if not audio_pipeline_service:
            raise Exception("Audio pipeline service not initialized")
            
        config = message.get("config", {})
        
        # Update pipeline config
        audio_pipeline_service.update_config(config)
        
        response = {
            "type": "config_updated",
            "session_id": session_id,
            "status": "success",
            "config": config
        }
        
        await websocket.send_text(json.dumps(response))
        logger.info(f"Updated config for session {session_id}")
        
    except Exception as e:
        logger.error(f"Error updating session config: {e}")
        await websocket.send_text(json.dumps({
            "type": "config_error",
            "status": "error",
            "message": f"Config update error: {str(e)}"
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
    pipeline_stats = {}
    if audio_pipeline_service:
        pipeline_stats = audio_pipeline_service.get_processing_stats()
    
    return {
        "active_connections": len(active_connections),
        "connections": list(active_connections.keys()),
        "pipeline_stats": pipeline_stats,
        "system_ready": audio_pipeline_service is not None
    }

@app.get("/sessions")
async def get_sessions():
    """Get information about all active sessions"""
    if not audio_pipeline_service:
        return {"sessions": [], "message": "Audio pipeline service not initialized"}
    
    sessions = audio_pipeline_service.get_all_sessions_info()
    return {
        "sessions": sessions,
        "total_sessions": len(sessions)
    }

@app.get("/sessions/{session_id}")
async def get_session_info(session_id: str):
    """Get information about a specific session"""
    if not audio_pipeline_service:
        return {"error": "Audio pipeline service not initialized"}
    
    session_info = audio_pipeline_service.get_session_info(session_id)
    if session_info:
        return session_info
    else:
        return {"error": f"Session {session_id} not found"}

@app.post("/sessions/{session_id}/stop")
async def stop_session_endpoint(session_id: str):
    """Stop a specific session via REST API"""
    if not audio_pipeline_service:
        return {"error": "Audio pipeline service not initialized"}
    
    success = await audio_pipeline_service.stop_session(session_id)
    return {
        "session_id": session_id,
        "status": "success" if success else "error",
        "message": "Session stopped" if success else "Failed to stop session"
    }

if __name__ == "__main__":
    logger.info("Starting TrueTone Backend Server...")
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
