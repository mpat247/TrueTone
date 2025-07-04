#!/usr/bin/env python3
"""
TrueTone Backend - FastAPI Server
Main entry point for the TrueTone voice-preserving translation service.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import json
import logging
from typing import Dict, Any
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

@app.get("/")
async def root():
    """Root endpoint - API information"""
    return {
        "message": "TrueTone API is running",
        "version": "1.0.0",
        "endpoints": {
            "health": "/health",
            "websocket": "/ws"
        }
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for the Chrome extension"""
    return {
        "status": "healthy",
        "service": "TrueTone Backend",
        "version": "1.0.0",
        "timestamp": asyncio.get_event_loop().time()
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time audio streaming"""
    await websocket.accept()
    connection_id = f"conn_{len(active_connections)}"
    active_connections[connection_id] = websocket
    
    logger.info(f"New WebSocket connection: {connection_id}")
    
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
            
            if message.get("type") == "audio":
                # Process audio data
                await process_audio_data(websocket, message)
            elif message.get("type") == "config":
                # Update configuration
                await update_config(websocket, message)
            else:
                # Echo back unknown messages for debugging
                await websocket.send_text(json.dumps({
                    "type": "echo",
                    "original": message
                }))
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: {connection_id}")
        del active_connections[connection_id]
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        if connection_id in active_connections:
            del active_connections[connection_id]

async def process_audio_data(websocket: WebSocket, message: Dict[str, Any]):
    """Process incoming audio data from Chrome extension"""
    try:
        audio_data = message.get("data", [])
        sample_rate = message.get("sampleRate", 44100)
        config = message.get("config", {})
        
        logger.info(f"Processing audio chunk: {len(audio_data)} samples at {sample_rate}Hz")
        
        # TODO: Implement actual audio processing pipeline
        # For now, just acknowledge receipt
        response = {
            "type": "audio_processed",
            "status": "received",
            "samples": len(audio_data),
            "sample_rate": sample_rate,
            "config": config,
            "message": "Audio processing pipeline not yet implemented"
        }
        
        await websocket.send_text(json.dumps(response))
        
    except Exception as e:
        logger.error(f"Error processing audio data: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Audio processing error: {str(e)}"
        }))

async def update_config(websocket: WebSocket, message: Dict[str, Any]):
    """Update translation configuration"""
    try:
        config = message.get("config", {})
        
        logger.info(f"Updating config: {config}")
        
        # TODO: Store and apply configuration
        response = {
            "type": "config_updated",
            "status": "success",
            "config": config
        }
        
        await websocket.send_text(json.dumps(response))
        
    except Exception as e:
        logger.error(f"Error updating config: {e}")
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Config update error: {str(e)}"
        }))

@app.get("/status")
async def get_status():
    """Get current system status"""
    return {
        "active_connections": len(active_connections),
        "connections": list(active_connections.keys()),
        "models_loaded": False,  # TODO: Implement model loading status
        "system_ready": True
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
