#!/usr/bin/env python3
"""
Video Downloader Web Interface - Production Version
Flask-based web application optimized for deployment on dl.xtend3d.com
"""

import os
import json
import uuid
import threading
import time
import re
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for
from flask_cors import CORS
from werkzeug.utils import secure_filename
import logging
from logging.handlers import RotatingFileHandler

# Import our existing video downloader
from video_downloader import download_video, check_dependencies, setup_output_directory
from deployment_config import config
# Import security utilities
from security_utils import validate_download_request, SecurityError, InputValidator
# Import rate limiting
from rate_limiter import rate_limit, security_rate_limit, rate_limiter
# Import performance optimization
from performance_optimizer import performance_monitor, get_performance_report

app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_LENGTH

# Enable CORS for extension integration
CORS(app, origins=config.CORS_ORIGINS)

# Set up production logging
if not config.DEBUG:
    if not os.path.exists('/var/log'):
        os.makedirs('/var/log', exist_ok=True)
    
    file_handler = RotatingFileHandler(
        config.LOG_FILE, 
        maxBytes=10240000,  # 10MB
        backupCount=10
    )
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('Video Downloader startup')

# Set up console logging for development
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Global job storage (in production, consider using Redis)
jobs = {}
job_lock = threading.Lock()

# Create downloads directory
DOWNLOADS_DIR = config.DOWNLOADS_DIR
DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)

class DownloadJob:
    def __init__(self, job_id, stream_info, options):
        self.job_id = job_id
        self.stream_info = stream_info
        self.options = options
        self.status = 'pending'
        self.progress = 0
        self.message = 'Initializing...'
        self.error = None
        self.file_path = None
        self.created_at = datetime.now()
        self.completed_at = None

def cleanup_old_files():
    """Clean up files older than configured retention time"""
    try:
        cutoff_time = datetime.now() - timedelta(hours=config.FILE_RETENTION_HOURS)
        cleaned_count = 0
        
        for file_path in DOWNLOADS_DIR.glob('*'):
            if file_path.is_file():
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_time < cutoff_time:
                    file_path.unlink()
                    cleaned_count += 1
                    logger.info(f"Cleaned up old file: {file_path}")
            elif file_path.is_dir():
                # Clean up empty job directories
                try:
                    if not any(file_path.iterdir()):
                        file_path.rmdir()
                        cleaned_count += 1
                        logger.info(f"Cleaned up empty directory: {file_path}")
                except OSError:
                    pass  # Directory not empty
        
        if cleaned_count > 0:
            logger.info(f"Cleanup completed: {cleaned_count} items removed")
            
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

def download_worker(job_id):
    """Background worker for downloading videos"""
    with job_lock:
        job = jobs.get(job_id)
        if not job:
            return

    try:
        job.status = 'downloading'
        job.message = 'Starting download...'
        
        # Create unique output directory for this job
        output_dir = DOWNLOADS_DIR / job_id
        output_dir.mkdir(exist_ok=True)
        
        # Download the video
        result = download_video(
            job.stream_info,
            str(output_dir),
            job.options.get('format', 'mp4'),
            job.options.get('quality', 'best'),
            job.options.get('filename'),
            job.options.get('verbose', False)
        )
        
        if result['success']:
            job.status = 'completed'
            job.message = 'Download completed successfully'
            job.progress = 100
            
            # Find the downloaded file
            files = list(output_dir.glob('*'))
            if files:
                job.file_path = str(files[0])
            
        else:
            job.status = 'failed'
            job.error = result.get('error', 'Unknown error')
            job.message = f'Download failed: {job.error}'
            
    except Exception as e:
        job.status = 'failed'
        job.error = str(e)
        job.message = f'Download failed: {str(e)}'
        logger.exception(f"Download job {job_id} failed")
    
    finally:
        job.completed_at = datetime.now()

@app.route('/')
def index():
    """Main page with download interface"""
    # Check dependencies
    deps = check_dependencies()
    return render_template('index.html', dependencies=deps)

@app.route('/health')
def health_check():
    """Health check endpoint for load balancers"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'version': '1.0'
    })

@app.route('/api/check-deps')
@rate_limit('requests')
def check_deps():
    """API endpoint to check dependencies"""
    deps = check_dependencies()
    return jsonify(deps)

@app.route('/api/validate-json', methods=['POST'])
@rate_limit('requests')
def validate_json():
    """Validate JSON input with security checks"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'valid': False, 'error': 'No data provided'})
        
        json_str = data.get('json_string', '')
        
        # Use security validation
        parsed = InputValidator.validate_json_input(json_str)
        
        # Additional validation for URL
        parsed['url'] = InputValidator.validate_url(parsed['url'])
        
        # Validate optional fields
        if 'headers' in parsed:
            parsed['headers'] = InputValidator.validate_headers(parsed['headers'])
        
        if 'cookies' in parsed:
            parsed['cookies'] = InputValidator.validate_cookies(parsed['cookies'])
        
        # Return sanitized version (without sensitive data in response)
        safe_parsed = {
            'url': parsed['url'],
            'sourceType': parsed.get('sourceType', 'unknown'),
            'hasHeaders': bool(parsed.get('headers')),
            'hasCookies': bool(parsed.get('cookies')),
            'hasReferer': bool(parsed.get('referer')),
            'hasUserAgent': bool(parsed.get('userAgent'))
        }
        
        return jsonify({'valid': True, 'parsed': safe_parsed})
    
    except SecurityError as e:
        logger.warning(f"Security validation failed: {e}")
        return jsonify({'valid': False, 'error': str(e)})
    except json.JSONDecodeError as e:
        return jsonify({'valid': False, 'error': f'Invalid JSON: {str(e)}'})
    except Exception as e:
        logger.exception("Unexpected error in JSON validation")
        return jsonify({'valid': False, 'error': 'Validation failed'})

