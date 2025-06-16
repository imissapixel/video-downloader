# 🚀 Production Deployment Guide - dl.xtend3d.com

## ⚡ **Deploy to Your Web Server with PM2**

### **Step 1: Server Prerequisites**
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Node.js and PM2
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
sudo npm install -g pm2

# Install Python and system dependencies
sudo apt install -y python3 python3-pip python3-venv ffmpeg

# Install yt-dlp globally
sudo pip3 install yt-dlp
```

### **Step 2: Deploy Application**
```bash
# Create application directory
sudo mkdir -p /var/www/video-downloader
cd /var/www/video-downloader

# Upload your project files here
# (Use scp, git clone, or file transfer)

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install Python dependencies
pip install -r requirements.txt
pip install Flask-CORS==4.0.0

# Set proper permissions
sudo chown -R $USER:$USER /var/www/video-downloader
sudo mkdir -p /var/www/downloads
sudo chown -R $USER:$USER /var/www/downloads
```

### **Step 3: Configure PM2**
```bash
# Create PM2 ecosystem file
cat > ecosystem.config.js << 'EOF'
module.exports = {
  apps: [{
    name: 'video-downloader',
    script: '/var/www/video-downloader/venv/bin/python',
    args: 'app_production.py',
    cwd: '/var/www/video-downloader',
    instances: 1,
    exec_mode: 'fork',
    env: {
      FLASK_ENV: 'production',
      PYTHONPATH: '/var/www/video-downloader',
      PATH: '/var/www/video-downloader/venv/bin:' + process.env.PATH
    },
    error_file: '/var/log/video-downloader-error.log',
    out_file: '/var/log/video-downloader-out.log',
    log_file: '/var/log/video-downloader.log',
    time: true,
    autorestart: true,
    max_restarts: 10,
    min_uptime: '10s',
    max_memory_restart: '1G'
  }]
};
EOF

# Start application with PM2
pm2 start ecosystem.config.js
pm2 save
pm2 startup
```

### **Step 4: Configure Nginx Reverse Proxy**
```bash
# Create nginx configuration
sudo tee /etc/nginx/sites-available/dl.xtend3d.com << 'EOF'
server {
    listen 80;
    server_name dl.xtend3d.com;
    
    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name dl.xtend3d.com;
    
    # SSL Configuration (add your SSL certificate paths)
    ssl_certificate /etc/letsencrypt/live/dl.xtend3d.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/dl.xtend3d.com/privkey.pem;
    
    # Security headers
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
    add_header X-XSS-Protection "1; mode=block";
    
    # CORS headers for extension
    add_header Access-Control-Allow-Origin *;
    add_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
    add_header Access-Control-Allow-Headers "Content-Type, Authorization";
    
    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Handle preflight requests
        if ($request_method = 'OPTIONS') {
            add_header Access-Control-Allow-Origin *;
            add_header Access-Control-Allow-Methods "GET, POST, OPTIONS";
            add_header Access-Control-Allow-Headers "Content-Type, Authorization";
            add_header Content-Length 0;
            add_header Content-Type text/plain;
            return 204;
        }
    }
    
    # Serve download files with proper headers
    location /api/download-file/ {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Increase timeout for large file downloads
        proxy_read_timeout 300s;
        proxy_send_timeout 300s;
    }
}
EOF

# Enable site and restart nginx
sudo ln -s /etc/nginx/sites-available/dl.xtend3d.com /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### **Step 5: Setup SSL Certificate**
```bash
# Install certbot
sudo apt install certbot python3-certbot-nginx -y

# Get SSL certificate
sudo certbot --nginx -d dl.xtend3d.com

# Verify auto-renewal
sudo certbot renew --dry-run
```

### **Step 6: Test Deployment**
```bash
# Check PM2 status
pm2 status
pm2 logs video-downloader

# Test health endpoint
curl https://dl.xtend3d.com/health

# Test API
curl https://dl.xtend3d.com/api/check-deps
```

### **Step 7: Update Chrome Extension**
```bash
# Users need to reload the extension to use production API
# Extension will automatically connect to https://dl.xtend3d.com
```

