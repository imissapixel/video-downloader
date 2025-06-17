#!/usr/bin/env python3
"""
Performance Optimization Module for Video Downloader
Ensures security measures don't impact application performance
"""

import time
import threading
import functools
import logging
from collections import OrderedDict
from typing import Any, Callable, Dict, Optional
import hashlib
import pickle
import gc

logger = logging.getLogger(__name__)

class LRUCache:
    """Thread-safe LRU Cache for validation results"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self.cache = OrderedDict()
        self.lock = threading.RLock()
        self.hits = 0
        self.misses = 0
    
    def get(self, key: str) -> Optional[Any]:
        """Get item from cache"""
        with self.lock:
            if key in self.cache:
                # Move to end (most recently used)
                self.cache.move_to_end(key)
                self.hits += 1
                return self.cache[key]
            else:
                self.misses += 1
                return None
    
    def put(self, key: str, value: Any) -> None:
        """Put item in cache"""
        with self.lock:
            if key in self.cache:
                # Update existing item
                self.cache[key] = value
                self.cache.move_to_end(key)
            else:
                # Add new item
                self.cache[key] = value
                # Remove oldest if over capacity
                if len(self.cache) > self.max_size:
                    self.cache.popitem(last=False)
    
    def clear(self) -> None:
        """Clear cache"""
        with self.lock:
            self.cache.clear()
            self.hits = 0
            self.misses = 0
    
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self.lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0
            return {
                'size': len(self.cache),
                'max_size': self.max_size,
                'hits': self.hits,
                'misses': self.misses,
                'hit_rate': f"{hit_rate:.1f}%"
            }

class ValidationCache:
    """Caching system for expensive validation operations"""
    
    def __init__(self):
        self.url_cache = LRUCache(max_size=500)
        self.json_cache = LRUCache(max_size=200)
        self.filename_cache = LRUCache(max_size=300)
        self.header_cache = LRUCache(max_size=100)
    
    def _hash_key(self, data: str) -> str:
        """Create hash key for caching"""
        return hashlib.sha256(data.encode('utf-8')).hexdigest()[:16]
    
    def cache_url_validation(self, url: str, result: Any) -> None:
        """Cache URL validation result"""
        key = self._hash_key(url)
        self.url_cache.put(key, result)
    
    def get_url_validation(self, url: str) -> Optional[Any]:
        """Get cached URL validation result"""
        key = self._hash_key(url)
        return self.url_cache.get(key)
    
    def cache_json_validation(self, json_str: str, result: Any) -> None:
        """Cache JSON validation result"""
        key = self._hash_key(json_str)
        self.json_cache.put(key, result)
    
    def get_json_validation(self, json_str: str) -> Optional[Any]:
        """Get cached JSON validation result"""
        key = self._hash_key(json_str)
        return self.json_cache.get(key)
    
    def cache_filename_validation(self, filename: str, result: Any) -> None:
        """Cache filename validation result"""
        key = self._hash_key(filename)
        self.filename_cache.put(key, result)
    
    def get_filename_validation(self, filename: str) -> Optional[Any]:
        """Get cached filename validation result"""
        key = self._hash_key(filename)
        return self.filename_cache.get(key)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        return {
            'url_cache': self.url_cache.stats(),
            'json_cache': self.json_cache.stats(),
            'filename_cache': self.filename_cache.stats(),
            'header_cache': self.header_cache.stats()
        }

# Global validation cache
validation_cache = ValidationCache()

def cached_validation(cache_type: str):
    """Decorator for caching validation results"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Only cache if first argument is a string (the input to validate)
            if args and isinstance(args[0], str):
                input_data = args[0]
                
                # Try to get from cache first
                if cache_type == 'url':
                    cached_result = validation_cache.get_url_validation(input_data)
                elif cache_type == 'json':
                    cached_result = validation_cache.get_json_validation(input_data)
                elif cache_type == 'filename':
                    cached_result = validation_cache.get_filename_validation(input_data)
                else:
                    cached_result = None
                
                if cached_result is not None:
                    return cached_result
                
                # Not in cache, compute result
                try:
                    result = func(*args, **kwargs)
                    
                    # Cache the result
                    if cache_type == 'url':
                        validation_cache.cache_url_validation(input_data, result)
                    elif cache_type == 'json':
                        validation_cache.cache_json_validation(input_data, result)
                    elif cache_type == 'filename':
                        validation_cache.cache_filename_validation(input_data, result)
                    
                    return result
                except Exception as e:
                    # Don't cache exceptions, but still raise them
                    raise e
            else:
                # No caching for non-string inputs
                return func(*args, **kwargs)
        
        return wrapper
    return decorator