@app.route('/api/download', methods=['POST'])
@rate_limit('downloads')
def start_download():
    """Start a new download job with security validation"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'})
        
        # Comprehensive security validation
        try:
            validated_data = validate_download_request(data)
        except SecurityError as e:
            logger.warning(f"Security validation failed for download request: {e}")
            return jsonify({'success': False, 'error': f'Security validation failed: {str(e)}'})
        
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Extract validated data
        stream_info = validated_data['stream_info']
        options = {
            'format': validated_data['format'],
            'quality': validated_data['quality'],
            'filename': validated_data['filename'],
            'verbose': validated_data['verbose']
        }
        
        # Create job with validated data
        job = DownloadJob(job_id, stream_info, options)
        
        with job_lock:
            jobs[job_id] = job
        
        # Start download in background
        thread = threading.Thread(target=download_worker, args=(job_id,))
        thread.daemon = True
        thread.start()
        
        logger.info(f"Started secure download job {job_id} for URL: {stream_info.get('url', 'unknown')}")
        return jsonify({'success': True, 'job_id': job_id})
        
    except SecurityError as e:
        logger.warning(f"Security error in download request: {e}")
        return jsonify({'success': False, 'error': f'Security error: {str(e)}'})
    except Exception as e:
        logger.exception("Unexpected error starting download")
        return jsonify({'success': False, 'error': 'Download request failed'})

@app.route('/api/status/<job_id>')
@rate_limit('requests')
def get_status(job_id):
    """Get status of a download job"""
    # Validate job_id format (should be UUID)
    try:
        uuid.UUID(job_id)
    except ValueError:
        return jsonify({'error': 'Invalid job ID format'}), 400
    
    with job_lock:
        job = jobs.get(job_id)
        
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    # Sanitize error messages to prevent information leakage
    error_message = job.error
    if error_message:
        # Remove potentially sensitive information from error messages
        error_message = re.sub(r'/[^\s]*', '[PATH]', error_message)  # Remove file paths
        error_message = re.sub(r'https?://[^\s]+', '[URL]', error_message)  # Remove URLs
    
    return jsonify({
        'job_id': job.job_id,
        'status': job.status,
        'progress': job.progress,
        'message': job.message,
        'error': error_message,
        'created_at': job.created_at.isoformat(),
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        'has_file': bool(job.file_path and os.path.exists(job.file_path))
    })

@app.route('/api/download-file/<job_id>')
@rate_limit('requests')
def download_file(job_id):
    """Download the completed file with security checks"""
    # Validate job_id format (should be UUID)
    try:
        uuid.UUID(job_id)
    except ValueError:
        return jsonify({'error': 'Invalid job ID format'}), 400
    
    with job_lock:
        job = jobs.get(job_id)
    
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    if job.status != 'completed' or not job.file_path:
        return jsonify({'error': 'File not ready'}), 400
    
    # Security: Validate file path is within expected directory
    try:
        file_path = Path(job.file_path).resolve()
        downloads_dir = DOWNLOADS_DIR.resolve()
        
        # Ensure file is within downloads directory (prevent path traversal)
        file_path.relative_to(downloads_dir)
    except (ValueError, OSError):
        logger.warning(f"Attempted access to file outside downloads directory: {job.file_path}")
        return jsonify({'error': 'File access denied'}), 403
    
    if not file_path.exists():
        return jsonify({'error': 'File not found'}), 404
    
    # Sanitize filename for download
    original_filename = file_path.name
    safe_filename = InputValidator.validate_filename(original_filename)
    if not safe_filename:
        safe_filename = f"download_{job_id[:8]}.{file_path.suffix.lstrip('.')}"
    
    try:
        return send_file(str(file_path), as_attachment=True, download_name=safe_filename)
    except Exception as e:
        logger.exception(f"Error sending file {file_path}: {e}")
        return jsonify({'error': 'File download failed'}), 500

@app.route('/api/rate-limit-status')
@rate_limit('requests')
def get_rate_limit_status():
    """Get current rate limit status for the client"""
    try:
        ip = rate_limiter.get_client_ip()
        status = rate_limiter.get_rate_limit_status(ip)
        return jsonify(status)
    except Exception as e:
        logger.exception("Error getting rate limit status")
        return jsonify({'error': 'Unable to get rate limit status'}), 500

@app.route('/api/performance-stats')
@rate_limit('requests')
def get_performance_stats():
    """Get performance statistics (admin endpoint)"""
    try:
        stats = get_performance_report()
        return jsonify(stats)
    except Exception as e:
        logger.exception("Error getting performance stats")
        return jsonify({'error': 'Unable to get performance stats'}), 500

# SECURITY: Removed public job listing endpoint to prevent data leakage
# Job history is now handled client-side using localStorage

# Cleanup old files on startup and periodically
cleanup_old_files()

def periodic_cleanup():
    """Run cleanup every configured interval"""
    while True:
        time.sleep(config.CLEANUP_INTERVAL)
        cleanup_old_files()

# Start cleanup thread
cleanup_thread = threading.Thread(target=periodic_cleanup)
cleanup_thread.daemon = True
cleanup_thread.start()

if __name__ == '__main__':
    app.run(
        debug=config.DEBUG,
        host=config.HOST,
        port=config.PORT
    )