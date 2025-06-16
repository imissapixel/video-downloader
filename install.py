#!/usr/bin/env python3
"""
Video Downloader Web Interface - Installation Script
Automated setup script for the video downloader web interface
"""

import os
import sys
import subprocess
import platform
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors"""
    print(f"📦 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"   Command: {command}")
        print(f"   Error: {e.stderr}")
        return False

def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 7):
        print("❌ Python 3.7+ is required")
        print(f"   Current version: {version.major}.{version.minor}.{version.micro}")
        return False
    
    print(f"✅ Python version: {version.major}.{version.minor}.{version.micro}")
    return True

def install_python_dependencies():
    """Install Python packages from requirements.txt"""
    if not Path('requirements.txt').exists():
        print("❌ requirements.txt not found")
        return False
    
    return run_command(
        f"{sys.executable} -m pip install -r requirements.txt",
        "Installing Python dependencies"
    )

def install_system_dependencies():
    """Install system dependencies based on the operating system"""
    system = platform.system().lower()
    
    print(f"🖥️  Detected operating system: {system}")
    
    if system == "linux":
        # Check if we're on Ubuntu/Debian
        try:
            subprocess.run(["which", "apt"], check=True, capture_output=True)
            print("📦 Installing ffmpeg via apt...")
            return run_command(
                "sudo apt update && sudo apt install -y ffmpeg",
                "Installing ffmpeg (Ubuntu/Debian)"
            )
        except subprocess.CalledProcessError:
            print("⚠️  apt not found. Please install ffmpeg manually:")
            print("   - For CentOS/RHEL: sudo yum install ffmpeg")
            print("   - For Arch: sudo pacman -S ffmpeg")
            return False
    
    elif system == "darwin":  # macOS
        try:
            subprocess.run(["which", "brew"], check=True, capture_output=True)
            return run_command(
                "brew install ffmpeg",
                "Installing ffmpeg via Homebrew"
            )
        except subprocess.CalledProcessError:
            print("⚠️  Homebrew not found. Please install ffmpeg manually:")
            print("   1. Install Homebrew: /bin/bash -c \"$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"")
            print("   2. Install ffmpeg: brew install ffmpeg")
            return False
    
    elif system == "windows":
        print("⚠️  Windows detected. Please install ffmpeg manually:")
        print("   1. Download from: https://ffmpeg.org/download.html")
        print("   2. Extract to a folder (e.g., C:\\ffmpeg)")
        print("   3. Add C:\\ffmpeg\\bin to your system PATH")
        print("   4. Restart your command prompt/terminal")
        return False
    
    else:
        print(f"⚠️  Unsupported operating system: {system}")
        print("   Please install ffmpeg manually for your system")
        return False

def install_yt_dlp():
    """Install yt-dlp"""
    return run_command(
        f"{sys.executable} -m pip install yt-dlp",
        "Installing yt-dlp"
    )

def verify_installation():
    """Verify that all dependencies are installed correctly"""
    print("\n🔍 Verifying installation...")
    
    # Check yt-dlp
    try:
        subprocess.run(["yt-dlp", "--version"], check=True, capture_output=True)
        print("✅ yt-dlp is working")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ yt-dlp not found or not working")
        return False
    
    # Check ffmpeg
    try:
        subprocess.run(["ffmpeg", "-version"], check=True, capture_output=True)
        print("✅ ffmpeg is working")
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ ffmpeg not found or not working")
        return False
    
    # Check Flask
    try:
        import flask
        print(f"✅ Flask {flask.__version__} is installed")
    except ImportError:
        print("❌ Flask not found")
        return False
    
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
    
    print("✅ Created necessary directories")

def main():
    print("🚀 Video Downloader Web Interface - Installation")
    print("=" * 50)
    
    # Check Python version
    if not check_python_version():
        sys.exit(1)
    
    # Create directories
    create_directories()
    
    # Install Python dependencies
    if not install_python_dependencies():
        print("\n❌ Failed to install Python dependencies")
        sys.exit(1)
    
    # Install yt-dlp specifically
    if not install_yt_dlp():
        print("\n❌ Failed to install yt-dlp")
        sys.exit(1)
    
    # Install system dependencies
    print("\n🔧 Installing system dependencies...")
    ffmpeg_success = install_system_dependencies()
    
    # Verify installation
    print("\n" + "=" * 50)
    if verify_installation():
        print("\n🎉 Installation completed successfully!")
        print("\n📋 Next steps:")
        print("   1. Run the application: python run.py")
        print("   2. Open your browser to: http://localhost:5000")
        print("   3. Start downloading videos!")
        
        if not ffmpeg_success:
            print("\n⚠️  Note: ffmpeg installation may have failed.")
            print("   Some video downloads might not work without ffmpeg.")
            print("   Please install ffmpeg manually for full functionality.")
    else:
        print("\n❌ Installation verification failed")
        print("   Please check the error messages above and try again")
        sys.exit(1)

if __name__ == '__main__':
    main()