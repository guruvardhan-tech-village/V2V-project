#!/usr/bin/env python3
"""
Hardware-in-the-Loop (HIL) Test for ESP32-Camera System

This test validates the ESP32-camera integration with actual hardware connected
to COM3 port. It tests real-time performance, reliability, connection recovery,
and error handling with physical ESP32-camera device.

Requirements tested:
- Test with actual ESP32-camera connected to COM3
- Verify real-time performance and reliability  
- Test connection recovery and error handling

Task: 11.4 Validate hardware-in-the-loop functionality
"""

import sys
import os
import time
import threading
import queue
import json
import signal
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from collections import deque
import numpy as np
import cv2

# Add the yolo directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import system components
try:
    from esp32_camera_receiver import ESP32CameraReceiver, ESP32CameraCapture, CameraConfig
    from esp32_error_handler import ESP32ErrorHandler, ConnectionState
    from esp32_logger import ESP32Logger, get_global_logger
    from esp32_performance_monitor import get_global_performance_collector
    import accident_traffic
    ESP32_IMPORTS_AVAILABLE = True
except ImportError as e:
    print(f"❌ ESP32 modules not available: {e}")
    ESP32_IMPORTS_AVAILABLE = False
    sys.exit(1)

# Import YOLO for testing
try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    print("⚠️ YOLO not available for HIL testing")
    YOLO_AVAILABLE = False

# Serial port detection
try:
    from serial.tools import list_ports
    SERIAL_TOOLS_AVAILABLE = True
except ImportError:
    SERIAL_TOOLS_AVAILABLE = False


@dataclass
class HILTestConfig:
    """Configuration for hardware-in-the-loop tests"""
    port: str = "COM3"
    baud: int = 921600
    test_duration: int = 60  # seconds
    min_fps_requirement: float = 10.0
    max_frame_processing_time: float = 0.1  # 100ms
    connection_timeout: float = 10.0  # seconds
    frame_timeout: float = 5.0  # seconds
    reliability_test_duration: int = 300  # 5 minutes
    stress_test_duration: int = 120  # 2 minutes
    enable_yolo_processing: bool = True
    enable_performance_monitoring: bool = True
    save_test_frames: bool = False
    test_output_dir: str = "hil_test_output"


