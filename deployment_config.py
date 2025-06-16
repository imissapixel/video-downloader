#!/usr/bin/env python3
"""
Production Deployment Configuration for dl.xtend3d.com
"""

import os
from pathlib import Path

# Production settings
class ProductionConfig:
    # Server settings
    HOST = '0.0.0.0'
    PORT = int(os.environ.get('PORT', 80))
    DEBUG = False
    
    # Security settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-production-secret-key-change-this')
    
    # CORS settings for production
    CORS_ORIGINS = [
        "chrome-extension://*",
        "moz-extension://*", 
        "https://dl.xtend3d.com"
    ]
    
    # File upload limits
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    
    # Download settings
    DOWNLOADS_DIR = Path('/var/www/downloads')  # Production download directory
    CLEANUP_INTERVAL = 3600  # 1 hour in seconds
    FILE_RETENTION_HOURS = 2  # Keep files for 2 hours in production
    
    # Logging settings
    LOG_LEVEL = 'INFO'
    LOG_FILE = '/var/log/video_downloader.log'
    
    # Rate limiting (optional)
    RATE_LIMIT_PER_MINUTE = 10
    RATE_LIMIT_PER_HOUR = 100

# Development settings (for local testing)
class DevelopmentConfig:
    HOST = '0.0.0.0'
    PORT = 5000
    DEBUG = True
    SECRET_KEY = 'dev-secret-key'
    CORS_ORIGINS = [
        "chrome-extension://*",
        "moz-extension://*",
        "http://localhost:5000",
        "https://dl.xtend3d.com"
    ]
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    DOWNLOADS_DIR = Path('static/downloads')
    CLEANUP_INTERVAL = 3600
    FILE_RETENTION_HOURS = 1
    LOG_LEVEL = 'DEBUG'

# Select configuration based on environment
config = ProductionConfig() if os.environ.get('FLASK_ENV') == 'production' else DevelopmentConfig()