#!/usr/bin/env python3
"""
Video Downloader - Command-line tool for downloading videos from URLs with enhanced metadata support
Compatible with Ubuntu, WSL, and Mac Terminal
"""

import argparse
import json
import os
import re
import sys
import subprocess
import logging
import shutil
import tempfile
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger('video_downloader')

def setup_output_directory(output_dir=None):
    if output_dir:
        directory = Path(output_dir).expanduser().resolve()
    else:
        directory = Path.home() / "Downloads"
    try:
        directory.mkdir(parents=True, exist_ok=True)
        logger.info(f"Output directory: {directory}")
        return str(directory)
    except Exception as e:
        logger.error(f"Failed to create output directory {directory}: {e}")
        fallback_dir = os.getcwd()
        logger.info(f"Falling back to current directory: {fallback_dir}")
        return fallback_dir

def sanitize_filename(filename):
    sanitized = re.sub(r'[\\/*?:"<>|]', '_', filename)
    sanitized = sanitized.strip('. ')
    return sanitized or "video"

def is_url(url):
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except:
        return False

def check_dependencies():
    dependencies = {"yt-dlp": False, "ffmpeg": False}
    try:
        subprocess.run(["yt-dlp", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        dependencies["yt-dlp"] = True
    except Exception:
        logger.warning("yt-dlp not found")
    try:
        subprocess.run(["ffmpeg", "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        dependencies["ffmpeg"] = True
    except Exception:
        logger.warning("ffmpeg not found")
    return dependencies

def install_dependencies():
    logger.info("Attempting to install missing dependencies...")
    try:
        subprocess.run(["pip", "install", "yt-dlp"], check=True)
        logger.info("Successfully installed yt-dlp")
    except Exception as e:
        logger.error(f"Failed to install yt-dlp: {str(e)}")
        logger.info("Please install yt-dlp manually: pip install yt-dlp")
    import platform
    system = platform.system()
    if system == "Linux":
        logger.info("To install ffmpeg on Ubuntu/Debian: sudo apt-get install ffmpeg")
    elif system == "Darwin":
        logger.info("To install ffmpeg on macOS with Homebrew: brew install ffmpeg")
    elif system == "Windows":
        logger.info("To install ffmpeg on Windows, download from: https://ffmpeg.org/download.html")

def is_supported_by_ytdlp(url):
    supported_domains = [
        'youtube.com', 'youtu.be', 'vimeo.com', 'dailymotion.com', 'facebook.com',
        'twitter.com', 'instagram.com', 'twitch.tv', 'tiktok.com', 'reddit.com',
        'soundcloud.com', 'bandcamp.com', 'vk.com', 'bilibili.com'
    ]
    try:
        domain = urlparse(url).netloc.lower()
        return any(domain == sd or domain.endswith('.' + sd) for sd in supported_domains)
    except:
        return False


def is_youtube_url(url):
    """Check if URL is a YouTube URL"""
    try:
        domain = urlparse(url).netloc.lower()
        return 'youtube.com' in domain or 'youtu.be' in domain
    except:
        return False

def create_temp_cookies_file(cookies, url):
    if not cookies:
        logger.info("No cookies provided")
        return None

    # Ensure cookies is a string
    if not isinstance(cookies, str):
        logger.error(f"Cookies is not a string: {type(cookies)}")
        return None
        
    # Remove any problematic characters that might cause parsing issues
    cookies = cookies.replace('\n', '').replace('\r', '')
        
    logger.info(f"Processing cookies for URL: {url}")
    logger.info(f"Cookies length: {len(cookies)} characters")

    # Count cookies for debugging
    cookie_count = len([c for c in cookies.split(';') if '=' in c.strip()])
    logger.info(f"Found {cookie_count} cookies to process")

    try:
        fd, cookies_file = tempfile.mkstemp(suffix='.txt')
        os.close(fd)
        with open(cookies_file, 'w') as f:
            # Write Netscape cookie file header
            f.write("# Netscape HTTP Cookie File\n")
            f.write("# This is a generated file! Do not edit.\n\n")

            parsed_url = urlparse(url)
            domain = parsed_url.netloc

            # Always use .youtube.com for YouTube cookies to ensure compatibility
            if 'youtube.com' in domain or 'youtu.be' in domain:
                base_domain = '.youtube.com'
                # For YouTube, we need to ensure we have the correct domain format
                # This is critical for authentication to work properly
                if not domain.startswith('.'):
                    domain = '.' + domain
            else:
                # Get the base domain for other sites
                domain_parts = domain.split('.')
                if len(domain_parts) >= 2:
                    base_domain = '.' + '.'.join(domain_parts[-2:])
                else:
                    base_domain = domain
                    
            # Ensure domain starts with a dot for proper cookie matching
            if not base_domain.startswith('.'):
                base_domain = '.' + base_domain

            # Split cookies by semicolon and process each one
            written_cookies = 0
            critical_youtube_cookies = ['VISITOR_INFO1_LIVE', 'YSC', 'GPS', 'PREF', 'CONSENT']
            found_critical = []

            # Handle YouTube cookies specially
            if 'youtube.com' in domain or 'youtu.be' in domain:
                logger.info("Processing YouTube cookies")
                
                try:
                    for cookie in cookies.split(';'):
                        cookie = cookie.strip()
                        if '=' in cookie:
                            parts = cookie.split('=', 1)
                            if len(parts) == 2:
                                name, value = parts
                                name = name.strip()
                                value = value.strip()

                                # Skip empty cookies
                                if not name or not value:
                                    continue

                                # Track critical YouTube cookies
                                if name in critical_youtube_cookies:
                                    found_critical.append(name)

                                # Use base domain for all cookies (YouTube needs this)
                                cookie_domain = base_domain
                                domain_specified = "TRUE"

                                # Set secure flag for __Secure- prefixed cookies and HTTPS sites
                                secure_flag = "TRUE" if (name.startswith('__Secure-') or name.startswith('__Host-') or
                                                      parsed_url.scheme == 'https') else "FALSE"

                                # Set expiration to far future (2038-01-19)
                                expires = "2147483647"

                                # Format: domain, domain_specified, path, secure, expires, name, value
                                f.write(f"{cookie_domain}\tTRUE\t/\t{secure_flag}\t{expires}\t{name}\t{value}\n")
                                written_cookies += 1
                except Exception as e:
                    logger.error(f"Error processing YouTube cookies: {e}")
                    # Write the cookies as a single line as fallback
                    f.write(f".youtube.com\tTRUE\t/\tTRUE\t2147483647\tYOUTUBE_COOKIES\t{cookies}\n")
                    written_cookies = 1
            else:
                # Standard cookie processing for non-YouTube sites
                for cookie in cookies.split(';'):
                    cookie = cookie.strip()
                    if '=' in cookie:
                        try:
                            name, value = cookie.split('=', 1)
                            name = name.strip()
                            value = value.strip()

                            # Skip empty cookies
                            if not name or not value:
                                continue

                            # Use base domain for all cookies
                            cookie_domain = base_domain
                            domain_specified = "TRUE"

                            # Set secure flag for __Secure- prefixed cookies and HTTPS sites
                            secure_flag = "TRUE" if (name.startswith('__Secure-') or name.startswith('__Host-') or
                                                  parsed_url.scheme == 'https') else "FALSE"

                            # Set expiration to far future (2038-01-19)
                            expires = "2147483647"

                            # Format: domain, domain_specified, path, secure, expires, name, value
                            f.write(f"{cookie_domain}\tTRUE\t/\t{secure_flag}\t{expires}\t{name}\t{value}\n")
                            written_cookies += 1
                        except Exception as e:
                            logger.warning(f"Skipping invalid cookie: {cookie}, error: {e}")
                            continue

            logger.info(f"Wrote {written_cookies} cookies to file")
            logger.info(f"Critical YouTube cookies found: {found_critical}")
            missing_critical = [c for c in critical_youtube_cookies if c not in found_critical]
            if missing_critical:
                logger.warning(f"Missing critical YouTube cookies: {missing_critical}")
                logger.warning("This may cause authentication failures. Ensure your browser extension captures HttpOnly cookies.")

        logger.debug(f"Created temporary cookies file: {cookies_file}")

        # Debug: Print the cookies file content
        if logger.level <= logging.DEBUG:
            try:
                with open(cookies_file, 'r') as f:
                    logger.debug(f"Cookies file content:\n{f.read()}")
            except Exception as e:
                logger.debug(f"Could not read cookies file for debug: {e}")

        return cookies_file
    except Exception as e:
        logger.warning(f"Failed to create cookies file: {e}")
        return None

def download_with_ytdlp(url, output_dir, format="mp4", quality="best", custom_filename=None,
                        headers=None, cookies=None, referer=None, user_agent=None, verbose=False, progress_callback=None, **advanced_options):
    cookies_file = None

    # For YouTube URLs, try multiple approaches
    if is_youtube_url(url):
        logger.info("YouTube URL detected. Trying multiple download strategies...")
        # Create a status update that's compatible with our progress_callback
        if progress_callback:
            try:
                # Use simple string for progress callback to avoid errors
                progress_callback("Analyzing YouTube video...")
                logger.info("Progress callback called successfully with string")
            except Exception as e:
                logger.error(f"Error calling progress_callback: {e}")
                # Continue without progress updates

        # Strategy 1: Try with provided cookies first for YouTube (most reliable)
        if cookies:
            logger.info("Trying with provided cookies...")
            if progress_callback:
                try:
                    progress_callback("Attempting download with authentication...")
                    logger.info("Progress callback called successfully")
                except Exception as e:
                    logger.error(f"Error calling progress_callback: {e}")
                        
            result = _try_ytdlp_download(url, output_dir, format, quality, custom_filename,
                                        headers, cookies, referer, user_agent, verbose, progress_callback, strategy="with_cookies")
            if result["success"]:
                return result
                
        # Strategy 2: Try without cookies (sometimes works for public videos)
        if progress_callback:
            try:
                progress_callback("Attempting download without authentication...")
            except Exception as e:
                logger.error(f"Error calling progress_callback: {e}")
                    
        result = _try_ytdlp_download(url, output_dir, format, quality, custom_filename,
                                    headers, None, referer, user_agent, verbose, progress_callback, strategy="no_auth")
        if result["success"]:
            return result

        # Strategy 3: Try with different client settings
        logger.info("Trying with alternative client settings...")
        if progress_callback:
            try:
                progress_callback("Trying alternative download method...")
            except Exception as e:
                logger.error(f"Error calling progress_callback: {e}")
                    
        result = _try_ytdlp_download(url, output_dir, format, quality, custom_filename,
                                    headers, cookies, referer, user_agent, verbose, progress_callback, strategy="alternative")
        if result["success"]:
            return result

        # Strategy 4: Try browser cookies approach (if running on a system with Chrome)
        try:
            logger.info("Trying with browser cookies extraction...")
            if progress_callback:
                try:
                    progress_callback("Attempting browser cookie extraction...")
                except Exception as e:
                    logger.error(f"Error calling progress_callback: {e}")
                        
            result = _try_ytdlp_download(url, output_dir, format, quality, custom_filename,
                                        headers, None, referer, user_agent, verbose, progress_callback, strategy="browser_cookies")
            if result["success"]:
                return result
        except Exception as e:
            logger.info(f"Browser cookies strategy failed: {e}")
            
        # Strategy 5: Last resort - try with cookies in a different format
        if cookies:
            logger.info("Trying with alternative cookie format...")
            if progress_callback:
                try:
                    progress_callback("Trying alternative cookie format...")
                except Exception as e:
                    logger.error(f"Error calling progress_callback: {e}")
            
            # Create a simplified cookies file directly
            try:
                fd, cookies_file = tempfile.mkstemp(suffix='.txt')
                os.close(fd)
                with open(cookies_file, 'w') as f:
                    f.write("# Netscape HTTP Cookie File\n")
                    f.write("# This is a generated file! Do not edit.\n\n")
                    f.write(f".youtube.com\tTRUE\t/\tTRUE\t2147483647\tYOUTUBE_COOKIES\t{cookies}\n")
                
                cmd = [
                    "yt-dlp",
                    "--cookies", cookies_file,
                    "--format", "best",  # Use best available format
                    "--output", os.path.join(output_dir, "%(title)s.%(ext)s"),
                    "--no-playlist",     # Don't download playlists
                    "--no-check-certificate",  # Avoid certificate issues
                    "--socket-timeout", "30",  # Prevent hanging
                    "--retries", "5",    # More retries for this last attempt
                    "--continue",        # Resume partial downloads
                    "--mark-watched",    # Mark as watched if logged in
                    "--extractor-args", "youtube:player_client=web,android",
                    url
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    return {"success": True, "file": "Downloaded"}
            except Exception as e:
                logger.error(f"Alternative cookie format failed: {e}")
            finally:
                if cookies_file and os.path.exists(cookies_file):
                    try:
                        os.remove(cookies_file)
                    except:
                        pass

        return {"success": False, "error": "All YouTube download strategies failed"}

    # For non-YouTube URLs, use the standard approach
    if progress_callback:
        try:
            progress_callback({"status": "downloading", "message": "Downloading media..."})
        except Exception:
            try:
                progress_callback("Downloading media...")
            except Exception:
                pass
    return _try_ytdlp_download(url, output_dir, format, quality, custom_filename,
                              headers, cookies, referer, user_agent, verbose, progress_callback, strategy="standard", **advanced_options)

def _try_ytdlp_download(url, output_dir, format="mp4", quality="best", custom_filename=None,
                       headers=None, cookies=None, referer=None, user_agent=None, verbose=False, progress_callback=None, strategy="standard", **advanced_options):
    cookies_file = None
    try:
        logger.info(f"_try_ytdlp_download called with strategy={strategy}, url={url[:30]}...")
        logger.info(f"Output directory: {output_dir}")
        logger.info(f"Format: {format}, Quality: {quality}")
        
        # Security: Validate all inputs
        if not is_url(url):
            logger.error(f"Invalid URL: {url[:30]}...")
            return {"success": False, "error": "Invalid URL"}

        # Check if output directory exists
        if not os.path.exists(output_dir):
            logger.warning(f"Output directory does not exist: {output_dir}")
            try:
                os.makedirs(output_dir, exist_ok=True)
                logger.info(f"Created output directory: {output_dir}")
            except Exception as e:
                logger.error(f"Failed to create output directory: {e}")
                return {"success": False, "error": f"Failed to create output directory: {str(e)}"}

        # Sanitize output directory and filename
        safe_output_dir = str(Path(output_dir).resolve())
        logger.info(f"Safe output directory: {safe_output_dir}")
        
        if custom_filename:
            safe_filename = sanitize_filename(custom_filename)
            output_template = os.path.join(safe_output_dir, f"{safe_filename}.%(ext)s")
        else:
            output_template = os.path.join(safe_output_dir, "%(title)s.%(ext)s")
            
        logger.info(f"Output template: {output_template}")

        # Debug logging for format selection
        if verbose:
            logger.info(f"Selecting format for quality: {quality}")

        # Validate format selection using best practices from yt-dlp documentation
        if quality == "2160p":
            # 4K quality - prioritize H.264 codec for compatibility
            format_selection = "bestvideo[height<=2160][vcodec^=avc1]+bestaudio/bestvideo[height<=2160][vcodec^=h264]+bestaudio/bestvideo[height<=2160]+bestaudio/best[height<=2160]"
        elif quality == "1440p":
            # 2K quality - prioritize H.264 codec for compatibility
            format_selection = "bestvideo[height<=1440][vcodec^=avc1]+bestaudio/bestvideo[height<=1440][vcodec^=h264]+bestaudio/bestvideo[height<=1440]+bestaudio/best[height<=1440]"
        elif quality == "1080p":
            # 1080p quality - prioritize H.264 codec for compatibility
            format_selection = "bestvideo[height<=1080][vcodec^=avc1]+bestaudio/bestvideo[height<=1080][vcodec^=h264]+bestaudio/bestvideo[height<=1080]+bestaudio/best[height<=1080]"
        elif quality == "1080p60":
            # 1080p 60fps - prioritize H.264 codec for compatibility
            format_selection = "bestvideo[height<=1080][fps>=50][vcodec^=avc1]+bestaudio/bestvideo[height<=1080][fps>=50][vcodec^=h264]+bestaudio/bestvideo[height<=1080][fps>=50]+bestaudio/best[height<=1080][fps>=50]"
        elif quality == "720p":
            # 720p quality - prioritize H.264 codec for compatibility
            format_selection = "bestvideo[height<=720][vcodec^=avc1]+bestaudio/bestvideo[height<=720][vcodec^=h264]+bestaudio/bestvideo[height<=720]+bestaudio/best[height<=720]"
        elif quality == "720p60":
            # 720p 60fps - prioritize H.264 codec for compatibility
            format_selection = "bestvideo[height<=720][fps>=50][vcodec^=avc1]+bestaudio/bestvideo[height<=720][fps>=50][vcodec^=h264]+bestaudio/bestvideo[height<=720][fps>=50]+bestaudio/best[height<=720][fps>=50]"
        elif quality == "480p":
            # 480p quality - prioritize H.264 codec for compatibility
            format_selection = "bestvideo[height<=480][vcodec^=avc1]+bestaudio/bestvideo[height<=480][vcodec^=h264]+bestaudio/bestvideo[height<=480]+bestaudio/best[height<=480]"
        elif quality == "360p":
            # 360p quality - prioritize H.264 codec for compatibility
            format_selection = "bestvideo[height<=360][vcodec^=avc1]+bestaudio/bestvideo[height<=360][vcodec^=h264]+bestaudio/bestvideo[height<=360]+bestaudio/best[height<=360]"
        elif quality == "best":
            # Best quality available - no restrictions
            format_selection = "bestvideo+bestaudio/best"
        else:
            # Fallback for any other quality - default to 1080p
            format_selection = "bestvideo[height<=1080][vcodec^=avc1]+bestaudio/bestvideo[height<=1080][vcodec^=h264]+bestaudio/bestvideo[height<=1080]+bestaudio/best[height<=1080]"

        # Build command based on strategy and yt-dlp documentation
        cmd = [
            "yt-dlp",
            "--format", format_selection,
            "--merge-output-format", format,
            "--output", output_template,
            "--no-playlist",            # Don't download playlists
            "--no-check-certificate",   # Avoid certificate issues
            "--socket-timeout", "30",   # Prevent hanging
            "--retries", "3",           # Limit retries
            "--fragment-retries", "10", # Retry fragments 10 times
            "--no-abort-on-error",      # Continue on errors
            "--ignore-errors",          # Ignore download errors
            "--no-overwrites",          # Don't overwrite files
            "--continue",               # Resume partial downloads
            "--no-cache-dir",           # Disable cache
            "--newline",                # Force progress on newline for better parsing
            "--progress",               # Show progress bar
            "--console-title"           # Show progress in console title
        ]

        # Debug: Log the exact command being executed
        if verbose:
            logger.info(f"Format selection string: {format_selection}")
            logger.info(f"Full yt-dlp command: {' '.join(cmd[:10])}...")  # Show first part of command

        # Add strategy-specific options
        if strategy == "no_auth":
            # Try without authentication, use basic settings
            if is_youtube_url(url):
                cmd.extend(["--extractor-args", "youtube:player_client=android"])
        elif strategy == "alternative":
            # Try alternative settings for difficult videos
            if is_youtube_url(url):
                cmd.extend([
                    "--extractor-args", "youtube:player_client=web,tv",
                    "--extractor-args", "youtube:skip=translated_subs"
                ])
        elif strategy == "browser_cookies":
            # NEW: Try using browser cookies directly (Chrome/Chromium)
            if is_youtube_url(url):
                # Try Chrome first, then Chromium as fallback
                cmd.extend([
                    "--cookies-from-browser", "chrome",
                    "--extractor-args", "youtube:player_client=web,android"
                ])
        else:
            # Standard or with_cookies strategy
            if is_youtube_url(url):
                cmd.extend([
                    # Use web and android clients for better format selection
                    "--extractor-args", "youtube:player_client=web,android",
                    # Skip translated subtitles but keep DASH formats
                    "--extractor-args", "youtube:skip=translated_subs",
                    # Mark video as watched if logged in
                    "--mark-watched"
                ])

        # Add verbosity flag
        cmd.append("--verbose" if verbose else "--quiet")

        # Add advanced options
        rate_limit = advanced_options.get('rateLimit', '')
        if rate_limit:
            cmd.extend(["--limit-rate", rate_limit])

        retries = advanced_options.get('retries', '10')
        if retries != '10':  # Only add if different from default
            cmd.extend(["--retries", retries])

        concurrent_fragments = advanced_options.get('concurrentFragments', '1')
        if concurrent_fragments != '1':  # Only add if different from default
            cmd.extend(["--concurrent-fragments", concurrent_fragments])

        # Audio extraction
        if advanced_options.get('extractAudio', False):
            cmd.append("--extract-audio")
            audio_format = advanced_options.get('audioFormat', 'best')
            if audio_format != 'best':
                cmd.extend(["--audio-format", audio_format])
            audio_quality = advanced_options.get('audioQuality', 'best')
            if audio_quality != 'best':
                cmd.extend(["--audio-quality", audio_quality])

        # Subtitle options - following yt-dlp documentation
        if advanced_options.get('writeSubs', False):
            cmd.append("--write-subs")  # Write subtitle file
        if advanced_options.get('autoSubs', False):
            cmd.append("--write-auto-subs")  # Write automatically generated subtitles

        # Handle subtitle languages
        subtitle_langs = advanced_options.get('subtitleLangs', '')
        if subtitle_langs:
            cmd.extend(["--sub-langs", subtitle_langs])  # Languages to download
        elif advanced_options.get('writeSubs', False) or advanced_options.get('autoSubs', False):
            # If subs are requested but no language specified, default to all
            cmd.extend(["--sub-langs", "all"])

        # Handle subtitle format
        subtitle_format = advanced_options.get('subtitleFormat', 'best')
        if subtitle_format != 'best':
            cmd.extend(["--sub-format", subtitle_format])
        else:
            # Default to srt if not specified (most compatible)
            cmd.extend(["--sub-format", "srt/best"])

        # Embedding options - following yt-dlp documentation
        if advanced_options.get('embedSubs', False):
            cmd.append("--embed-subs")  # Embed subtitles in the video
            # Make sure we're writing subs if we want to embed them
            if not advanced_options.get('writeSubs', False) and not advanced_options.get('autoSubs', False):
                cmd.append("--write-subs")
                
        if advanced_options.get('embedThumbnail', False):
            cmd.append("--embed-thumbnail")  # Embed thumbnail in the video/audio file
            # Add yt-dlp recommended option for embedding thumbnails
            cmd.append("--convert-thumbnails")
            cmd.append("jpg")
            
        if advanced_options.get('embedMetadata', False):
            cmd.append("--embed-metadata")  # Embed metadata in the video file
            cmd.append("--add-metadata")    # Write metadata to file

        # Fragment options
        if advanced_options.get('keepFragments', False):
            cmd.append("--keep-fragments")  # Keep downloaded fragments
        else:
            cmd.append("--no-keep-fragments")  # Delete fragments after download

        # Post-processing: Convert to H.264 only if format is MP4 and NOT audio-only
        if format.lower() == "mp4" and not advanced_options.get('extractAudio', False):
            # Use recommended settings from yt-dlp documentation for MP4
            cmd.extend([
                # Use libx264 for video, aac for audio, and optimize for streaming
                "--postprocessor-args", "ffmpeg:-c:v libx264 -preset medium -c:a aac -movflags +faststart",
                # Force recode to ensure compatibility
                "--recode-video", "mp4"
            ])
            # Add additional quality settings if needed
            if "1080" in quality or "720" in quality:
                cmd.extend([
                    # For HD content, use a good balance of quality and size
                    "--postprocessor-args", "ffmpeg:-crf 18"
                ])
            elif "2160" in quality or "1440" in quality:
                cmd.extend([
                    # For 4K/2K content, use slightly higher compression
                    "--postprocessor-args", "ffmpeg:-crf 22"
                ])

        # Security: Validate and sanitize headers
        if headers and isinstance(headers, dict):
            for name, value in headers.items():
                # Validate header name and value
                if isinstance(name, str) and isinstance(value, str):
                    # Remove dangerous characters
                    safe_name = re.sub(r'[^\w-]', '', name)
                    safe_value = re.sub(r'[\r\n]', '', value)
                    if safe_name and safe_value:
                        cmd.extend(["--add-header", f"{safe_name}: {safe_value}"])

        # Security: Handle cookies safely
        if cookies:
            # Ensure cookies is a string
            if not isinstance(cookies, str):
                try:
                    cookies = str(cookies)
                    logger.warning("Converted cookies to string")
                except Exception as e:
                    logger.error(f"Failed to convert cookies to string: {e}")
                    cookies = None
                    
            if cookies:
                cookies_file = create_temp_cookies_file(cookies, url)
                if cookies_file:
                    cmd.extend(["--cookies", cookies_file])
                    # For YouTube, add extra arguments to help with authentication
                    if is_youtube_url(url):
                        cmd.extend(["--mark-watched"])  # Mark as watched if logged in
                        cmd.extend(["--no-check-certificates"])  # Skip certificate validation

        # Security: Validate referer
        if referer and isinstance(referer, str) and is_url(referer):
            cmd.extend(["--referer", referer])

        # Security: Validate user agent
        if user_agent and isinstance(user_agent, str):
            # Remove dangerous characters from user agent
            safe_ua = re.sub(r'[^\w\s\-\.\(\);:/]', '', user_agent)[:512]
            if safe_ua:
                cmd.extend(["--user-agent", safe_ua])

        # Add URL as the last argument
        cmd.append(url)

        # Execute with security measures
        logger.debug(f"Executing yt-dlp command: {' '.join(cmd[:5])}... [URL hidden]")

        if progress_callback:
            try:
                # Use simple string for progress callback to avoid errors
                progress_callback("Downloading media...")
                logger.info("Progress callback called for download start")
            except Exception as e:
                logger.error(f"Error calling progress_callback: {e}")

        # Use subprocess.run with timeout and security settings
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=safe_output_dir,  # Set working directory
            env={"PATH": os.environ.get("PATH", "")},  # Minimal environment
        )

        # Monitor the process output for progress updates
        download_started = False
        try:
            while True:
                # Check if process is still running
                if process.poll() is not None:
                    break

                # Read stderr line by line for progress info
                try:
                    import select
                    import sys

                    if sys.platform != 'win32':
                        # Unix-like systems
                        ready, _, _ = select.select([process.stderr], [], [], 0.1)
                        if ready:
                            line = process.stderr.readline()
                            if line and progress_callback:
                                line = line.strip()
                                # Log the line for debugging
                                logger.debug(f"yt-dlp output: {line}")
                                
                                # Handle download progress
                                if '[download]' in line:
                                    if not download_started:
                                        download_started = True
                                        if progress_callback:
                                            try:
                                                progress_callback("Downloading media...")
                                            except Exception as e:
                                                logger.error(f"Error in progress callback: {e}")
                                    
                                    # Try to extract percentage
                                    if '%' in line:
                                        try:
                                            # Just send the line as a progress update
                                            if progress_callback:
                                                progress_callback(f"Download progress: {line}")
                                        except Exception as e:
                                            logger.error(f"Error updating progress: {e}")
                                
                                # Handle post-processing
                                elif 'Merging formats' in line or 'Post-processing' in line:
                                    if progress_callback:
                                        try:
                                            progress_callback("Converting to H.264 and finalizing...")
                                        except Exception as e:
                                            logger.error(f"Error in progress callback: {e}")
                                            
                                # Handle cleanup
                                elif 'Deleting original file' in line:
                                    if progress_callback:
                                        try:
                                            progress_callback("Cleaning up temporary files...")
                                        except Exception as e:
                                            logger.error(f"Error in progress callback: {e}")
                    else:
                        # Windows - just wait a bit and update periodically
                        import time
                        time.sleep(0.5)
                        if not download_started and progress_callback:
                            progress_callback("Downloading media...")
                            download_started = True
                except:
                    # If monitoring fails, just continue
                    pass

            stdout, stderr = process.communicate(timeout=1800)  # 30 minute timeout
        except subprocess.TimeoutExpired:
            process.kill()
            return {"success": False, "error": "Download timeout (30 minutes)"}

        if process.returncode == 0:
            if progress_callback:
                try:
                    progress_callback("Download completed successfully")
                    logger.info("Final progress callback called")
                except Exception as e:
                    logger.error(f"Error in final progress callback: {e}")
            logger.info("Download completed successfully.")
            return {"success": True, "file": "Downloaded"}
        else:
            # Sanitize error message
            error_msg = stderr.strip()
            error_msg = re.sub(r'https?://[^\s]+', '[URL]', error_msg)  # Hide URLs
            error_msg = re.sub(r'/[^\s]*', '[PATH]', error_msg)  # Hide paths

            # Check for cookie-related errors and provide helpful message
            if "Sign in to confirm you're not a bot" in error_msg or "authentication" in error_msg.lower():
                error_msg += "\n\n💡 TIP: YouTube cookies expire quickly. Please:\n1. Refresh the YouTube page\n2. Capture fresh cookies from your extension\n3. Try the download immediately"

            logger.error(f"yt-dlp error: {error_msg}")
            return {"success": False, "error": error_msg}

    except Exception as e:
        logger.exception(f"Exception during yt-dlp download: {str(e)}")
        return {"success": False, "error": "Download failed"}
    finally:
        if cookies_file and os.path.exists(cookies_file):
            try:
                os.remove(cookies_file)
            except Exception as e:
                logger.warning(f"Failed to remove temporary cookies file: {e}")

def download_with_ffmpeg(url, output_dir, format="mp4", custom_filename=None,
                         headers=None, cookies=None, referer=None, user_agent=None, verbose=False, progress_callback=None):
    try:
        # Security: Validate all inputs
        if not is_url(url):
            return {"success": False, "error": "Invalid URL"}

        # Sanitize output directory and filename
        safe_output_dir = str(Path(output_dir).resolve())
        if custom_filename:
            filename = sanitize_filename(custom_filename)
        else:
            filename = f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Validate format
        allowed_formats = ['mp4', 'webm', 'mkv', 'avi', 'mov', 'flv']
        if format not in allowed_formats:
            format = 'mp4'  # Default to safe format

        output_file = os.path.join(safe_output_dir, f"{filename}.{format}")

        # Build command with security considerations
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output files
            "-timeout", "1800000000",  # 30 minute timeout in microseconds
            "-reconnect", "1",
            "-reconnect_streamed", "1",
            "-reconnect_delay_max", "5"
        ]

        if not verbose:
            cmd.extend(["-loglevel", "error"])

        # Security: Validate and sanitize headers
        header_list = []
        if headers and isinstance(headers, dict):
            for k, v in headers.items():
                if isinstance(k, str) and isinstance(v, str):
                    # Remove dangerous characters
                    safe_key = re.sub(r'[^\w-]', '', k)
                    safe_value = re.sub(r'[\r\n]', '', v)
                    if safe_key and safe_value:
                        header_list.append(f"{safe_key}: {safe_value}")

        # Security: Validate cookies
        if cookies and isinstance(cookies, str):
            safe_cookies = re.sub(r'[\r\n]', '', cookies)
            if safe_cookies:
                header_list.append(f"Cookie: {safe_cookies}")

        # Security: Validate referer
        if referer and isinstance(referer, str) and is_url(referer):
            header_list.append(f"Referer: {referer}")

        # Security: Validate user agent
        if user_agent and isinstance(user_agent, str):
            safe_ua = re.sub(r'[^\w\s\-\.\(\);:/]', '', user_agent)[:512]
            if safe_ua:
                header_list.append(f"User-Agent: {safe_ua}")

        # Add headers if any
        if header_list:
            headers_str = "\r\n".join(header_list) + "\r\n"
            cmd.extend(["-headers", headers_str])

        # Add input and output
        cmd.extend(["-i", url, "-c", "copy", output_file])

        # Execute with security measures
        logger.debug(f"Executing ffmpeg command: {' '.join(cmd[:5])}... [URL hidden]")

        if progress_callback:
            progress_callback("Downloading media...")

        # Use subprocess.run with timeout and security settings
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=1800,  # 30 minute timeout
            cwd=safe_output_dir,  # Set working directory
            env={"PATH": os.environ.get("PATH", "")},  # Minimal environment
            check=True
        )

        if progress_callback:
            try:
                progress_callback("Download completed successfully")
            except Exception as e:
                logger.error(f"Error in progress callback: {e}")

        logger.info(f"Download completed: {output_file}")
        return {"success": True, "file": output_file}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Download timeout (30 minutes)"}
    except subprocess.CalledProcessError as e:
        # Sanitize error message
        error_msg = e.stderr if e.stderr else str(e)
        error_msg = re.sub(r'https?://[^\s]+', '[URL]', error_msg)  # Hide URLs
        error_msg = re.sub(r'/[^\s]*', '[PATH]', error_msg)  # Hide paths
        logger.error(f"ffmpeg error: {error_msg}")
        return {"success": False, "error": "Download failed"}
    except Exception as e:
        logger.exception(f"Exception during ffmpeg download: {str(e)}")
        return {"success": False, "error": "Download failed"}

def parse_stream_info(json_data):
    """Parse stream info from various JSON formats"""
    # Just return the JSON data directly if it's a dictionary with a URL
    if isinstance(json_data, dict) and 'url' in json_data:
        logger.info("Using direct JSON data with URL")
        return json_data
        
    # Handle array format (from browser extension)
    if isinstance(json_data, list):
        if len(json_data) > 0:
            item = json_data[0]  # Take the first item
            if isinstance(item, dict) and 'url' in item:
                logger.info("Using first item from JSON array")
                return item
            else:
                logger.error("First item in JSON array doesn't have a URL")
                return {"url": "", "error": "Missing URL in JSON array"}
        else:
            logger.error("Empty JSON array received")
            return {"url": "", "error": "Empty JSON array"}

    # Handle nested 'info' structure as a last resort
    if isinstance(json_data, dict) and 'info' in json_data:
        if isinstance(json_data['info'], dict):
            info = dict(json_data['info'])  # Create a copy to avoid modifying the original
            # Merge top-level url with info if needed
            if 'url' not in info and 'url' in json_data:
                info['url'] = json_data['url']
            logger.info("Using info field from JSON")
            return info

    # If we got here, we couldn't find a valid structure
    logger.error(f"Could not extract valid stream info from JSON: {type(json_data)}")
    return {"url": "", "error": "Could not extract valid stream info from JSON"}

def get_available_formats(url, headers=None, cookies=None, referer=None, user_agent=None):
    """Get available video formats and qualities for a URL"""
    try:
        cmd = ["yt-dlp", "--list-formats", "--no-warnings"]

        # Add authentication if provided
        if cookies:
            fd, cookies_file = tempfile.mkstemp(suffix='.txt')
            os.close(fd)
            try:
                with open(cookies_file, 'w') as f:
                    f.write("# Netscape HTTP Cookie File\n")
                    f.write("# This is a generated file! Do not edit.\n\n")

                    for cookie in cookies.split(';'):
                        cookie = cookie.strip()
                        if '=' in cookie:
                            name, value = cookie.split('=', 1)
                            name = name.strip()
                            value = value.strip()
                            if name and value:
                                f.write(f".youtube.com\tTRUE\t/\tTRUE\t2147483647\t{name}\t{value}\n")

                cmd.extend(["--cookies", cookies_file])
            except Exception as e:
                logger.warning(f"Failed to create cookies file: {e}")

        if headers:
            for key, value in headers.items():
                cmd.extend(["--add-header", f"{key}:{value}"])

        if referer:
            cmd.extend(["--referer", referer])

        if user_agent:
            cmd.extend(["--user-agent", user_agent])

        # Add YouTube-specific settings
        if is_youtube_url(url):
            cmd.extend([
                "--extractor-args", "youtube:player_client=web,android",
                "--extractor-args", "youtube:skip=translated_subs"
            ])

        cmd.append(url)

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if cookies and 'cookies_file' in locals():
            try:
                os.remove(cookies_file)
            except:
                pass

        if result.returncode == 0:
            # Parse the format list to extract available qualities
            formats = []
            lines = result.stdout.split('\n')

            for line in lines:
                if 'mp4' in line or 'webm' in line:
                    # Extract resolution information
                    if '1080p' in line or '1920x1080' in line:
                        formats.append('1080p')
                    elif '720p' in line or '1280x720' in line:
                        formats.append('720p')
                    elif '480p' in line or '854x480' in line:
                        formats.append('480p')
                    elif '360p' in line or '640x360' in line:
                        formats.append('360p')
                    elif '1440p' in line or '2560x1440' in line:
                        formats.append('1440p')
                    elif '2160p' in line or '3840x2160' in line:
                        formats.append('2160p')

            # Remove duplicates and sort by quality
            unique_formats = list(set(formats))
            quality_order = ['2160p', '1440p', '1080p', '720p', '480p', '360p']
            available_qualities = [q for q in quality_order if q in unique_formats]

            return {
                'success': True,
                'available_qualities': available_qualities,
                'raw_output': result.stdout
            }
        else:
            return {
                'success': False,
                'error': result.stderr,
                'available_qualities': []
            }

    except Exception as e:
        logger.error(f"Failed to get available formats: {e}")
        return {
            'success': False,
            'error': str(e),
            'available_qualities': []
        }

def download_video(stream_info, output_dir, format="mp4", quality="best", filename=None, verbose=False, progress_callback=None, **advanced_options):
    logger.info(f"download_video called with output_dir={output_dir}, format={format}, quality={quality}")
    logger.info(f"Advanced options: {advanced_options}")
    
    # Validate stream_info is a dictionary
    if not isinstance(stream_info, dict):
        logger.error(f"stream_info is not a dictionary: {type(stream_info)}")
        return {"success": False, "error": "Invalid stream information format"}
        
    # Check for error from parse_stream_info
    if 'error' in stream_info:
        logger.error(f"Error in stream info: {stream_info['error']}")
        return {"success": False, "error": stream_info['error']}
        
    url = stream_info.get('url')
    logger.info(f"URL from stream_info: {url[:30]}..." if url else "No URL found")
    
    if not url or not is_url(url):
        logger.error(f"Invalid or missing URL: {url}")
        return {"success": False, "error": "Invalid or missing URL"}
        
    source_type = stream_info.get('sourceType', '')
    logger.info(f"Source type: {source_type}")
    
    # Ensure headers is a dictionary
    headers = stream_info.get('headers', {})
    if not isinstance(headers, dict):
        logger.warning(f"Headers is not a dictionary: {type(headers)}, using empty dict instead")
        headers = {}
    logger.info(f"Headers: {headers.keys() if headers else 'None'}")
        
    # Get cookies and ensure it's a string
    cookies = stream_info.get('cookies', '')
    logger.info(f"Cookies length: {len(cookies) if cookies else 0}")
    if not isinstance(cookies, str):
        logger.warning(f"Cookies is not a string: {type(cookies)}, converting to string")
        try:
            cookies = str(cookies)
        except Exception as e:
            logger.error(f"Failed to convert cookies to string: {e}")
            cookies = ""
            
    # Clean up cookies if needed
    if cookies:
        cookies = cookies.replace('\n', '').replace('\r', '')
        
    referer = stream_info.get('referer', stream_info.get('pageUrl', ''))
    user_agent = stream_info.get('userAgent', '')

    # Check dependencies
    deps = check_dependencies()
    has_ytdlp = deps.get("yt-dlp", False)
    has_ffmpeg = deps.get("ffmpeg", False)

    # Extract advanced options
    video_quality_advanced = advanced_options.get('videoQualityAdvanced', '')
    audio_quality = advanced_options.get('audioQuality', 'best')
    audio_format = advanced_options.get('audioFormat', 'best')
    container_advanced = advanced_options.get('containerAdvanced', '')
    rate_limit = advanced_options.get('rateLimit', '')
    retries = advanced_options.get('retries', '10')
    concurrent_fragments = advanced_options.get('concurrentFragments', '1')
    extract_audio = advanced_options.get('extractAudio', False)
    embed_subs = advanced_options.get('embedSubs', False)
    embed_thumbnail = advanced_options.get('embedThumbnail', False)
    embed_metadata = advanced_options.get('embedMetadata', False)
    keep_fragments = advanced_options.get('keepFragments', False)
    write_subs = advanced_options.get('writeSubs', False)
    auto_subs = advanced_options.get('autoSubs', False)
    subtitle_langs = advanced_options.get('subtitleLangs', '')
    subtitle_format = advanced_options.get('subtitleFormat', 'best')

    # Use advanced quality if specified, otherwise use simple quality
    effective_quality = video_quality_advanced if video_quality_advanced else quality
    effective_format = container_advanced if container_advanced else format

    # Debug logging
    if verbose:
        logger.info(f"Download parameters:")
        logger.info(f"  URL: {url}")
        logger.info(f"  Quality requested: {quality}")
        logger.info(f"  Advanced quality: {video_quality_advanced}")
        logger.info(f"  Effective quality: {effective_quality}")
        logger.info(f"  Format: {effective_format}")

    # Try different download methods based on source type and available tools
    if source_type == 'youtube' or 'youtube.com' in url or 'youtu.be' in url or source_type == 'vimeo' or 'vimeo.com' in url:
        if has_ytdlp:
            return download_with_ytdlp(url, output_dir, effective_format, effective_quality, filename, headers, cookies, referer, user_agent, verbose, progress_callback, **advanced_options)
        else:
            return {"success": False, "error": "yt-dlp is required for this URL but not installed"}
    elif source_type == 'hls' or url.endswith('.m3u8') or source_type == 'dash' or url.endswith('.mpd'):
        if has_ffmpeg:
            return download_with_ffmpeg(url, output_dir, format, filename, headers, cookies, referer, user_agent, verbose, progress_callback)
        elif has_ytdlp:
            # Try yt-dlp as fallback for HLS/DASH
            return download_with_ytdlp(url, output_dir, format, quality, filename, headers, cookies, referer, user_agent, verbose, progress_callback)
        else:
            return {"success": False, "error": "ffmpeg or yt-dlp is required for this URL but neither is installed"}
    elif is_supported_by_ytdlp(url):
        if has_ytdlp:
            return download_with_ytdlp(url, output_dir, format, quality, filename, headers, cookies, referer, user_agent, verbose, progress_callback)
        else:
            return {"success": False, "error": "yt-dlp is required for this URL but not installed"}
    else:
        # For direct URLs or unknown types, try yt-dlp first, then ffmpeg
        if has_ytdlp:
            logger.info(f"Trying yt-dlp for URL: {url}")
            result = download_with_ytdlp(url, output_dir, format, quality, filename, headers, cookies, referer, user_agent, verbose, progress_callback)
            if result["success"]:
                return result
            logger.info("yt-dlp failed, trying ffmpeg if available...")

        if has_ffmpeg:
            logger.info(f"Trying ffmpeg for URL: {url}")
            return download_with_ffmpeg(url, output_dir, format, filename, headers, cookies, referer, user_agent, verbose, progress_callback)

        # If we get here, either both failed or neither tool is available
        if has_ytdlp or has_ffmpeg:
            return {"success": False, "error": "Unable to download with available tools"}
        else:
            return {"success": False, "error": "No download tools available (yt-dlp and ffmpeg not installed)"}

def main():
    parser = argparse.ArgumentParser(description='Download videos from URLs with enhanced metadata support')
    parser.add_argument('url', nargs='?', help='Video URL')
    parser.add_argument('--output-dir', '-o', help='Directory to save the video')
    parser.add_argument('--format', '-f', default='mp4', help='Output format (default: mp4)')
    parser.add_argument('--quality', '-q', choices=['best', '2160p', '1440p', '1080p', '720p', '480p', '360p', 'worst'], default='best', help='Video quality')
    parser.add_argument('--filename', '-n', help='Custom filename')
    parser.add_argument('--json', '-j', help='JSON string with metadata')
    parser.add_argument('--json-file', help='Path to JSON file with metadata')
    parser.add_argument('--check-deps', action='store_true', help='Check dependencies')
    parser.add_argument('--install-deps', action='store_true', help='Install missing dependencies')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose mode')
    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)
    if args.check_deps:
        deps = check_dependencies()
        for k, v in deps.items():
            print(f"{k}: {'Installed' if v else 'Not installed'}")
        return
    if args.install_deps:
        install_dependencies()
        return

    stream_info = None
    if args.json:
        parsed_json = json.loads(args.json)
        stream_info = parse_stream_info(parsed_json)
    elif args.json_file:
        with open(args.json_file, 'r') as f:
            parsed_json = json.load(f)
            stream_info = parse_stream_info(parsed_json)
    elif args.url:
        stream_info = {'url': args.url}

    if not stream_info:
        parser.print_help()
        return

    deps = check_dependencies()
    if not deps.get("yt-dlp", False):
        logger.error("yt-dlp is required but not installed")
        return

    output_path = setup_output_directory(args.output_dir)
    result = download_video(stream_info, output_path, args.format, args.quality, args.filename, args.verbose)
    if result["success"]:
        print(f"Download completed: {result['file']}")
    else:
        print(f"Download failed: {result['error']}")

if __name__ == "__main__":
    main()