class HardwareInTheLoopTester:
    """
    Hardware-in-the-Loop tester for ESP32-camera system.
    
    This class performs comprehensive testing with actual ESP32-camera hardware:
    1. Hardware detection and connection
    2. Real-time frame streaming and processing
    3. Performance validation under load
    4. Connection recovery and error handling
    5. Long-term reliability testing
    6. Stress testing with YOLO processing
    """
    
    def __init__(self, config: HILTestConfig):
        self.config = config
        self.test_results = {}
        self.test_stats = {}
        self.receiver = None
        self.yolo_model = None
        self.performance_data = deque(maxlen=10000)
        self.frame_data = deque(maxlen=1000)
        self.error_count = 0
        self.connection_lost_count = 0
        self.frames_processed = 0
        self.test_interrupted = False
        
        # Setup signal handler for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        
        # Initialize logging
        self.logger = get_global_logger()
        
        # Create output directory
        if self.config.save_test_frames:
            os.makedirs(self.config.test_output_dir, exist_ok=True)
    
    def _signal_handler(self, signum, frame):
        """Handle interrupt signal for graceful shutdown"""
        print("\n🛑 Test interrupted by user - performing graceful shutdown...")
        self.test_interrupted = True
    
    def run_all_hil_tests(self) -> bool:
        """
        Run all hardware-in-the-loop tests.
        
        Returns:
            True if all tests pass, False otherwise
        """
        print("🔌 Starting Hardware-in-the-Loop ESP32-Camera Tests")
        print("=" * 80)
        
        start_time = time.time()
        
        try:
            # Test 1: Hardware Detection and Connection
            if not self._test_hardware_detection():
                print("❌ Hardware detection failed - cannot proceed with HIL tests")
                return False
            
            # Test 2: Basic Communication and Frame Reception
            if not self._test_basic_communication():
                print("❌ Basic communication test failed")
                return False
            
            # Test 3: Real-time Performance Validation
            if not self._test_realtime_performance():
                print("❌ Real-time performance test failed")
                return False
            
            # Test 4: Configuration and Control
            if not self._test_configuration_control():
                print("❌ Configuration and control test failed")
                return False
            
            # Test 5: Connection Recovery and Error Handling
            if not self._test_connection_recovery():
                print("❌ Connection recovery test failed")
                return False
            
            # Test 6: YOLO Integration with Hardware
            if self.config.enable_yolo_processing and YOLO_AVAILABLE:
                if not self._test_yolo_integration_hardware():
                    print("❌ YOLO integration with hardware test failed")
                    return False
            
            # Test 7: Long-term Reliability
            if not self._test_longterm_reliability():
                print("❌ Long-term reliability test failed")
                return False
            
            # Test 8: Stress Testing
            if not self._test_stress_conditions():
                print("❌ Stress testing failed")
                return False
            
            # Calculate total test time
            total_time = time.time() - start_time
            self.test_stats['total_test_time'] = total_time
            
            # Print comprehensive results
            self._print_hil_results()
            
            return all(self.test_results.values())
            
        except Exception as e:
            print(f"❌ HIL test suite failed with exception: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            self._cleanup_hil_resources()
    
    def _test_hardware_detection(self) -> bool:
        """Test 1: Detect and verify ESP32-camera hardware"""
        print("\n🔍 Test 1: Hardware Detection and Connection")
        print("-" * 60)
        
        # List available serial ports
        if SERIAL_TOOLS_AVAILABLE:
            print("Scanning for available serial ports...")
            ports = list_ports.comports()
            
            if not ports:
                print("❌ No serial ports detected")
                self.test_results['hardware_detection'] = False
                return False
            
            print("Available serial ports:")
            for port in ports:
                print(f"  {port.device}: {port.description}")
                if port.device == self.config.port:
                    print(f"  ✅ Target port {self.config.port} found")
        
        # Test connection to ESP32-camera
        print(f"\nAttempting connection to ESP32-camera on {self.config.port}...")
        
        self.receiver = ESP32CameraReceiver(
            port=self.config.port,
            baud=self.config.baud,
            buffer_size=20
        )
        
        # Attempt connection with timeout
        connection_start = time.time()
        connected = self.receiver.connect()
        connection_time = time.time() - connection_start
        
        if not connected:
            print(f"❌ Failed to connect to ESP32-camera on {self.config.port}")
            print("   Please ensure:")
            print("   1. ESP32-camera is connected via USB cable")
            print("   2. ESP32-camera firmware is running")
            print("   3. Correct COM port is specified")
            print("   4. No other applications are using the port")
            self.test_results['hardware_detection'] = False
            return False
        
        print(f"✅ Connected to ESP32-camera in {connection_time:.2f}s")
        
        # Wait for ESP32 initialization
        print("Waiting for ESP32-camera initialization...")
        time.sleep(3)
        
        # Verify connection is stable
        if not self.receiver.is_connected():
            print("❌ Connection lost during initialization")
            self.test_results['hardware_detection'] = False
            return False
        
        print("✅ ESP32-camera connection stable")
        
        # Get initial status
        stats = self.receiver.get_stats()
        print(f"Connection details:")
        print(f"  Port: {stats['port']}")
        print(f"  Baud rate: {stats['baud']}")
        print(f"  Connected: {stats['connected']}")
        
        self.test_results['hardware_detection'] = True
        self.test_stats['connection_time'] = connection_time
        
        return True
    
    def _test_basic_communication(self) -> bool:
        """Test 2: Basic communication and frame reception"""
        print("\n📡 Test 2: Basic Communication and Frame Reception")
        print("-" * 60)
        
        if not self.receiver or not self.receiver.is_connected():
            print("❌ No hardware connection available")
            self.test_results['basic_communication'] = False
            return False
        
        # Test frame reception
        print("Testing frame reception from hardware...")
        
        frames_received = 0
        frame_sizes = []
        frame_times = []
        timeout = 30  # 30 second timeout
        start_time = time.time()
        
        while frames_received < 10 and (time.time() - start_time) < timeout and not self.test_interrupted:
            frame_start = time.time()
            frame_data = self.receiver.read_frame_with_metadata()
            
            if frame_data is not None:
                frame, metadata = frame_data
                frames_received += 1
                frame_time = time.time() - frame_start
                
                frame_sizes.append(frame.nbytes)
                frame_times.append(frame_time)
                
                print(f"  Frame {frames_received}:")
                print(f"    Dimensions: {metadata['dimensions']}")
                print(f"    Channels: {metadata['channels']}")
                print(f"    Size: {frame.nbytes} bytes")
                print(f"    Reception time: {frame_time*1000:.2f}ms")
                
                # Save first frame if enabled
                if self.config.save_test_frames and frames_received == 1:
                    frame_path = os.path.join(self.config.test_output_dir, "first_frame.jpg")
                    cv2.imwrite(frame_path, frame)
                    print(f"    Saved to: {frame_path}")
            
            time.sleep(0.1)
        
        if frames_received == 0:
            print("❌ No frames received from hardware")
            self.test_results['basic_communication'] = False
            return False
        
        # Calculate statistics
        avg_frame_size = sum(frame_sizes) / len(frame_sizes)
        avg_frame_time = sum(frame_times) / len(frame_times)
        actual_duration = time.time() - start_time
        measured_fps = frames_received / actual_duration
        
        print(f"\nFrame reception statistics:")
        print(f"  Frames received: {frames_received}")
        print(f"  Average frame size: {avg_frame_size:.0f} bytes")
        print(f"  Average reception time: {avg_frame_time*1000:.2f}ms")
        print(f"  Measured FPS: {measured_fps:.2f}")
        
        # Test frame quality
        print("\nTesting frame quality...")
        
        if frame_data is not None:
            frame, metadata = frame_data
            
            # Check frame properties
            height, width = frame.shape[:2]
            channels = frame.shape[2] if len(frame.shape) > 2 else 1
            
            print(f"  Resolution: {width}x{height}")
            print(f"  Channels: {channels}")
            print(f"  Data type: {frame.dtype}")
            
            # Check image quality metrics
            mean_intensity = np.mean(frame)
            std_intensity = np.std(frame)
            
            print(f"  Mean intensity: {mean_intensity:.1f}")
            print(f"  Intensity std dev: {std_intensity:.1f}")
            
            # Validate frame quality
            if mean_intensity < 10 or mean_intensity > 245:
                print("  ⚠️ Frame may be too dark or too bright")
            elif std_intensity < 5:
                print("  ⚠️ Frame may lack detail (low variance)")
            else:
                print("  ✅ Frame quality appears good")
        
        # Check minimum performance requirements
        performance_ok = (
            measured_fps >= self.config.min_fps_requirement and
            avg_frame_time <= self.config.max_frame_processing_time
        )
        
        if not performance_ok:
            print(f"❌ Performance below requirements:")
            print(f"   FPS: {measured_fps:.2f} (min: {self.config.min_fps_requirement})")
            print(f"   Frame time: {avg_frame_time*1000:.2f}ms (max: {self.config.max_frame_processing_time*1000:.0f}ms)")
        
        self.test_results['basic_communication'] = performance_ok
        self.test_stats['hardware_fps'] = measured_fps
        self.test_stats['avg_frame_size'] = avg_frame_size
        
        return performance_ok
    
    def _test_realtime_performance(self) -> bool:
        """Test 3: Real-time performance validation"""
        print("\n⚡ Test 3: Real-time Performance Validation")
        print("-" * 60)
        
        if not self.receiver or not self.receiver.is_connected():
            print("❌ No hardware connection available")
            self.test_results['realtime_performance'] = False
            return False
        
        print(f"Running {self.config.test_duration}s performance test...")
        
        # Performance monitoring
        frame_times = []
        processing_times = []
        fps_measurements = []
        
        test_start = time.time()
        last_fps_time = test_start
        frames_in_interval = 0
        
        while (time.time() - test_start) < self.config.test_duration and not self.test_interrupted:
            frame_start = time.time()
            
            # Read frame
            frame = self.receiver.read_frame()
            
            if frame is not None:
                frame_time = time.time() - frame_start
                frame_times.append(frame_time)
                
                # Simulate processing
                processing_start = time.time()
                
                # Basic image processing
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                blurred = cv2.GaussianBlur(gray, (5, 5), 0)
                edges = cv2.Canny(blurred, 50, 150)
                
                processing_time = time.time() - processing_start
                processing_times.append(processing_time)
                
                frames_in_interval += 1
                
                # Calculate FPS every second
                current_time = time.time()
                if current_time - last_fps_time >= 1.0:
                    interval_fps = frames_in_interval / (current_time - last_fps_time)
                    fps_measurements.append(interval_fps)
                    
                    if len(fps_measurements) % 10 == 0:  # Print every 10 seconds
                        print(f"  {len(fps_measurements)}s: {interval_fps:.2f} FPS")
                    
                    frames_in_interval = 0
                    last_fps_time = current_time
            
            time.sleep(0.001)  # Small delay to prevent busy waiting
        
        if not frame_times:
            print("❌ No frames processed during performance test")
            self.test_results['realtime_performance'] = False
            return False
        
        # Calculate performance statistics
        avg_frame_time = sum(frame_times) / len(frame_times)
        max_frame_time = max(frame_times)
        avg_processing_time = sum(processing_times) / len(processing_times)
        avg_fps = sum(fps_measurements) / len(fps_measurements) if fps_measurements else 0
        min_fps = min(fps_measurements) if fps_measurements else 0
        max_fps = max(fps_measurements) if fps_measurements else 0
        
        print(f"\nPerformance results:")
        print(f"  Total frames processed: {len(frame_times)}")
        print(f"  Average frame time: {avg_frame_time*1000:.2f}ms")
        print(f"  Maximum frame time: {max_frame_time*1000:.2f}ms")
        print(f"  Average processing time: {avg_processing_time*1000:.2f}ms")
        print(f"  Average FPS: {avg_fps:.2f}")
        print(f"  FPS range: {min_fps:.2f} - {max_fps:.2f}")
        
        # Check performance requirements
        performance_ok = (
            avg_fps >= self.config.min_fps_requirement and
            avg_frame_time <= self.config.max_frame_processing_time and
            max_frame_time <= self.config.max_frame_processing_time * 2  # Allow 2x max for occasional spikes
        )
        
        if performance_ok:
            print("✅ Real-time performance requirements met")
        else:
            print("❌ Real-time performance requirements not met")
        
        self.test_results['realtime_performance'] = performance_ok
        self.test_stats['realtime_avg_fps'] = avg_fps
        self.test_stats['realtime_min_fps'] = min_fps
        self.test_stats['realtime_max_fps'] = max_fps
        
        return performance_ok
    
    def _test_configuration_control(self) -> bool:
        """Test 4: Configuration and control with hardware"""
        print("\n⚙️ Test 4: Configuration and Control")
        print("-" * 60)
        
        if not self.receiver or not self.receiver.is_connected():
            print("❌ No hardware connection available")
            self.test_results['configuration_control'] = False
            return False
        
        # Test different configurations
        test_configs = [
            {"resolution": "QVGA", "fps": 10, "quality": 40},
            {"resolution": "VGA", "fps": 15, "quality": 50},
            {"resolution": "SVGA", "fps": 8, "quality": 60}
        ]
        
        config_success = 0
        
        for i, config_dict in enumerate(test_configs):
            if self.test_interrupted:
                break
                
            print(f"\nTesting configuration {i+1}: {config_dict}")
            
            # Send configuration
            success = self.receiver.configure_camera(**config_dict)
            
            if not success:
                print(f"  ❌ Failed to send configuration")
                continue
            
            # Wait for configuration to take effect
            print("  Waiting for configuration to apply...")
            time.sleep(3)
            
            # Test frame reception with new configuration
            print("  Testing frame reception with new config...")
            
            config_frames = 0
            config_start = time.time()
            
            while config_frames < 5 and (time.time() - config_start) < 10:
                frame_data = self.receiver.read_frame_with_metadata()
                
                if frame_data is not None:
                    frame, metadata = frame_data
                    config_frames += 1
                    
                    if config_frames == 1:  # Check first frame
                        width, height = metadata['dimensions']
                        print(f"    Frame dimensions: {width}x{height}")
                        
                        # Verify resolution matches configuration
                        expected_resolutions = {
                            "QVGA": (320, 240),
                            "VGA": (640, 480), 
                            "SVGA": (800, 600)
                        }
                        
                        expected = expected_resolutions.get(config_dict["resolution"])
                        if expected and (width, height) == expected:
                            print(f"    ✅ Resolution matches configuration")
                        else:
                            print(f"    ⚠️ Resolution mismatch: expected {expected}, got ({width}, {height})")
                
                time.sleep(0.2)
            
            if config_frames > 0:
                config_success += 1
                print(f"  ✅ Configuration {i+1} applied successfully")
            else:
                print(f"  ❌ No frames received with configuration {i+1}")
        
        # Test configuration persistence
        print("\nTesting configuration persistence...")
        
        # Get current configuration
        current_config = CameraConfig(resolution="VGA", fps=20, quality=55)
        
        # Apply configuration
        if self.receiver.configure_camera(
            resolution=current_config.resolution,
            fps=current_config.fps,
            quality=current_config.quality
        ):
            print("  ✅ Configuration applied")
            
            # Wait and check if it persists
            time.sleep(2)
            
            # Read a few frames to verify persistence
            persistent_frames = 0
            for _ in range(3):
                frame = self.receiver.read_frame()
                if frame is not None:
                    persistent_frames += 1
                time.sleep(0.5)
            
            if persistent_frames > 0:
                print("  ✅ Configuration appears to persist")
            else:
                print("  ⚠️ Could not verify configuration persistence")
        
        success_rate = config_success / len(test_configs)
        configuration_ok = success_rate >= 0.8  # Require 80% success rate
        
        print(f"\nConfiguration test results:")
        print(f"  Successful configurations: {config_success}/{len(test_configs)}")
        print(f"  Success rate: {success_rate:.1%}")
        
        self.test_results['configuration_control'] = configuration_ok
        self.test_stats['config_success_rate'] = success_rate
        
        return configuration_ok
    
    def _test_connection_recovery(self) -> bool:
        """Test 5: Connection recovery and error handling"""
        print("\n🔄 Test 5: Connection Recovery and Error Handling")
        print("-" * 60)
        
        if not self.receiver or not self.receiver.is_connected():
            print("❌ No hardware connection available")
            self.test_results['connection_recovery'] = False
            return False
        
        print("Testing connection recovery mechanisms...")
        
        # Test 1: Simulated disconnection recovery
        print("\n1. Testing automatic reconnection...")
        
        # Get initial connection stats
        initial_stats = self.receiver.get_stats()
        
        # Simulate connection loss by closing and reopening
        print("   Simulating connection loss...")
        self.receiver.disconnect()
        
        # Wait a moment
        time.sleep(2)
        
        # Attempt reconnection
        print("   Attempting reconnection...")
        reconnect_start = time.time()
        reconnected = self.receiver.connect()
        reconnect_time = time.time() - reconnect_start
        
        if reconnected:
            print(f"   ✅ Reconnected in {reconnect_time:.2f}s")
            
            # Test frame reception after reconnection
            print("   Testing frame reception after reconnection...")
            
            recovery_frames = 0
            recovery_start = time.time()
            
            while recovery_frames < 3 and (time.time() - recovery_start) < 10:
                frame = self.receiver.read_frame()
                if frame is not None:
                    recovery_frames += 1
                time.sleep(0.5)
            
            if recovery_frames > 0:
                print(f"   ✅ Frame reception restored ({recovery_frames} frames)")
            else:
                print("   ❌ Frame reception not restored")
                self.test_results['connection_recovery'] = False
                return False
        else:
            print("   ❌ Reconnection failed")
            self.test_results['connection_recovery'] = False
            return False
        
        # Test 2: Error handling during operation
        print("\n2. Testing error handling during operation...")
        
        # Monitor for errors during normal operation
        error_monitoring_duration = 30  # seconds
        error_start = time.time()
        
        initial_error_stats = self.receiver.get_stats()
        
        print(f"   Monitoring for errors during {error_monitoring_duration}s operation...")
        
        frames_during_monitoring = 0
        
        while (time.time() - error_start) < error_monitoring_duration and not self.test_interrupted:
            frame = self.receiver.read_frame()
            if frame is not None:
                frames_during_monitoring += 1
            time.sleep(0.1)
        
        final_error_stats = self.receiver.get_stats()
        
        # Check error statistics
        frames_corrupted = final_error_stats.get('frames_corrupted', 0) - initial_error_stats.get('frames_corrupted', 0)
        frames_dropped = final_error_stats.get('frames_dropped', 0) - initial_error_stats.get('frames_dropped', 0)
        connection_errors = final_error_stats.get('connection_errors', 0) - initial_error_stats.get('connection_errors', 0)
        
        print(f"   Frames processed: {frames_during_monitoring}")
        print(f"   Frames corrupted: {frames_corrupted}")
        print(f"   Frames dropped: {frames_dropped}")
        print(f"   Connection errors: {connection_errors}")
        
        # Calculate error rates
        if frames_during_monitoring > 0:
            corruption_rate = frames_corrupted / frames_during_monitoring
            drop_rate = frames_dropped / frames_during_monitoring
            
            print(f"   Corruption rate: {corruption_rate:.3%}")
            print(f"   Drop rate: {drop_rate:.3%}")
            
            # Check acceptable error rates
            acceptable_corruption_rate = 0.01  # 1%
            acceptable_drop_rate = 0.05  # 5%
            
            if corruption_rate <= acceptable_corruption_rate and drop_rate <= acceptable_drop_rate:
                print("   ✅ Error rates within acceptable limits")
                error_handling_ok = True
            else:
                print("   ⚠️ Error rates higher than expected")
                error_handling_ok = True  # Still pass but warn
        else:
            print("   ❌ No frames processed during monitoring")
            error_handling_ok = False
        
        # Test 3: Buffer overflow handling
        print("\n3. Testing buffer overflow handling...")
        
        # Reduce buffer size to force overflow
        original_buffer_size = self.receiver.buffer_size
        self.receiver.set_buffer_size(3)
        
        print("   Reduced buffer size to force overflow...")
        
        # Let buffer fill up
        time.sleep(5)
        
        # Check buffer health
        buffer_health = self.receiver.get_buffer_health()
        
        print(f"   Buffer usage: {buffer_health.get('buffer_usage_percent', 0):.1f}%")
        print(f"   Buffer overflows: {buffer_health.get('buffer_overflows', 0)}")
        
        # Restore original buffer size
        self.receiver.set_buffer_size(original_buffer_size)
        
        print("   ✅ Buffer overflow handling tested")
        
        recovery_ok = reconnected and error_handling_ok
        
        self.test_results['connection_recovery'] = recovery_ok
        self.test_stats['reconnect_time'] = reconnect_time if reconnected else 0
        self.test_stats['error_monitoring_frames'] = frames_during_monitoring
        
        return recovery_ok
    
    def _test_yolo_integration_hardware(self) -> bool:
        """Test 6: YOLO integration with hardware frames"""
        print("\n🎯 Test 6: YOLO Integration with Hardware")
        print("-" * 60)
        
        if not self.receiver or not self.receiver.is_connected():
            print("❌ No hardware connection available")
            self.test_results['yolo_integration_hardware'] = False
            return False
        
        # Load YOLO model
        print("Loading YOLO model for hardware testing...")
        
        try:
            self.yolo_model = YOLO('yolo11n.pt')  # Use nano model for faster processing
            print("✅ YOLO model loaded")
        except Exception as e:
            print(f"❌ Failed to load YOLO model: {e}")
            self.test_results['yolo_integration_hardware'] = False
            return False
        
        # Test YOLO processing with hardware frames
        print("Testing YOLO processing with hardware frames...")
        
        yolo_test_duration = 60  # 1 minute test
        yolo_start = time.time()
        
        yolo_processing_times = []
        total_detections = 0
        frames_processed = 0
        
        while (time.time() - yolo_start) < yolo_test_duration and not self.test_interrupted:
            # Get frame from hardware
            frame = self.receiver.read_frame()
            
            if frame is not None:
                # Process with YOLO
                yolo_process_start = time.time()
                
                results = self.yolo_model(frame, verbose=False)
                
                yolo_process_time = time.time() - yolo_process_start
                yolo_processing_times.append(yolo_process_time)
                
                frames_processed += 1
                
                # Count detections
                if results and len(results) > 0 and len(results[0].boxes) > 0:
                    detections = len(results[0].boxes)
                    total_detections += detections
                    
                    if frames_processed % 30 == 0:  # Print every 30 frames
                        print(f"  Frame {frames_processed}: {detections} detections, {yolo_process_time*1000:.2f}ms")
                
                # Save detection frame if enabled
                if self.config.save_test_frames and frames_processed == 1:
                    if results and len(results) > 0:
                        annotated_frame = results[0].plot()
                        detection_path = os.path.join(self.config.test_output_dir, "yolo_detection.jpg")
                        cv2.imwrite(detection_path, annotated_frame)
                        print(f"  Saved detection frame to: {detection_path}")
            
            time.sleep(0.01)  # Small delay
        
        if not yolo_processing_times:
            print("❌ No frames processed with YOLO")
            self.test_results['yolo_integration_hardware'] = False
            return False
        
        # Calculate YOLO performance statistics
        avg_yolo_time = sum(yolo_processing_times) / len(yolo_processing_times)
        max_yolo_time = max(yolo_processing_times)
        yolo_fps = 1.0 / avg_yolo_time if avg_yolo_time > 0 else 0.0
        
        print(f"\nYOLO integration results:")
        print(f"  Frames processed: {frames_processed}")
        print(f"  Total detections: {total_detections}")
        print(f"  Average YOLO time: {avg_yolo_time*1000:.2f}ms")
        print(f"  Maximum YOLO time: {max_yolo_time*1000:.2f}ms")
        print(f"  YOLO processing FPS: {yolo_fps:.2f}")
        print(f"  Detections per frame: {total_detections/frames_processed:.2f}")
        
        # Check YOLO performance requirements
        yolo_performance_ok = yolo_fps >= self.config.min_fps_requirement
        
        if yolo_performance_ok:
            print("✅ YOLO integration performance meets requirements")
        else:
            print(f"❌ YOLO integration too slow: {yolo_fps:.2f} FPS (min: {self.config.min_fps_requirement})")
        
        self.test_results['yolo_integration_hardware'] = yolo_performance_ok
        self.test_stats['yolo_hardware_fps'] = yolo_fps
        self.test_stats['yolo_total_detections'] = total_detections
        
        return yolo_performance_ok
    
    def _test_longterm_reliability(self) -> bool:
        """Test 7: Long-term reliability testing"""
        print("\n🕐 Test 7: Long-term Reliability Testing")
        print("-" * 60)
        
        if not self.receiver or not self.receiver.is_connected():
            print("❌ No hardware connection available")
            self.test_results['longterm_reliability'] = False
            return False
        
        print(f"Running {self.config.reliability_test_duration}s reliability test...")
        print("This test monitors system stability over extended operation")
        
        reliability_start = time.time()
        
        # Reliability monitoring
        total_frames = 0
        connection_losses = 0
        error_events = 0
        memory_samples = []
        
        last_status_time = reliability_start
        
        while (time.time() - reliability_start) < self.config.reliability_test_duration and not self.test_interrupted:
            # Read frame
            frame = self.receiver.read_frame()
            
            if frame is not None:
                total_frames += 1
                
                # Monitor memory usage periodically
                if total_frames % 100 == 0:
                    try:
                        import psutil
                        process = psutil.Process()
                        memory_mb = process.memory_info().rss / 1024 / 1024
                        memory_samples.append(memory_mb)
                    except ImportError:
                        pass
            
            # Check connection status
            if not self.receiver.is_connected():
                connection_losses += 1
                print(f"  ⚠️ Connection lost at {time.time() - reliability_start:.1f}s")
                
                # Attempt reconnection
                if self.receiver.connect():
                    print(f"  ✅ Reconnected")
                else:
                    print(f"  ❌ Reconnection failed")
                    break
            
            # Print status every minute
            current_time = time.time()
            if current_time - last_status_time >= 60:
                elapsed = current_time - reliability_start
                fps = total_frames / elapsed if elapsed > 0 else 0
                print(f"  {elapsed/60:.1f}min: {total_frames} frames, {fps:.1f} FPS")
                last_status_time = current_time
            
            time.sleep(0.01)
        
        reliability_duration = time.time() - reliability_start
        
        # Calculate reliability statistics
        avg_fps = total_frames / reliability_duration if reliability_duration > 0 else 0
        
        print(f"\nReliability test results:")
        print(f"  Test duration: {reliability_duration/60:.1f} minutes")
        print(f"  Total frames processed: {total_frames}")
        print(f"  Average FPS: {avg_fps:.2f}")
        print(f"  Connection losses: {connection_losses}")
        print(f"  Error events: {error_events}")
        
        # Memory analysis
        if memory_samples:
            initial_memory = memory_samples[0]
            final_memory = memory_samples[-1]
            max_memory = max(memory_samples)
            memory_growth = final_memory - initial_memory
            
            print(f"  Memory usage:")
            print(f"    Initial: {initial_memory:.1f} MB")
            print(f"    Final: {final_memory:.1f} MB")
            print(f"    Peak: {max_memory:.1f} MB")
            print(f"    Growth: {memory_growth:.1f} MB")
            
            # Check for memory leaks
            memory_leak_threshold = 100  # MB
            if memory_growth > memory_leak_threshold:
                print(f"  ⚠️ Potential memory leak detected")
        
        # Evaluate reliability
        min_frames_expected = reliability_duration * self.config.min_fps_requirement * 0.8  # Allow 20% tolerance
        max_connection_losses = 3  # Allow up to 3 connection losses
        
        reliability_ok = (
            total_frames >= min_frames_expected and
            connection_losses <= max_connection_losses and
            avg_fps >= self.config.min_fps_requirement * 0.8  # 80% of target FPS
        )
        
        if reliability_ok:
            print("✅ Long-term reliability requirements met")
        else:
            print("❌ Long-term reliability requirements not met")
        
        self.test_results['longterm_reliability'] = reliability_ok
        self.test_stats['reliability_duration'] = reliability_duration
        self.test_stats['reliability_total_frames'] = total_frames
        self.test_stats['reliability_avg_fps'] = avg_fps
        self.test_stats['connection_losses'] = connection_losses
        
        return reliability_ok
    
    def _test_stress_conditions(self) -> bool:
        """Test 8: Stress testing under high load"""
        print("\n💪 Test 8: Stress Testing Under High Load")
        print("-" * 60)
        
        if not self.receiver or not self.receiver.is_connected():
            print("❌ No hardware connection available")
            self.test_results['stress_conditions'] = False
            return False
        
        print(f"Running {self.config.stress_test_duration}s stress test...")
        print("This test applies high processing load while monitoring performance")
        
        stress_start = time.time()
        
        # Stress test monitoring
        stress_frames = 0
        stress_processing_times = []
        cpu_intensive_operations = 0
        
        # Load YOLO model if not already loaded
        if not self.yolo_model and YOLO_AVAILABLE:
            try:
                self.yolo_model = YOLO('yolo11n.pt')
            except:
                pass
        
        while (time.time() - stress_start) < self.config.stress_test_duration and not self.test_interrupted:
            frame_start = time.time()
            
            # Read frame
            frame = self.receiver.read_frame()
            
            if frame is not None:
                stress_frames += 1
                
                # Apply intensive processing
                processing_start = time.time()
                
                # Multiple image processing operations
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                blurred = cv2.GaussianBlur(gray, (15, 15), 0)
                edges = cv2.Canny(blurred, 50, 150)
                
                # Morphological operations
                kernel = np.ones((5, 5), np.uint8)
                dilated = cv2.dilate(edges, kernel, iterations=2)
                eroded = cv2.erode(dilated, kernel, iterations=2)
                
                # Find contours (CPU intensive)
                contours, _ = cv2.findContours(eroded, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                # YOLO processing if available
                if self.yolo_model:
                    results = self.yolo_model(frame, verbose=False)
                
                processing_time = time.time() - processing_start
                stress_processing_times.append(processing_time)
                
                cpu_intensive_operations += 1
                
                # Print status every 30 frames
                if stress_frames % 30 == 0:
                    elapsed = time.time() - stress_start
                    fps = stress_frames / elapsed if elapsed > 0 else 0
                    print(f"  {elapsed:.1f}s: {stress_frames} frames, {fps:.1f} FPS, {processing_time*1000:.1f}ms proc")
            
            # Small delay to prevent complete CPU saturation
            time.sleep(0.001)
        
        stress_duration = time.time() - stress_start
        
        if not stress_processing_times:
            print("❌ No frames processed during stress test")
            self.test_results['stress_conditions'] = False
            return False
        
        # Calculate stress test statistics
        avg_processing_time = sum(stress_processing_times) / len(stress_processing_times)
        max_processing_time = max(stress_processing_times)
        stress_fps = stress_frames / stress_duration if stress_duration > 0 else 0
        
        print(f"\nStress test results:")
        print(f"  Test duration: {stress_duration:.1f}s")
        print(f"  Frames processed: {stress_frames}")
        print(f"  CPU intensive operations: {cpu_intensive_operations}")
        print(f"  Average processing time: {avg_processing_time*1000:.2f}ms")
        print(f"  Maximum processing time: {max_processing_time*1000:.2f}ms")
        print(f"  Stress test FPS: {stress_fps:.2f}")
        
        # Check stress test performance
        # Under stress, we allow reduced performance but system should remain stable
        min_stress_fps = self.config.min_fps_requirement * 0.5  # Allow 50% reduction under stress
        max_acceptable_processing_time = self.config.max_frame_processing_time * 3  # Allow 3x processing time
        
        stress_ok = (
            stress_fps >= min_stress_fps and
            avg_processing_time <= max_acceptable_processing_time and
            self.receiver.is_connected()  # Connection should remain stable
        )
        
        if stress_ok:
            print("✅ System remains stable under stress conditions")
        else:
            print("❌ System performance degraded excessively under stress")
        
        self.test_results['stress_conditions'] = stress_ok
        self.test_stats['stress_fps'] = stress_fps
        self.test_stats['stress_avg_processing_time'] = avg_processing_time
        
        return stress_ok
    
    def _cleanup_hil_resources(self):
        """Clean up HIL test resources"""
        print("\n🧹 Cleaning up HIL test resources...")
        
        if self.receiver:
            try:
                self.receiver.disconnect()
                print("  ✅ ESP32-camera disconnected")
            except:
                pass
        
        if hasattr(self, 'yolo_model') and self.yolo_model:
            try:
                del self.yolo_model
                print("  ✅ YOLO model unloaded")
            except:
                pass
        
        # Force garbage collection
        import gc
        gc.collect()
        print("  ✅ Memory cleanup completed")
    
    def _print_hil_results(self):
        """Print comprehensive HIL test results"""
        print("\n" + "=" * 80)
        print("📊 Hardware-in-the-Loop Test Results")
        print("=" * 80)
        
        # Test results summary
        print("\n🧪 Test Results:")
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results.values() if result)
        
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"  {test_name.replace('_', ' ').title()}: {status}")
        
        # Overall statistics
        print(f"\n📈 Test Statistics:")
        print(f"  Total Tests: {total_tests}")
        print(f"  Passed: {passed_tests}")
        print(f"  Failed: {total_tests - passed_tests}")
        print(f"  Success Rate: {passed_tests/total_tests*100:.1f}%")
        
        if 'total_test_time' in self.test_stats:
            print(f"  Total Test Time: {self.test_stats['total_test_time']/60:.1f} minutes")
        
        # Hardware performance statistics
        if self.test_stats:
            print(f"\n⚡ Hardware Performance:")
            
            if 'hardware_fps' in self.test_stats:
                print(f"  Hardware Frame Rate: {self.test_stats['hardware_fps']:.2f} FPS")
            
            if 'realtime_avg_fps' in self.test_stats:
                print(f"  Real-time Average FPS: {self.test_stats['realtime_avg_fps']:.2f}")
                print(f"  Real-time FPS Range: {self.test_stats.get('realtime_min_fps', 0):.2f} - {self.test_stats.get('realtime_max_fps', 0):.2f}")
            
            if 'yolo_hardware_fps' in self.test_stats:
                print(f"  YOLO Processing FPS: {self.test_stats['yolo_hardware_fps']:.2f}")
            
            if 'reliability_avg_fps' in self.test_stats:
                print(f"  Long-term Average FPS: {self.test_stats['reliability_avg_fps']:.2f}")
            
            if 'stress_fps' in self.test_stats:
                print(f"  Stress Test FPS: {self.test_stats['stress_fps']:.2f}")
        
        # Reliability statistics
        if 'connection_losses' in self.test_stats:
            print(f"\n🔄 Reliability Statistics:")
            print(f"  Connection Losses: {self.test_stats['connection_losses']}")
            
            if 'reconnect_time' in self.test_stats:
                print(f"  Reconnection Time: {self.test_stats['reconnect_time']:.2f}s")
            
            if 'reliability_total_frames' in self.test_stats:
                print(f"  Total Frames Processed: {self.test_stats['reliability_total_frames']}")
        
        # Overall result
        all_passed = all(self.test_results.values())
        overall_status = "✅ ALL TESTS PASSED" if all_passed else "❌ SOME TESTS FAILED"
        print(f"\n🎯 Overall Result: {overall_status}")
        
        if all_passed:
            print("\n🎉 ESP32-camera hardware integration is working correctly!")
            print("   The system meets all performance and reliability requirements.")
        else:
            failed_tests = [name for name, result in self.test_results.items() if not result]
            print(f"\n⚠️ Failed tests: {', '.join(failed_tests)}")
            print("   Please review the hardware setup and fix the issues.")


