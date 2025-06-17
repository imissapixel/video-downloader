#!/usr/bin/env python3
"""
Video Downloader Web Interface
Flask-based web application for the video downloader with support for simple URLs and advanced JSON configurations
Supports both development and production environments via environment variables
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

# Load environment variables from .env file if it exists
def load_env_file():
    env_file = Path('.env')
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    os.environ.setdefault(key.strip(), value.strip())

load_env_file()

# Configuration from environment variables
def get_bool_env(key, default=False):
    """Convert environment variable to boolean"""
    value = os.environ.get(key, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')

def get_int_env(key, default=0):
    """Convert environment variable to integer"""
    try:
        return int(os.environ.get(key, default))
    except ValueError:
        return default

def get_list_env(key, default=None):
    """Convert comma-separated environment variable to list"""
    if default is None:
        default = []
    value = os.environ.get(key, '')
    return [item.strip() for item in value.split(',') if item.strip()] or default

# Environment configuration
FLASK_ENV = os.environ.get('FLASK_ENV', 'development')
IS_PRODUCTION = FLASK_ENV == 'production'

# Flask app configuration
SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-this')
if SECRET_KEY in ('your-secret-key-change-this', 'dev-secret-key-change-this') and IS_PRODUCTION:
    raise ValueError("You must set a secure SECRET_KEY environment variable for production!")

HOST = os.environ.get('HOST', '0.0.0.0')
PORT = get_int_env('PORT', 80 if IS_PRODUCTION else 5000)
DEBUG = get_bool_env('DEBUG', not IS_PRODUCTION)
MAX_CONTENT_LENGTH = get_int_env('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)

# CORS configuration
CORS_ORIGINS = get_list_env('CORS_ORIGINS', [
    "chrome-extension://*", 
    "moz-extension://*", 
    "https://dl.xtend3d.com",
    "http://localhost:5000"
])

# Download configuration
DOWNLOADS_DIR = Path(os.environ.get('DOWNLOADS_DIR', 'static/downloads'))
CLEANUP_INTERVAL = get_int_env('CLEANUP_INTERVAL', 3600)
FILE_RETENTION_HOURS = get_int_env('FILE_RETENTION_HOURS', 2 if IS_PRODUCTION else 1)

# Logging configuration
LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
LOG_FILE = os.environ.get('LOG_FILE', 'video_downloader.log')

# Content Security Policy
CSP_STRING = (
    "default-src 'self'; "
    "script-src 'self' https://cdn.jsdelivr.net; "
    "style-src 'self' https://cdn.jsdelivr.net 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self' https://cdn.jsdelivr.net;"
)

# Import our existing video downloader
from video_downloader import download_video, check_dependencies, get_available_formats, setup_output_directory
# Import security utilities
from security_utils import validate_download_request, SecurityError, InputValidator
# Import rate limiting
from rate_limiter import rate_limit, security_rate_limit, rate_limiter
# Import performance optimization
from performance_optimizer import performance_monitor, get_performance_report

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

# Enable CORS for extension integration
CORS(app, origins=CORS_ORIGINS)

# Set up logging
def setup_logging():
    """Configure logging based on environment"""
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    
    if IS_PRODUCTION:
        # Production logging with rotation
        log_dir = Path(LOG_FILE).parent
        log_dir.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=10
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(log_level)
        
        app.logger.addHandler(file_handler)
        app.logger.setLevel(log_level)
    else:
        # Development logging
        logging.basicConfig(level=log_level)
    
    return logging.getLogger(__name__)

logger = setup_logging()

# Global job storage (in production, use Redis or database)
jobs = {}
job_lock = threading.Lock()

# Track active downloads by URL to prevent duplicates
active_downloads = {}  # url -> job_id
active_downloads_lock = threading.Lock()

# Create downloads directory
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

class MultiDownloadJob:
    def __init__(self, job_id, videos_info, options):
        self.job_id = job_id
        self.videos_info = videos_info  # List of video stream info
        self.options = options
        self.status = 'pending'
        self.progress = 0
        self.message = 'Initializing parallel downloads...'
        self.error = None
        self.completed_videos = 0
        self.total_videos = len(videos_info)
        self.video_jobs = {}  # video_index -> individual job status
        self.file_paths = []  # List of downloaded file paths
        self.created_at = datetime.now()
        self.completed_at = None
        
        # Initialize individual video job tracking
        for i in range(self.total_videos):
            self.video_jobs[i] = {
                'status': 'pending',
                'progress': 0,
                'message': 'Waiting to start...',
                'error': None,
                'file_path': None
            }

def cleanup_old_files():
    """Clean up files older than configured retention time"""
    try:
        cutoff_time = datetime.now() - timedelta(hours=FILE_RETENTION_HOURS)
        for file_path in DOWNLOADS_DIR.glob('*'):
            if file_path.is_file():
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_time < cutoff_time:
                    file_path.unlink()
                    logger.info(f"Cleaned up old file: {file_path}")
    except Exception as e:
        logger.error(f"Error during cleanup: {e}")

def download_worker(job_id):
    """Background worker for downloading videos"""
    with job_lock:
        job = jobs.get(job_id)
        if not job:
            return

    def update_progress(message):
        """Update job progress message"""
        with job_lock:
            if job_id in jobs:
                jobs[job_id].message = message

    try:
        job.status = 'downloading'
        update_progress('Initializing download...')
        
        # Create unique output directory for this job
        output_dir = DOWNLOADS_DIR / job_id
        output_dir.mkdir(exist_ok=True)
        
        update_progress('Extracting video information...')
        
        # Download the video with all advanced options
        result = download_video(
            job.stream_info,
            str(output_dir),
            job.options.get('format', 'mp4'),
            job.options.get('quality', 'best'),
            job.options.get('filename'),
            job.options.get('verbose', False),
            progress_callback=update_progress,
            # Pass all advanced options
            videoQualityAdvanced=job.options.get('videoQualityAdvanced', ''),
            audioQuality=job.options.get('audioQuality', 'best'),
            audioFormat=job.options.get('audioFormat', 'best'),
            containerAdvanced=job.options.get('containerAdvanced', ''),
            rateLimit=job.options.get('rateLimit', ''),
            retries=job.options.get('retries', '10'),
            concurrentFragments=job.options.get('concurrentFragments', '1'),
            extractAudio=job.options.get('extractAudio', False),
            embedSubs=job.options.get('embedSubs', False),
            embedThumbnail=job.options.get('embedThumbnail', False),
            embedMetadata=job.options.get('embedMetadata', False),
            keepFragments=job.options.get('keepFragments', False),
            writeSubs=job.options.get('writeSubs', False),
            autoSubs=job.options.get('autoSubs', False),
            subtitleLangs=job.options.get('subtitleLangs', ''),
            subtitleFormat=job.options.get('subtitleFormat', 'best')
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
        
        # Clean up active downloads tracking
        download_url = job.stream_info.get('url', '')
        if download_url:
            with active_downloads_lock:
                if download_url in active_downloads and active_downloads[download_url] == job_id:
                    del active_downloads[download_url]

def multi_download_worker(job_id):
    """Background worker for downloading multiple videos in parallel"""
    with job_lock:
        job = jobs.get(job_id)
        if not job or not isinstance(job, MultiDownloadJob):
            return

    def update_overall_progress():
        """Update overall job progress based on individual video progress"""
        with job_lock:
            if job_id not in jobs:
                return
            
            total_progress = sum(video_job['progress'] for video_job in job.video_jobs.values())
            job.progress = total_progress // job.total_videos
            
            completed = sum(1 for video_job in job.video_jobs.values() if video_job['status'] == 'completed')
            failed = sum(1 for video_job in job.video_jobs.values() if video_job['status'] == 'failed')
            
            if completed == job.total_videos:
                job.status = 'completed'
                job.message = f'All {job.total_videos} videos downloaded successfully'
                job.completed_at = datetime.now()
            elif failed > 0 and (completed + failed) == job.total_videos:
                job.status = 'completed_with_errors'
                job.message = f'{completed} videos completed, {failed} failed'
                job.completed_at = datetime.now()
            else:
                job.status = 'downloading'
                job.message = f'Downloading {job.total_videos} videos... ({completed} completed, {failed} failed)'

    def download_single_video(video_index, video_info):
        """Download a single video within the multi-download job"""
        try:
            # Update video job status
            with job_lock:
                if job_id in jobs:
                    job.video_jobs[video_index]['status'] = 'downloading'
                    job.video_jobs[video_index]['message'] = 'Starting download...'
            
            # Create unique output directory for this video
            output_dir = DOWNLOADS_DIR / job_id / f"video_{video_index + 1}"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            def video_progress_callback(message):
                """Update progress for individual video"""
                with job_lock:
                    if job_id in jobs:
                        job.video_jobs[video_index]['message'] = message
                        # Estimate progress based on message content
                        if 'completed' in message.lower():
                            job.video_jobs[video_index]['progress'] = 100
                        elif 'download' in message.lower():
                            job.video_jobs[video_index]['progress'] = 50
                        elif 'extract' in message.lower():
                            job.video_jobs[video_index]['progress'] = 25
                        update_overall_progress()
            
            # Download the video
            result = download_video(
                video_info,
                str(output_dir),
                job.options.get('format', 'mp4'),
                job.options.get('quality', 'best'),
                job.options.get('filename'),
                job.options.get('verbose', False),
                progress_callback=video_progress_callback,
                # Pass all advanced options
                videoQualityAdvanced=job.options.get('videoQualityAdvanced', ''),
                audioQuality=job.options.get('audioQuality', 'best'),
                audioFormat=job.options.get('audioFormat', 'best'),
                containerAdvanced=job.options.get('containerAdvanced', ''),
                rateLimit=job.options.get('rateLimit', ''),
                retries=job.options.get('retries', '10'),
                concurrentFragments=job.options.get('concurrentFragments', '1'),
                extractAudio=job.options.get('extractAudio', False),
                embedSubs=job.options.get('embedSubs', False),
                embedThumbnail=job.options.get('embedThumbnail', False),
                embedMetadata=job.options.get('embedMetadata', False),
                keepFragments=job.options.get('keepFragments', False),
                writeSubs=job.options.get('writeSubs', False),
                autoSubs=job.options.get('autoSubs', False),
                subtitleLangs=job.options.get('subtitleLangs', ''),
                subtitleFormat=job.options.get('subtitleFormat', 'best')
            )
            
            with job_lock:
                if job_id in jobs:
                    if result['success']:
                        job.video_jobs[video_index]['status'] = 'completed'
                        job.video_jobs[video_index]['progress'] = 100
                        job.video_jobs[video_index]['message'] = 'Download completed'
                        
                        # Find the downloaded file
                        files = list(output_dir.glob('*'))
                        if files:
                            job.video_jobs[video_index]['file_path'] = str(files[0])
                            job.file_paths.append(str(files[0]))
                    else:
                        job.video_jobs[video_index]['status'] = 'failed'
                        job.video_jobs[video_index]['error'] = result.get('error', 'Unknown error')
                        job.video_jobs[video_index]['message'] = f'Failed: {job.video_jobs[video_index]["error"]}'
                    
                    update_overall_progress()
                    
        except Exception as e:
            with job_lock:
                if job_id in jobs:
                    job.video_jobs[video_index]['status'] = 'failed'
                    job.video_jobs[video_index]['error'] = str(e)
                    job.video_jobs[video_index]['message'] = f'Failed: {str(e)}'
                    update_overall_progress()
            logger.exception(f"Video {video_index + 1} in job {job_id} failed")

    try:
        job.status = 'downloading'
        
        # Start parallel downloads using threading
        threads = []
        for i, video_info in enumerate(job.videos_info):
            thread = threading.Thread(target=download_single_video, args=(i, video_info))
            thread.daemon = True
            threads.append(thread)
            thread.start()
        
        # Wait for all downloads to complete
        for thread in threads:
            thread.join()
            
    except Exception as e:
        with job_lock:
            if job_id in jobs:
                job.status = 'failed'
                job.error = str(e)
                job.message = f'Multi-download failed: {str(e)}'
                job.completed_at = datetime.now()
        logger.exception(f"Multi-download job {job_id} failed")
    
    finally:
        # Clean up active downloads tracking for all videos
        for video_info in job.videos_info:
            download_url = video_info.get('url', '')
            if download_url:
                with active_downloads_lock:
                    if download_url in active_downloads and active_downloads[download_url] == job_id:
                        del active_downloads[download_url]

@app.route('/')
def index():
    """Main page with download interface"""
    # Check dependencies
    deps = check_dependencies()
    return render_template('index.html', dependencies=deps)

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
    """Start a new download job with security validation and duplicate prevention"""
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
        
        options = {
            'format': validated_data['format'],
            'quality': validated_data['quality'],
            'filename': validated_data['filename'],
            'verbose': validated_data['verbose'],
            # Advanced options
            'videoQualityAdvanced': validated_data.get('videoQualityAdvanced', ''),
            'audioQuality': validated_data.get('audioQuality', 'best'),
            'audioFormat': validated_data.get('audioFormat', 'best'),
            'containerAdvanced': validated_data.get('containerAdvanced', ''),
            'rateLimit': validated_data.get('rateLimit', ''),
            'retries': validated_data.get('retries', '10'),
            'concurrentFragments': validated_data.get('concurrentFragments', '1'),
            'extractAudio': validated_data.get('extractAudio', False),
            'embedSubs': validated_data.get('embedSubs', False),
            'embedThumbnail': validated_data.get('embedThumbnail', False),
            'embedMetadata': validated_data.get('embedMetadata', False),
            'keepFragments': validated_data.get('keepFragments', False),
            'writeSubs': validated_data.get('writeSubs', False),
            'autoSubs': validated_data.get('autoSubs', False),
            'subtitleLangs': validated_data.get('subtitleLangs', ''),
            'subtitleFormat': validated_data.get('subtitleFormat', 'best')
        }
        
        if validated_data.get('is_multi', False):
            # Multi-video download
            videos_info = validated_data['videos']
            
            # Check for duplicate downloads for each video
            duplicate_urls = []
            with active_downloads_lock:
                for video_info in videos_info:
                    download_url = video_info.get('url', '')
                    if download_url in active_downloads:
                        existing_job_id = active_downloads[download_url]
                        with job_lock:
                            if existing_job_id in jobs:
                                existing_job = jobs[existing_job_id]
                                time_since_created = (datetime.now() - existing_job.created_at).total_seconds()
                                if existing_job.status in ['pending', 'downloading'] and time_since_created < 30:
                                    duplicate_urls.append(download_url)
            
            if duplicate_urls:
                logger.info(f"Recent duplicate download requests found for {len(duplicate_urls)} videos")
                return jsonify({'success': False, 'error': f'Some videos are already being downloaded'})
            
            # Create multi-download job
            job = MultiDownloadJob(job_id, videos_info, options)
            
            # Add to job storage and track all video URLs
            with job_lock:
                jobs[job_id] = job
            
            with active_downloads_lock:
                for video_info in videos_info:
                    download_url = video_info.get('url', '')
                    if download_url:
                        active_downloads[download_url] = job_id
            
            # Start multi-download in background
            thread = threading.Thread(target=multi_download_worker, args=(job_id,))
            thread.daemon = True
            thread.start()
            
            logger.info(f"Started multi-download job {job_id} for {len(videos_info)} videos")
            return jsonify({'success': True, 'job_id': job_id, 'is_multi': True, 'video_count': len(videos_info)})
            
        else:
            # Single video download (existing logic)
            stream_info = validated_data['stream_info']
            download_url = stream_info.get('url', '')
            
            # Check for duplicate downloads (only for very recent requests within 30 seconds)
            with active_downloads_lock:
                if download_url in active_downloads:
                    existing_job_id = active_downloads[download_url]
                    # Check if the existing job is still active and recent
                    with job_lock:
                        if existing_job_id in jobs:
                            existing_job = jobs[existing_job_id]
                            # Only prevent duplicates if job is active AND created within last 30 seconds
                            time_since_created = (datetime.now() - existing_job.created_at).total_seconds()
                            if existing_job.status in ['pending', 'downloading'] and time_since_created < 30:
                                logger.info(f"Recent duplicate download request for {download_url}, returning existing job {existing_job_id}")
                                return jsonify({'success': True, 'job_id': existing_job_id, 'duplicate': True})
                            else:
                                # Job completed/failed or too old, remove from active downloads
                                logger.info(f"Removing stale download tracking for {download_url} (status: {existing_job.status}, age: {time_since_created}s)")
                                del active_downloads[download_url]
            
            # Create single download job
            job = DownloadJob(job_id, stream_info, options)
            
            # Add to both job storage and active downloads
            with job_lock:
                jobs[job_id] = job
            
            with active_downloads_lock:
                active_downloads[download_url] = job_id
            
            # Start download in background
            thread = threading.Thread(target=download_worker, args=(job_id,))
            thread.daemon = True
            thread.start()
            
            logger.info(f"Started secure download job {job_id} for URL: {download_url}")
            return jsonify({'success': True, 'job_id': job_id})
        
    except SecurityError as e:
        logger.warning(f"Security error in download request: {e}")
        return jsonify({'success': False, 'error': f'Security error: {str(e)}'})
    except Exception as e:
        logger.exception("Unexpected error starting download")
        return jsonify({'success': False, 'error': 'Download request failed'})

@app.route('/api/status/<job_id>')
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
    
    # Base response for all job types
    response = {
        'job_id': job.job_id,
        'status': job.status,
        'progress': job.progress,
        'message': job.message,
        'error': error_message,
        'created_at': job.created_at.isoformat(),
        'completed_at': job.completed_at.isoformat() if job.completed_at else None
    }
    
    # Handle multi-video jobs
    if isinstance(job, MultiDownloadJob):
        response.update({
            'is_multi': True,
            'total_videos': job.total_videos,
            'completed_videos': job.completed_videos,
            'video_jobs': job.video_jobs,
            'has_files': len(job.file_paths) > 0,
            'file_count': len(job.file_paths)
        })
    else:
        # Single video job
        response.update({
            'is_multi': False,
            'has_file': bool(job.file_path and os.path.exists(job.file_path))
        })
    
    return jsonify(response)

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
    
    # Handle multi-video jobs
    if isinstance(job, MultiDownloadJob):
        if job.status not in ['completed', 'completed_with_errors'] or not job.file_paths:
            return jsonify({'error': 'Files not ready'}), 400
        
        # For multi-video jobs, create a ZIP file containing all downloaded videos
        return create_multi_video_zip(job, job_id)
    
    # Handle single video jobs
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

def create_multi_video_zip(job, job_id):
    """Create a ZIP file containing all videos from a multi-video job"""
    import zipfile
    import tempfile
    
    try:
        # Create a temporary ZIP file
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        temp_zip.close()
        
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for i, file_path in enumerate(job.file_paths):
                try:
                    file_path_obj = Path(file_path).resolve()
                    downloads_dir = DOWNLOADS_DIR.resolve()
                    
                    # Security check
                    file_path_obj.relative_to(downloads_dir)
                    
                    if file_path_obj.exists():
                        # Add file to ZIP with a clean name
                        original_name = file_path_obj.name
                        safe_name = InputValidator.validate_filename(original_name)
                        if not safe_name:
                            safe_name = f"video_{i+1}.{file_path_obj.suffix.lstrip('.')}"
                        
                        zip_file.write(str(file_path_obj), safe_name)
                        logger.info(f"Added {safe_name} to ZIP for job {job_id}")
                    else:
                        logger.warning(f"File not found for ZIP: {file_path}")
                        
                except Exception as e:
                    logger.error(f"Error adding file {file_path} to ZIP: {e}")
                    continue
        
        # Send the ZIP file
        zip_filename = f"batch_download_{job_id[:8]}.zip"
        
        def remove_temp_file():
            """Remove temporary file after sending"""
            try:
                Path(temp_zip.name).unlink()
            except Exception as e:
                logger.error(f"Error removing temp ZIP file: {e}")
        
        # Schedule cleanup after response
        import atexit
        atexit.register(remove_temp_file)
        
        return send_file(
            temp_zip.name, 
            as_attachment=True, 
            download_name=zip_filename,
            mimetype='application/zip'
        )
        
    except Exception as e:
        logger.exception(f"Error creating ZIP file for job {job_id}: {e}")
        return jsonify({'error': 'Failed to create download package'}), 500

@app.route('/api/get-formats', methods=['POST'])
@rate_limit('requests')
def get_formats():
    """Get available video formats and qualities for a URL"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Validate and extract stream info
        validated_data = validate_download_request(data)
        stream_info = validated_data['stream_info']
        
        url = stream_info.get('url')
        headers = stream_info.get('headers')
        cookies = stream_info.get('cookies')
        referer = stream_info.get('referer')
        user_agent = stream_info.get('userAgent')
        
        # Get available formats
        formats_result = get_available_formats(url, headers, cookies, referer, user_agent)
        
        if formats_result['success']:
            return jsonify({
                'success': True,
                'available_qualities': formats_result['available_qualities'],
                'url': url
            })
        else:
            return jsonify({
                'success': False,
                'error': formats_result['error'],
                'available_qualities': []
            })
            
    except SecurityError as e:
        logger.warning(f"Security validation failed for format detection: {e}")
        return jsonify({'error': f'Security validation failed: {e}'}), 400
    except Exception as e:
        logger.error(f"Error getting formats: {e}")
        return jsonify({'error': 'Failed to get available formats'}), 500

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
        
        # Add active downloads info
        with active_downloads_lock:
            stats['active_downloads'] = len(active_downloads)
            
        with job_lock:
            active_jobs = sum(1 for job in jobs.values() if job.status in ['pending', 'downloading'])
            stats['active_jobs'] = active_jobs
            
        return jsonify(stats)
    except Exception as e:
        logger.exception("Error getting performance stats")
        return jsonify({'error': 'Unable to get performance stats'}), 500

