#!/usr/bin/env python3
"""
ESP32 Camera Receiver Module

This module provides the ESP32CameraReceiver class for receiving video frames
from ESP32-camera module over serial communication. It handles frame parsing,
reconstruction, JPEG decoding, and frame buffering.

Requirements covered:
- 3.1: Serial connection to COM3 port
- 3.2: Parse frame headers and reconstruct JPEG data
- 3.3: Decode received JPEG frames to OpenCV format
- 3.4: Validate frame integrity and dimensions
- 3.5: Create frame buffer to handle timing variations
- 7.2: Implement buffer overflow management
"""

import serial
import time
import threading
import queue
import struct
import zlib
import gc
import weakref
from typing import Optional, Tuple, Dict, Any
from dataclasses import dataclass
from collections import deque
import numpy as np
import cv2

# Memory monitoring imports
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠️ psutil not available - memory monitoring will be limited")

# Import error handler, logger, and frame validator for comprehensive error handling
try:
    from esp32_error_handler import ESP32ErrorHandler, ConnectionState
    from esp32_logger import ESP32Logger, ErrorCategory, ErrorSeverity, get_global_logger
    from esp32_frame_validator import ESP32FrameValidator, get_global_validator, CorruptionReport
except ImportError:
    # Fallback if modules not available
    ESP32ErrorHandler = None
    ConnectionState = None
    ESP32Logger = None
    ErrorCategory = None
    ErrorSeverity = None
    get_global_logger = None
    ESP32FrameValidator = None
    get_global_validator = None
    CorruptionReport = None


@dataclass
class FrameMetadata:
    """Metadata for a video frame"""
    sequence: int
    size: int
    timestamp: float
    checksum: str
    fps: float = 0.0
    
    @classmethod
    def from_header(cls, header: str) -> 'FrameMetadata':
        """Parse FRAME_START header to extract metadata"""
        # Expected format: FRAME_START|size:12345|seq:001
        parts = header.split('|')
        metadata = {}
        
        for part in parts[1:]:  # Skip FRAME_START
            if ':' in part:
                key, value = part.split(':', 1)
                metadata[key.strip()] = value.strip()
        
        return cls(
            sequence=int(metadata.get('seq', 0)),
            size=int(metadata.get('size', 0)),
            timestamp=time.time(),
            checksum='',
            fps=float(metadata.get('fps', 0.0))
        )


@dataclass
class CameraConfig:
    """Camera configuration parameters"""
    resolution: str = "VGA"  # QVGA, VGA, SVGA, XGA
    fps: int = 15           # 5-30 FPS
    quality: int = 50       # JPEG quality 10-63
    port: str = "COM3"      # Serial port
    baud: int = 921600      # Baud rate
    
    def to_command(self) -> str:
        """Convert configuration to ESP32 command format"""
        return f"CONFIG|resolution:{self.resolution}|fps:{self.fps}|quality:{self.quality}"


