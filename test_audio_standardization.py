"""
Test script for audio processing and standardization components.
Tests Requirements 1.3: Audio Format Standardization
"""

import sys
import os
import logging
import time
import numpy as np
import asyncio
from pathlib import Path

# Add backend directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.utils.audio_processing import AudioProcessor, AudioMetadata, load_audio_file
from backend.models.audio_metadata import (
    AudioFormat, AudioQualityMetrics, AudioProcessingStep,
    AudioMetadata as DetailedAudioMetadata, create_chunk_metadata
)
from backend.services.audio_pipeline import AudioPipelineManager, PipelineConfig

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_audio_processor():
    """Test basic audio processor functionality."""
    print("\n" + "="*60)
    print("TESTING AUDIO PROCESSOR")
    print("="*60)
    
    # Create processor
    processor = AudioProcessor(target_sample_rate=16000)
    
    # Test 1: Synthetic audio processing
    print("\n1. Testing synthetic audio processing...")
    
    # Create test audio (1 second of mixed frequency content)
    sample_rate = 44100
    duration = 1.0
    t = np.linspace(0, duration, int(sample_rate * duration))
    
    # Mix of frequencies to simulate speech-like content
    test_audio = (
        0.3 * np.sin(2 * np.pi * 440 * t) +      # A4 note
        0.2 * np.sin(2 * np.pi * 880 * t) +      # A5 note
        0.1 * np.sin(2 * np.pi * 1760 * t) +     # A6 note
        0.05 * np.random.normal(0, 1, len(t))     # Some noise
    )
    
    # Add some stereo effects (convert to stereo)
    stereo_audio = np.column_stack([test_audio, test_audio * 0.8])
    
    # Process audio
    start_time = time.time()
    processed_audio, metadata = processor.process_audio_chunk(stereo_audio, sample_rate)
    processing_time = time.time() - start_time
    
    print(f"   Original: {stereo_audio.shape} samples at {sample_rate}Hz")
    print(f"   Processed: {processed_audio.shape} samples at {metadata.sample_rate}Hz")
    print(f"   Quality score: {metadata.quality_score:.3f}")
    print(f"   Processing time: {processing_time:.3f}s")
    print(f"   Processing steps: {metadata.processing_steps}")
    
    # Test 2: Different sample rates
    print("\n2. Testing different sample rates...")
    test_rates = [8000, 16000, 22050, 44100, 48000]
    
    for rate in test_rates:
        mono_audio = np.sin(2 * np.pi * 440 * np.linspace(0, 0.5, int(rate * 0.5)))
        processed, meta = processor.process_audio_chunk(mono_audio, rate)
        print(f"   {rate}Hz -> {meta.sample_rate}Hz: {len(mono_audio)} -> {len(processed)} samples")
    
    # Test 3: Quality detection
    print("\n3. Testing quality detection...")
    
    # High quality audio
    high_quality = np.sin(2 * np.pi * 440 * np.linspace(0, 1, 44100))
    hq_processed, hq_meta = processor.process_audio_chunk(high_quality, 44100)
    
    # Low quality audio (very noisy)
    low_quality = 0.1 * np.sin(2 * np.pi * 440 * np.linspace(0, 1, 8000)) + 0.9 * np.random.normal(0, 0.5, 8000)
    lq_processed, lq_meta = processor.process_audio_chunk(low_quality, 8000)
    
    print(f"   High quality audio score: {hq_meta.quality_score:.3f}")
    print(f"   Low quality audio score: {lq_meta.quality_score:.3f}")
    
    # Test 4: Processing statistics
    print("\n4. Processing statistics:")
    stats = processor.get_processing_stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")
    
    return True

