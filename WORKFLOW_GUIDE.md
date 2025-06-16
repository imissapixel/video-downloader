# 🎬 Video Downloader - Complete Workflow Guide

## Extension → Web Interface Integration

This guide explains how to use your Chrome extension with the web interface for seamless video downloading.

---

## 🚀 **Quick Start Workflow**

### **Step 1: Install & Setup**
1. **Load the Chrome extension** in Developer Mode
2. **Start the web interface**: `./start_server.sh` or `./video_downloader_env/bin/python app.py`
3. **Open web interface**: http://localhost:5000

### **Step 2: Capture Video Data**
1. **Navigate to any video page** (YouTube, Vimeo, streaming sites, etc.)
2. **Click the extension icon** in your browser toolbar
3. **Wait for detection** - the badge will show the number of streams found
4. **Review detected streams** in the popup

### **Step 3: Download Videos**
Choose one of these methods:

#### **Method A: Individual Stream (Recommended)**
1. **Select the stream** you want to download
2. **Click "Copy"** button next to the stream
3. **Switch to web interface** tab
4. **Select "Advanced JSON" mode**
5. **Paste** the JSON data (Ctrl+V)
6. **Click "Validate JSON"** to verify
7. **Choose quality/format** options
8. **Click "Start Download"**

#### **Method B: Bulk Data**
1. **Click "Copy All Stream Data as JSON"** in extension
2. **Switch to web interface**
3. **Select "Advanced JSON" mode**
4. **Paste the array** and select individual streams
5. **Process each stream** as needed

---

## 🎯 **Detailed Workflow Examples**

### **Example 1: YouTube Video**
```
1. Visit: https://youtube.com/watch?v=dQw4w9WgXcQ
2. Extension detects: YouTube URL + any HLS streams
3. Copy JSON from extension:
   {
     "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
     "title": "Rick Astley - Never Gonna Give You Up",
     "sourceType": "youtube",
     "headers": {},
     "cookies": "...",
     "referer": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
     "userAgent": "Mozilla/5.0..."
   }
4. Paste in web interface → Download with yt-dlp
```

### **Example 2: HLS Stream (Protected)**
```
1. Visit: https://example.com/protected-video
2. Extension detects: .m3u8 stream + captures headers/cookies
3. Copy JSON from extension:
   {
     "url": "https://cdn.example.com/video/playlist.m3u8",
     "title": "Protected Video Stream",
     "sourceType": "hls",
     "headers": {
       "Authorization": "Bearer abc123",
       "Referer": "https://example.com"
     },
     "cookies": "session_id=xyz789; auth_token=def456",
     "referer": "https://example.com/protected-video",
     "userAgent": "Mozilla/5.0..."
   }
4. Paste in web interface → Download with ffmpeg + authentication
```

### **Example 3: Embedded Video**
```
1. Visit: News site with embedded video player
2. Extension detects: Multiple sources (iframe, direct, HLS)
3. Choose best quality stream from popup
4. Copy → Paste → Download
```

---

## 🔍 **Extension Features Explained**

### **Main Tab: Media Streams**
- **Stream List**: All detected video/audio sources
- **Stream Types**: YouTube, HLS, DASH, Direct, Embedded
- **Copy Button**: Individual stream JSON export
- **Copy All**: Bulk export of all streams
- **Metadata Toggle**: View detailed stream information

### **Advanced Tab: Debug Info**
- **Stream Count**: Total detected streams
- **Current Page**: URL being analyzed
- **Last Updated**: Timestamp of last scan
- **Debug Info**: Technical details and stream types
- **Force Deep Scan**: Aggressive detection mode

### **Stream Type Indicators**
- 🔴 **YouTube**: `youtube` - Uses yt-dlp
- 🟠 **HLS**: `hls` - Uses ffmpeg for .m3u8 streams
- 🟡 **DASH**: `dash` - Uses ffmpeg for .mpd streams
- 🟢 **Direct**: `direct` - Direct video file URLs
- 🔵 **Embedded**: `embed` - Iframe embedded players
- 🟣 **MediaSource**: `mediaSource` - JavaScript media sources

---

## 🌐 **Web Interface Features**

### **Simple URL Mode**
- **Best for**: YouTube, Vimeo, TikTok, public videos
- **Input**: Just paste the page URL
- **Detection**: Automatic platform detection

### **Advanced JSON Mode** ⭐
- **Best for**: Protected streams, HLS/DASH, complex sites
- **Input**: JSON from Chrome extension
- **Features**: Headers, cookies, authentication support
- **Validation**: Real-time JSON syntax checking