# SECURITY: Removed public job listing endpoint to prevent data leakage
# Job history is now handled client-side using localStorage

# Cleanup old files on startup and periodically
cleanup_old_files()

def periodic_cleanup():
    """Run cleanup at configured intervals"""
    while True:
        time.sleep(CLEANUP_INTERVAL)
        cleanup_old_files()
        cleanup_stale_downloads()

def cleanup_stale_downloads():
    """Clean up stale active downloads that may have been orphaned"""
    try:
        current_time = datetime.now()
        stale_urls = []
        
        with active_downloads_lock:
            for url, job_id in active_downloads.items():
                with job_lock:
                    job = jobs.get(job_id)
                    if not job:
                        # Job doesn't exist, mark URL as stale
                        stale_urls.append(url)
                    elif job.completed_at and (current_time - job.completed_at).total_seconds() > 300:  # 5 minutes
                        # Job completed more than 5 minutes ago, clean up
                        stale_urls.append(url)
                    elif job.created_at and (current_time - job.created_at).total_seconds() > 3600:  # 1 hour
                        # Job is too old, likely stuck, clean up
                        stale_urls.append(url)
            
            # Remove stale URLs
            for url in stale_urls:
                if url in active_downloads:
                    logger.info(f"Cleaning up stale download tracking for URL: {url}")
                    del active_downloads[url]
                    
    except Exception as e:
        logger.exception("Error during stale download cleanup")

# Start cleanup thread
cleanup_thread = threading.Thread(target=periodic_cleanup)
cleanup_thread.daemon = True
cleanup_thread.start()

@app.after_request
def add_security_headers(response):
    response.headers['Content-Security-Policy'] = CSP_STRING
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    return response

if __name__ == '__main__':
    logger.info(f"Starting Video Downloader Web Interface")
    logger.info(f"Environment: {FLASK_ENV}")
    logger.info(f"Debug mode: {DEBUG}")
    logger.info(f"Host: {HOST}:{PORT}")
    logger.info(f"Downloads directory: {DOWNLOADS_DIR}")
    logger.info(f"File retention: {FILE_RETENTION_HOURS} hours")
    
    app.run(debug=DEBUG, host=HOST, port=PORT)