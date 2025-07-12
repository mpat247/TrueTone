"""
TrueTone Voice Synthesis Module
Uses ElevenLabs API for high-quality voice cloning and synthesis
"""

import os
from typing import List, Optional
from dotenv import load_dotenv
from elevenlabs import clone, generate, save, set_api_key, voices

class TrueToneVoiceSynthesis:
    """Voice synthesis class for TrueTone using ElevenLabs API"""
    
    def __init__(self):
        """Initialize the voice synthesis engine"""
        load_dotenv()  # Load API key from .env file
        api_key = os.getenv("ELEVENLABS_API_KEY")
        if not api_key:
            print("WARNING: ELEVENLABS_API_KEY not found in environment variables")
            print("Get your API key from https://elevenlabs.io")
        else:
            set_api_key(api_key)
        
        self.voice_cache = {}  # Cache for voice IDs
    
    def list_available_voices(self):
        """List all available voices in your ElevenLabs account"""
        all_voices = voices()
        return [{"name": voice.name, "id": voice.voice_id} for voice in all_voices]
    
    def clone_voice(self, name: str, audio_files: List[str]) -> str:
        """
        Clone a voice from audio samples
        
        Args:
            name: A name for the cloned voice
            audio_files: List of paths to audio files for voice cloning
            
        Returns:
            voice_id: The ID of the cloned voice
        """
        voice = clone(
            name=name,
            files=audio_files,
            description=f"TrueTone cloned voice: {name}"
        )
        
        voice_id = voice.voice_id
        self.voice_cache[name] = voice_id
        return voice_id
    
    def generate_speech(
        self, 
        text: str, 
        voice_id: str, 
        output_file: Optional[str] = None
    ) -> bytes:
        """
        Generate speech using a specified voice
        
        Args:
            text: The text to convert to speech
            voice_id: The voice ID to use
            output_file: Optional path to save the audio file
            
        Returns:
            audio_data: The generated audio as bytes
        """
        audio_data = generate(
            text=text,
            voice=voice_id,
            model="eleven_multilingual_v2"  # Use multilingual model for translations
        )
        
        if output_file:
            save(audio_data, output_file)
            
        return audio_data
    
    def translate_with_voice_preservation(
        self, 
        source_text: str,
        source_language: str,
        target_language: str,
        voice_id: str,
        output_file: Optional[str] = None
    ) -> bytes:
        """
        Core TrueTone functionality: Translate text while preserving the original voice
        
        Args:
            source_text: Original text to translate
            source_language: Language code of the source text
            target_language: Language code for the translation
            voice_id: Voice ID to use for speech synthesis
            output_file: Optional path to save the audio file
            
        Returns:
            audio_data: The generated audio as bytes
        """
        # This is where you would integrate with a translation service
        # For now, we'll just use a placeholder
        # TODO: Implement actual translation using a service like Google Translate or DeepL
        
        # Placeholder translation
        translated_text = f"[Translated from {source_language} to {target_language}]: {source_text}"
        
        # Generate speech with the translated text but preserved voice
        return self.generate_speech(translated_text, voice_id, output_file)

# Example usage
if __name__ == "__main__":
    # Create a .env file with your ElevenLabs API key: ELEVENLABS_API_KEY=your_api_key_here
    synthesis = TrueToneVoiceSynthesis()
    
    # List available voices
    print("Available voices:")
    voices = synthesis.list_available_voices()
    for voice in voices:
        print(f"- {voice['name']} (ID: {voice['id']})")
    
    if voices:
        # Use an existing voice
        voice_id = voices[0]["id"]
        
        # Generate speech
        synthesis.generate_speech(
            "Hello, this is TrueTone. I can translate while preserving the speaker's voice.",
            voice_id,
            "example_output.mp3"
        )
        
        print("Generated example_output.mp3")
    else:
        print("No voices available. You need to create a voice or clone one first.")
        
    # Note: To clone a voice, you would use:
    # voice_id = synthesis.clone_voice("Speaker Name", ["path/to/audio1.mp3", "path/to/audio2.mp3"])
