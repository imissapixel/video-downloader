#!/bin/bash
# Video Downloader Web Interface - Server Startup Script

echo "🚀 Starting Video Downloader Web Interface..."
echo "================================================"

# Check if virtual environment exists
if [ ! -d "video_downloader_env" ]; then
    echo "❌ Virtual environment not found!"
    echo "   Please run: python3 -m venv video_downloader_env"
    echo "   Then run: ./video_downloader_env/bin/pip install -r requirements.txt"
    exit 1
fi

# Check if dependencies are installed
if ! ./video_downloader_env/bin/python -c "import flask" 2>/dev/null; then
    echo "❌ Flask not installed in virtual environment!"
    echo "   Please run: ./video_downloader_env/bin/pip install -r requirements.txt"
    exit 1
fi

echo "✅ Virtual environment found"
echo "✅ Dependencies installed"
echo ""
echo "🌐 Starting web server..."
echo "📍 URL: http://localhost:5000"
echo "🛑 Press Ctrl+C to stop"
echo "================================================"

# Start the Flask application
./video_downloader_env/bin/python app.py