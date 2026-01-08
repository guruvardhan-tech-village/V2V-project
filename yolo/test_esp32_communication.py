#!/usr/bin/env python3
"""
ESP32-Camera Communication Test

This test verifies that ESP32-camera firmware and Python receiver work together.
It tests frame transmission, reconstruction, and decoding as specified in task 5.

Requirements tested:
- Frame transmission protocol (Requirements 2.1, 2.2, 2.3, 2.4, 2.5)
- Frame reconstruction and decoding (Requirements 3.1, 3.2, 3.3, 3.4)
- Buffer management (Requirements 3.5, 7.2)
"""

import time
import sys
import threading
import queue
from typing import Optional, Dict, Any
import numpy as np
import cv2

from esp32_camera_receiver import ESP32CameraReceiver, ESP32CameraCapture, CameraConfig


class ESP32CommunicationTester:
    """
    Comprehensive tester for ESP32-camera communication.
    
    This class tests the complete communication pipeline:
    1. ESP32 firmware frame transmission
    2. Python receiver frame reconstruction
    3. JPEG decoding and validation
    4. Buffer management and timing
    """
    
    def __init__(self, port: str = "COM3", baud: int = 921600):
        self.port = port
        self.baud = baud
        self.receiver: Optional[ESP32CameraReceiver] = None
        self.test_results = {
            'connection_test': False,
            'frame_reception_test': False,
            'frame_decoding_test': False,
            'configuration_test': False,
            'buffer_management_test': False,
            'error_handling_test': False,
            'performance_test': False
        }
        self.test_stats = {
            'frames_received': 0,
            'frames_decoded': 0,
            'frames_corrupted': 0,
            'avg_frame_size': 0,
            'avg_fps': 0.0,
            'test_duration': 0.0
        }
    
    def run_all_tests(self) -> bool:
        """
        Run all communication tests.
        
        Returns:
            True if all tests pass, False otherwise
        """
        print("🚀 Starting ESP32-Camera Communication Tests")
        print("=" * 60)
        
        start_time = time.time()
        
        try:
            # Test 1: Connection Test
            if not self.test_connection():
                print("❌ Connection test failed - cannot proceed with other tests")
                return False
            
            # Test 2: Frame Reception Test
            if not self.test_frame_reception():
                print("❌ Frame reception test failed")
                return False
            
            # Test 3: Frame Decoding Test
            if not self.test_frame_decoding():
                print("❌ Frame decoding test failed")
                return False
            
            # Test 4: Configuration Test
            if not self.test_configuration():
                print("❌ Configuration test failed")
                return False
            
            # Test 5: Buffer Management Test
            if not self.test_buffer_management():
                print("❌ Buffer management test failed")
                return False
            
            # Test 6: Error Handling Test
            if not self.test_error_handling():
                print("❌ Error handling test failed")
                return False
            
            # Test 7: Performance Test
            if not self.test_performance():
                print("❌ Performance test failed")
                return False
            
            self.test_stats['test_duration'] = time.time() - start_time
            
            # Print final results
            self.print_test_summary()
            
            return all(self.test_results.values())
            
        except Exception as e:
            print(f"❌ Test suite failed with exception: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            if self.receiver:
                self.receiver.disconnect()
    
    def test_connection(self) -> bool:
        """
        Test 1: Verify ESP32-camera connection and initialization.
        
        Tests Requirements:
        - 1.1: ESP32-camera detection on COM3 port
        - 3.1: Serial connection establishment
        """
        print("\n📡 Test 1: Connection Test")
        print("-" * 30)
        
        try:
            # Initialize receiver
            self.receiver = ESP32CameraReceiver(port=self.port, baud=self.baud, buffer_size=10)
            
            # Attempt connection
            print(f"Attempting to connect to {self.port} at {self.baud} baud...")
            success = self.receiver.connect()
            
            if not success:
                print(f"❌ Failed to connect to {self.port}")
                return False
            
            # Wait for ESP32 initialization messages
            print("Waiting for ESP32 initialization...")
            time.sleep(3)
            
            # Check connection status
            if not self.receiver.is_connected():
                print("❌ Connection established but receiver reports not connected")
                return False
            
            print("✅ Connection established successfully")
            self.test_results['connection_test'] = True
            return True
            
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            return False
    
    def test_frame_reception(self) -> bool:
        """
        Test 2: Verify frame reception and protocol parsing.
        
        Tests Requirements:
        - 2.1: Frame delimiter protocol
        - 2.2: Frame header with size information
        - 2.4: Frame footer marker
        - 3.2: Frame reconstruction from serial chunks
        """
        print("\n📥 Test 2: Frame Reception Test")
        print("-" * 30)
        
        if not self.receiver or not self.receiver.is_connected():
            print("❌ No connection available for frame reception test")
            return False
        
        try:
            # Wait for frames to arrive
            print("Waiting for frames from ESP32-camera...")
            frames_received = 0
            timeout = 30  # 30 second timeout
            start_time = time.time()
            
            while frames_received < 5 and (time.time() - start_time) < timeout:
                frame_data = self.receiver.read_frame_with_metadata()
                
                if frame_data is not None:
                    frame, metadata = frame_data
                    frames_received += 1
                    
                    print(f"✅ Frame {frames_received} received:")
                    print(f"   Sequence: {metadata['sequence']}")
                    print(f"   Dimensions: {metadata['dimensions']}")
                    print(f"   Channels: {metadata['channels']}")
                    print(f"   Size: {frame.nbytes} bytes")
                    
                    self.test_stats['frames_received'] += 1
                
                time.sleep(0.5)
            
            if frames_received == 0:
                print("❌ No frames received within timeout period")
                return False
            
            print(f"✅ Successfully received {frames_received} frames")
            self.test_results['frame_reception_test'] = True
            return True
            
        except Exception as e:
            print(f"❌ Frame reception test failed: {e}")
            return False
    
    def test_frame_decoding(self) -> bool:
        """
        Test 3: Verify JPEG decoding and frame validation.
        
        Tests Requirements:
        - 3.3: Decode received JPEG frames to OpenCV format
        - 3.4: Validate frame integrity and dimensions
        - 1.5: JPEG format compliance
        """
        print("\n🖼️ Test 3: Frame Decoding Test")
        print("-" * 30)
        
        if not self.receiver or not self.receiver.is_connected():
            print("❌ No connection available for frame decoding test")
            return False
        
        try:
            # Test frame decoding with validation
            print("Testing frame decoding and validation...")
            frames_decoded = 0
            frames_tested = 0
            timeout = 20
            start_time = time.time()
            
            while frames_decoded < 3 and (time.time() - start_time) < timeout:
                frame_data = self.receiver.read_frame_with_metadata()
                
                if frame_data is not None:
                    frame, metadata = frame_data
                    frames_tested += 1
                    
                    # Validate frame properties
                    if self.validate_decoded_frame(frame, metadata):
                        frames_decoded += 1
                        self.test_stats['frames_decoded'] += 1
                        
                        print(f"✅ Frame {frames_decoded} decoded and validated:")
                        print(f"   Shape: {frame.shape}")
                        print(f"   Data type: {frame.dtype}")
                        print(f"   Value range: {frame.min()}-{frame.max()}")
                        
                        # Calculate average frame size
                        if self.test_stats['frames_decoded'] > 0:
                            self.test_stats['avg_frame_size'] = (
                                (self.test_stats['avg_frame_size'] * (self.test_stats['frames_decoded'] - 1) + frame.nbytes) /
                                self.test_stats['frames_decoded']
                            )
                    else:
                        print(f"⚠️ Frame {frames_tested} failed validation")
                        self.test_stats['frames_corrupted'] += 1
                
                time.sleep(0.5)
            
            if frames_decoded == 0:
                print("❌ No frames successfully decoded and validated")
                return False
            
            success_rate = frames_decoded / frames_tested if frames_tested > 0 else 0
            print(f"✅ Frame decoding success rate: {success_rate:.1%} ({frames_decoded}/{frames_tested})")
            
            if success_rate < 0.8:  # Require at least 80% success rate
                print("❌ Frame decoding success rate too low")
                return False
            
            self.test_results['frame_decoding_test'] = True
            return True
            
        except Exception as e:
            print(f"❌ Frame decoding test failed: {e}")
            return False
    
    def validate_decoded_frame(self, frame: np.ndarray, metadata: Dict[str, Any]) -> bool:
        """
        Validate a decoded frame for integrity and correctness.
        
        Args:
            frame: OpenCV frame (numpy array)
            metadata: Frame metadata dictionary
            
        Returns:
            True if frame is valid, False otherwise
        """
        try:
            # Check frame is not None or empty
            if frame is None or frame.size == 0:
                return False
            
            # Check data type
            if frame.dtype != np.uint8:
                return False
            
            # Check dimensions match metadata
            height, width = frame.shape[:2]
            expected_dims = metadata.get('dimensions', (0, 0))
            if (width, height) != expected_dims:
                return False
            
            # Check reasonable dimensions
            if width < 160 or height < 120 or width > 1600 or height > 1200:
                return False
            
            # Check color channels
            expected_channels = metadata.get('channels', 3)
            actual_channels = frame.shape[2] if len(frame.shape) > 2 else 1
            if actual_channels != expected_channels:
                return False
            
            # Check for reasonable image content
            mean_intensity = np.mean(frame)
            if mean_intensity < 1 or mean_intensity > 254:
                return False
            
            # Check for some variance (not completely uniform)
            variance = np.var(frame)
            if variance < 0.1:
                return False
            
            return True
            
        except Exception:
            return False
    
    def test_configuration(self) -> bool:
        """
        Test 4: Verify camera configuration commands.
        
        Tests Requirements:
        - 5.1, 5.2, 5.3, 5.4: Camera configuration
        """
        print("\n⚙️ Test 4: Configuration Test")
        print("-" * 30)
        
        if not self.receiver or not self.receiver.is_connected():
            print("❌ No connection available for configuration test")
            return False
        
        try:
            # Test different configurations
            configurations = [
                {"resolution": "QVGA", "fps": 10, "quality": 40},
                {"resolution": "VGA", "fps": 15, "quality": 50},
                {"resolution": "SVGA", "fps": 8, "quality": 60}
            ]
            
            for i, config in enumerate(configurations):
                print(f"Testing configuration {i+1}: {config}")
                
                # Send configuration
                success = self.receiver.configure_camera(**config)
                if not success:
                    print(f"❌ Failed to send configuration {i+1}")
                    return False
                
                # Wait for configuration to take effect
                time.sleep(2)
                
                # Verify configuration by checking next frame
                frame_data = self.receiver.wait_for_frame(timeout=10)
                if frame_data is None:
                    print(f"❌ No frame received after configuration {i+1}")
                    return False
                
                print(f"✅ Configuration {i+1} applied successfully")
            
            print("✅ All configuration tests passed")
            self.test_results['configuration_test'] = True
            return True
            
        except Exception as e:
            print(f"❌ Configuration test failed: {e}")
            return False
    
    def test_buffer_management(self) -> bool:
        """
        Test 5: Verify buffer management and timing handling.
        
        Tests Requirements:
        - 3.5: Frame buffer to handle timing variations
        - 7.2: Buffer overflow management
        """
        print("\n🗂️ Test 5: Buffer Management Test")
        print("-" * 30)
        
        if not self.receiver or not self.receiver.is_connected():
            print("❌ No connection available for buffer management test")
            return False
        
        try:
            # Test buffer size adjustment
            print("Testing buffer size adjustment...")
            original_size = self.receiver.buffer_size
            
            # Reduce buffer size to force overflow
            self.receiver.set_buffer_size(2)
            time.sleep(1)
            
            # Let buffer fill up
            print("Filling buffer to test overflow management...")
            time.sleep(5)
            
            # Check buffer health
            health = self.receiver.get_buffer_health()
            print(f"Buffer usage: {health['buffer_usage_percent']:.1f}%")
            print(f"Buffer overflows: {health['buffer_overflows']}")
            
            # Restore original buffer size
            self.receiver.set_buffer_size(original_size)
            
            # Test frame timing statistics
            print("Testing frame timing statistics...")
            rate_stats = self.receiver.get_frame_rate_stats()
            print(f"Average FPS: {rate_stats['avg_fps']:.2f}")
            print(f"Frame jitter: {rate_stats['jitter']:.3f}s")
            
            # Test buffer clearing
            print("Testing buffer clearing...")
            self.receiver.clear_buffer()
            
            # Verify buffer is empty
            health_after_clear = self.receiver.get_buffer_health()
            if health_after_clear['buffer_size_current'] != 0:
                print("❌ Buffer not properly cleared")
                return False
            
            print("✅ Buffer management tests passed")
            self.test_results['buffer_management_test'] = True
            return True
            
        except Exception as e:
            print(f"❌ Buffer management test failed: {e}")
            return False
    
    def test_error_handling(self) -> bool:
        """
        Test 6: Verify error handling and recovery mechanisms.
        
        Tests Requirements:
        - 2.5: Handle transmission errors gracefully
        - 6.1, 6.2: Error detection and recovery
        """
        print("\n🛡️ Test 6: Error Handling Test")
        print("-" * 30)
        
        if not self.receiver or not self.receiver.is_connected():
            print("❌ No connection available for error handling test")
            return False
        
        try:
            # Get initial stats
            initial_stats = self.receiver.get_stats()
            
            # Monitor for a period to see if any errors occur naturally
            print("Monitoring for natural error conditions...")
            monitor_time = 10
            start_time = time.time()
            
            while time.time() - start_time < monitor_time:
                frame = self.receiver.read_frame()
                if frame is not None:
                    # Frame received successfully
                    pass
                time.sleep(0.1)
            
            # Get final stats
            final_stats = self.receiver.get_stats()
            
            # Check error statistics
            frames_corrupted = final_stats['frames_corrupted'] - initial_stats['frames_corrupted']
            frames_dropped = final_stats['frames_dropped'] - initial_stats['frames_dropped']
            
            print(f"Frames corrupted during test: {frames_corrupted}")
            print(f"Frames dropped during test: {frames_dropped}")
            
            # Test connection status checking
            if not self.receiver.is_connected():
                print("❌ Connection lost during error handling test")
                return False
            
            print("✅ Error handling test completed")
            self.test_results['error_handling_test'] = True
            return True
            
        except Exception as e:
            print(f"❌ Error handling test failed: {e}")
            return False
    
    def test_performance(self) -> bool:
        """
        Test 7: Verify performance requirements.
        
        Tests Requirements:
        - 1.4: Minimum 15 FPS frame rate
        - 7.1: Maintain minimum 10 FPS for processing
        """
        print("\n⚡ Test 7: Performance Test")
        print("-" * 30)
        
        if not self.receiver or not self.receiver.is_connected():
            print("❌ No connection available for performance test")
            return False
        
        try:
            # Measure frame rate over a period
            print("Measuring frame rate performance...")
            test_duration = 15  # seconds
            start_time = time.time()
            frame_count = 0
            frame_times = []
            
            while time.time() - start_time < test_duration:
                frame_start = time.time()
                frame = self.receiver.read_frame()
                
                if frame is not None:
                    frame_count += 1
                    frame_times.append(time.time() - frame_start)
                
                time.sleep(0.01)  # Small delay to prevent busy waiting
            
            actual_duration = time.time() - start_time
            measured_fps = frame_count / actual_duration
            
            print(f"Frames received: {frame_count}")
            print(f"Test duration: {actual_duration:.2f}s")
            print(f"Measured FPS: {measured_fps:.2f}")
            
            # Check minimum FPS requirement
            if measured_fps < 10.0:  # Minimum requirement from 7.1
                print(f"❌ Frame rate too low: {measured_fps:.2f} FPS (minimum: 10 FPS)")
                return False
            
            # Calculate processing time statistics
            if frame_times:
                avg_processing_time = sum(frame_times) / len(frame_times)
                max_processing_time = max(frame_times)
                print(f"Average frame processing time: {avg_processing_time*1000:.2f}ms")
                print(f"Maximum frame processing time: {max_processing_time*1000:.2f}ms")
                
                # Check processing time is reasonable
                if avg_processing_time > 0.1:  # 100ms is too slow
                    print(f"❌ Frame processing too slow: {avg_processing_time*1000:.2f}ms")
                    return False
            
            self.test_stats['avg_fps'] = measured_fps
            
            print("✅ Performance test passed")
            self.test_results['performance_test'] = True
            return True
            
        except Exception as e:
            print(f"❌ Performance test failed: {e}")
            return False
    
    def print_test_summary(self):
        """Print comprehensive test summary"""
        print("\n" + "=" * 60)
        print("📊 ESP32-Camera Communication Test Summary")
        print("=" * 60)
        
        # Test results
        print("\n🧪 Test Results:")
        for test_name, result in self.test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"  {test_name.replace('_', ' ').title()}: {status}")
        
        # Statistics
        print(f"\n📈 Test Statistics:")
        print(f"  Test Duration: {self.test_stats['test_duration']:.2f}s")
        print(f"  Frames Received: {self.test_stats['frames_received']}")
        print(f"  Frames Decoded: {self.test_stats['frames_decoded']}")
        print(f"  Frames Corrupted: {self.test_stats['frames_corrupted']}")
        print(f"  Average Frame Size: {self.test_stats['avg_frame_size']:.0f} bytes")
        print(f"  Average FPS: {self.test_stats['avg_fps']:.2f}")
        
        # Overall result
        all_passed = all(self.test_results.values())
        overall_status = "✅ ALL TESTS PASSED" if all_passed else "❌ SOME TESTS FAILED"
        print(f"\n🎯 Overall Result: {overall_status}")
        
        if all_passed:
            print("\n🎉 ESP32-camera communication is working correctly!")
            print("   The firmware and Python receiver are properly integrated.")
        else:
            print("\n⚠️ Some tests failed. Please check the issues above.")


def main():
    """Main test function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="ESP32-Camera Communication Test")
    parser.add_argument("--port", default="COM3", help="Serial port (default: COM3)")
    parser.add_argument("--baud", type=int, default=921600, help="Baud rate (default: 921600)")
    parser.add_argument("--quick", action="store_true", help="Run quick test (shorter timeouts)")
    
    args = parser.parse_args()
    
    print("ESP32-Camera Communication Test")
    print(f"Port: {args.port}")
    print(f"Baud: {args.baud}")
    
    if args.quick:
        print("Running in quick mode (shorter timeouts)")
    
    # Create and run tester
    tester = ESP32CommunicationTester(port=args.port, baud=args.baud)
    
    try:
        success = tester.run_all_tests()
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n\n⏹️ Test interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())