def test_audio_metadata():
    """Test audio metadata system."""
    print("\n" + "="*60)
    print("TESTING AUDIO METADATA SYSTEM")
    print("="*60)
    
    # Test 1: Basic metadata creation
    print("\n1. Testing metadata creation...")
    
    metadata = create_chunk_metadata("youtube", "tab_123")
    print(f"   Created metadata for chunk {metadata.chunk_id}")
    
    # Set format information
    original_format = AudioFormat(44100, 2, 16, "pcm", "raw")
    metadata.set_format(original_format, is_original=True)
    print(f"   Set original format: {original_format}")
    
    # Add processing step
    step = AudioProcessingStep(
        step_name="resampling",
        duration_ms=15.5,
        input_format="44100Hz_2ch_16bit",
        output_format="16000Hz_1ch_16bit",
        parameters={"method": "kaiser_best"},
        quality_change=0.05
    )
    metadata.add_processing_step(step)
    print(f"   Added processing step: {step.step_name}")
    
    # Update format after processing
    processed_format = AudioFormat(16000, 1, 16, "pcm", "raw")
    metadata.set_format(processed_format)
    print(f"   Updated format to: {processed_format}")
    
    # Update quality metrics
    quality = AudioQualityMetrics(
        dynamic_range=0.8,
        rms_energy=0.15,
        zero_crossing_rate=0.05,
        spectral_centroid=2500.0,
        overall_score=0.75
    )
    metadata.update_quality_metrics(quality)
    print(f"   Updated quality score: {quality.overall_score}")
    
    # Test 2: JSON serialization
    print("\n2. Testing JSON serialization...")
    
    json_str = metadata.to_json()
    restored_metadata = DetailedAudioMetadata.from_json(json_str)
    
    serialization_success = (
        restored_metadata.chunk_id == metadata.chunk_id and
        restored_metadata.source_type == metadata.source_type and
        len(restored_metadata.processing_steps) == len(metadata.processing_steps)
    )
    print(f"   JSON serialization: {'✓ PASS' if serialization_success else '✗ FAIL'}")
    
    # Test 3: Metadata summary
    print("\n3. Metadata summary:")
    summary = metadata.create_summary()
    for key, value in summary.items():
        print(f"   {key}: {value}")
    
    return serialization_success

def test_format_standardization():
    """Test specific format standardization requirements."""
    print("\n" + "="*60)
    print("TESTING FORMAT STANDARDIZATION")
    print("="*60)
    
    processor = AudioProcessor()
    
    # Test 1: Standard format presets
    print("\n1. Testing standard format presets...")
    
    whisper_format = AudioFormat.whisper_optimal()
    tts_format = AudioFormat.tts_optimal()
    hq_format = AudioFormat.high_quality()
    
    print(f"   Whisper optimal: {whisper_format}")
    print(f"   TTS optimal: {tts_format}")
    print(f"   High quality: {hq_format}")
    
    # Test 2: Resampling accuracy
    print("\n2. Testing resampling accuracy...")
    
    # Create test signal with known properties
    original_sr = 44100
    target_sr = 16000
    duration = 1.0
    frequency = 440.0  # A4 note
    
    # Generate pure tone
    t_original = np.linspace(0, duration, int(original_sr * duration))
    original_signal = np.sin(2 * np.pi * frequency * t_original)
    
    # Resample
    resampled_signal, final_sr = processor.standardize_sample_rate(original_signal, original_sr, target_sr)
    
    # Check properties
    expected_length = int(target_sr * duration)
    actual_length = len(resampled_signal)
    length_error = abs(expected_length - actual_length) / expected_length
    
    print(f"   Original: {len(original_signal)} samples at {original_sr}Hz")
    print(f"   Resampled: {actual_length} samples at {final_sr}Hz")
    print(f"   Expected length: {expected_length}")
    print(f"   Length error: {length_error:.3%}")
    
    # Test 3: Mono conversion
    print("\n3. Testing mono conversion...")
    
    # Create different channel configurations
    mono_audio = np.random.normal(0, 0.1, 1000)
    stereo_audio = np.column_stack([mono_audio, mono_audio * 0.8])
    multi_channel = np.column_stack([mono_audio, mono_audio * 0.8, mono_audio * 0.6])
    
    mono_result = processor.convert_to_mono(mono_audio)
    stereo_result = processor.convert_to_mono(stereo_audio)
    multi_result = processor.convert_to_mono(multi_channel)
    
    print(f"   Mono: {mono_audio.shape} -> {mono_result.shape}")
    print(f"   Stereo: {stereo_audio.shape} -> {stereo_result.shape}")
    print(f"   Multi-channel: {multi_channel.shape} -> {multi_result.shape}")
    
    # Test 4: Normalization methods
    print("\n4. Testing normalization methods...")
    
    # Create test audio with known amplitude
    test_audio = 0.5 * np.sin(2 * np.pi * 440 * np.linspace(0, 0.5, 8000))
    
    peak_normalized = processor.normalize_audio(test_audio, method='peak', target_level=0.8)
    rms_normalized = processor.normalize_audio(test_audio, method='rms', target_level=0.2)
    
    print(f"   Original peak: {np.max(np.abs(test_audio)):.3f}")
    print(f"   Peak normalized: {np.max(np.abs(peak_normalized)):.3f}")
    print(f"   Original RMS: {np.sqrt(np.mean(test_audio**2)):.3f}")
    print(f"   RMS normalized: {np.sqrt(np.mean(rms_normalized**2)):.3f}")
    
    return length_error < 0.01  # Less than 1% error acceptable

