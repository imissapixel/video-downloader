#!/usr/bin/env python3
"""
Video Downloader Web Interface - Launcher Script
Simple script to run the Flask application with proper configuration
"""

import os
import sys
from pathlib import Path

def check_dependencies():
    """Check if required files exist"""
    required_files = [
        'app.py',
        'video_downloader.py',
        'requirements.txt',
        'templates/base.html',
        'templates/index.html'
    ]
    
    missing_files = []
    for file_path in required_files:
        if not Path(file_path).exists():
            missing_files.append(file_path)
    
    if missing_files:
        print("❌ Missing required files:")
        for file_path in missing_files:
            print(f"   - {file_path}")
        print("\nPlease ensure all project files are in the current directory.")
        return False
    
    print("✅ All required files found")
    return True

def check_python_packages():
    """Check if required Python packages are installed"""
    required_packages = ['flask', 'werkzeug']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        print("❌ Missing Python packages:")
        for package in missing_packages:
            print(f"   - {package}")
        print("\nInstall missing packages with: pip install -r requirements.txt")
        return False
    
    print("✅ Required Python packages found")
    return True

def create_directories():
    """Create necessary directories"""
    directories = [
        'static/downloads',
        'static/css',
        'static/js',
        'templates'
    ]
    
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    print("✅ Directories created/verified")

def main():
    print("🚀 Video Downloader Web Interface")
    print("=" * 40)
    
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)
    
    if not check_python_packages():
        sys.exit(1)
    
    # Create directories
    create_directories()
    
    # Set environment variables
    os.environ.setdefault('FLASK_ENV', 'development')
    
    print("\n🌐 Starting web server...")
    print("📍 URL: http://localhost:5000")
    print("🛑 Press Ctrl+C to stop")
    print("-" * 40)
    
    # Import and run the Flask app
    try:
        from app import app
        app.run(debug=True, host='0.0.0.0', port=5000)
    except ImportError as e:
        print(f"❌ Error importing app: {e}")
        print("Make sure app.py is in the current directory")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n👋 Server stopped by user")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()