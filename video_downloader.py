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

def create_temp_cookies_file(cookies, url):
    if not cookies:
        return None
    try:
        fd, cookies_file = tempfile.mkstemp(suffix='.txt')
        os.close(fd)
        with open(cookies_file, 'w') as f:
            domain = urlparse(url).netloc
            for cookie in cookies.split(';'):
                if '=' in cookie:
                    name, value = cookie.strip().split('=', 1)
                    f.write(f"{domain}\tTRUE\t/\tFALSE\t0\t{name}\t{value}\n")
        logger.debug(f"Created temporary cookies file: {cookies_file}")
        return cookies_file
    except Exception as e:
        logger.warning(f"Failed to create cookies file: {e}")
        return None

def download_with_ytdlp(url, output_dir, format="mp4", quality="best", custom_filename=None,
                        headers=None, cookies=None, referer=None, user_agent=None, verbose=False):
    cookies_file = None
    try:
        output_template = os.path.join(output_dir, f"{sanitize_filename(custom_filename)}.%(ext)s") if custom_filename else os.path.join(output_dir, "%(title)s.%(ext)s")
        format_selection = "bestvideo+bestaudio/best"
        if quality == "medium":
            format_selection = "bestvideo[height<=720]+bestaudio/best[height<=720]"
        elif quality == "low":
            format_selection = "bestvideo[height<=480]+bestaudio/best[height<=480]"
        cmd = ["yt-dlp", "--format", format_selection, "--merge-output-format", format, "--output", output_template, "--no-playlist"]
        cmd.append("--verbose" if verbose else "--quiet")
        if headers:
            for name, value in headers.items():
                cmd.extend(["--add-header", f"{name}: {value}"])
        if cookies:
            cookies_file = create_temp_cookies_file(cookies, url)
            if cookies_file:
                cmd.extend(["--cookies", cookies_file])
        if referer:
            cmd.extend(["--referer", referer])
        if user_agent:
            cmd.extend(["--user-agent", user_agent])
        cmd.append(url)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        if process.returncode == 0:
            logger.info("Download completed successfully.")
            return {"success": True, "file": "Downloaded"}
        else:
            logger.error(f"yt-dlp error: {stderr.strip()}")
            return {"success": False, "error": stderr.strip()}
    except Exception as e:
        logger.exception(f"Exception during yt-dlp download: {str(e)}")
        return {"success": False, "error": str(e)}
    finally:
        if cookies_file and os.path.exists(cookies_file):
            try:
                os.remove(cookies_file)
            except Exception as e:
                logger.warning(f"Failed to remove temporary cookies file: {e}")

def download_with_ffmpeg(url, output_dir, format="mp4", custom_filename=None,
                         headers=None, cookies=None, referer=None, user_agent=None, verbose=False):
    try:
        filename = sanitize_filename(custom_filename) if custom_filename else f"video_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        output_file = os.path.join(output_dir, f"{filename}.{format}")
        cmd = ["ffmpeg", "-y"]
        if not verbose:
            cmd.extend(["-loglevel", "error"])
        header_list = []
        if headers:
            header_list.extend([f"{k}: {v}" for k, v in headers.items()])
        if cookies:
            header_list.append(f"Cookie: {cookies}")
        if referer:
            header_list.append(f"Referer: {referer}")
        if user_agent:
            header_list.append(f"User-Agent: {user_agent}")
        if header_list:
            cmd.extend(["-headers", "\r\n".join(header_list) + "\r\n"])
        cmd.extend(["-i", url, "-c", "copy", output_file])
        subprocess.run(cmd, check=True)
        logger.info(f"Download completed: {output_file}")
        return {"success": True, "file": output_file}
    except Exception as e:
        logger.exception(f"Exception during ffmpeg download: {str(e)}")
        return {"success": False, "error": str(e)}

def download_video(stream_info, output_dir, format="mp4", quality="best", filename=None, verbose=False):
    url = stream_info.get('url')
    if not url or not is_url(url):
        return {"success": False, "error": "Invalid or missing URL"}
    source_type = stream_info.get('sourceType', '')
    headers = stream_info.get('headers', {})
    cookies = stream_info.get('cookies', '')
    referer = stream_info.get('referer', stream_info.get('pageUrl', ''))
    user_agent = stream_info.get('userAgent', '')
    if source_type == 'youtube' or 'youtube.com' in url or 'youtu.be' in url or source_type == 'vimeo' or 'vimeo.com' in url:
        return download_with_ytdlp(url, output_dir, format, quality, filename, headers, cookies, referer, user_agent, verbose)
    elif source_type == 'hls' or url.endswith('.m3u8') or source_type == 'dash' or url.endswith('.mpd'):
        return download_with_ffmpeg(url, output_dir, format, filename, headers, cookies, referer, user_agent, verbose)
    elif is_supported_by_ytdlp(url):
        return download_with_ytdlp(url, output_dir, format, quality, filename, headers, cookies, referer, user_agent, verbose)
    else:
        return {"success": False, "error": "Unsupported stream type or URL"}

def main():
    parser = argparse.ArgumentParser(description='Download videos from URLs with enhanced metadata support')
    parser.add_argument('url', nargs='?', help='Video URL')
    parser.add_argument('--output-dir', '-o', help='Directory to save the video')
    parser.add_argument('--format', '-f', default='mp4', help='Output format (default: mp4)')
    parser.add_argument('--quality', '-q', choices=['best', 'medium', 'low'], default='best', help='Video quality')
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
        stream_info = json.loads(args.json)
    elif args.json_file:
        with open(args.json_file, 'r') as f:
            stream_info = json.load(f)
    elif args.url:
        stream_info = {'url': args.url}

    if not stream_info:
        parser.print_help()
        return

    deps = check_dependencies()
    if not all(deps.values()):
        logger.error("Missing dependencies")
        return

    output_path = setup_output_directory(args.output_dir)
    result = download_video(stream_info, output_path, args.format, args.quality, args.filename, args.verbose)
    if result["success"]:
        print(f"Download completed: {result['file']}")
    else:
        print(f"Download failed: {result['error']}")

if __name__ == "__main__":
    main()