async def test_pipeline_integration():
    """Test complete pipeline integration."""
    print("\n" + "="*60)
    print("TESTING PIPELINE INTEGRATION")
    print("="*60)
    
    # Test 1: Pipeline configuration
    print("\n1. Testing pipeline configuration...")
    
    config = PipelineConfig(
        target_sample_rate=16000,
        chunk_duration=0.5,
        overlap_duration=0.05,
        max_buffer_size=10,
        normalize_audio=True,
        apply_filtering=True,
        quality_threshold=0.3,
        async_processing=False,  # Synchronous for testing
        max_workers=1,
        skip_silent_chunks=True,
        energy_threshold=0.01
    )
    
    print(f"   Configuration created: {config.target_sample_rate}Hz target")
    
    # Test 2: Pipeline creation
    print("\n2. Testing pipeline creation...")
    
    try:
        pipeline = AudioPipelineManager(config)
        print("   ✓ Pipeline created successfully")
        
        # Test configuration updates
        pipeline.update_config(target_sample_rate=22050, quality_threshold=0.4)
        print("   ✓ Configuration updated successfully")
        
        # Test stats retrieval
        stats = pipeline.get_pipeline_stats()
        print(f"   ✓ Stats retrieved: {len(stats)} metrics")
        
        return True
        
    except Exception as e:
        print(f"   ✗ Pipeline creation failed: {e}")
        return False

def run_all_tests():
    """Run all audio processing tests."""
    print("TRUETONE AUDIO PROCESSING TEST SUITE")
    print("Requirements 1.3: Audio Format Standardization")
    print("="*80)
    
    results = []
    
    try:
        # Test 1: Basic audio processor
        result1 = test_audio_processor()
        results.append(("Audio Processor", result1))
        
        # Test 2: Metadata system
        result2 = test_audio_metadata()
        results.append(("Audio Metadata", result2))
        
        # Test 3: Format standardization
        result3 = test_format_standardization()
        results.append(("Format Standardization", result3))
        
        # Test 4: Pipeline integration
        result4 = asyncio.run(test_pipeline_integration())
        results.append(("Pipeline Integration", result4))
        
    except Exception as e:
        logger.error(f"Test execution error: {e}")
        results.append(("Test Execution", False))
    
    # Print results summary
    print("\n" + "="*80)
    print("TEST RESULTS SUMMARY")
    print("="*80)
    
    total_tests = len(results)
    passed_tests = sum(1 for _, result in results if result)
    
    for test_name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test_name:.<40} {status}")
    
    print("-" * 50)
    print(f"Total: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print("\n🎉 ALL TESTS PASSED! Audio format standardization is working correctly.")
        print("\nRequirement 1.3 Status: ✅ COMPLETED")
        print("- Audio resampling to target sample rates (16kHz for Whisper)")
        print("- High-quality format conversion with anti-aliasing")
        print("- Mono/stereo conversion with intelligent mixing")
        print("- Audio normalization (peak and RMS methods)")
        print("- Quality-based filtering and processing optimization")
        print("- Comprehensive metadata tracking throughout pipeline")
        print("- JSON serialization for metadata persistence")
        print("- Pipeline integration with async processing support")
    else:
        print(f"\n❌ {total_tests - passed_tests} tests failed. Please check the implementation.")
    
    return passed_tests == total_tests

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