class PerformanceMonitor:
    """Monitor performance of security operations"""
    
    def __init__(self):
        self.timings = {}
        self.lock = threading.Lock()
    
    def time_operation(self, operation_name: str):
        """Context manager for timing operations"""
        return TimingContext(self, operation_name)
    
    def record_timing(self, operation_name: str, duration: float):
        """Record timing for an operation"""
        with self.lock:
            if operation_name not in self.timings:
                self.timings[operation_name] = []
            
            self.timings[operation_name].append(duration)
            
            # Keep only last 100 measurements
            if len(self.timings[operation_name]) > 100:
                self.timings[operation_name] = self.timings[operation_name][-100:]
    
    def get_stats(self) -> Dict[str, Any]:
        """Get performance statistics"""
        with self.lock:
            stats = {}
            for operation, timings in self.timings.items():
                if timings:
                    stats[operation] = {
                        'count': len(timings),
                        'avg_ms': sum(timings) * 1000 / len(timings),
                        'min_ms': min(timings) * 1000,
                        'max_ms': max(timings) * 1000,
                        'total_ms': sum(timings) * 1000
                    }
            return stats

class TimingContext:
    """Context manager for timing operations"""
    
    def __init__(self, monitor: PerformanceMonitor, operation_name: str):
        self.monitor = monitor
        self.operation_name = operation_name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            duration = time.time() - self.start_time
            self.monitor.record_timing(self.operation_name, duration)

# Global performance monitor
performance_monitor = PerformanceMonitor()

def timed_operation(operation_name: str):
    """Decorator for timing operations"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with performance_monitor.time_operation(operation_name):
                return func(*args, **kwargs)
        return wrapper
    return decorator

class AsyncValidator:
    """Asynchronous validation for non-blocking operations"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.thread_pool = None
        self._init_thread_pool()
    
    def _init_thread_pool(self):
        """Initialize thread pool for async operations"""
        try:
            from concurrent.futures import ThreadPoolExecutor
            self.thread_pool = ThreadPoolExecutor(max_workers=self.max_workers)
            logger.info(f"Initialized async validator with {self.max_workers} workers")
        except ImportError:
            logger.warning("ThreadPoolExecutor not available, async validation disabled")
    
    def validate_async(self, validation_func: Callable, *args, **kwargs):
        """Submit validation to thread pool"""
        if self.thread_pool:
            return self.thread_pool.submit(validation_func, *args, **kwargs)
        else:
            # Fallback to synchronous execution
            return validation_func(*args, **kwargs)
    
    def shutdown(self):
        """Shutdown thread pool"""
        if self.thread_pool:
            self.thread_pool.shutdown(wait=True)

# Global async validator
async_validator = AsyncValidator()

class MemoryOptimizer:
    """Memory optimization for security operations"""
    
    @staticmethod
    def optimize_string_operations():
        """Optimize string operations for better memory usage"""
        # Force garbage collection
        gc.collect()
    
    @staticmethod
    def clear_caches():
        """Clear all caches to free memory"""
        validation_cache.url_cache.clear()
        validation_cache.json_cache.clear()
        validation_cache.filename_cache.clear()
        validation_cache.header_cache.clear()
        gc.collect()
        logger.info("Cleared all validation caches")
    
    @staticmethod
    def get_memory_stats():
        """Get memory usage statistics"""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        return {
            'rss_mb': memory_info.rss / 1024 / 1024,  # Resident Set Size
            'vms_mb': memory_info.vms / 1024 / 1024,  # Virtual Memory Size
            'percent': process.memory_percent(),
            'available_mb': psutil.virtual_memory().available / 1024 / 1024
        }

def optimize_security_performance():
    """Apply performance optimizations for security operations"""
    
    # Patch security validation functions with caching
    try:
        from security_utils import InputValidator
        
        # Cache URL validation
        original_validate_url = InputValidator.validate_url
        InputValidator.validate_url = staticmethod(
            cached_validation('url')(timed_operation('url_validation')(original_validate_url))
        )
        
        # Cache JSON validation  
        original_validate_json = InputValidator.validate_json_input
        InputValidator.validate_json_input = staticmethod(
            cached_validation('json')(timed_operation('json_validation')(original_validate_json))
        )
        
        # Cache filename validation
        original_validate_filename = InputValidator.validate_filename
        InputValidator.validate_filename = staticmethod(
            cached_validation('filename')(timed_operation('filename_validation')(original_validate_filename))
        )
        
        logger.info("Applied performance optimizations to security validation")
        
    except ImportError:
        logger.warning("Could not apply security performance optimizations")

def get_performance_report():
    """Get comprehensive performance report"""
    return {
        'cache_stats': validation_cache.get_stats(),
        'timing_stats': performance_monitor.get_stats(),
        'memory_stats': MemoryOptimizer.get_memory_stats() if 'psutil' in globals() else None
    }

def start_performance_monitoring():
    """Start background performance monitoring"""
    def monitor_worker():
        while True:
            time.sleep(300)  # Monitor every 5 minutes
            try:
                # Log performance stats
                stats = get_performance_report()
                logger.info(f"Performance stats: {stats}")
                
                # Optimize memory if needed
                memory_stats = stats.get('memory_stats')
                if memory_stats and memory_stats.get('percent', 0) > 80:
                    logger.warning("High memory usage detected, clearing caches")
                    MemoryOptimizer.clear_caches()
                
            except Exception as e:
                logger.error(f"Error in performance monitoring: {e}")
    
    monitor_thread = threading.Thread(target=monitor_worker, daemon=True)
    monitor_thread.start()
    logger.info("Performance monitoring thread started")

# Auto-apply optimizations when module is imported
optimize_security_performance()
start_performance_monitoring()