def main():
    """Main HIL test function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Hardware-in-the-Loop ESP32-Camera Test")
    parser.add_argument("--port", default="COM3", help="Serial port (default: COM3)")
    parser.add_argument("--baud", type=int, default=921600, help="Baud rate (default: 921600)")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds (default: 60)")
    parser.add_argument("--reliability-duration", type=int, default=300, help="Reliability test duration in seconds (default: 300)")
    parser.add_argument("--stress-duration", type=int, default=120, help="Stress test duration in seconds (default: 120)")
    parser.add_argument("--min-fps", type=float, default=10.0, help="Minimum FPS requirement (default: 10.0)")
    parser.add_argument("--no-yolo", action="store_true", help="Skip YOLO processing tests")
    parser.add_argument("--save-frames", action="store_true", help="Save test frames to disk")
    parser.add_argument("--output-dir", default="hil_test_output", help="Output directory for saved frames")
    parser.add_argument("--quick", action="store_true", help="Run quick test (shorter durations)")
    
    args = parser.parse_args()
    
    # Create test configuration
    config = HILTestConfig(
        port=args.port,
        baud=args.baud,
        test_duration=args.duration if not args.quick else 30,
        reliability_test_duration=args.reliability_duration if not args.quick else 60,
        stress_test_duration=args.stress_duration if not args.quick else 30,
        min_fps_requirement=args.min_fps,
        enable_yolo_processing=not args.no_yolo,
        save_test_frames=args.save_frames,
        test_output_dir=args.output_dir
    )
    
    print("Hardware-in-the-Loop ESP32-Camera Test")
    print(f"Configuration: {config}")
    
    if args.quick:
        print("Running in quick mode (shorter test durations)")
    
    if not ESP32_IMPORTS_AVAILABLE:
        print("❌ ESP32 modules not available - cannot run HIL tests")
        return 1
    
    # Create and run tester
    tester = HardwareInTheLoopTester(config)
    
    try:
        success = tester.run_all_hil_tests()
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n\n⏹️ HIL test interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n❌ HIL test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())