### **Download Options**
- **Quality**: Best / Medium (720p) / Low (480p)
- **Format**: MP4 / WebM / MKV / AVI
- **Custom Filename**: Optional custom naming
- **Verbose Mode**: Detailed logging for debugging

---

## 🛠️ **Troubleshooting**

### **Extension Issues**

#### **No Streams Detected**
```
Solutions:
1. Click "Force Deep Scan" in Advanced tab
2. Play the video first, then check extension
3. Refresh the page and wait for full load
4. Check if site uses unusual player technology
```

#### **Copy Button Not Working**
```
Solutions:
1. Check browser clipboard permissions
2. Try "Copy All" instead of individual copy
3. Manually select and copy from metadata view
4. Check browser console for errors
```

#### **Wrong Stream Type**
```
Solutions:
1. Try different streams from the list
2. Look for HLS (.m3u8) or DASH (.mpd) streams
3. Use Force Deep Scan for hidden streams
4. Check if video requires authentication
```

### **Web Interface Issues**

#### **JSON Validation Failed**
```
Solutions:
1. Check JSON syntax in extension popup
2. Use "Validate JSON" button to see specific errors
3. Ensure all quotes are properly escaped
4. Try copying individual stream instead of bulk data
```

#### **Download Failed**
```
Solutions:
1. Check if yt-dlp/ffmpeg are installed
2. Try different quality settings
3. Check verbose mode for detailed errors
4. Verify stream URL is still valid
5. For protected content, ensure headers/cookies are included
```

#### **Authentication Required**
```
Solutions:
1. Make sure to use Advanced JSON mode
2. Verify cookies were captured by extension
3. Check if additional headers are needed
4. Try accessing the video page first to establish session
```

---

## 📋 **Best Practices**

### **For Extension Use**
1. **Let pages fully load** before checking for streams
2. **Play videos briefly** to trigger stream detection
3. **Check multiple stream types** - some sites have backup streams
4. **Use Force Deep Scan** on complex sites
5. **Copy individual streams** rather than bulk for better success

### **For Web Interface**
1. **Always validate JSON** before downloading
2. **Start with lower quality** for testing
3. **Use verbose mode** when troubleshooting
4. **Check dependencies** if downloads fail
5. **Monitor download progress** for large files

### **For Protected Content**
1. **Ensure you're logged in** to the source site
2. **Copy streams immediately** after detection
3. **Don't wait too long** - sessions may expire
4. **Include all metadata** (headers, cookies, referer)
5. **Test with short clips** first

---

## 🔗 **Integration API**

### **Direct API Usage**
Your extension can also POST directly to the web interface API:

```javascript
// From your extension's content script or popup
fetch('http://localhost:5000/api/download', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    mode: 'json',
    json_string: JSON.stringify(streamData),
    quality: 'best',
    format: 'mp4',
    filename: 'my_video'
  })
})
.then(response => response.json())
.then(data => {
  if (data.success) {
    // Poll for status: /api/status/${data.job_id}
    // Download when ready: /api/download-file/${data.job_id}
  }
});
```

### **Status Polling**
```javascript
// Check download progress
fetch(`http://localhost:5000/api/status/${jobId}`)
.then(response => response.json())
.then(status => {
  console.log(`Status: ${status.status}, Progress: ${status.progress}%`);
});
```

---

## 🎉 **Success Tips**

### **High Success Rate Sites**
- ✅ **YouTube**: Almost always works with extension
- ✅ **Vimeo**: Good detection and download success
- ✅ **News sites**: Usually have detectable streams
- ✅ **Educational platforms**: Often use standard players

### **Sites Requiring Special Handling**
- ⚠️ **Netflix/Prime**: DRM protected, won't work
- ⚠️ **Live streams**: May need special handling
- ⚠️ **Social media**: May require login/session
- ⚠️ **Premium content**: Needs valid authentication

### **Optimization Tips**
- 🚀 **Use HLS streams** when available (better quality)
- 🚀 **Prefer direct video URLs** for simplicity
- 🚀 **Copy metadata immediately** after detection
- 🚀 **Test with low quality first** for speed
- 🚀 **Keep web interface open** while browsing

---

## 📞 **Support**

If you encounter issues:

1. **Check the browser console** for JavaScript errors
2. **Use verbose mode** in the web interface
3. **Try Force Deep Scan** in the extension
4. **Verify dependencies** are installed (yt-dlp, ffmpeg)
5. **Test with known working sites** (YouTube) first

---

**Happy downloading! 🎬✨**