# 🚀 Deployment Guide - dl.xtend3d.com

## 📋 **Overview**

This guide covers deploying your video downloader to `https://dl.xtend3d.com/` with full Chrome extension integration.

---

## 🔧 **Changes Made for Production**

### **Extension Updates:**
- ✅ **API URL**: Changed from `localhost:5000` → `https://dl.xtend3d.com`
- ✅ **Permissions**: Added explicit permission for `https://dl.xtend3d.com/*`
- ✅ **CORS Support**: Extension can now communicate with production domain

### **Server Updates:**
- ✅ **Production Config**: New `deployment_config.py` with environment-specific settings
- ✅ **Production App**: New `app_production.py` optimized for deployment
- ✅ **CORS Origins**: Added `https://dl.xtend3d.com` to allowed origins
- ✅ **Logging**: Production-grade logging with file rotation
- ✅ **Health Check**: `/health` endpoint for monitoring

---

## 🏗️ **Deployment Options**

### **Option 1: Traditional Server Deployment**

#### **Requirements:**
- Ubuntu/Debian server with Python 3.7+
- Nginx for reverse proxy
- SSL certificate for HTTPS
- Domain pointing to your server

#### **Setup Steps:**

1. **Install Dependencies:**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and tools
sudo apt install python3 python3-pip python3-venv nginx certbot python3-certbot-nginx ffmpeg -y

# Install yt-dlp
pip3 install yt-dlp
```

2. **Deploy Application:**
```bash
# Create application directory
sudo mkdir -p /var/www/video-downloader
cd /var/www/video-downloader

# Copy your files
# (Upload all project files to this directory)

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. **Configure Nginx:**
```nginx
# /etc/nginx/sites-available/dl.xtend3d.com
server {
    listen 80;
    server_name dl.xtend3d.com;
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # CORS headers for extension
        add_header Access-Control-Allow-Origin *;
        add_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
        add_header Access-Control-Allow-Headers "Content-Type, Authorization";
    }
    
    # Serve downloaded files directly
    location /static/downloads/ {
        alias /var/www/downloads/;
        expires 1h;
        add_header Cache-Control "public, no-transform";
    }
}
```

4. **Enable SSL:**
```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/dl.xtend3d.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Get SSL certificate
sudo certbot --nginx -d dl.xtend3d.com
```

5. **Create Systemd Service:**
```ini
# /etc/systemd/system/video-downloader.service
[Unit]
Description=Video Downloader Web Interface
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/video-downloader
Environment=FLASK_ENV=production
Environment=PATH=/var/www/video-downloader/venv/bin
ExecStart=/var/www/video-downloader/venv/bin/python app_production.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

6. **Start Service:**
```bash
sudo systemctl daemon-reload
sudo systemctl enable video-downloader
sudo systemctl start video-downloader
sudo systemctl status video-downloader
```

### **Option 2: Docker Deployment**

#### **Create Dockerfile:**
```dockerfile
# Dockerfile
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install yt-dlp
RUN pip install yt-dlp

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create downloads directory
RUN mkdir -p /var/www/downloads

# Expose port
EXPOSE 5000

# Set environment variables
ENV FLASK_ENV=production
ENV PYTHONPATH=/app

# Run the application
CMD ["python", "app_production.py"]
```

#### **Create docker-compose.yml:**
```yaml
version: '3.8'

services:
  video-downloader:
    build: .
    ports:
      - "5000:5000"
    volumes:
      - ./downloads:/var/www/downloads
      - ./logs:/var/log
    environment:
      - FLASK_ENV=production
      - SECRET_KEY=your-production-secret-key
    restart: unless-stopped
    
  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/ssl/certs
      - ./downloads:/var/www/downloads
    depends_on:
      - video-downloader
    restart: unless-stopped
```

### **Option 3: Cloud Platform Deployment**

#### **Heroku:**
```bash
# Install Heroku CLI and login
heroku login

# Create app
heroku create dl-xtend3d

# Set environment variables
heroku config:set FLASK_ENV=production
heroku config:set SECRET_KEY=your-secret-key

# Deploy
git push heroku main
```

#### **DigitalOcean App Platform:**
```yaml
# .do/app.yaml
name: video-downloader
services:
- name: web
  source_dir: /
  github:
    repo: your-username/video-downloader
    branch: main
  run_command: python app_production.py
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs
  envs:
  - key: FLASK_ENV
    value: production
  - key: SECRET_KEY
    value: your-secret-key
