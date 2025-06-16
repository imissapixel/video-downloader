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
def check_deps():
    """API endpoint to check dependencies"""
    deps = check_dependencies()
    return jsonify(deps)

@app.route('/api/validate-json', methods=['POST'])
def validate_json():
    """Validate JSON input"""
    try:
        data = request.get_json()
        json_str = data.get('json_string', '')
        
        # Try to parse the JSON
        parsed = json.loads(json_str)
        
        # Basic validation
        if 'url' not in parsed:
            return jsonify({'valid': False, 'error': 'JSON must contain a "url" field'})
        
        return jsonify({'valid': True, 'parsed': parsed})
    
    except json.JSONDecodeError as e:
        return jsonify({'valid': False, 'error': f'Invalid JSON: {str(e)}'})
    except Exception as e:
        return jsonify({'valid': False, 'error': str(e)})

@app.route('/api/download', methods=['POST'])
def start_download():
    """Start a new download job"""
    try:
        data = request.get_json()
        
        # Generate unique job ID
        job_id = str(uuid.uuid4())
        
        # Parse input based on mode
        mode = data.get('mode', 'simple')
        
        if mode == 'simple':
            stream_info = {
                'url': data.get('url', '').strip()
            }
            if not stream_info['url']:
                return jsonify({'success': False, 'error': 'URL is required'})
                
        elif mode == 'json':
            try:
                stream_info = json.loads(data.get('json_string', '{}'))
            except json.JSONDecodeError as e:
                return jsonify({'success': False, 'error': f'Invalid JSON: {str(e)}'})
                
        else:
            return jsonify({'success': False, 'error': 'Invalid mode'})
        
        # Extract options
        options = {
            'format': data.get('format', 'mp4'),
            'quality': data.get('quality', 'best'),
            'filename': data.get('filename', '').strip() or None,
            'verbose': data.get('verbose', False)
        }
        
        # Create job
        job = DownloadJob(job_id, stream_info, options)
        
        with job_lock:
            jobs[job_id] = job
        
        # Start download in background
        thread = threading.Thread(target=download_worker, args=(job_id,))
        thread.daemon = True
        thread.start()
        
        logger.info(f"Started download job {job_id} for URL: {stream_info.get('url', 'unknown')}")
        return jsonify({'success': True, 'job_id': job_id})
        
    except Exception as e:
        logger.exception("Error starting download")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/status/<job_id>')
def get_status(job_id):
    """Get status of a download job"""
    with job_lock:
        job = jobs.get(job_id)
        
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify({
        'job_id': job.job_id,
        'status': job.status,
        'progress': job.progress,
        'message': job.message,
        'error': job.error,
        'created_at': job.created_at.isoformat(),
        'completed_at': job.completed_at.isoformat() if job.completed_at else None,
        'has_file': bool(job.file_path and os.path.exists(job.file_path))
    })

@app.route('/api/download-file/<job_id>')
def download_file(job_id):
    """Download the completed file"""
    with job_lock:
        job = jobs.get(job_id)
    
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    if job.status != 'completed' or not job.file_path:
        return jsonify({'error': 'File not ready'}), 400
    
    if not os.path.exists(job.file_path):
        return jsonify({'error': 'File not found'}), 404
    
    filename = os.path.basename(job.file_path)
    return send_file(job.file_path, as_attachment=True, download_name=filename)

@app.route('/api/jobs')
def list_jobs():
    """List all jobs (for debugging)"""
    with job_lock:
        job_list = []
        for job in jobs.values():
            job_list.append({
                'job_id': job.job_id,
                'status': job.status,
                'message': job.message,
                'created_at': job.created_at.isoformat()
            })
    
    return jsonify(job_list)

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