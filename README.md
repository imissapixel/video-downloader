# Video Downloader Web Interface

A comprehensive web-based interface for downloading videos from various platforms with support for simple URLs and advanced JSON configurations. Perfect for integration with Chrome extensions and automated workflows.

## Features

### 🎯 **Core Functionality**
- **Multi-platform support**: YouTube, Vimeo, TikTok, Twitter, Instagram, Twitch, Reddit, SoundCloud, and more
- **Dual download engines**: yt-dlp for popular platforms, ffmpeg for direct streams
- **Real-time progress tracking** with live status updates
- **Background job processing** for non-blocking downloads

### 🔧 **Input Methods**
- **Simple URL mode**: Just paste any video URL
- **Advanced JSON mode**: Full metadata support with headers, cookies, authentication
- **JSON validation**: Real-time syntax checking and validation
- **Chrome extension integration**: Direct API endpoints for seamless integration

### ⚙️ **Download Options**
- **Quality selection**: Best, Medium (720p), Low (480p)
- **Format options**: MP4, WebM, MKV, AVI
- **Custom filenames** with automatic sanitization
- **Verbose logging** for debugging

### 🎨 **User Interface**
- **Responsive design** for desktop and mobile
- **Real-time progress bars** with status messages
- **Download history** with job tracking
- **Dependency status checking**
- **Error handling** with retry functionality

## Installation

### Prerequisites
- Python 3.7+
- pip (Python package manager)

### Dependencies
The application requires these external tools:
- **yt-dlp**: For downloading from popular video platforms
- **ffmpeg**: For processing video streams and format conversion

### Setup

1. **Clone or download the project files**
```bash
# Ensure you have all the project files:
# - app.py
# - video_downloader.py
# - requirements.txt
# - templates/
# - static/
```

2. **Install Python dependencies**
```bash
pip install -r requirements.txt
```

3. **Install external dependencies**

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
pip install yt-dlp
```

**macOS (with Homebrew):**
```bash
brew install ffmpeg
pip install yt-dlp
```

**Windows:**
- Download ffmpeg from https://ffmpeg.org/download.html
- Add ffmpeg to your system PATH
- Install yt-dlp: `pip install yt-dlp`

4. **Run the application**
```bash
python app.py
```

5. **Access the web interface**
Open your browser and go to: `http://localhost:5000`

## Usage

### Simple URL Download
1. Select "Simple URL" mode
2. Paste your video URL
3. Choose quality and format options
4. Click "Start Download"
5. Wait for completion and download the file

### Advanced JSON Mode
Perfect for videos requiring authentication or special headers:

```json
{
  "url": "https://example.com/protected-video.m3u8",
  "sourceType": "hls",
  "headers": {
    "Authorization": "Bearer your-token",
    "Referer": "https://example.com"
  },
  "cookies": "session_id=abc123; auth_token=xyz789",
  "userAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}
```

### Chrome Extension Integration
The web interface provides REST API endpoints for integration:

**Start Download:**
```javascript
fetch('http://localhost:5000/api/download', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    mode: 'json',
    json_string: JSON.stringify(videoMetadata),
    quality: 'best',
    format: 'mp4'
  })
})
```

**Check Status:**
```javascript
fetch(`http://localhost:5000/api/status/${jobId}`)
```

**Download File:**
```javascript
window.open(`http://localhost:5000/api/download-file/${jobId}`)
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Main web interface |
| `/api/check-deps` | GET | Check system dependencies |
| `/api/validate-json` | POST | Validate JSON configuration |
| `/api/download` | POST | Start new download job |
| `/api/status/<job_id>` | GET | Get download status |
| `/api/download-file/<job_id>` | GET | Download completed file |
| ~~`/api/jobs`~~ | ~~GET~~ | ~~Removed for security~~ |

## Supported Platforms

### Popular Video Platforms (via yt-dlp)
- YouTube (youtube.com, youtu.be)
- Vimeo (vimeo.com)
- TikTok (tiktok.com)
- Twitter (twitter.com)
- Instagram (instagram.com)
- Twitch (twitch.tv)
- Reddit (reddit.com)
- SoundCloud (soundcloud.com)
- And 1000+ more sites

### Direct Video Streams (via ffmpeg)
- HLS streams (.m3u8)
- DASH streams (.mpd)
- Direct video files (.mp4, .webm, etc.)

## Configuration

### Environment Variables
- `FLASK_ENV`: Set to `development` for debug mode
- `FLASK_PORT`: Change default port (default: 5000)

### File Storage
- Downloaded files are temporarily stored in `static/downloads/`
- Files are automatically cleaned up after 1 hour
- Each download gets a unique directory

### Security Considerations
- Input validation for URLs and JSON
- File path sanitization
- Automatic cleanup of temporary files
- Rate limiting (can be added)

## Troubleshooting

### Common Issues

**"Dependencies not found"**
- Install yt-dlp: `pip install yt-dlp`
- Install ffmpeg for your operating system
- Check that both are in your system PATH

**"Download failed"**
- Check if the URL is accessible
- For protected content, ensure proper headers/cookies in JSON mode
- Check the verbose output for detailed error messages

**"File not found after download"**
- Files are cleaned up after 1 hour
- Check the download immediately after completion
- Ensure sufficient disk space

### Debug Mode
Run with verbose logging:
```bash
FLASK_ENV=development python app.py
```

## Development

### Project Structure
```
video-downloader/
├── app.py                 # Main Flask application
├── video_downloader.py    # Core download functionality
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── templates/
│   ├── base.html         # Base template
│   └── index.html        # Main interface
└── static/
    ├── css/
    │   └── custom.css    # Custom styles
    ├── js/
    │   └── app.js        # Frontend JavaScript
    └── downloads/        # Temporary file storage
```

### Adding New Features
1. Backend API endpoints in `app.py`
2. Frontend functionality in `static/js/app.js`
3. UI components in `templates/index.html`
4. Styling in `static/css/custom.css`

## License

This project is open source. Feel free to modify and distribute according to your needs.

## Contributing

Contributions are welcome! Please feel free to submit issues, feature requests, or pull requests.

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the browser console for JavaScript errors
3. Check the Flask application logs
4. Ensure all dependencies are properly installed