1. Open Chrome → `chrome://extensions/`
2. Find "Video URL Capture" extension
3. Click **"Reload"** button
4. Extension now connects to production server

### **Step 8: Verify Everything Works**
1. **Visit YouTube**: https://youtube.com/watch?v=dQw4w9WgXcQ
2. **Click extension icon** → Should show "1" badge
3. **Check status**: Should see "🌐 Web Interface Connected"
4. **Click "Download"** → Should start downloading automatically
5. **Access web interface**: https://dl.xtend3d.com

---

## 🔧 **PM2 Management Commands**

### **Basic Operations**
```bash
# Check application status
pm2 status

# View logs in real-time
pm2 logs video-downloader

# Restart application
pm2 restart video-downloader

# Stop application
pm2 stop video-downloader

# Delete application from PM2
pm2 delete video-downloader
```

### **Monitoring & Debugging**
```bash
# Monitor CPU and memory usage
pm2 monit

# View detailed application info
pm2 show video-downloader

# View error logs only
pm2 logs video-downloader --err

# View last 100 log lines
pm2 logs video-downloader --lines 100
```

### **Auto-Startup Configuration**
```bash
# Save current PM2 configuration
pm2 save

# Generate startup script (run after any changes)
pm2 startup

# Disable auto-startup
pm2 unstartup
```

---

## 📋 **Troubleshooting**

### **PM2 Application Not Starting**
```bash
# Check PM2 logs for errors
pm2 logs video-downloader

# Check if Python virtual environment is working
/var/www/video-downloader/venv/bin/python --version

# Manually test the application
cd /var/www/video-downloader
source venv/bin/activate
python app_production.py
```

### **Extension Shows "Web Interface Offline"**
```bash
# Check if PM2 app is running
pm2 status

# Check if nginx is running
sudo systemctl status nginx

# Test direct connection to Flask app
curl http://localhost:5000/health

# Check nginx configuration
sudo nginx -t
```

### **SSL Certificate Issues**
```bash
# Check certificate status
sudo certbot certificates

# Renew certificate if needed
sudo certbot renew

# Test SSL configuration
curl -I https://dl.xtend3d.com/health
```

### **Downloads Failing**
```bash
# Check if yt-dlp is installed
yt-dlp --version

# Check if ffmpeg is installed
ffmpeg -version

# Check disk space
df -h /var/www/downloads

# Check application logs
pm2 logs video-downloader --lines 50
```

---

## 🎉 **Success Indicators**

### **Server Working:**
- ✅ `pm2 status` shows app as "online"
- ✅ `curl https://dl.xtend3d.com/health` returns success
- ✅ Nginx serving HTTPS correctly
- ✅ SSL certificate valid

### **Extension Working:**
- ✅ Badge shows number on video pages
- ✅ Green "🌐 Web Interface Connected" status
- ✅ "Download" buttons visible next to streams

### **Integration Working:**
- ✅ Click "Download" in extension starts download
- ✅ Progress updates in real-time
- ✅ "Download File" button appears when complete
- ✅ Files download successfully from server

---

## 🔧 **Maintenance Tasks**

### **Regular Maintenance**
```bash
# Update system packages
sudo apt update && sudo apt upgrade

# Update yt-dlp
sudo pip3 install --upgrade yt-dlp

# Check disk usage
df -h

# Restart application (if needed)
pm2 restart video-downloader
```

### **Log Management**
```bash
# Rotate PM2 logs
pm2 flush

# Check log sizes
ls -lh /var/log/video-downloader*

# Archive old logs (optional)
sudo logrotate /etc/logrotate.conf
```

---

## 📊 **Performance Monitoring**

### **Resource Usage**
```bash
# Monitor real-time performance
pm2 monit

# Check system resources
htop

# Monitor network usage
iftop
```

### **Application Metrics**
```bash
# Check active downloads
curl https://dl.xtend3d.com/api/jobs

# Monitor download directory size
du -sh /var/www/downloads

# Check application uptime
pm2 show video-downloader
```

---

**🎬 Your production video downloader is now live at https://dl.xtend3d.com! 🚀**

**Next Steps:**
1. Test with YouTube videos
2. Share extension with users
3. Monitor server performance
4. Set up automated backups