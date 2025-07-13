"""
Quick diagnostic test to check if audio processing components work
"""

import sys
import os
import logging

# Add backend directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

print("Starting diagnostic test...")

try:
    print("1. Testing numpy import...")
    import numpy as np
    print("   ✓ numpy imported successfully")
    
    print("2. Testing soundfile import...")
    import soundfile as sf
    print("   ✓ soundfile imported successfully")
    
    print("3. Testing librosa import...")
    import librosa
    print("   ✓ librosa imported successfully")
    
    print("4. Testing basic numpy operations...")
    test_array = np.random.normal(0, 0.1, 1000)
    print(f"   ✓ Created test array: {test_array.shape}")
    
    print("5. Testing basic librosa operations...")
    sr = 22050
    duration = 1.0
    t = np.linspace(0, duration, int(sr * duration))
    test_audio = np.sin(2 * np.pi * 440 * t)
    
    # Try resampling
    resampled = librosa.resample(test_audio, orig_sr=sr, target_sr=16000)
    print(f"   ✓ Resampling test: {len(test_audio)} -> {len(resampled)} samples")
    
    print("6. Testing AudioProcessor import...")
    from backend.utils.audio_processing import AudioProcessor
    print("   ✓ AudioProcessor imported successfully")
    
    print("7. Testing AudioProcessor creation...")
    processor = AudioProcessor(target_sample_rate=16000)
    print("   ✓ AudioProcessor created successfully")
    
    print("8. Testing basic audio processing...")
    processed_audio, metadata = processor.process_audio_chunk(test_audio, sr)
    print(f"   ✓ Audio processed: {len(test_audio)} -> {len(processed_audio)} samples")
    print(f"   ✓ Quality score: {metadata.quality_score:.3f}")
    
    print("\n🎉 ALL DIAGNOSTIC TESTS PASSED!")
    print("The audio processing system is working correctly.")
    
except Exception as e:
    print(f"\n❌ DIAGNOSTIC TEST FAILED: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
