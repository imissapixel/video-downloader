#!/usr/bin/env python3
"""
Security utilities for the video downloader application
Provides input validation, sanitization, and injection protection
"""

import re
import os
import json
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging

logger = logging.getLogger(__name__)

class SecurityError(Exception):
    """Custom exception for security-related errors"""
    pass

class InputValidator:
    """Comprehensive input validation and sanitization"""
    
    # URL schemes that are allowed
    ALLOWED_URL_SCHEMES = {'http', 'https'}
    
    # File extensions that are allowed for downloads
    ALLOWED_EXTENSIONS = {
        'mp4', 'webm', 'mkv', 'avi', 'mov', 'flv', 'wmv', 
        'mp3', 'wav', 'aac', 'ogg', 'flac', 'm4a'
    }
    
    # Maximum lengths for various inputs
    MAX_URL_LENGTH = 2048
    MAX_FILENAME_LENGTH = 255
    MAX_TITLE_LENGTH = 255
    MAX_HEADER_VALUE_LENGTH = 8192
    MAX_COOKIE_LENGTH = 32768  # 32KB - increased for modern web apps with large cookies
    MAX_JSON_SIZE = 1024 * 1024  # 1MB
    
    # Dangerous patterns to block in URLs (excluding & which is valid in query strings)
    DANGEROUS_URL_PATTERNS = [
        r'[;|`$()]',   # Shell metacharacters (excluding & which is valid in URLs)
        r'\.\./',      # Path traversal
        r'\\\.\\',     # Windows path traversal
        r'file://',    # Local file access
        r'ftp://',     # FTP access
        r'javascript:', # JavaScript URLs
        r'data:',      # Data URLs
        r'vbscript:',  # VBScript URLs
    ]
    
    # Dangerous patterns for general content (includes all shell metacharacters)
    DANGEROUS_PATTERNS = [
        r'[;&|`$()]',  # Shell metacharacters
        r'\.\./',      # Path traversal
        r'\\\.\\',     # Windows path traversal
        r'file://',    # Local file access
        r'ftp://',     # FTP access
        r'javascript:', # JavaScript URLs
        r'data:',      # Data URLs
        r'vbscript:',  # VBScript URLs
    ]
    
    # Dangerous filename patterns
    DANGEROUS_FILENAME_PATTERNS = [
        r'^\.',        # Hidden files
        r'\.exe$',     # Executables
        r'\.bat$',     # Batch files
        r'\.cmd$',     # Command files
        r'\.sh$',      # Shell scripts
        r'\.ps1$',     # PowerShell scripts
        r'\.py$',      # Python scripts
        r'\.js$',      # JavaScript files
        r'\.vbs$',     # VBScript files
        r'\.scr$',     # Screen savers
        r'\.com$',     # COM files
        r'\.pif$',     # Program information files
    ]
    
    # Additional path traversal patterns (Windows and Unix)
    PATH_TRAVERSAL_PATTERNS = [
        r'\.\.',       # Standard path traversal
        r'\\\.\\',     # Windows path traversal
        r'/\./',       # Unix path traversal
        r'%2e%2e',     # URL encoded ..
        r'%252e%252e', # Double URL encoded ..
        r'\.%2f',      # Mixed encoding
        r'%5c',        # URL encoded backslash
    ]

    @staticmethod
    def validate_url(url: str) -> str:
        """Validate and sanitize URL input"""
        if not url or not isinstance(url, str):
            raise SecurityError("URL must be a non-empty string")
        
        url = url.strip()
        
        if len(url) > InputValidator.MAX_URL_LENGTH:
            raise SecurityError(f"URL too long (max {InputValidator.MAX_URL_LENGTH} characters)")
        
        # Check for dangerous patterns (use URL-specific patterns)
        for pattern in InputValidator.DANGEROUS_URL_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                raise SecurityError(f"URL contains dangerous pattern: {pattern}")
        
        # Parse and validate URL
        try:
            parsed = urllib.parse.urlparse(url)
        except Exception as e:
            raise SecurityError(f"Invalid URL format: {e}")
        
        if not parsed.scheme:
            raise SecurityError("URL must include a scheme (http/https)")
        
        if parsed.scheme.lower() not in InputValidator.ALLOWED_URL_SCHEMES:
            raise SecurityError(f"URL scheme '{parsed.scheme}' not allowed")
        
        if not parsed.netloc:
            raise SecurityError("URL must include a domain")
        
        # Block localhost and private IP ranges
        hostname = parsed.hostname
        if hostname:
            if hostname.lower() in ['localhost', '127.0.0.1', '::1']:
                raise SecurityError("Localhost URLs not allowed")
            
            # Block private IP ranges
            if re.match(r'^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)', hostname):
                raise SecurityError("Private IP addresses not allowed")
        
        return url

    @staticmethod
    def validate_filename(filename: str) -> str:
        """Validate and sanitize filename input"""
        if not filename:
            return None
        
        if not isinstance(filename, str):
            raise SecurityError("Filename must be a string")
        
        filename = filename.strip()
        
        if len(filename) > InputValidator.MAX_FILENAME_LENGTH:
            raise SecurityError(f"Filename too long (max {InputValidator.MAX_FILENAME_LENGTH} characters)")
        
        # Check for dangerous patterns
        for pattern in InputValidator.DANGEROUS_FILENAME_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                raise SecurityError(f"Filename contains dangerous pattern: {pattern}")
        
        # Check for path traversal patterns
        for pattern in InputValidator.PATH_TRAVERSAL_PATTERNS:
            if re.search(pattern, filename, re.IGNORECASE):
                raise SecurityError(f"Filename contains path traversal pattern: {pattern}")
        
        # Remove dangerous characters
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename)
        sanitized = re.sub(r'\.+$', '', sanitized)  # Remove trailing dots
        sanitized = sanitized.strip()
        
        if not sanitized:
            raise SecurityError("Filename becomes empty after sanitization")
        
        # Ensure filename doesn't start with dangerous prefixes
        if sanitized.lower().startswith(('con', 'prn', 'aux', 'nul', 'com', 'lpt')):
            sanitized = f"file_{sanitized}"
        
        return sanitized

    @staticmethod
    def validate_headers(headers: Dict[str, str]) -> Dict[str, str]:
        """Validate and sanitize HTTP headers"""
        if not headers:
            return {}
        
        if not isinstance(headers, dict):
            raise SecurityError("Headers must be a dictionary")
        
        sanitized_headers = {}
        
        for name, value in headers.items():
            if not isinstance(name, str) or not isinstance(value, str):
                raise SecurityError("Header names and values must be strings")
            
            name = name.strip()
            value = value.strip()
            
            if len(value) > InputValidator.MAX_HEADER_VALUE_LENGTH:
                raise SecurityError(f"Header value too long (max {InputValidator.MAX_HEADER_VALUE_LENGTH} characters)")
            
            # Block dangerous header names
            dangerous_headers = ['host', 'content-length', 'transfer-encoding', 'connection']
            if name.lower() in dangerous_headers:
                logger.warning(f"Skipping dangerous header: {name}")
                continue
            
            # Check for header injection
            if '\r' in value or '\n' in value:
                raise SecurityError("Header values cannot contain newlines")
            
            # Sanitize header value
            value = re.sub(r'[^\x20-\x7E]', '', value)  # Remove non-printable chars
            
            sanitized_headers[name] = value
        
        return sanitized_headers

    @staticmethod
    def validate_cookies(cookies: str) -> str:
        """Validate and sanitize cookie string"""
        if not cookies:
            return ""
        
        if not isinstance(cookies, str):
            raise SecurityError("Cookies must be a string")
        
        cookies = cookies.strip()
        
        if len(cookies) > InputValidator.MAX_COOKIE_LENGTH:
            logger.warning(f"Large cookie string detected: {len(cookies)} characters")
            # Allow large cookies but log for monitoring
            if len(cookies) > 65536:  # 64KB absolute maximum
                raise SecurityError(f"Cookie string too long (max 64KB characters)")
        
        # Check for dangerous patterns
        if '\r' in cookies or '\n' in cookies:
            raise SecurityError("Cookies cannot contain newlines")
        
        # Basic cookie format validation - allow standard cookie characters including URL encoding
        # Allow URL-encoded characters (%XX), standard cookie chars, and common symbols used in cookies
        # This includes: alphanumeric, underscore, dash, equals, semicolon, space, slash, plus, colon, ampersand, percent, tilde, parentheses
        if not re.match(r'^[a-zA-Z0-9_\-=;. /+:&%~()A-F]+$', cookies):
            raise SecurityError("Cookies contain invalid characters")
        
        return cookies

    @staticmethod
    def validate_json_input(json_str: str) -> Dict[str, Any]:
        """Validate and parse JSON input safely"""
        if not json_str:
            raise SecurityError("JSON string cannot be empty")
        
        if not isinstance(json_str, str):
            raise SecurityError("JSON input must be a string")
        
        json_str = json_str.strip()
        
        if len(json_str) > InputValidator.MAX_JSON_SIZE:
            raise SecurityError(f"JSON too large (max {InputValidator.MAX_JSON_SIZE} bytes)")
        
        try:
            # Parse JSON with strict mode
            parsed = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise SecurityError(f"Invalid JSON format: {e}")
        
        if not isinstance(parsed, dict):
            raise SecurityError("JSON must be an object/dictionary")
        
        # Validate required fields
        if 'url' not in parsed:
            raise SecurityError("JSON must contain 'url' field")
        
        # Check for command injection patterns in non-standard fields
        # Standard fields (url, headers, cookies, etc.) are validated separately
        standard_fields = {'url', 'headers', 'cookies', 'referer', 'userAgent', 'sourceType', 'title'}
        # Safe fields that don't need command injection checking (display-only fields)
        safe_display_fields = {'title', 'sourceType'}
        command_injection_patterns = [r'[;&|`$]', r'\.\./', r'\\\.\\']
        
        for key, value in parsed.items():
            if isinstance(value, str):
                # For non-standard fields, check for command injection
                if key not in standard_fields:
                    for pattern in command_injection_patterns:
                        if re.search(pattern, value):
                            raise SecurityError(f"JSON field '{key}' contains dangerous pattern: {pattern}")
                # For URL fields, use URL validation (done later)
                # For other standard fields, they have their own validation
                # Safe display fields (like title) don't need command injection checking
        
        # Validate and sanitize title if present
        if 'title' in parsed:
            title = parsed.get('title')
            if isinstance(title, str):
                if len(title) > InputValidator.MAX_TITLE_LENGTH:
                    raise SecurityError(f"Title too long (max {InputValidator.MAX_TITLE_LENGTH} characters)")
                parsed['title'] = InputValidator.sanitize_html_field(title)
            elif title is not None: # Allow null title, but not other types
                raise SecurityError("Title must be a string or null")

        return parsed

    @staticmethod
    def sanitize_html_field(text: str) -> str:
        """Sanitize a string field by escaping HTML special characters."""
        if not isinstance(text, str):
            # Or raise an error, depending on desired strictness
            return ""
        return text.replace('&', '&amp;') \
                   .replace('<', '&lt;') \
                   .replace('>', '&gt;') \
                   .replace('"', '&quot;') \
                   .replace("'", '&#x27;')

    @staticmethod
    def validate_format(format_str: str) -> str:
        """Validate output format"""
        if not format_str:
            return "mp4"  # Default
        
        if not isinstance(format_str, str):
            raise SecurityError("Format must be a string")
        
        format_str = format_str.lower().strip()
        
        if format_str not in InputValidator.ALLOWED_EXTENSIONS:
            raise SecurityError(f"Format '{format_str}' not allowed")
        
        return format_str

    @staticmethod
    def validate_quality(quality: str) -> str:
        """Validate quality setting"""
        allowed_qualities = ['2160p', '1440p', '1080p', '1080p60', '720p', '720p60', '480p', '360p']
        
        if not quality:
            return "720p"  # Default
        
        if not isinstance(quality, str):
            raise SecurityError("Quality must be a string")
        
        quality = quality.lower().strip()
        
        if quality not in allowed_qualities:
            raise SecurityError(f"Quality '{quality}' not allowed")
        
        return quality

    @staticmethod
    def validate_audio_quality(audio_quality: str) -> str:
        """Validate audio quality setting"""
        allowed_qualities = ['best', '320k', '256k', '192k', '128k', '96k']
        
        if not audio_quality:
            return "best"
        
        if not isinstance(audio_quality, str):
            raise SecurityError("Audio quality must be a string")
        
        audio_quality = audio_quality.lower().strip()
        
        if audio_quality not in allowed_qualities:
            raise SecurityError(f"Audio quality '{audio_quality}' not allowed")
        
        return audio_quality

    @staticmethod
    def validate_audio_format(audio_format: str) -> str:
        """Validate audio format setting"""
        allowed_formats = ['best', 'aac', 'mp3', 'opus', 'vorbis', 'flac', 'wav']
        
        if not audio_format:
            return "best"
        
        if not isinstance(audio_format, str):
            raise SecurityError("Audio format must be a string")
        
        audio_format = audio_format.lower().strip()
        
        if audio_format not in allowed_formats:
            raise SecurityError(f"Audio format '{audio_format}' not allowed")
        
        return audio_format

    @staticmethod
    def validate_rate_limit(rate_limit: str) -> str:
        """Validate rate limit setting"""
        allowed_rates = ['', '10M', '5M', '2M', '1M', '500K']
        
        if not rate_limit:
            return ""
        
        if not isinstance(rate_limit, str):
            raise SecurityError("Rate limit must be a string")
        
        rate_limit = rate_limit.strip()
        
        if rate_limit not in allowed_rates:
            raise SecurityError(f"Rate limit '{rate_limit}' not allowed")
        
        return rate_limit

    @staticmethod
    def validate_retries(retries: str) -> str:
        """Validate retry count setting"""
        allowed_retries = ['1', '3', '5', '10', 'infinite']
        
        if not retries:
            return "10"
        
        if not isinstance(retries, str):
            raise SecurityError("Retries must be a string")
        
        retries = retries.strip()
        
        if retries not in allowed_retries:
            raise SecurityError(f"Retries '{retries}' not allowed")
        
        return retries

    @staticmethod
    def sanitize_output_directory(output_dir: str) -> str:
        """Validate and sanitize output directory path"""
        if not output_dir:
            raise SecurityError("Output directory cannot be empty")
        
        if not isinstance(output_dir, str):
            raise SecurityError("Output directory must be a string")
        
        # Resolve path and check for traversal
        try:
            path = Path(output_dir).resolve()
        except Exception as e:
            raise SecurityError(f"Invalid output directory path: {e}")
        
        # Ensure path is within allowed directories
        # This should be configured based on your deployment
        allowed_base_dirs = [
            Path.cwd(),  # Current working directory
            Path('/tmp'),  # Temporary directory
            Path.home() / 'Downloads',  # User downloads
        ]
        
        # Check if path is within allowed directories
        path_allowed = False
        for base_dir in allowed_base_dirs:
            try:
                path.relative_to(base_dir.resolve())
                path_allowed = True
                break
            except ValueError:
                continue
        
        if not path_allowed:
            raise SecurityError("Output directory not in allowed locations")
        
        return str(path)