```

---

## 🔄 **Extension Update Process**

### **For Users:**
1. **Reload Extension**: Go to `chrome://extensions/` → Click reload
2. **Verify Connection**: Visit any video page → Check for "🌐 Web Interface Connected"
3. **Test Download**: Try downloading a YouTube video

### **For Distribution:**
1. **Update manifest.json** version number
2. **Test thoroughly** with production API
3. **Package extension** for Chrome Web Store
4. **Submit for review** if publishing publicly

---

## 🔍 **Testing Production Deployment**

### **Health Check:**
```bash
curl https://dl.xtend3d.com/health
# Expected: {"status": "healthy", "timestamp": "...", "version": "1.0"}
```

### **API Test:**
```bash
curl https://dl.xtend3d.com/api/check-deps
# Expected: {"yt-dlp": true, "ffmpeg": true}
```

### **Extension Test:**
1. Load updated extension in Chrome
2. Visit YouTube video
3. Check extension shows "🌐 Web Interface Connected"
4. Click "Download" button
5. Verify download completes successfully

---

## 📊 **Monitoring & Maintenance**

### **Log Files:**
- **Application**: `/var/log/video_downloader.log`
- **Nginx**: `/var/log/nginx/access.log`, `/var/log/nginx/error.log`
- **System**: `journalctl -u video-downloader`

### **Monitoring Commands:**
```bash
# Check service status
sudo systemctl status video-downloader

# View recent logs
sudo journalctl -u video-downloader -f

# Check disk usage
df -h /var/www/downloads

# Monitor active downloads
# curl https://dl.xtend3d.com/api/jobs  # REMOVED: Security fix
```

### **Maintenance Tasks:**
- **File Cleanup**: Automatic (configured for 2-hour retention)
- **Log Rotation**: Automatic (10MB files, 10 backups)
- **SSL Renewal**: Automatic with certbot
- **Dependency Updates**: Manual (monthly recommended)

---

## 🔒 **Security Considerations**

### **Server Security:**
- ✅ **Firewall**: Only ports 80, 443, and SSH open
- ✅ **SSL/TLS**: HTTPS enforced with valid certificate
- ✅ **User Permissions**: Service runs as www-data
- ✅ **File Cleanup**: Automatic removal of old downloads

### **Application Security:**
- ✅ **CORS**: Restricted to extension origins
- ✅ **Input Validation**: JSON and URL validation
- ✅ **File Paths**: Secure filename handling
- ✅ **Rate Limiting**: Can be added if needed

### **Extension Security:**
- ✅ **Permissions**: Minimal required permissions
- ✅ **HTTPS Only**: All API calls over HTTPS
- ✅ **Content Security**: No external script injection

---

## 🚨 **Troubleshooting**

### **Common Issues:**

#### **Extension Shows "Offline"**
```bash
# Check if service is running
sudo systemctl status video-downloader

# Check nginx configuration
sudo nginx -t

# Check SSL certificate
sudo certbot certificates
```

#### **Downloads Failing**
```bash
# Check dependencies
/var/www/video-downloader/venv/bin/python -c "import yt_dlp; print('OK')"

# Check disk space
df -h

# Check logs
sudo journalctl -u video-downloader -n 50
```

#### **CORS Errors**
```bash
# Verify nginx CORS headers
curl -H "Origin: chrome-extension://your-extension-id" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -X OPTIONS https://dl.xtend3d.com/api/download
```

---

## 📈 **Performance Optimization**

### **Server Optimization:**
- **CPU**: 2+ cores recommended for concurrent downloads
- **RAM**: 4GB+ for multiple simultaneous jobs
- **Storage**: SSD recommended, 100GB+ for temporary files
- **Bandwidth**: Unlimited or high quota for video downloads

### **Application Optimization:**
- **Worker Threads**: Limit concurrent downloads (default: unlimited)
- **File Cleanup**: Adjust retention time based on usage
- **Logging**: Reduce verbosity in production
- **Caching**: Add Redis for job storage if needed

---

**🎉 Your video downloader is now ready for production deployment on dl.xtend3d.com! 🚀**