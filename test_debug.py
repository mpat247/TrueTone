"""
Minimal test for audio processing to debug the hanging issue.
"""

import sys
import os
import logging
import time
import traceback

# Add backend directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

# Configure logging with more verbose output
logging.basicConfig(
    level=logging.DEBUG, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def test_imports():
    """Test all imports to identify the problematic one."""
    print("🔍 Testing imports...")
    
    try:
        print("  ✓ Importing numpy...")
        import numpy as np
        print(f"    numpy version: {np.__version__}")
    except Exception as e:
        print(f"  ✗ numpy import failed: {e}")
        return False
    
    try:
        print("  ✓ Importing soundfile...")
        import soundfile as sf
        print(f"    soundfile imported successfully")
    except Exception as e:
        print(f"  ✗ soundfile import failed: {e}")
        return False
    
    try:
        print("  ✓ Importing librosa...")
        import librosa
        print(f"    librosa version: {librosa.__version__}")
    except Exception as e:
        print(f"  ✗ librosa import failed: {e}")
        return False
    
    try:
        print("  ✓ Importing scipy...")
        from scipy.signal import butter, filtfilt
        print(f"    scipy imported successfully")
    except Exception as e:
        print(f"  ✗ scipy import failed: {e}")
        return False
    
    print("✅ All imports successful!")
    return True

def test_basic_numpy():
    """Test basic numpy operations."""
    print("\n🔢 Testing basic numpy operations...")
    
    try:
        import numpy as np
        
        # Simple array creation
        print("  Creating test array...")
        test_array = np.array([1, 2, 3, 4, 5])
        print(f"  ✓ Array created: {test_array}")
        
        # Simple math operations
        print("  Testing math operations...")
        result = np.sin(test_array)
        print(f"  ✓ Sin operation: {result}")
        
        # Random data
        print("  Creating random data...")
        random_data = np.random.normal(0, 1, 100)
        print(f"  ✓ Random data shape: {random_data.shape}")
        
        return True
    
    except Exception as e:
        print(f"  ✗ Numpy test failed: {e}")
        traceback.print_exc()
        return False

def test_audio_generation():
    """Test simple audio generation."""
    print("\n🎵 Testing audio generation...")
    
    try:
        import numpy as np
        
        print("  Generating sine wave...")
        sample_rate = 1000  # Small for testing
        duration = 0.1  # Very short
        
        t = np.linspace(0, duration, int(sample_rate * duration))
        print(f"  ✓ Time array created: {len(t)} samples")
        
        audio = np.sin(2 * np.pi * 440 * t)
        print(f"  ✓ Audio generated: {audio.shape}, range [{audio.min():.3f}, {audio.max():.3f}]")
        
        return True
    
    except Exception as e:
        print(f"  ✗ Audio generation failed: {e}")
        traceback.print_exc()
        return False

def test_librosa_basic():
    """Test basic librosa operations."""
    print("\n📚 Testing librosa operations...")
    
    try:
        import numpy as np
        import librosa
        
        # Create simple test audio
        print("  Creating test audio for librosa...")
        audio = np.sin(2 * np.pi * 440 * np.linspace(0, 0.1, 1000))
        
        print("  Testing zero crossing rate...")
        zcr = librosa.feature.zero_crossing_rate(audio, frame_length=256, hop_length=128)
        print(f"  ✓ ZCR computed: shape {zcr.shape}")
        
        print("  Testing spectral centroid...")
        spectral_centroids = librosa.feature.spectral_centroid(y=audio, sr=1000)
        print(f"  ✓ Spectral centroid computed: shape {spectral_centroids.shape}")
        
        return True
    
    except Exception as e:
        print(f"  ✗ Librosa test failed: {e}")
        traceback.print_exc()
        return False

def test_audio_processor_import():
    """Test importing the audio processor."""
    print("\n🔧 Testing AudioProcessor import...")
    
    try:
        print("  Importing AudioProcessor...")
        from backend.utils.audio_processing import AudioProcessor
        print("  ✓ AudioProcessor imported successfully")
        
        print("  Creating AudioProcessor instance...")
        processor = AudioProcessor(target_sample_rate=1000)  # Small sample rate
        print("  ✓ AudioProcessor created successfully")
        
        return True
    
    except Exception as e:
        print(f"  ✗ AudioProcessor import/creation failed: {e}")
        traceback.print_exc()
        return False

def test_simple_processing():
    """Test very simple audio processing."""
    print("\n⚙️  Testing simple audio processing...")
    
    try:
        import numpy as np
        from backend.utils.audio_processing import AudioProcessor
        
        print("  Creating processor...")
        processor = AudioProcessor(target_sample_rate=1000)
        
        print("  Creating very simple test audio...")
        # Very simple audio - just 100 samples
        simple_audio = np.array([0.1, 0.2, 0.3, 0.2, 0.1] * 20, dtype=np.float32)
        print(f"  ✓ Simple audio created: {simple_audio.shape}")
        
        print("  Testing detect_audio_properties...")
        metadata = processor.detect_audio_properties(simple_audio, 1000)
        print(f"  ✓ Properties detected: quality={metadata.quality_score:.3f}")
        
        print("  Testing mono conversion...")
        mono_result = processor.convert_to_mono(simple_audio)
        print(f"  ✓ Mono conversion: {simple_audio.shape} -> {mono_result.shape}")
        
        print("  Testing normalization...")
        normalized = processor.normalize_audio(simple_audio, method='peak')
        print(f"  ✓ Normalization complete: max={np.max(np.abs(normalized)):.3f}")
        
        return True
    
    except Exception as e:
        print(f"  ✗ Simple processing failed: {e}")
        traceback.print_exc()
        return False

def main():
    """Main test function with timeout handling."""
    print("🚀 DEBUGGING AUDIO PROCESSING HANG")
    print("=" * 50)
    
    start_time = time.time()
    
    tests = [
        ("Import Test", test_imports),
        ("Numpy Test", test_basic_numpy),
        ("Audio Generation", test_audio_generation),
        ("Librosa Basic", test_librosa_basic),
        ("AudioProcessor Import", test_audio_processor_import),
        ("Simple Processing", test_simple_processing),
    ]
    
    for test_name, test_func in tests:
        print(f"\n{'='*20} {test_name} {'='*20}")
        
        test_start = time.time()
        
        try:
            # Add timeout protection
            result = test_func()
            test_time = time.time() - test_start
            
            if result:
                print(f"✅ {test_name} PASSED ({test_time:.2f}s)")
            else:
                print(f"❌ {test_name} FAILED ({test_time:.2f}s)")
                print(f"⚠️  Stopping tests at first failure to isolate issue.")
                break
                
        except Exception as e:
            test_time = time.time() - test_start
            print(f"💥 {test_name} CRASHED ({test_time:.2f}s): {e}")
            traceback.print_exc()
            print(f"⚠️  Stopping tests at first crash to isolate issue.")
            break
        
        # Check if test is taking too long
        if test_time > 30:
            print(f"⏰ {test_name} took too long ({test_time:.2f}s), might be hanging")
            break
    
    total_time = time.time() - start_time
    print(f"\n🏁 Testing completed in {total_time:.2f}s")
    
    if total_time > 60:
        print("⚠️  Tests took longer than expected - possible hanging issue identified")
    
    print("\n💡 TROUBLESHOOTING TIPS:")
    print("- If tests hang at librosa, try: pip install --upgrade librosa")
    print("- If tests hang at numpy, try: pip install --upgrade numpy")
    print("- Check system resources with: top or Activity Monitor")
    print("- Try running with: python -u test_debug.py")

if __name__ == "__main__":
    main()