class CommandSanitizer:
    """Sanitize command-line arguments to prevent injection"""
    
    @staticmethod
    def escape_shell_arg(arg: str) -> str:
        """Escape shell argument to prevent injection"""
        if not isinstance(arg, str):
            raise SecurityError("Argument must be a string")
        
        # Use shlex.quote for proper shell escaping
        import shlex
        return shlex.quote(arg)
    
    @staticmethod
    def validate_command_args(args: List[str]) -> List[str]:
        """Validate command arguments"""
        if not isinstance(args, list):
            raise SecurityError("Arguments must be a list")
        
        validated_args = []
        for arg in args:
            if not isinstance(arg, str):
                raise SecurityError("All arguments must be strings")
            
            # Check for dangerous patterns
            for pattern in InputValidator.DANGEROUS_PATTERNS:
                if re.search(pattern, arg):
                    raise SecurityError(f"Argument contains dangerous pattern: {pattern}")
            
            validated_args.append(arg)
        
        return validated_args

def validate_download_request(data: Dict[str, Any]) -> Dict[str, Any]:
    """Comprehensive validation of download request data"""
    try:
        validated = {}
        
        # Validate mode
        mode = data.get('mode', 'simple')
        if mode not in ['simple', 'json']:
            raise SecurityError("Invalid mode")
        validated['mode'] = mode
        
        # Validate based on mode
        if mode == 'simple':
            url = data.get('url', '').strip()
            validated['url'] = InputValidator.validate_url(url)
            validated['stream_info'] = {'url': validated['url']}
            
        elif mode == 'json':
            json_str = data.get('json_string', '')
            parsed_json = InputValidator.validate_json_input(json_str)
            
            # Validate URL in JSON
            parsed_json['url'] = InputValidator.validate_url(parsed_json['url'])
            
            # Validate optional fields in JSON
            if 'headers' in parsed_json:
                parsed_json['headers'] = InputValidator.validate_headers(parsed_json['headers'])
            
            if 'cookies' in parsed_json:
                parsed_json['cookies'] = InputValidator.validate_cookies(parsed_json['cookies'])
            
            if 'referer' in parsed_json:
                parsed_json['referer'] = InputValidator.validate_url(parsed_json['referer'])
            
            if 'userAgent' in parsed_json:
                # Basic user agent validation
                ua = parsed_json['userAgent']
                if not isinstance(ua, str) or len(ua) > 512:
                    raise SecurityError("Invalid user agent")
                parsed_json['userAgent'] = re.sub(r'[^\x20-\x7E]', '', ua)
            
            validated['stream_info'] = parsed_json
        
        # Validate basic options
        validated['format'] = InputValidator.validate_format(data.get('format', 'mp4'))
        validated['quality'] = InputValidator.validate_quality(data.get('quality', 'best'))
        
        filename = data.get('filename', '').strip()
        if filename:
            validated['filename'] = InputValidator.validate_filename(filename)
        else:
            validated['filename'] = None
        
        # Validate verbose flag
        verbose = data.get('verbose', False)
        validated['verbose'] = bool(verbose)
        
        # Validate advanced options
        validated['videoQualityAdvanced'] = InputValidator.validate_quality(data.get('videoQualityAdvanced', '')) if data.get('videoQualityAdvanced') else ''
        validated['audioQuality'] = InputValidator.validate_audio_quality(data.get('audioQuality', 'best'))
        validated['audioFormat'] = InputValidator.validate_audio_format(data.get('audioFormat', 'best'))
        validated['containerAdvanced'] = InputValidator.validate_format(data.get('containerAdvanced', '')) if data.get('containerAdvanced') else ''
        validated['rateLimit'] = InputValidator.validate_rate_limit(data.get('rateLimit', ''))
        validated['retries'] = InputValidator.validate_retries(data.get('retries', '10'))
        
        # Validate concurrent fragments
        concurrent = data.get('concurrentFragments', '1')
        if concurrent and concurrent.isdigit() and 1 <= int(concurrent) <= 16:
            validated['concurrentFragments'] = concurrent
        else:
            validated['concurrentFragments'] = '1'
        
        # Validate feature toggles
        validated['extractAudio'] = bool(data.get('extractAudio', False))
        validated['embedSubs'] = bool(data.get('embedSubs', False))
        validated['embedThumbnail'] = bool(data.get('embedThumbnail', False))
        validated['embedMetadata'] = bool(data.get('embedMetadata', False))
        validated['keepFragments'] = bool(data.get('keepFragments', False))
        validated['writeSubs'] = bool(data.get('writeSubs', False))
        validated['autoSubs'] = bool(data.get('autoSubs', False))
        
        # Validate subtitle options
        subtitle_langs = data.get('subtitleLangs', '').strip()
        if subtitle_langs:
            # Basic validation for subtitle languages (alphanumeric, commas, hyphens)
            if re.match(r'^[a-zA-Z0-9,\-_\s]+$', subtitle_langs):
                validated['subtitleLangs'] = subtitle_langs
            else:
                validated['subtitleLangs'] = ''
        else:
            validated['subtitleLangs'] = ''
        
        subtitle_format = data.get('subtitleFormat', 'best')
        allowed_sub_formats = ['best', 'srt', 'vtt', 'ass', 'lrc']
        if subtitle_format in allowed_sub_formats:
            validated['subtitleFormat'] = subtitle_format
        else:
            validated['subtitleFormat'] = 'best'
        
        return validated
        
    except SecurityError:
        raise
    except Exception as e:
        raise SecurityError(f"Validation error: {e}")