class ESP32CameraReceiver:
    """
    Handles serial communication with ESP32-camera module.
    
    This class manages:
    - Serial connection to ESP32-camera
    - Frame header/footer parsing
    - JPEG frame reconstruction from chunks
    - Frame decoding and validation
    - Frame buffering and timing management (Requirements 3.5, 7.2)
    - Memory optimization for continuous operation (Requirements 7.5)
    """
    
    def __init__(self, port: str = "COM3", baud: int = 921600, buffer_size: int = 10):
        """
        Initialize ESP32 camera receiver.
        
        Args:
            port: Serial port (e.g., "COM3")
            baud: Baud rate for serial communication
            buffer_size: Maximum number of frames to buffer (Requirements 3.5)
        """
        self.port = port
        self.baud = baud
        self.buffer_size = buffer_size
        
        # Serial connection
        self.serial_port: Optional[serial.Serial] = None
        self.connected = False
        
        # Memory management tracking (Requirements 7.5)
        self._memory_stats = {
            'peak_memory_mb': 0.0,
            'current_memory_mb': 0.0,
            'memory_leaks_detected': 0,
            'gc_collections': 0,
            'last_memory_check': 0.0,
            'frame_buffer_memory_mb': 0.0,
            'total_frames_processed': 0,
            'memory_cleanup_count': 0
        }
        self._memory_check_interval = 30.0  # Check memory every 30 seconds
        self._memory_threshold_mb = 500.0   # Trigger cleanup if memory exceeds 500MB
        self._last_gc_time = time.time()
        self._gc_interval = 60.0  # Force garbage collection every 60 seconds
        
        # Weak references for cleanup tracking
        self._frame_references = weakref.WeakSet()
        
        # Error handler for connection management (Requirements 6.1, 6.3)
        if ESP32ErrorHandler:
            self.error_handler = ESP32ErrorHandler(
                max_retry_attempts=10,
                initial_backoff=1.0,
                max_backoff=30.0,
                backoff_multiplier=2.0,
                connection_timeout=5.0
            )
            # Set up error handler callbacks
            self.error_handler.set_status_callback(self._on_connection_status_change)
            self.error_handler.set_error_callback(self._on_connection_error)
        else:
            self.error_handler = None
        
        # Comprehensive error logger (Requirements 6.5, 8.5)
        if get_global_logger:
            self.logger = get_global_logger()
            # Set up UI status callback for error reporting
            self.logger.add_status_callback(self._on_error_logged)
        else:
            self.logger = None
        
        # Frame corruption validator (Requirements 6.2)
        if get_global_validator:
            self.frame_validator = get_global_validator()
            # Set up validation callbacks
            self.frame_validator.set_corruption_callback(self._on_frame_corruption)
            self.frame_validator.set_retransmission_callback(self._on_retransmission_request)
        else:
            self.frame_validator = None
        
        # Frame reconstruction state
        self.current_frame_data = bytearray()
        self.current_metadata: Optional[FrameMetadata] = None
        self.expected_size = 0
        self.receiving_frame = False
        
        # Frame buffer for timing management (Requirements 3.5, 7.2)
        self.frame_buffer = queue.Queue(maxsize=buffer_size)
        self.frame_stats = {
            'frames_received': 0,
            'frames_dropped': 0,
            'frames_corrupted': 0,
            'last_fps': 0.0,
            'buffer_overflows': 0,
            'avg_frame_time': 0.0,
            'last_frame_time': 0.0,
            'connection_errors': 0,
            'reconnection_attempts': 0
        }
        
        # Timing management for buffer overflow prevention (Requirements 7.2)
        self.frame_timestamps = deque(maxlen=30)  # Track last 30 frame times
        self.last_buffer_check = time.time()
        self.buffer_check_interval = 1.0  # Check buffer health every second
        
        # Threading for continuous reading
        self.read_thread: Optional[threading.Thread] = None
        self.stop_reading = threading.Event()
        
        # Configuration
        self.config = CameraConfig(port=port, baud=baud)
        
        # Connection monitoring
        self.last_frame_received = 0.0
        self.connection_check_interval = 5.0  # Check connection every 5 seconds
        self.frame_timeout = 10.0  # Consider connection lost if no frames for 10 seconds
    
    def connect(self) -> bool:
        """
        Establish serial connection to ESP32-camera with error handling.
        Implements Requirements 6.1: Automatic reconnection with exponential backoff
        
        Returns:
            True if connection successful, False otherwise
        """
        if self.error_handler:
            # Use error handler for robust connection
            return self.error_handler.attempt_connection(self._attempt_serial_connection)
        else:
            # Fallback to simple connection
            return self._attempt_serial_connection()
    
    def _attempt_serial_connection(self) -> bool:
        """
        Attempt to establish serial connection (internal method).
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Close existing connection if any
            if self.serial_port and self.serial_port.is_open:
                self.serial_port.close()
            
            self.serial_port = serial.Serial(
                port=self.port,
                baudrate=self.baud,
                timeout=0.1,
                write_timeout=1.0
            )
            
            # Wait for ESP32 to initialize
            time.sleep(2)
            
            # Test connection by sending a simple command
            test_success = self._test_connection()
            
            if test_success:
                self.connected = True
                self.last_frame_received = time.time()
                print(f"✅ Connected to ESP32-camera on {self.port} @ {self.baud}")
                
                # Start reading thread
                self.stop_reading.clear()
                self.read_thread = threading.Thread(target=self._read_serial_data, daemon=True)
                self.read_thread.start()
                
                # Start connection monitoring
                self._start_connection_monitoring()
                
                return True
            else:
                if self.serial_port:
                    self.serial_port.close()
                self.connected = False
                return False
            
        except serial.SerialException as e:
            error_msg = f"Serial connection failed on {self.port}: {e}"
            print(f"❌ {error_msg}")
            
            # Log detailed error (Requirements 6.5)
            if self.logger:
                self.logger.log_connection_error(
                    error_msg,
                    port=self.port,
                    baud=self.baud,
                    exception=e,
                    context={'connection_attempt': True}
                )
            
            if self.error_handler:
                self.error_handler._notify_error(error_msg, e)
            self.frame_stats['connection_errors'] += 1
            self.connected = False
            return False
        except Exception as e:
            error_msg = f"Unexpected error connecting to {self.port}: {e}"
            print(f"❌ {error_msg}")
            
            # Log detailed error (Requirements 6.5)
            if self.logger:
                self.logger.log_connection_error(
                    error_msg,
                    port=self.port,
                    baud=self.baud,
                    exception=e,
                    context={'connection_attempt': True, 'unexpected_error': True}
                )
            
            if self.error_handler:
                self.error_handler._notify_error(error_msg, e)
            self.frame_stats['connection_errors'] += 1
            self.connected = False
            return False
    
    def _test_connection(self) -> bool:
        """
        Test ESP32-camera connection by sending a status request.
        
        Returns:
            True if ESP32 responds, False otherwise
        """
        try:
            if not self.serial_port or not self.serial_port.is_open:
                return False
            
            # Clear any pending data
            self.serial_port.reset_input_buffer()
            self.serial_port.reset_output_buffer()
            
            # Send status request
            self.serial_port.write(b"STATUS\n")
            
            # Wait for response (up to 3 seconds)
            start_time = time.time()
            while time.time() - start_time < 3.0:
                if self.serial_port.in_waiting > 0:
                    response = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    if response.startswith("STATUS") or response.startswith("FRAME_"):
                        print(f"📡 ESP32 connection test successful: {response}")
                        return True
                time.sleep(0.1)
            
            print("⚠️ ESP32 connection test timeout - no response")
            return False
            
        except Exception as e:
            print(f"⚠️ ESP32 connection test failed: {e}")
            return False
    
    def _start_connection_monitoring(self):
        """Start background connection monitoring"""
        if hasattr(self, '_monitor_thread') and self._monitor_thread and self._monitor_thread.is_alive():
            return
        
        self._monitor_thread = threading.Thread(target=self._connection_monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def _check_memory_usage(self):
        """
        Monitor memory usage and perform cleanup if needed (Requirements 7.5).
        Implements proper memory cleanup for frame buffers and prevents memory leaks.
        """
        current_time = time.time()
        
        # Only check memory periodically to avoid performance impact
        if current_time - self._memory_stats['last_memory_check'] < self._memory_check_interval:
            return
        
        self._memory_stats['last_memory_check'] = current_time
        
        # Get current memory usage
        if PSUTIL_AVAILABLE:
            try:
                process = psutil.Process()
                memory_info = process.memory_info()
                current_memory_mb = memory_info.rss / 1024 / 1024  # Convert to MB
                
                self._memory_stats['current_memory_mb'] = current_memory_mb
                
                # Track peak memory usage
                if current_memory_mb > self._memory_stats['peak_memory_mb']:
                    self._memory_stats['peak_memory_mb'] = current_memory_mb
                
                # Calculate frame buffer memory usage estimate
                buffer_memory_mb = (self.frame_buffer.qsize() * 640 * 480 * 3) / (1024 * 1024)  # Rough estimate
                self._memory_stats['frame_buffer_memory_mb'] = buffer_memory_mb
                
                # Check for memory threshold breach
                if current_memory_mb > self._memory_threshold_mb:
                    print(f"⚠️ Memory usage high: {current_memory_mb:.1f}MB (threshold: {self._memory_threshold_mb}MB)")
                    self._perform_memory_cleanup()
                
                # Detect potential memory leaks
                if (self._memory_stats['total_frames_processed'] > 1000 and 
                    current_memory_mb > self._memory_stats['peak_memory_mb'] * 0.9):
                    # Memory usage is consistently high - potential leak
                    self._memory_stats['memory_leaks_detected'] += 1
                    if self._memory_stats['memory_leaks_detected'] % 10 == 0:
                        print(f"⚠️ Potential memory leak detected - consistent high usage: {current_memory_mb:.1f}MB")
                        self._perform_aggressive_cleanup()
                
            except Exception as e:
                print(f"⚠️ Error checking memory usage: {e}")
        
        # Force garbage collection periodically
        if current_time - self._last_gc_time > self._gc_interval:
            self._force_garbage_collection()
            self._last_gc_time = current_time
    
    def _perform_memory_cleanup(self):
        """
        Perform memory cleanup to free up resources (Requirements 7.5).
        """
        print("🧹 Performing memory cleanup...")
        cleanup_count = 0
        
        # Clear old frames from buffer if it's getting full
        if self.frame_buffer.qsize() > self.buffer_size * 0.8:
            frames_to_remove = max(1, self.frame_buffer.qsize() // 4)
            for _ in range(frames_to_remove):
                try:
                    old_frame = self.frame_buffer.get_nowait()
                    # Explicitly delete frame data
                    if 'frame' in old_frame:
                        del old_frame['frame']
                    del old_frame
                    cleanup_count += 1
                except queue.Empty:
                    break
        
        # Clear frame reconstruction buffers
        if len(self.current_frame_data) > 0:
            self.current_frame_data = bytearray()
            cleanup_count += 1
        
        # Trim frame timestamps if too many
        if len(self.frame_timestamps) > 20:
            # Keep only the most recent 15 timestamps
            while len(self.frame_timestamps) > 15:
                self.frame_timestamps.popleft()
            cleanup_count += 1
        
        # Force garbage collection
        self._force_garbage_collection()
        
        self._memory_stats['memory_cleanup_count'] += 1
        
        if cleanup_count > 0:
            print(f"🧹 Memory cleanup completed: {cleanup_count} items freed")
    
    def _perform_aggressive_cleanup(self):
        """
        Perform aggressive memory cleanup for potential memory leaks (Requirements 7.5).
        """
        print("🧹 Performing aggressive memory cleanup...")
        
        # Clear entire frame buffer
        cleared_frames = 0
        while not self.frame_buffer.empty():
            try:
                old_frame = self.frame_buffer.get_nowait()
                if 'frame' in old_frame:
                    del old_frame['frame']
                del old_frame
                cleared_frames += 1
            except queue.Empty:
                break
        
        # Reset frame reconstruction state
        self.current_frame_data = bytearray()
        self.current_metadata = None
        self.expected_size = 0
        self.receiving_frame = False
        
        # Clear frame timestamps
        self.frame_timestamps.clear()
        
        # Force multiple garbage collections
        for _ in range(3):
            self._force_garbage_collection()
        
        print(f"🧹 Aggressive cleanup completed: {cleared_frames} frames cleared")
    
    def _force_garbage_collection(self):
        """
        Force garbage collection and track statistics (Requirements 7.5).
        """
        collected = gc.collect()
        self._memory_stats['gc_collections'] += 1
        
        if collected > 0:
            print(f"🗑️ Garbage collection freed {collected} objects")
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """
        Get detailed memory usage statistics (Requirements 7.5).
        
        Returns:
            Dictionary with memory usage metrics
        """
        # Update current memory usage
        current_memory_mb = 0.0
        if PSUTIL_AVAILABLE:
            try:
                process = psutil.Process()
                current_memory_mb = process.memory_info().rss / 1024 / 1024
                self._memory_stats['current_memory_mb'] = current_memory_mb
            except:
                pass
        
        # Calculate memory efficiency metrics
        frames_per_mb = 0.0
        if current_memory_mb > 0 and self._memory_stats['total_frames_processed'] > 0:
            frames_per_mb = self._memory_stats['total_frames_processed'] / current_memory_mb
        
        return {
            'current_memory_mb': current_memory_mb,
            'peak_memory_mb': self._memory_stats['peak_memory_mb'],
            'frame_buffer_memory_mb': self._memory_stats['frame_buffer_memory_mb'],
            'memory_leaks_detected': self._memory_stats['memory_leaks_detected'],
            'gc_collections': self._memory_stats['gc_collections'],
            'memory_cleanup_count': self._memory_stats['memory_cleanup_count'],
            'frames_per_mb': frames_per_mb,
            'total_frames_processed': self._memory_stats['total_frames_processed'],
            'buffer_usage_percent': (self.frame_buffer.qsize() / self.buffer_size * 100) if self.buffer_size > 0 else 0,
            'psutil_available': PSUTIL_AVAILABLE
        }
    
    def optimize_memory_usage(self, target_memory_mb: float = None):
        """
        Optimize memory usage by adjusting buffer sizes and cleanup thresholds (Requirements 7.5).
        
        Args:
            target_memory_mb: Target memory usage in MB (optional)
        """
        if target_memory_mb:
            self._memory_threshold_mb = target_memory_mb
        
        # Get current memory usage
        memory_stats = self.get_memory_stats()
        current_memory = memory_stats['current_memory_mb']
        
        print(f"🔧 Optimizing memory usage (current: {current_memory:.1f}MB, target: {self._memory_threshold_mb:.1f}MB)")
        
        # Adjust buffer size based on memory usage
        if current_memory > self._memory_threshold_mb:
            # Reduce buffer size to save memory
            new_buffer_size = max(3, self.buffer_size // 2)
            if new_buffer_size != self.buffer_size:
                self.set_buffer_size(new_buffer_size)
                print(f"🔧 Reduced buffer size to {new_buffer_size} to save memory")
        
        elif current_memory < self._memory_threshold_mb * 0.5:
            # Increase buffer size if we have plenty of memory
            new_buffer_size = min(20, self.buffer_size * 2)
            if new_buffer_size != self.buffer_size:
                self.set_buffer_size(new_buffer_size)
                print(f"🔧 Increased buffer size to {new_buffer_size} (plenty of memory available)")
        
        # Adjust memory check frequency based on usage
        if current_memory > self._memory_threshold_mb * 0.8:
            self._memory_check_interval = 10.0  # Check more frequently
            self._gc_interval = 30.0  # More frequent GC
        else:
            self._memory_check_interval = 30.0  # Normal frequency
            self._gc_interval = 60.0  # Normal GC frequency
        
        # Perform cleanup if needed
        if current_memory > self._memory_threshold_mb:
            self._perform_memory_cleanup()

    def _connection_monitor_loop(self):
        """Monitor connection health and trigger recovery if needed"""
        while self.connected and not self.stop_reading.is_set():
            try:
                current_time = time.time()
                
                # Handle retransmission timeouts (Requirements 6.2)
                if self.frame_validator:
                    self.frame_validator.handle_retransmission_timeout()
                
                # Check if we've received frames recently
                if (self.last_frame_received > 0 and 
                    current_time - self.last_frame_received > self.frame_timeout):
                    
                    print(f"⚠️ No frames received for {self.frame_timeout}s - connection may be lost")
                    
                    # Test connection
                    if not self._test_connection():
                        print("❌ Connection test failed - triggering recovery")
                        self._trigger_connection_recovery()
                        break
                
                # Sleep before next check
                time.sleep(self.connection_check_interval)
                
            except Exception as e:
                print(f"⚠️ Error in connection monitor: {e}")
                break
    
    def _trigger_connection_recovery(self):
        """Trigger automatic connection recovery"""
        self.connected = False
        self.frame_stats['reconnection_attempts'] += 1
        
        if self.error_handler:
            print("🔄 Starting automatic connection recovery...")
            self.error_handler.start_automatic_recovery(self._attempt_serial_connection)
        else:
            print("⚠️ No error handler available for recovery")
    
    def _on_connection_status_change(self, state: 'ConnectionState', message: str):
        """Handle connection status changes from error handler"""
        print(f"📡 Connection status: {state.value} - {message}")
        
        if state == ConnectionState.CONNECTED:
            self.connected = True
        elif state in [ConnectionState.FAILED, ConnectionState.FALLBACK]:
            self.connected = False
    
    def _on_connection_error(self, error_message: str, exception: Exception = None):
        """Handle connection errors from error handler"""
        print(f"❌ Connection error: {error_message}")
        self.frame_stats['connection_errors'] += 1
    
    def _on_error_logged(self, error_record):
        """Handle error logging callback for UI status updates (Requirements 8.5)"""
        # This method can be overridden by subclasses or used for additional processing
        pass
    
    def _on_frame_corruption(self, corruption_report: 'CorruptionReport'):
        """Handle frame corruption detection (Requirements 6.2)"""
        print(f"🔍 Frame corruption detected: {corruption_report.corruption_type.value} "
              f"for frame {corruption_report.frame_sequence}")
        
        # Log corruption details
        if self.logger:
            self.logger.log_frame_corruption(
                f"Frame corruption: {corruption_report.corruption_type.value}",
                frame_size=corruption_report.details.get('frame_size', 0),
                sequence=corruption_report.frame_sequence,
                expected_value=str(corruption_report.expected_value),
                actual_value=str(corruption_report.actual_value),
                corruption_details=corruption_report.details
            )
    
    def _on_retransmission_request(self, retransmission_request):
        """Handle retransmission request (Requirements 6.2)"""
        try:
            if not self.serial_port or not self.serial_port.is_open:
                print("⚠️ Cannot send retransmission request: not connected")
                return
            
            # Generate retransmission command
            if self.frame_validator:
                command = self.frame_validator.get_retransmission_command(
                    retransmission_request.sequence_number
                )
            else:
                command = f"RETRANSMIT|seq:{retransmission_request.sequence_number:03d}"
            
            # Send retransmission request to ESP32
            self.serial_port.write((command + "\n").encode('utf-8'))
            
            print(f"📤 Sent retransmission request: {command}")
            
            # Log retransmission request
            if self.logger:
                self.logger.log_transmission_error(
                    f"Retransmission requested for frame {retransmission_request.sequence_number}",
                    frame_seq=retransmission_request.sequence_number,
                    corruption_type=retransmission_request.corruption_type.value,
                    retry_count=retransmission_request.retry_count
                )
            
        except Exception as e:
            print(f"❌ Error sending retransmission request: {e}")
            if self.logger:
                self.logger.log_transmission_error(
                    f"Failed to send retransmission request: {e}",
                    frame_seq=retransmission_request.sequence_number,
                    exception=e
                )
    
    def disconnect(self):
        """Close serial connection and stop reading thread with memory cleanup (Requirements 7.5)"""
        self.connected = False
        
        # Stop error handler recovery
        if self.error_handler:
            self.error_handler.stop_automatic_recovery()
        
        # Stop reading thread
        if self.read_thread and self.read_thread.is_alive():
            self.stop_reading.set()
            self.read_thread.join(timeout=2)
        
        # Stop monitor thread
        if hasattr(self, '_monitor_thread') and self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1)
        
        # Perform comprehensive memory cleanup (Requirements 7.5)
        print("🧹 Performing disconnect memory cleanup...")
        
        # Clear frame buffer with proper cleanup
        cleared_frames = 0
        while not self.frame_buffer.empty():
            try:
                frame_package = self.frame_buffer.get_nowait()
                if 'frame' in frame_package:
                    del frame_package['frame']
                del frame_package
                cleared_frames += 1
            except queue.Empty:
                break
        
        # Clear frame reconstruction state
        self.current_frame_data = bytearray()
        self.current_metadata = None
        self.expected_size = 0
        self.receiving_frame = False
        
        # Clear timing data
        self.frame_timestamps.clear()
        
        # Clear weak references
        self._frame_references.clear()
        
        # Force garbage collection
        self._force_garbage_collection()
        
        # Close serial port
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
            print(f"📡 Disconnected from {self.port}")
        
        if cleared_frames > 0:
            print(f"🧹 Cleanup completed: {cleared_frames} frames freed")
    
    def get_fallback_capture(self):
        """Get fallback video capture if available (Requirements 6.3)"""
        if self.error_handler:
            return self.error_handler.get_fallback_capture()
        return None
    
    def is_using_fallback(self) -> bool:
        """Check if currently using fallback webcam (Requirements 6.3)"""
        if self.error_handler:
            return self.error_handler.is_using_fallback()
        return False
    
    def configure_camera(self, resolution: str = None, fps: int = None, quality: int = None) -> bool:
        """
        Send configuration commands to ESP32-camera.
        
        Args:
            resolution: Camera resolution (QVGA, VGA, SVGA, XGA)
            fps: Frame rate (5-30 FPS)
            quality: JPEG quality (10-63)
            
        Returns:
            True if command sent successfully, False otherwise
        """
        if not self.connected or not self.serial_port:
            print("❌ Cannot configure camera: not connected")
            return False
        
        # Update configuration
        if resolution is not None:
            self.config.resolution = resolution
        if fps is not None:
            self.config.fps = fps
        if quality is not None:
            self.config.quality = quality
        
        try:
            command = self.config.to_command() + "\n"
            self.serial_port.write(command.encode('utf-8'))
            print(f"📤 Sent configuration: {command.strip()}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to send configuration: {e}")
            return False
    
    def _read_serial_data(self):
        """
        Continuously read data from serial port in background thread.
        Handles frame parsing and reconstruction.
        """
        while not self.stop_reading.is_set() and self.connected:
            try:
                if not self.serial_port or not self.serial_port.is_open:
                    break
                
                if self.serial_port.in_waiting > 0:
                    line = self.serial_port.readline().decode('utf-8', errors='ignore').strip()
                    
                    if line:
                        self._process_serial_line(line)
                
                time.sleep(0.001)  # Small delay to prevent CPU spinning
                
            except Exception as e:
                print(f"❌ Error reading serial data: {e}")
                
                # Log transmission error (Requirements 6.5)
                if self.logger:
                    self.logger.log_transmission_error(
                        f"Serial data reading error: {e}",
                        exception=e,
                        context={'port': self.port, 'connected': self.connected}
                    )
                
                break
    
    def _process_serial_line(self, line: str):
        """
        Process a line received from ESP32-camera.
        
        Args:
            line: Raw line from serial port
        """
        if line.startswith("FRAME_START"):
            self._handle_frame_start(line)
        elif line.startswith("FRAME_END"):
            self._handle_frame_end(line)
        elif line.startswith("STATUS"):
            self._handle_status(line)
        elif line.startswith("ERROR"):
            print(f"⚠️ ESP32 Error: {line}")
        elif self.receiving_frame:
            # This should be binary frame data, but we received text
            # This indicates a protocol error
            print(f"⚠️ Unexpected text during frame reception: {line}")
            self._reset_frame_state()
    
    def _handle_frame_start(self, line: str):
        """
        Handle FRAME_START message.
        
        Args:
            line: FRAME_START line with metadata
        """
        try:
            self.current_metadata = FrameMetadata.from_header(line)
            self.expected_size = self.current_metadata.size
            self.current_frame_data = bytearray()
            self.receiving_frame = True
            
            print(f"📥 Frame {self.current_metadata.sequence} started, size: {self.expected_size}")
            
        except Exception as e:
            print(f"❌ Error parsing frame header: {e}")
            self._reset_frame_state()
    
    def _handle_frame_end(self, line: str):
        """
        Handle FRAME_END message and complete frame reconstruction with validation.
        Implements Requirements 6.2: Frame corruption detection and recovery
        
        Args:
            line: FRAME_END line with checksum
        """
        if not self.receiving_frame or not self.current_metadata:
            print("⚠️ Received FRAME_END without FRAME_START")
            return
        
        try:
            # Parse frame end for checksum
            parts = line.split('|')
            checksum = None
            sequence = None
            
            for part in parts[1:]:  # Skip FRAME_END
                if ':' in part:
                    key, value = part.split(':', 1)
                    if key.strip() == 'checksum':
                        checksum = value.strip()
                    elif key.strip() == 'seq':
                        sequence = int(value.strip())
            
            # Validate sequence number
            if sequence != self.current_metadata.sequence:
                print(f"⚠️ Sequence mismatch: expected {self.current_metadata.sequence}, got {sequence}")
                self.frame_stats['frames_corrupted'] += 1
                self._reset_frame_state()
                return
            
            # Comprehensive frame validation (Requirements 6.2)
            if self.frame_validator:
                is_valid, corruption_report = self.frame_validator.validate_frame(
                    frame_data=bytes(self.current_frame_data),
                    sequence=self.current_metadata.sequence,
                    expected_size=self.expected_size,
                    provided_checksum=checksum or ""
                )
                
                if not is_valid:
                    print(f"❌ Frame validation failed: {corruption_report.corruption_type.value}")
                    self.frame_stats['frames_corrupted'] += 1
                    self._reset_frame_state()
                    return
            else:
                # Fallback validation without frame validator
                # Validate frame size
                if len(self.current_frame_data) != self.expected_size:
                    print(f"⚠️ Size mismatch: expected {self.expected_size}, got {len(self.current_frame_data)}")
                    self.frame_stats['frames_corrupted'] += 1
                    self._reset_frame_state()
                    return
                
                # Validate checksum if provided
                if checksum:
                    calculated_checksum = format(zlib.crc32(self.current_frame_data) & 0xffffffff, '08X')
                    if checksum.upper() != calculated_checksum:
                        error_msg = f"Checksum mismatch: expected {checksum}, calculated {calculated_checksum}"
                        print(f"⚠️ {error_msg}")
                        
                        # Log frame corruption error (Requirements 6.5)
                        if self.logger:
                            self.logger.log_frame_corruption(
                                error_msg,
                                frame_size=len(self.current_frame_data),
                                checksum=checksum,
                                calculated_checksum=calculated_checksum,
                                sequence=self.current_metadata.sequence
                            )
                        
                        self.frame_stats['frames_corrupted'] += 1
                        self._reset_frame_state()
                        return
            
            # Frame is valid, decode it
            self._decode_and_buffer_frame()
            
        except Exception as e:
            print(f"❌ Error processing frame end: {e}")
            self.frame_stats['frames_corrupted'] += 1
            self._reset_frame_state()
    
    def _decode_and_buffer_frame(self):
        """
        Decode JPEG frame and add to buffer.
        Implements Requirements 3.3 and 3.4:
        - Decode received JPEG frames to OpenCV format
        - Validate frame integrity and dimensions
        """
        try:
            # Validate JPEG header before decoding (Requirements 3.4)
            if not self._validate_jpeg_header():
                error_msg = "Invalid JPEG header"
                print(f"❌ {error_msg}")
                
                # Log frame corruption error (Requirements 6.5)
                if self.logger:
                    self.logger.log_frame_corruption(
                        error_msg,
                        frame_size=len(self.current_frame_data),
                        sequence=self.current_metadata.sequence if self.current_metadata else 0,
                        context={'validation_stage': 'jpeg_header'}
                    )
                
                self.frame_stats['frames_corrupted'] += 1
                self._reset_frame_state()
                return
            
            # Decode JPEG data to OpenCV format (Requirements 3.3)
            frame_array = np.frombuffer(self.current_frame_data, dtype=np.uint8)
            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
            
            if frame is None:
                print("❌ Failed to decode JPEG frame - corrupted data")
                self.frame_stats['frames_corrupted'] += 1
                self._reset_frame_state()
                return
            
            # Validate frame dimensions and integrity (Requirements 3.4)
            height, width = frame.shape[:2]
            if not self._validate_frame_dimensions(width, height):
                print(f"❌ Invalid frame dimensions: {width}x{height}")
                self.frame_stats['frames_corrupted'] += 1
                self._reset_frame_state()
                return
            
            # Additional frame integrity checks
            if not self._validate_frame_content(frame):
                print("❌ Frame content validation failed")
                self.frame_stats['frames_corrupted'] += 1
                self._reset_frame_state()
                return
            
            # Create frame package with metadata
            frame_package = {
                'frame': frame,
                'metadata': self.current_metadata,
                'timestamp': time.time(),
                'dimensions': (width, height),
                'channels': frame.shape[2] if len(frame.shape) > 2 else 1,
                'dtype': str(frame.dtype)
            }
            
            # Add to weak reference set for memory tracking (Requirements 7.5)
            self._frame_references.add(frame)
            
            # Update timing statistics
            current_time = time.time()
            self.frame_timestamps.append(current_time)
            self.frame_stats['last_frame_time'] = current_time
            self.last_frame_received = current_time  # Update for connection monitoring
            
            # Calculate average frame time for timing management
            if len(self.frame_timestamps) > 1:
                time_diffs = [self.frame_timestamps[i] - self.frame_timestamps[i-1] 
                             for i in range(1, len(self.frame_timestamps))]
                self.frame_stats['avg_frame_time'] = sum(time_diffs) / len(time_diffs)
            
            # Update memory statistics (Requirements 7.5)
            self._memory_stats['total_frames_processed'] += 1
            
            # Check memory usage periodically
            self._check_memory_usage()
            
            # Buffer management with overflow handling (Requirements 3.5, 7.2)
            success = self._add_frame_to_buffer(frame_package)
            
            if success:
                self.frame_stats['frames_received'] += 1
                print(f"✅ Frame {self.current_metadata.sequence} decoded and buffered ({width}x{height}, {frame.shape[2]} channels)")
            
            # Periodic buffer health check
            self._check_buffer_health()
            
            self._reset_frame_state()
            
        except Exception as e:
            print(f"❌ Error decoding frame: {e}")
            
            # Log frame corruption error (Requirements 6.5)
            if self.logger:
                self.logger.log_frame_corruption(
                    f"Frame decoding error: {e}",
                    frame_size=len(self.current_frame_data) if self.current_frame_data else 0,
                    sequence=self.current_metadata.sequence if self.current_metadata else 0,
                    exception=e,
                    context={'decoding_stage': 'opencv_decode'}
                )
            
            self.frame_stats['frames_corrupted'] += 1
            self._reset_frame_state()
    
    def _add_frame_to_buffer(self, frame_package: Dict) -> bool:
        """
        Add frame to buffer with overflow management.
        Implements Requirements 7.2: Buffer overflow management
        
        Args:
            frame_package: Frame data with metadata
            
        Returns:
            True if frame was added successfully, False if dropped
        """
        try:
            # Try to add frame without blocking
            self.frame_buffer.put_nowait(frame_package)
            return True
            
        except queue.Full:
            # Buffer overflow - implement overflow management strategy
            self.frame_stats['buffer_overflows'] += 1
            
            # Log buffer overflow error (Requirements 6.5)
            if self.logger:
                self.logger.log_buffer_error(
                    "Frame buffer overflow - dropping frames",
                    buffer_size=self.buffer_size,
                    buffer_usage=100.0,
                    frame_sequence=frame_package['metadata'].sequence,
                    context={'overflow_management': 'drop_oldest'}
                )
            
            # Strategy 1: Drop oldest frames to make room (FIFO)
            frames_dropped = 0
            while self.frame_buffer.full() and frames_dropped < 3:
                try:
                    dropped_frame = self.frame_buffer.get_nowait()
                    frames_dropped += 1
                    self.frame_stats['frames_dropped'] += 1
                    print(f"⚠️ Buffer overflow: dropped frame seq {dropped_frame['metadata'].sequence}")
                except queue.Empty:
                    break
            
            # Try to add the new frame again
            try:
                self.frame_buffer.put_nowait(frame_package)
                print(f"✅ Frame added after dropping {frames_dropped} old frames")
                return True
            except queue.Full:
                # Still full, drop this frame
                self.frame_stats['frames_dropped'] += 1
                print(f"⚠️ Buffer still full: dropping current frame seq {frame_package['metadata'].sequence}")
                return False
    
    def _check_buffer_health(self):
        """
        Periodic buffer health monitoring and management.
        Implements Requirements 7.2: Buffer overflow management
        """
        current_time = time.time()
        
        if current_time - self.last_buffer_check < self.buffer_check_interval:
            return
        
        self.last_buffer_check = current_time
        
        buffer_usage = self.frame_buffer.qsize() / self.buffer_size
        
        # Log buffer health
        if buffer_usage > 0.8:
            print(f"⚠️ Buffer usage high: {buffer_usage:.1%} ({self.frame_buffer.qsize()}/{self.buffer_size})")
        elif buffer_usage > 0.5:
            print(f"📊 Buffer usage: {buffer_usage:.1%} ({self.frame_buffer.qsize()}/{self.buffer_size})")
        
        # Adaptive buffer management based on frame rate
        if len(self.frame_timestamps) > 5:
            recent_fps = len(self.frame_timestamps) / (self.frame_timestamps[-1] - self.frame_timestamps[0])
            
            # If receiving frames too fast and buffer is filling up, we might need to drop more aggressively
            if buffer_usage > 0.9 and recent_fps > 20:
                print(f"⚠️ High frame rate ({recent_fps:.1f} FPS) with full buffer - consider reducing ESP32 frame rate")
    
    def get_buffer_health(self) -> Dict[str, Any]:
        """
        Get detailed buffer health information.
        
        Returns:
            Dictionary with buffer health metrics
        """
        buffer_usage = self.frame_buffer.qsize() / self.buffer_size if self.buffer_size > 0 else 0
        
        # Calculate recent FPS
        recent_fps = 0.0
        if len(self.frame_timestamps) > 1:
            time_span = self.frame_timestamps[-1] - self.frame_timestamps[0]
            if time_span > 0:
                recent_fps = (len(self.frame_timestamps) - 1) / time_span
        
        return {
            'buffer_usage_percent': buffer_usage * 100,
            'buffer_size_current': self.frame_buffer.qsize(),
            'buffer_size_max': self.buffer_size,
            'recent_fps': recent_fps,
            'avg_frame_interval': self.frame_stats['avg_frame_time'],
            'buffer_overflows': self.frame_stats['buffer_overflows'],
            'frames_dropped_total': self.frame_stats['frames_dropped'],
            'last_frame_age': time.time() - self.frame_stats['last_frame_time'] if self.frame_stats['last_frame_time'] > 0 else 0
        }
    
    def clear_buffer(self):
        """
        Clear all frames from buffer.
        Useful for resetting timing after connection issues.
        """
        cleared_count = 0
        while not self.frame_buffer.empty():
            try:
                self.frame_buffer.get_nowait()
                cleared_count += 1
            except queue.Empty:
                break
        
        if cleared_count > 0:
            print(f"🗑️ Cleared {cleared_count} frames from buffer")
        
        # Reset timing statistics
        self.frame_timestamps.clear()
        self.frame_stats['last_frame_time'] = 0.0
        self.frame_stats['avg_frame_time'] = 0.0
    
    def _validate_jpeg_header(self) -> bool:
        """
        Validate JPEG file header for integrity.
        
        Returns:
            True if valid JPEG header, False otherwise
        """
        if len(self.current_frame_data) < 4:
            return False
        
        # Check for JPEG SOI (Start of Image) marker: 0xFF 0xD8
        if self.current_frame_data[0] != 0xFF or self.current_frame_data[1] != 0xD8:
            return False
        
        # Check for JPEG EOI (End of Image) marker: 0xFF 0xD9 at the end
        if len(self.current_frame_data) >= 2:
            if (self.current_frame_data[-2] != 0xFF or 
                self.current_frame_data[-1] != 0xD9):
                return False
        
        return True
    
    def _validate_frame_dimensions(self, width: int, height: int) -> bool:
        """
        Validate frame dimensions are reasonable.
        
        Args:
            width: Frame width in pixels
            height: Frame height in pixels
            
        Returns:
            True if dimensions are valid, False otherwise
        """
        # Minimum dimensions check
        if width < 10 or height < 10:
            return False
        
        # Maximum dimensions check (reasonable limits for ESP32-camera)
        if width > 2048 or height > 1536:
            return False
        
        # Aspect ratio check (should be reasonable)
        aspect_ratio = width / height
        if aspect_ratio < 0.5 or aspect_ratio > 3.0:
            return False
        
        # Check for common ESP32-camera resolutions
        valid_resolutions = [
            (160, 120),   # QQVGA
            (320, 240),   # QVGA
            (640, 480),   # VGA
            (800, 600),   # SVGA
            (1024, 768),  # XGA
            (1280, 1024), # SXGA
            (1600, 1200), # UXGA
        ]
        
        # Allow some tolerance for resolution variations
        for valid_w, valid_h in valid_resolutions:
            if (abs(width - valid_w) <= 16 and abs(height - valid_h) <= 16):
                return True
        
        # If not a standard resolution, still allow if dimensions are reasonable
        return True
    
    def _validate_frame_content(self, frame: np.ndarray) -> bool:
        """
        Validate frame content for basic integrity.
        
        Args:
            frame: OpenCV frame (numpy array)
            
        Returns:
            True if frame content is valid, False otherwise
        """
        try:
            # Check if frame is not empty
            if frame.size == 0:
                return False
            
            # Check data type
            if frame.dtype != np.uint8:
                return False
            
            # Check for reasonable color distribution (not all black or all white)
            mean_intensity = np.mean(frame)
            if mean_intensity < 5 or mean_intensity > 250:
                # Allow very dark or very bright frames, but log warning
                print(f"⚠️ Unusual frame brightness: {mean_intensity:.1f}")
            
            # Check for reasonable variance (not completely uniform)
            variance = np.var(frame)
            if variance < 1.0:
                print(f"⚠️ Very low frame variance: {variance:.2f}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error validating frame content: {e}")
            return False
    
    def _handle_status(self, line: str):
        """
        Handle STATUS message from ESP32.
        
        Args:
            line: STATUS line with performance info
        """
        # Parse status for FPS and other metrics
        # Expected format: STATUS|fps:14.2|temp:45.6|free_heap:234567
        try:
            parts = line.split('|')
            for part in parts[1:]:  # Skip STATUS
                if ':' in part:
                    key, value = part.split(':', 1)
                    if key.strip() == 'fps':
                        self.frame_stats['last_fps'] = float(value.strip())
            
            print(f"📊 ESP32 Status: {line}")
            
        except Exception as e:
            print(f"⚠️ Error parsing status: {e}")
    
    def _reset_frame_state(self):
        """Reset frame reception state"""
        self.receiving_frame = False
        self.current_frame_data = bytearray()
        self.current_metadata = None
        self.expected_size = 0
    
    def read_frame(self) -> Optional[np.ndarray]:
        """
        Read the next available frame from buffer.
        Implements Requirements 3.3: Decode received JPEG frames to OpenCV format
        
        Returns:
            OpenCV frame (numpy array) or None if no frame available
        """
        try:
            frame_package = self.frame_buffer.get_nowait()
            return frame_package['frame']
        except queue.Empty:
            return None
    
    def read_frame_with_metadata(self) -> Optional[Tuple[np.ndarray, Dict[str, Any]]]:
        """
        Read the next available frame with metadata from buffer.
        
        Returns:
            Tuple of (frame, metadata_dict) or None if no frame available
        """
        try:
            frame_package = self.frame_buffer.get_nowait()
            return frame_package['frame'], {
                'sequence': frame_package['metadata'].sequence,
                'timestamp': frame_package['timestamp'],
                'dimensions': frame_package['dimensions'],
                'channels': frame_package.get('channels', 3),
                'dtype': frame_package.get('dtype', 'uint8'),
                'fps': frame_package['metadata'].fps
            }
        except queue.Empty:
            return None
    
    def peek_frame(self) -> Optional[np.ndarray]:
        """
        Peek at the next frame without removing it from buffer.
        
        Returns:
            OpenCV frame (numpy array) or None if no frame available
        """
        try:
            # Get frame but put it back
            frame_package = self.frame_buffer.get_nowait()
            # Put it back at the front (this is a limitation of queue.Queue)
            # We'll create a temporary queue to preserve order
            temp_queue = queue.Queue(maxsize=self.buffer_size)
            temp_queue.put(frame_package)
            
            # Move all other items
            while not self.frame_buffer.empty():
                try:
                    temp_queue.put(self.frame_buffer.get_nowait())
                except queue.Empty:
                    break
            
            # Restore the queue
            self.frame_buffer = temp_queue
            
            return frame_package['frame']
        except queue.Empty:
            return None
    
    def get_latest_frame(self) -> Optional[np.ndarray]:
        """
        Get the most recent frame, discarding older frames.
        
        Returns:
            Most recent OpenCV frame or None if no frame available
        """
        latest_frame = None
        
        # Drain the buffer and keep only the latest frame
        while True:
            try:
                frame_package = self.frame_buffer.get_nowait()
                latest_frame = frame_package['frame']
            except queue.Empty:
                break
        
        return latest_frame
    
    def wait_for_frame(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """
        Wait for a frame with timeout to handle timing variations.
        Implements Requirements 3.5: Handle timing variations
        
        Args:
            timeout: Maximum time to wait for a frame (seconds)
            
        Returns:
            OpenCV frame or None if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            frame = self.read_frame()
            if frame is not None:
                return frame
            
            time.sleep(0.01)  # Small delay to prevent busy waiting
        
        return None
    
    def set_buffer_size(self, new_size: int):
        """
        Dynamically adjust buffer size for timing management.
        
        Args:
            new_size: New buffer size
        """
        if new_size <= 0:
            print("❌ Buffer size must be positive")
            return
        
        old_size = self.buffer_size
        self.buffer_size = new_size
        
        # If reducing size, remove excess frames
        if new_size < old_size:
            excess_frames = self.frame_buffer.qsize() - new_size
            for _ in range(max(0, excess_frames)):
                try:
                    self.frame_buffer.get_nowait()
                    self.frame_stats['frames_dropped'] += 1
                except queue.Empty:
                    break
        
        print(f"📊 Buffer size changed from {old_size} to {new_size}")
    
    def get_frame_rate_stats(self) -> Dict[str, float]:
        """
        Get detailed frame rate statistics for timing analysis.
        
        Returns:
            Dictionary with frame rate metrics
        """
        if len(self.frame_timestamps) < 2:
            return {
                'current_fps': 0.0,
                'avg_fps': 0.0,
                'min_interval': 0.0,
                'max_interval': 0.0,
                'jitter': 0.0
            }
        
        # Calculate intervals between frames
        intervals = [self.frame_timestamps[i] - self.frame_timestamps[i-1] 
                    for i in range(1, len(self.frame_timestamps))]
        
        if not intervals:
            return {
                'current_fps': 0.0,
                'avg_fps': 0.0,
                'min_interval': 0.0,
                'max_interval': 0.0,
                'jitter': 0.0
            }
        
        avg_interval = sum(intervals) / len(intervals)
        min_interval = min(intervals)
        max_interval = max(intervals)
        
        # Calculate jitter (standard deviation of intervals)
        variance = sum((interval - avg_interval) ** 2 for interval in intervals) / len(intervals)
        jitter = variance ** 0.5
        
        return {
            'current_fps': 1.0 / intervals[-1] if intervals[-1] > 0 else 0.0,
            'avg_fps': 1.0 / avg_interval if avg_interval > 0 else 0.0,
            'min_interval': min_interval,
            'max_interval': max_interval,
            'jitter': jitter
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get receiver statistics including buffer health, error information, and memory usage (Requirements 7.5).
        
        Returns:
            Dictionary with frame, buffer, error, and memory statistics
        """
        buffer_health = self.get_buffer_health()
        memory_stats = self.get_memory_stats()
        
        stats = {
            'connected': self.connected,
            'frames_received': self.frame_stats['frames_received'],
            'frames_dropped': self.frame_stats['frames_dropped'],
            'frames_corrupted': self.frame_stats['frames_corrupted'],
            'buffer_overflows': self.frame_stats['buffer_overflows'],
            'connection_errors': self.frame_stats['connection_errors'],
            'reconnection_attempts': self.frame_stats['reconnection_attempts'],
            'buffer_size': self.frame_buffer.qsize(),
            'max_buffer_size': self.buffer_size,
            'buffer_usage_percent': buffer_health['buffer_usage_percent'],
            'last_fps': self.frame_stats['last_fps'],
            'recent_fps': buffer_health['recent_fps'],
            'avg_frame_interval': buffer_health['avg_frame_interval'],
            'last_frame_age': buffer_health['last_frame_age'],
            'port': self.port,
            'baud': self.baud,
            # Memory statistics (Requirements 7.5)
            'memory_usage_mb': memory_stats['current_memory_mb'],
            'peak_memory_mb': memory_stats['peak_memory_mb'],
            'memory_leaks_detected': memory_stats['memory_leaks_detected'],
            'gc_collections': memory_stats['gc_collections'],
            'memory_cleanup_count': memory_stats['memory_cleanup_count'],
            'frames_per_mb': memory_stats['frames_per_mb'],
            'total_frames_processed': memory_stats['total_frames_processed']
        }
        
        # Add error handler statistics if available
        if self.error_handler:
            error_stats = self.error_handler.get_connection_stats()
            stats.update({
                'error_handler_state': error_stats['current_state'],
                'total_connection_attempts': error_stats['total_attempts'],
                'connection_success_rate': error_stats['success_rate'],
                'using_fallback': error_stats['using_fallback'],
                'recent_errors': error_stats.get('recent_errors', [])
            })
        
        # Add frame validation statistics if available (Requirements 6.2)
        if self.frame_validator:
            validation_stats = self.frame_validator.get_validation_stats()
            stats.update({
                'frames_validated': validation_stats['frames_validated'],
                'corruption_rate': validation_stats['corruption_rate'],
                'retransmissions_requested': validation_stats['retransmissions_requested'],
                'retransmissions_successful': validation_stats['retransmissions_successful'],
                'retransmissions_failed': validation_stats['retransmissions_failed'],
                'pending_retransmissions': validation_stats['pending_retransmissions'],
                'corruption_by_type': validation_stats['corruption_by_type']
            })
        
        return stats
    
    def get_corruption_summary(self) -> Dict[str, Any]:
        """
        Get frame corruption summary for analysis (Requirements 6.2).
        
        Returns:
            Dictionary with corruption analysis data
        """
        if self.frame_validator:
            return self.frame_validator.get_corruption_summary()
        else:
            return {
                'total_corruptions': self.frame_stats['frames_corrupted'],
                'recent_corruptions': [],
                'corruption_by_type': {},
                'pending_retransmissions': []
            }
    
    def reset_validation_state(self):
        """Reset frame validation state for fresh connection"""
        if self.frame_validator:
            self.frame_validator.reset_validation_state()
            print("🔄 Frame validation state reset")
    
    def is_connected(self) -> bool:
        """Check if receiver is connected to ESP32-camera"""
        return self.connected and self.serial_port and self.serial_port.is_open
    
    def __enter__(self):
        """Context manager entry"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()


# Compatibility class for integration with existing video capture systems
class ESP32CameraCapture:
    """
    OpenCV VideoCapture-compatible wrapper for ESP32CameraReceiver.
    
    This class provides a similar interface to cv2.VideoCapture for seamless
    integration with existing video processing pipelines.
    """
    
    def __init__(self, port: str = "COM3", baud: int = 921600):
        """
        Initialize ESP32 camera capture.
        
        Args:
            port: Serial port for ESP32-camera
            baud: Baud rate for serial communication
        """
        self.receiver = ESP32CameraReceiver(port, baud)
        self._opened = False
    
    def isOpened(self) -> bool:
        """Check if camera is opened and connected or using fallback"""
        return (self._opened and self.receiver.is_connected()) or self.receiver.is_using_fallback()
    
    def open(self, port: str = None) -> bool:
        """
        Open connection to ESP32-camera.
        
        Args:
            port: Optional port override
            
        Returns:
            True if opened successfully
        """
        if port:
            self.receiver.port = port
        
        success = self.receiver.connect()
        self._opened = success
        return success
    
    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read frame from ESP32-camera with fallback support.
        Implements Requirements 6.3: Fallback to default webcam
        
        Returns:
            Tuple of (success, frame) compatible with cv2.VideoCapture.read()
        """
        if not self.isOpened():
            return False, None
        
        # Check if using fallback
        if self.receiver.is_using_fallback():
            fallback_cap = self.receiver.get_fallback_capture()
            if fallback_cap:
                return fallback_cap.read()
        
        # Try to read from ESP32-camera
        frame = self.receiver.read_frame()
        return frame is not None, frame
    
    def release(self):
        """Release ESP32-camera connection"""
        self.receiver.disconnect()
        self._opened = False
    
    def set(self, prop_id: int, value: Any) -> bool:
        """
        Set camera property (limited support).
        
        Args:
            prop_id: Property ID (cv2.CAP_PROP_*)
            value: Property value
            
        Returns:
            True if property was set
        """
        # Limited property support for ESP32-camera
        if prop_id == cv2.CAP_PROP_FPS:
            return self.receiver.configure_camera(fps=int(value))
        elif prop_id == cv2.CAP_PROP_FRAME_WIDTH or prop_id == cv2.CAP_PROP_FRAME_HEIGHT:
            # Resolution changes require specific resolution names
            # This is a simplified mapping
            if value <= 320:
                return self.receiver.configure_camera(resolution="QVGA")
            elif value <= 640:
                return self.receiver.configure_camera(resolution="VGA")
            elif value <= 800:
                return self.receiver.configure_camera(resolution="SVGA")
            else:
                return self.receiver.configure_camera(resolution="XGA")
        
        return False
    
    def get(self, prop_id: int) -> float:
        """
        Get camera property.
        
        Args:
            prop_id: Property ID (cv2.CAP_PROP_*)
            
        Returns:
            Property value
        """
        stats = self.receiver.get_stats()
        
        if prop_id == cv2.CAP_PROP_FPS:
            return stats.get('last_fps', 0.0)
        elif prop_id == cv2.CAP_PROP_FRAME_COUNT:
            return stats.get('frames_received', 0)
        
        return 0.0


if __name__ == "__main__":
    """Test ESP32CameraReceiver functionality"""
    import sys
    
    port = sys.argv[1] if len(sys.argv) > 1 else "COM3"
    
    print(f"Testing ESP32CameraReceiver on {port}")
    
    with ESP32CameraReceiver(port) as receiver:
        if not receiver.is_connected():
            print("Failed to connect to ESP32-camera")
            sys.exit(1)
        
        # Configure camera
        receiver.configure_camera(resolution="VGA", fps=15, quality=50)
        
        # Read frames for 30 seconds
        start_time = time.time()
        frame_count = 0
        
        while time.time() - start_time < 30:
            frame = receiver.read_frame()
            if frame is not None:
                frame_count += 1
                print(f"Received frame {frame_count}: {frame.shape}")
                
                # Optional: display frame
                cv2.imshow("ESP32 Camera", frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
            
            time.sleep(0.1)
        
        # Print statistics
        stats = receiver.get_stats()
        print(f"\nStatistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
    
    cv2.destroyAllWindows()
    print("Test completed")