#!/usr/bin/env python3
"""
ESP32 Camera Comprehensive Logging Module

This module provides detailed error logging and reporting for ESP32-camera
integration, including structured logging, error categorization, and
UI status indicator integration.

Requirements covered:
- 6.5: Log all connection and transmission errors with details
- 8.5: Implement error reporting in UI status indicators
"""

import logging
import json
import time
import os
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime
import threading


class ErrorCategory(Enum):
    """Categories of ESP32-camera errors"""
    CONNECTION = "connection"
    TRANSMISSION = "transmission"
    FRAME_CORRUPTION = "frame_corruption"
    CONFIGURATION = "configuration"
    HARDWARE = "hardware"
    PROTOCOL = "protocol"
    BUFFER = "buffer"
    TIMEOUT = "timeout"


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorRecord:
    """Structured error record for detailed logging"""
    timestamp: float
    category: ErrorCategory
    severity: ErrorSeverity
    message: str
    details: Dict[str, Any]
    exception_type: str = ""
    exception_message: str = ""
    stack_trace: str = ""
    context: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.context is None:
            self.context = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert error record to dictionary for JSON serialization"""
        data = asdict(self)
        data['category'] = self.category.value
        data['severity'] = self.severity.value
        data['datetime'] = datetime.fromtimestamp(self.timestamp).isoformat()
        return data
    
    def to_log_message(self) -> str:
        """Convert error record to formatted log message"""
        dt = datetime.fromtimestamp(self.timestamp)
        return (f"[{dt.strftime('%Y-%m-%d %H:%M:%S')}] "
                f"{self.severity.value.upper()} {self.category.value}: "
                f"{self.message}")


class ESP32Logger:
    """
    Comprehensive logging system for ESP32-camera errors.
    
    Implements Requirements 6.5, 8.5:
    - Log all connection and transmission errors with details
    - Implement error reporting in UI status indicators
    """
    
    def __init__(self, log_dir: str = "logs", max_log_files: int = 10):
        """
        Initialize ESP32 logger.
        
        Args:
            log_dir: Directory for log files
            max_log_files: Maximum number of log files to keep
        """
        self.log_dir = log_dir
        self.max_log_files = max_log_files
        
        # Create log directory
        os.makedirs(log_dir, exist_ok=True)
        
        # Error storage
        self.error_records: List[ErrorRecord] = []
        self.max_memory_records = 1000  # Keep last 1000 errors in memory
        
        # Statistics
        self.error_stats = {
            'total_errors': 0,
            'errors_by_category': {cat.value: 0 for cat in ErrorCategory},
            'errors_by_severity': {sev.value: 0 for sev in ErrorSeverity},
            'last_error_time': 0.0,
            'error_rate_per_hour': 0.0
        }
        
        # UI callbacks for status indicators (Requirements 8.5)
        self.status_callbacks: List[Callable[[ErrorRecord], None]] = []
        
        # Setup logging
        self.logger = self._setup_logging()
        
        # Background thread for log file management
        self.log_thread = threading.Thread(target=self._log_maintenance_loop, daemon=True)
        self.log_thread.start()
        
        self.logger.info("ESP32Logger initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """Setup structured logging system"""
        logger = logging.getLogger("ESP32Camera")
        logger.setLevel(logging.DEBUG)
        
        # Clear existing handlers
        logger.handlers.clear()
        
        # Create formatters
        detailed_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        
        simple_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        
        # File handler for detailed logs
        log_file = os.path.join(self.log_dir, f"esp32_camera_{datetime.now().strftime('%Y%m%d')}.log")
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(detailed_formatter)
        logger.addHandler(file_handler)
        
        # Error file handler for errors only
        error_file = os.path.join(self.log_dir, f"esp32_errors_{datetime.now().strftime('%Y%m%d')}.log")
        error_handler = logging.FileHandler(error_file, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(detailed_formatter)
        logger.addHandler(error_handler)
        
        # Console handler for important messages
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(simple_formatter)
        logger.addHandler(console_handler)
        
        return logger
    
    def add_status_callback(self, callback: Callable[[ErrorRecord], None]):
        """Add callback for UI status updates (Requirements 8.5)"""
        self.status_callbacks.append(callback)
    
    def remove_status_callback(self, callback: Callable[[ErrorRecord], None]):
        """Remove status callback"""
        if callback in self.status_callbacks:
            self.status_callbacks.remove(callback)
    
    def log_error(self, 
                  category: ErrorCategory,
                  severity: ErrorSeverity,
                  message: str,
                  details: Dict[str, Any] = None,
                  exception: Exception = None,
                  context: Dict[str, Any] = None) -> ErrorRecord:
        """
        Log an error with full details (Requirements 6.5).
        
        Args:
            category: Error category
            severity: Error severity level
            message: Human-readable error message
            details: Additional error details
            exception: Exception object if available
            context: Additional context information
            
        Returns:
            Created error record
        """
        if details is None:
            details = {}
        if context is None:
            context = {}
        
        # Create error record
        error_record = ErrorRecord(
            timestamp=time.time(),
            category=category,
            severity=severity,
            message=message,
            details=details,
            context=context
        )
        
        # Add exception information if provided
        if exception:
            error_record.exception_type = type(exception).__name__
            error_record.exception_message = str(exception)
            
            # Get stack trace
            import traceback
            error_record.stack_trace = traceback.format_exc()
        
        # Store error record
        self.error_records.append(error_record)
        
        # Maintain memory limit
        if len(self.error_records) > self.max_memory_records:
            self.error_records = self.error_records[-self.max_memory_records:]
        
        # Update statistics
        self._update_error_stats(error_record)
        
        # Log to file system
        log_level = self._severity_to_log_level(severity)
        log_message = self._format_log_message(error_record)
        self.logger.log(log_level, log_message)
        
        # Save detailed error to JSON file for analysis
        self._save_error_json(error_record)
        
        # Notify UI callbacks (Requirements 8.5)
        self._notify_status_callbacks(error_record)
        
        return error_record
    
    def _severity_to_log_level(self, severity: ErrorSeverity) -> int:
        """Convert error severity to logging level"""
        mapping = {
            ErrorSeverity.LOW: logging.INFO,
            ErrorSeverity.MEDIUM: logging.WARNING,
            ErrorSeverity.HIGH: logging.ERROR,
            ErrorSeverity.CRITICAL: logging.CRITICAL
        }
        return mapping.get(severity, logging.ERROR)
    
    def _format_log_message(self, error_record: ErrorRecord) -> str:
        """Format error record for logging"""
        msg = f"[{error_record.category.value.upper()}] {error_record.message}"
        
        if error_record.details:
            details_str = ", ".join(f"{k}={v}" for k, v in error_record.details.items())
            msg += f" | Details: {details_str}"
        
        if error_record.exception_message:
            msg += f" | Exception: {error_record.exception_message}"
        
        return msg
    
    def _save_error_json(self, error_record: ErrorRecord):
        """Save error record as JSON for detailed analysis"""
        try:
            json_file = os.path.join(self.log_dir, f"esp32_errors_{datetime.now().strftime('%Y%m%d')}.json")
            
            # Read existing data
            errors_data = []
            if os.path.exists(json_file):
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        errors_data = json.load(f)
                except (json.JSONDecodeError, IOError):
                    errors_data = []
            
            # Add new error
            errors_data.append(error_record.to_dict())
            
            # Keep only last 500 errors per file
            if len(errors_data) > 500:
                errors_data = errors_data[-500:]
            
            # Save updated data
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(errors_data, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            # Don't let logging errors break the main application
            print(f"Warning: Failed to save error JSON: {e}")
    
    def _update_error_stats(self, error_record: ErrorRecord):
        """Update error statistics"""
        self.error_stats['total_errors'] += 1
        self.error_stats['errors_by_category'][error_record.category.value] += 1
        self.error_stats['errors_by_severity'][error_record.severity.value] += 1
        self.error_stats['last_error_time'] = error_record.timestamp
        
        # Calculate error rate (errors per hour)
        if len(self.error_records) > 1:
            time_span = self.error_records[-1].timestamp - self.error_records[0].timestamp
            if time_span > 0:
                self.error_stats['error_rate_per_hour'] = len(self.error_records) / (time_span / 3600)
    
    def _notify_status_callbacks(self, error_record: ErrorRecord):
        """Notify UI status callbacks (Requirements 8.5)"""
        for callback in self.status_callbacks:
            try:
                callback(error_record)
            except Exception as e:
                # Don't let callback errors break logging
                print(f"Warning: Error in status callback: {e}")
    
    def _log_maintenance_loop(self):
        """Background thread for log file maintenance"""
        while True:
            try:
                self._cleanup_old_logs()
                time.sleep(3600)  # Run every hour
            except Exception as e:
                print(f"Warning: Error in log maintenance: {e}")
                time.sleep(3600)
    
    def _cleanup_old_logs(self):
        """Clean up old log files"""
        try:
            # Get all log files
            log_files = []
            for filename in os.listdir(self.log_dir):
                if filename.startswith('esp32_') and (filename.endswith('.log') or filename.endswith('.json')):
                    filepath = os.path.join(self.log_dir, filename)
                    log_files.append((filepath, os.path.getmtime(filepath)))
            
            # Sort by modification time (newest first)
            log_files.sort(key=lambda x: x[1], reverse=True)
            
            # Remove old files
            if len(log_files) > self.max_log_files:
                for filepath, _ in log_files[self.max_log_files:]:
                    try:
                        os.remove(filepath)
                        self.logger.info(f"Removed old log file: {filepath}")
                    except OSError as e:
                        self.logger.warning(f"Failed to remove log file {filepath}: {e}")
                        
        except Exception as e:
            self.logger.error(f"Error during log cleanup: {e}")
    
    # Convenience methods for common error types
    
    def log_connection_error(self, message: str, port: str = "", exception: Exception = None, **kwargs):
        """Log connection-related error"""
        details = {'port': port}
        details.update(kwargs)
        return self.log_error(
            ErrorCategory.CONNECTION,
            ErrorSeverity.HIGH,
            message,
            details=details,
            exception=exception
        )
    
    def log_transmission_error(self, message: str, frame_seq: int = 0, exception: Exception = None, **kwargs):
        """Log transmission-related error"""
        details = {'frame_sequence': frame_seq}
        details.update(kwargs)
        return self.log_error(
            ErrorCategory.TRANSMISSION,
            ErrorSeverity.MEDIUM,
            message,
            details=details,
            exception=exception
        )
    
    def log_frame_corruption(self, message: str, frame_size: int = 0, checksum: str = "", **kwargs):
        """Log frame corruption error"""
        details = {'frame_size': frame_size, 'checksum': checksum}
        details.update(kwargs)
        return self.log_error(
            ErrorCategory.FRAME_CORRUPTION,
            ErrorSeverity.MEDIUM,
            message,
            details=details
        )
    
    def log_configuration_error(self, message: str, config_params: Dict[str, Any] = None, **kwargs):
        """Log configuration-related error"""
        details = {'config_params': config_params or {}}
        details.update(kwargs)
        return self.log_error(
            ErrorCategory.CONFIGURATION,
            ErrorSeverity.LOW,
            message,
            details=details
        )
    
    def log_buffer_error(self, message: str, buffer_size: int = 0, buffer_usage: float = 0.0, **kwargs):
        """Log buffer-related error"""
        details = {'buffer_size': buffer_size, 'buffer_usage_percent': buffer_usage}
        details.update(kwargs)
        return self.log_error(
            ErrorCategory.BUFFER,
            ErrorSeverity.MEDIUM,
            message,
            details=details
        )
    
    def log_timeout_error(self, message: str, timeout_duration: float = 0.0, **kwargs):
        """Log timeout-related error"""
        details = {'timeout_duration': timeout_duration}
        details.update(kwargs)
        return self.log_error(
            ErrorCategory.TIMEOUT,
            ErrorSeverity.HIGH,
            message,
            details=details
        )
    
    # Query and analysis methods
    
    def get_recent_errors(self, count: int = 10) -> List[ErrorRecord]:
        """Get most recent errors"""
        return self.error_records[-count:] if self.error_records else []
    
    def get_errors_by_category(self, category: ErrorCategory, count: int = 50) -> List[ErrorRecord]:
        """Get errors by category"""
        filtered = [err for err in self.error_records if err.category == category]
        return filtered[-count:] if filtered else []
    
    def get_errors_by_severity(self, severity: ErrorSeverity, count: int = 50) -> List[ErrorRecord]:
        """Get errors by severity"""
        filtered = [err for err in self.error_records if err.severity == severity]
        return filtered[-count:] if filtered else []
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get comprehensive error statistics"""
        return self.error_stats.copy()
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get error summary for UI display"""
        recent_errors = self.get_recent_errors(5)
        
        return {
            'total_errors': self.error_stats['total_errors'],
            'error_rate_per_hour': self.error_stats['error_rate_per_hour'],
            'last_error_time': self.error_stats['last_error_time'],
            'recent_errors': [
                {
                    'category': err.category.value,
                    'severity': err.severity.value,
                    'message': err.message,
                    'timestamp': err.timestamp
                }
                for err in recent_errors
            ],
            'errors_by_category': self.error_stats['errors_by_category'],
            'errors_by_severity': self.error_stats['errors_by_severity']
        }
    
    def export_errors_csv(self, filename: str = None) -> str:
        """Export errors to CSV file for analysis"""
        if filename is None:
            filename = f"esp32_errors_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        filepath = os.path.join(self.log_dir, filename)
        
        try:
            import csv
            
            with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['timestamp', 'datetime', 'category', 'severity', 'message', 
                             'exception_type', 'exception_message', 'details']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                for error in self.error_records:
                    row = {
                        'timestamp': error.timestamp,
                        'datetime': datetime.fromtimestamp(error.timestamp).isoformat(),
                        'category': error.category.value,
                        'severity': error.severity.value,
                        'message': error.message,
                        'exception_type': error.exception_type,
                        'exception_message': error.exception_message,
                        'details': json.dumps(error.details)
                    }
                    writer.writerow(row)
            
            self.logger.info(f"Exported {len(self.error_records)} errors to {filepath}")
            return filepath
            
        except Exception as e:
            self.logger.error(f"Failed to export errors to CSV: {e}")
            raise


# Global logger instance
_global_logger: Optional[ESP32Logger] = None


def get_global_logger() -> ESP32Logger:
    """Get or create global ESP32 logger instance"""
    global _global_logger
    if _global_logger is None:
        _global_logger = ESP32Logger()
    return _global_logger


def reset_global_logger():
    """Reset global logger"""
    global _global_logger
    _global_logger = None