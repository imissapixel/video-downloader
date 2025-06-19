#!/usr/bin/env python3
"""
Test script to verify audio extraction functionality
"""

import os
import tempfile
import shutil
from video_downloader import download_video

def test_audio_extraction():
    """Test audio extraction with a sample video"""
    
    # Create temporary directory for test
    test_dir = tempfile.mkdtemp()
    print(f"Test directory: {test_dir}")
    
    try:
        # Test stream info (using a public domain video)
        stream_info = {
            'url': 'https://www.youtube.com/watch?v=jNQXAC9IVRw',  # Sample video
            'sourceType': 'youtube'
        }
        
        # Test with audio extraction enabled
        advanced_options = {
            'extractAudio': True,
            'audioFormat': 'mp3',
            'audioQuality': 'best'
        }
        
        print("Testing audio extraction...")
        print(f"Stream info: {stream_info}")
        print(f"Advanced options: {advanced_options}")
        
        # Call download_video function
        result = download_video(
            stream_info=stream_info,
            output_dir=test_dir,
            format='mp4',  # This should be ignored for audio extraction
            quality='best',
            filename=None,
            verbose=True,  # Enable verbose logging
            progress_callback=lambda msg: print(f"Progress: {msg}"),
            **advanced_options
        )
        
        print(f"Download result: {result}")
        
        # Check if any files were created
        files = os.listdir(test_dir)
        print(f"Files created: {files}")
        
        # Check file extensions
        audio_files = [f for f in files if f.endswith(('.mp3', '.m4a', '.webm', '.ogg'))]
        video_files = [f for f in files if f.endswith(('.mp4', '.mkv', '.webm', '.avi'))]
        
        print(f"Audio files: {audio_files}")
        print(f"Video files: {video_files}")
        
        if audio_files and not video_files:
            print("✅ SUCCESS: Audio extraction working correctly!")
            return True
        elif video_files:
            print("❌ ISSUE: Video files found when audio-only was requested")
            return False
        else:
            print("❌ ISSUE: No files found")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False
    finally:
        # Clean up
        shutil.rmtree(test_dir, ignore_errors=True)

if __name__ == "__main__":
    success = test_audio_extraction()
    exit(0 if success else 1)