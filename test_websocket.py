#!/usr/bin/env python3
"""
WebSocket test client for TrueTone backend
Simulates Chrome extension WebSocket communication
"""

import asyncio
import websockets
import json
import base64
import numpy as np
import time

async def test_websocket_connection():
    """Test WebSocket connection and audio streaming"""
    uri = "ws://localhost:8000/ws"
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to TrueTone backend WebSocket")
            
            # Listen for connection established message
            message = await websocket.recv()
            data = json.loads(message)
            print(f"📨 Received: {data['type']} - {data['message']}")
            
            # Send audio configuration
            config_message = {
                "type": "audio_config",
                "config": {
                    "action": "start",
                    "sampleRate": 16000,
                    "channels": 1,
                    "format": "float32",
                    "compression": {"enabled": True}
                }
            }
            
            await websocket.send(json.dumps(config_message))
            print("📤 Sent audio configuration")
            
            # Wait for response
            response = await websocket.recv()
            response_data = json.loads(response)
            print(f"📨 Config response: {response_data['status']}")
            
            # Generate and send test audio chunk
            sample_rate = 16000
            duration = 0.1  # 100ms chunk
            frequency = 440  # A4 note
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            sine_wave = np.sin(2 * np.pi * frequency * t).astype(np.float32)
            
            # Convert to base64
            audio_bytes = sine_wave.tobytes()
            base64_audio = base64.b64encode(audio_bytes).decode('utf-8')
            
            # Send audio chunk
            audio_message = {
                "type": "audio_chunk",
                "sequence": 1,
                "timestamp": int(time.time() * 1000),
                "sampleRate": 16000,
                "channels": 1,
                "data": base64_audio,
                "metadata": {
                    "bufferSize": len(sine_wave),
                    "quality": {
                        "averageLevel": 0.5,
                        "peakLevel": 0.8,
                        "hasClipping": False,
                        "isSilent": False,
                        "snrEstimate": 20.0
                    }
                }
            }
            
            await websocket.send(json.dumps(audio_message))
            print(f"📤 Sent audio chunk: {len(audio_bytes)} bytes")
            
            # Wait for processing response
            audio_response = await websocket.recv()
            audio_response_data = json.loads(audio_response)
            print(f"📨 Audio response: {audio_response_data['status']}")
            
            if 'buffer_stats' in audio_response_data:
                stats = audio_response_data['buffer_stats']
                print(f"   Buffer: {stats['size']} bytes, {stats['utilization']:.1f}% full")
            
            # Request synchronization
            sync_message = {
                "type": "sync_request",
                "client_time": time.time()
            }
            
            await websocket.send(json.dumps(sync_message))
            print("📤 Requested clock synchronization")
            
            # Wait for sync response
            sync_response = await websocket.recv()
            sync_data = json.loads(sync_response)
            print(f"📨 Sync response: offset={sync_data['offset']:.3f}s")
            
            # Request statistics
            stats_message = {
                "type": "stats_request",
                "stats_type": "all"
            }
            
            await websocket.send(json.dumps(stats_message))
            print("📤 Requested statistics")
            
            # Wait for stats response
            stats_response = await websocket.recv()
            stats_data = json.loads(stats_response)
            print(f"📨 Stats response received")
            
            if 'system_stats' in stats_data:
                sys_stats = stats_data['system_stats']
                print(f"   System: CPU={sys_stats['cpu_percent']:.1f}%, "
                      f"Memory={sys_stats['memory_percent']:.1f}%")
            
            print("✅ WebSocket test completed successfully!")
            
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")

if __name__ == "__main__":
    print("🔌 Testing TrueTone WebSocket Connection")
    print("=" * 40)
    asyncio.run(test_websocket_connection())
