#!/usr/bin/env python3
"""
ESP32 Camera Error Handler Module

This module provides comprehensive error handling and recovery mechanisms
for ESP32-camera integration, including connection failure handling,
automatic reconnection with exponential backoff, and fallback mechanisms.

Requirements covered:
- 6.1: Automatic reconnection with exponential backoff
- 6.3: Fallback to default webcam when ESP32-camera fails
- 6.5: Log all connection and transmission errors with details
- 8.5: Implement error reporting in UI status indicators
"""

import time
import threading
import logging
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass
from enum import Enum
import cv2


class ConnectionState(Enum):
    """ESP32-camera connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"
    FALLBACK = "fallback"


@dataclass
class ConnectionAttempt:
    """Record of a connection attempt"""
    timestamp: float
    success: bool
    error_message: str = ""
    attempt_number: int = 0
    backoff_delay: float = 0.0


class ESP32ErrorHandler:
    """
    Handles ESP32-camera connection errors and recovery.
    
    Implements Requirements 6.1, 6.3:
    - Automatic reconnection with exponential backoff
    - Fallback to default webcam when ESP32-camera fails
    """
    
    def __init__(self, 
                 max_retry_attempts: int = 10,
                 initial_backoff: float = 1.0,
                 max_backoff: float = 30.0,
                 backoff_multiplier: float = 2.0,
                 connection_timeout: float = 5.0):
        """
        Initialize error handler.
        
        Args:
            max_retry_attempts: Maximum number of reconnection attempts
            initial_backoff: Initial backoff delay in seconds
            max_backoff: Maximum backoff delay in seconds
            backoff_multiplier: Multiplier for exponential backoff
            connection_timeout: Timeout for connection attempts
        """
        self.max_retry_attempts = max_retry_attempts
        self.initial_backoff = initial_backoff
        self.max_backoff = max_backoff
        self.backoff_multiplier = backoff_multiplier
        self.connection_timeout = connection_timeout
        
        # Connection state tracking
        self.state = ConnectionState.DISCONNECTED
        self.retry_count = 0
        self.last_error = ""
        self.connection_history = []
        
        # Callbacks for status updates (Requirements 8.5)
        self.status_callback: Optional[Callable[[ConnectionState, str], None]] = None
        self.error_callback: Optional[Callable[[str, Exception], None]] = None
        
        # Fallback video capture
        self.fallback_capture: Optional[cv2.VideoCapture] = None
        self.using_fallback = False
        
        # Recovery thread
        self.recovery_thread: Optional[threading.Thread] = None
        self.stop_recovery = threading.Event()
        
        # Setup logging (Requirements 6.5)
        self.logger = self._setup_logging()
    
    def _setup_logging(self) -> logging.Logger:
        """Setup detailed error logging (Requirements 6.5)"""
        logger = logging.getLogger("ESP32ErrorHandler")
        logger.setLevel(logging.DEBUG)
        
        # Create file handler for error logs
        file_handler = logging.FileHandler("esp32_errors.log")
        file_handler.setLevel(logging.DEBUG)
        
        # Create console handler for important messages
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        
        return logger
    
    def set_status_callback(self, callback: Callable[[ConnectionState, str], None]):
        """Set callback for status updates (Requirements 8.5)"""
        self.status_callback = callback
    
    def set_error_callback(self, callback: Callable[[str, Exception], None]):
        """Set callback for error notifications"""
        self.error_callback = callback
    
    def _update_status(self, state: ConnectionState, message: str = ""):
        """Update connection state and notify callbacks"""
        self.state = state
        
        # Log status change
        self.logger.info(f"Connection state changed to {state.value}: {message}")
        
        # Notify UI callback (Requirements 8.5)
        if self.status_callback:
            try:
                self.status_callback(state, message)
            except Exception as e:
                self.logger.error(f"Error in status callback: {e}")
    
    def _notify_error(self, error_message: str, exception: Exception = None):
        """Notify error callbacks and log error (Requirements 6.5)"""
        self.last_error = error_message
        
        # Log error with full details
        if exception:
            self.logger.error(f"ESP32 Error: {error_message}", exc_info=exception)
        else:
            self.logger.error(f"ESP32 Error: {error_message}")
        
        # Notify error callback
        if self.error_callback:
            try:
                self.error_callback(error_message, exception)
            except Exception as e:
                self.logger.error(f"Error in error callback: {e}")
    
    def calculate_backoff_delay(self, attempt_number: int) -> float:
        """
        Calculate exponential backoff delay (Requirements 6.1).
        
        Args:
            attempt_number: Current attempt number (0-based)
            
        Returns:
            Backoff delay in seconds
        """
        if attempt_number == 0:
            return 0.0  # No delay for first attempt
        
        # Exponential backoff: initial_backoff * (multiplier ^ (attempt - 1))
        delay = self.initial_backoff * (self.backoff_multiplier ** (attempt_number - 1))
        
        # Cap at maximum backoff
        return min(delay, self.max_backoff)
    
    def record_connection_attempt(self, success: bool, error_message: str = ""):
        """Record connection attempt for analysis"""
        attempt = ConnectionAttempt(
            timestamp=time.time(),
            success=success,
            error_message=error_message,
            attempt_number=self.retry_count,
            backoff_delay=self.calculate_backoff_delay(self.retry_count)
        )
        
        self.connection_history.append(attempt)
        
        # Keep only last 50 attempts to prevent memory growth
        if len(self.connection_history) > 50:
            self.connection_history = self.connection_history[-50:]
        
        # Log attempt details (Requirements 6.5)
        if success:
            self.logger.info(f"Connection attempt {self.retry_count} succeeded")
        else:
            self.logger.warning(
                f"Connection attempt {self.retry_count} failed: {error_message}"
            )
    
    def attempt_connection(self, connect_func: Callable[[], bool]) -> bool:
        """
        Attempt ESP32-camera connection with error handling.
        
        Args:
            connect_func: Function that attempts connection, returns True if successful
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._update_status(ConnectionState.CONNECTING, "Attempting connection...")
            
            # Set connection timeout
            start_time = time.time()
            success = False
            
            try:
                success = connect_func()
            except Exception as e:
                error_msg = f"Connection function failed: {str(e)}"
                self._notify_error(error_msg, e)
                self.record_connection_attempt(False, error_msg)
                return False
            
            # Check if connection took too long
            connection_time = time.time() - start_time
            if connection_time > self.connection_timeout:
                error_msg = f"Connection timeout after {connection_time:.1f}s"
                self._notify_error(error_msg)
                self.record_connection_attempt(False, error_msg)
                return False
            
            if success:
                self._update_status(ConnectionState.CONNECTED, "Connection established")
                self.record_connection_attempt(True)
                self.retry_count = 0  # Reset retry count on success
                self.using_fallback = False
                return True
            else:
                error_msg = "Connection function returned False"
                self._notify_error(error_msg)
                self.record_connection_attempt(False, error_msg)
                return False
                
        except Exception as e:
            error_msg = f"Unexpected error during connection: {str(e)}"
            self._notify_error(error_msg, e)
            self.record_connection_attempt(False, error_msg)
            return False
    
    def start_automatic_recovery(self, connect_func: Callable[[], bool]):
        """
        Start automatic reconnection with exponential backoff (Requirements 6.1).
        
        Args:
            connect_func: Function that attempts connection
        """
        if self.recovery_thread and self.recovery_thread.is_alive():
            self.logger.warning("Recovery thread already running")
            return
        
        self.stop_recovery.clear()
        self.recovery_thread = threading.Thread(
            target=self._recovery_loop,
            args=(connect_func,),
            daemon=True
        )
        self.recovery_thread.start()
        
        self.logger.info("Started automatic recovery thread")
    
    def stop_automatic_recovery(self):
        """Stop automatic recovery thread"""
        if self.recovery_thread and self.recovery_thread.is_alive():
            self.stop_recovery.set()
            self.recovery_thread.join(timeout=5.0)
            self.logger.info("Stopped automatic recovery thread")
    
    def _recovery_loop(self, connect_func: Callable[[], bool]):
        """
        Main recovery loop with exponential backoff (Requirements 6.1).
        
        Args:
            connect_func: Function that attempts connection
        """
        self.retry_count = 0
        
        while not self.stop_recovery.is_set() and self.retry_count < self.max_retry_attempts:
            try:
                # Calculate backoff delay
                backoff_delay = self.calculate_backoff_delay(self.retry_count)
                
                if backoff_delay > 0:
                    self._update_status(
                        ConnectionState.RECONNECTING,
                        f"Waiting {backoff_delay:.1f}s before retry {self.retry_count + 1}/{self.max_retry_attempts}"
                    )
                    
                    # Wait with ability to be interrupted
                    if self.stop_recovery.wait(timeout=backoff_delay):
                        break  # Stop signal received
                
                # Attempt reconnection
                self.retry_count += 1
                self._update_status(
                    ConnectionState.RECONNECTING,
                    f"Reconnection attempt {self.retry_count}/{self.max_retry_attempts}"
                )
                
                if self.attempt_connection(connect_func):
                    self.logger.info(f"Reconnection successful after {self.retry_count} attempts")
                    return  # Success, exit recovery loop
                
            except Exception as e:
                error_msg = f"Error in recovery loop: {str(e)}"
                self._notify_error(error_msg, e)
        
        # All retry attempts failed
        if self.retry_count >= self.max_retry_attempts:
            self._update_status(
                ConnectionState.FAILED,
                f"All {self.max_retry_attempts} reconnection attempts failed"
            )
            self.logger.error(f"Recovery failed after {self.max_retry_attempts} attempts")
            
            # Activate fallback mechanism (Requirements 6.3)
            self.activate_fallback()
    
    def activate_fallback(self):
        """
        Activate fallback to default webcam (Requirements 6.3).
        """
        try:
            self._update_status(ConnectionState.FALLBACK, "Activating fallback webcam...")
            
            # Try to open default webcam
            self.fallback_capture = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not self.fallback_capture.isOpened():
                # Try without DirectShow
                self.fallback_capture.release()
                self.fallback_capture = cv2.VideoCapture(0)
            
            if self.fallback_capture.isOpened():
                # Test fallback capture
                ret, frame = self.fallback_capture.read()
                if ret and frame is not None:
                    self.using_fallback = True
                    self._update_status(
                        ConnectionState.FALLBACK,
                        "Fallback webcam activated successfully"
                    )
                    self.logger.info("Fallback webcam activated successfully")
                    return True
                else:
                    self.fallback_capture.release()
                    self.fallback_capture = None
            
            # Fallback failed
            self._update_status(ConnectionState.FAILED, "Fallback webcam activation failed")
            self.logger.error("Failed to activate fallback webcam")
            return False
            
        except Exception as e:
            error_msg = f"Error activating fallback webcam: {str(e)}"
            self._notify_error(error_msg, e)
            self._update_status(ConnectionState.FAILED, "Fallback activation error")
            return False
    
    def get_fallback_capture(self) -> Optional[cv2.VideoCapture]:
        """
        Get fallback video capture if active.
        
        Returns:
            Fallback VideoCapture object or None
        """
        if self.using_fallback and self.fallback_capture:
            return self.fallback_capture
        return None
    
    def is_using_fallback(self) -> bool:
        """Check if currently using fallback webcam"""
        return self.using_fallback
    
    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get detailed connection statistics for analysis.
        
        Returns:
            Dictionary with connection statistics
        """
        if not self.connection_history:
            return {
                'total_attempts': 0,
                'successful_attempts': 0,
                'failed_attempts': 0,
                'success_rate': 0.0,
                'avg_connection_time': 0.0,
                'last_error': self.last_error,
                'current_state': self.state.value,
                'retry_count': self.retry_count,
                'using_fallback': self.using_fallback
            }
        
        successful = [a for a in self.connection_history if a.success]
        failed = [a for a in self.connection_history if not a.success]
        
        return {
            'total_attempts': len(self.connection_history),
            'successful_attempts': len(successful),
            'failed_attempts': len(failed),
            'success_rate': len(successful) / len(self.connection_history) * 100,
            'last_error': self.last_error,
            'current_state': self.state.value,
            'retry_count': self.retry_count,
            'using_fallback': self.using_fallback,
            'recent_errors': [a.error_message for a in failed[-5:]]  # Last 5 errors
        }
    
    def reset_error_state(self):
        """Reset error handler state for fresh start"""
        self.stop_automatic_recovery()
        
        self.state = ConnectionState.DISCONNECTED
        self.retry_count = 0
        self.last_error = ""
        self.using_fallback = False
        
        if self.fallback_capture:
            self.fallback_capture.release()
            self.fallback_capture = None
        
        self.logger.info("Error handler state reset")
    
    def cleanup(self):
        """Cleanup resources"""
        self.stop_automatic_recovery()
        
        if self.fallback_capture:
            self.fallback_capture.release()
            self.fallback_capture = None
        
        self.logger.info("Error handler cleanup completed")


# Global error handler instance for shared use
_global_error_handler: Optional[ESP32ErrorHandler] = None


def get_global_error_handler() -> ESP32ErrorHandler:
    """Get or create global error handler instance"""
    global _global_error_handler
    if _global_error_handler is None:
        _global_error_handler = ESP32ErrorHandler()
    return _global_error_handler


def reset_global_error_handler():
    """Reset global error handler"""
    global _global_error_handler
    if _global_error_handler:
        _global_error_handler.cleanup()
    _global_error_handler = None