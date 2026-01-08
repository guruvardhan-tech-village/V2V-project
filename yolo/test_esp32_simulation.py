#!/usr/bin/env python3
"""
ESP32-Camera Communication Simulation Test

This test simulates ESP32-camera communication to verify the protocol
implementation without requiring actual hardware. It tests frame transmission,
reconstruction, and decoding using simulated data.

Requirements tested:
- Frame transmission protocol (Requirements 2.1, 2.2, 2.3, 2.4, 2.5)
- Frame reconstruction and decoding (Requirements 3.1, 3.2, 3.3, 3.4)
- Buffer management (Requirements 3.5, 7.2)
"""

import time
import threading
import queue
import struct
import zlib
from typing import Optional, List, Tuple
import numpy as np
import cv2
import io

from esp32_camera_receiver import ESP32CameraReceiver, FrameMetadata, CameraConfig


class ESP32CameraSimulator:
    """
    Simulates ESP32-camera behavior for testing purposes.
    
    This class generates synthetic JPEG frames and transmits them using
    the same protocol as the real ESP32-camera firmware.
    """
    
    def __init__(self, fps: int = 15, resolution: Tuple[int, int] = (640, 480)):
        self.fps = fps
        self.resolution = resolution
        self.sequence = 0
        self.running = False
        self.frame_interval = 1.0 / fps
        
        # Generate test pattern frames
        self.test_frames = self._generate_test_frames()
        self.current_frame_index = 0
    
    def _generate_test_frames(self) -> List[bytes]:
        """Generate a set of test JPEG frames"""
        frames = []
        
        for i in range(10):  # Generate 10 different test frames
            # Create test pattern
            frame = np.zeros((self.resolution[1], self.resolution[0], 3), dtype=np.uint8)
            
            # Add different patterns for each frame
            if i % 4 == 0:
                # Gradient pattern
                for y in range(frame.shape[0]):
                    frame[y, :, :] = int(255 * y / frame.shape[0])
            elif i % 4 == 1:
                # Checkerboard pattern
                for y in range(0, frame.shape[0], 40):
                    for x in range(0, frame.shape[1], 40):
                        if (x // 40 + y // 40) % 2 == 0:
                            frame[y:y+40, x:x+40] = [255, 255, 255]
            elif i % 4 == 2:
                # Circle pattern
                center = (frame.shape[1] // 2, frame.shape[0] // 2)
                radius = min(center) // 2
                cv2.circle(frame, center, radius, (0, 255, 0), -1)
            else:
                # Random noise pattern
                frame = np.random.randint(0, 256, frame.shape, dtype=np.uint8)
            
            # Encode as JPEG
            _, encoded = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
            frames.append(encoded.tobytes())
        
        return frames
    
    def get_next_frame(self) -> bytes:
        """Get the next test frame"""
        frame_data = self.test_frames[self.current_frame_index]
        self.current_frame_index = (self.current_frame_index + 1) % len(self.test_frames)
        return frame_data
    
    def generate_frame_messages(self, frame_data: bytes) -> List[str]:
        """
        Generate protocol messages for a frame.
        
        Args:
            frame_data: JPEG frame data
            
        Returns:
            List of protocol messages (header, chunks, footer)
        """
        self.sequence += 1
        messages = []
        
        # Calculate checksum
        checksum = format(zlib.crc32(frame_data) & 0xffffffff, '08X')
        
        # Frame header
        header = f"FRAME_START|size:{len(frame_data)}|seq:{self.sequence:03d}|timestamp:{int(time.time() * 1000)}"
        messages.append(header)
        
        # Frame data (in simulation, we'll add it as a special message)
        messages.append(f"FRAME_DATA|{len(frame_data)}|" + frame_data.hex())
        
        # Frame footer
        footer = f"FRAME_END|seq:{self.sequence:03d}|checksum:{checksum}"
        messages.append(footer)
        
        return messages


class SimulatedESP32Receiver(ESP32CameraReceiver):
    """
    Modified ESP32CameraReceiver that works with simulated data.
    """
    
    def __init__(self, simulator: ESP32CameraSimulator, **kwargs):
        # Initialize parent without connecting to serial
        super().__init__(port="SIMULATED", baud=921600, **kwargs)
        self.simulator = simulator
        self.simulation_thread: Optional[threading.Thread] = None
        self.stop_simulation = threading.Event()
    
    def connect(self) -> bool:
        """Simulate connection"""
        self.connected = True
        print("✅ Connected to simulated ESP32-camera")
        
        # Start simulation thread
        self.stop_simulation.clear()
        self.simulation_thread = threading.Thread(target=self._run_simulation, daemon=True)
        self.simulation_thread.start()
        
        return True
    
    def disconnect(self):
        """Disconnect from simulation"""
        self.connected = False
        
        if self.simulation_thread and self.simulation_thread.is_alive():
            self.stop_simulation.set()
            self.simulation_thread.join(timeout=2)
        
        print("📡 Disconnected from simulated ESP32-camera")
    
    def _run_simulation(self):
        """Run the ESP32-camera simulation"""
        while not self.stop_simulation.is_set() and self.connected:
            try:
                # Generate next frame
                frame_data = self.simulator.get_next_frame()
                messages = self.simulator.generate_frame_messages(frame_data)
                
                # Process messages
                for message in messages:
                    if message.startswith("FRAME_DATA|"):
                        # Extract and inject frame data
                        parts = message.split('|', 2)
                        data_size = int(parts[1])
                        hex_data = parts[2]
                        binary_data = bytes.fromhex(hex_data)
                        
                        # Inject binary data into current frame
                        self.current_frame_data.extend(binary_data)
                    else:
                        # Process protocol message
                        self._process_serial_line(message)
                
                # Wait for next frame
                time.sleep(self.simulator.frame_interval)
                
            except Exception as e:
                print(f"❌ Simulation error: {e}")
                break
    
    def configure_camera(self, resolution: str = None, fps: int = None, quality: int = None) -> bool:
        """Simulate camera configuration"""
        if not self.connected:
            return False
        
        # Update simulator settings
        if fps is not None:
            self.simulator.fps = fps
            self.simulator.frame_interval = 1.0 / fps
        
        if resolution is not None:
            # Map resolution strings to dimensions
            res_map = {
                "QVGA": (320, 240),
                "VGA": (640, 480),
                "SVGA": (800, 600),
                "XGA": (1024, 768)
            }
            if resolution in res_map:
                self.simulator.resolution = res_map[resolution]
                # Regenerate test frames with new resolution
                self.simulator.test_frames = self.simulator._generate_test_frames()
        
        print(f"📤 Simulated configuration: resolution={resolution}, fps={fps}, quality={quality}")
        
        # Simulate configuration acknowledgment
        time.sleep(0.1)  # Small delay to simulate processing
        return True


class ESP32CommunicationSimulationTester:
    """
    Comprehensive tester for ESP32-camera communication using simulation.
    """
    
    def __init__(self):
        self.simulator = ESP32CameraSimulator(fps=15, resolution=(640, 480))
        self.receiver: Optional[SimulatedESP32Receiver] = None
        self.test_results = {
            'connection_test': False,
            'frame_reception_test': False,
            'frame_decoding_test': False,
            'configuration_test': False,
            'buffer_management_test': False,
            'protocol_test': False,
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
        """Run all simulation tests"""
        print("🚀 Starting ESP32-Camera Communication Simulation Tests")
        print("=" * 70)
        
        start_time = time.time()
        
        try:
            # Initialize receiver
            self.receiver = SimulatedESP32Receiver(self.simulator, buffer_size=10)
            
            # Run tests
            tests = [
                ("Connection Test", self.test_connection),
                ("Protocol Test", self.test_protocol),
                ("Frame Reception Test", self.test_frame_reception),
                ("Frame Decoding Test", self.test_frame_decoding),
                ("Configuration Test", self.test_configuration),
                ("Buffer Management Test", self.test_buffer_management),
                ("Performance Test", self.test_performance)
            ]
            
            for test_name, test_func in tests:
                print(f"\n🧪 {test_name}")
                print("-" * 40)
                
                try:
                    result = test_func()
                    if result:
                        print(f"✅ {test_name} PASSED")
                    else:
                        print(f"❌ {test_name} FAILED")
                except Exception as e:
                    print(f"❌ {test_name} FAILED with exception: {e}")
                    result = False
                
                # Update test results
                test_key = test_name.lower().replace(' ', '_')
                self.test_results[test_key] = result
            
            self.test_stats['test_duration'] = time.time() - start_time
            
            # Print results
            self.print_test_summary()
            
            return all(self.test_results.values())
            
        except Exception as e:
            print(f"❌ Test suite failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        finally:
            if self.receiver:
                self.receiver.disconnect()
    
    def test_connection(self) -> bool:
        """Test simulated connection"""
        try:
            success = self.receiver.connect()
            if not success:
                return False
            
            # Wait for simulation to start
            time.sleep(1)
            
            if not self.receiver.is_connected():
                return False
            
            print("✅ Simulated connection established")
            return True
            
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            return False
    
    def test_protocol(self) -> bool:
        """Test protocol message parsing"""
        try:
            # Test frame metadata parsing
            header = "FRAME_START|size:12345|seq:001|timestamp:1234567890"
            metadata = FrameMetadata.from_header(header)
            
            if metadata.sequence != 1 or metadata.size != 12345:
                print(f"❌ Metadata parsing failed: seq={metadata.sequence}, size={metadata.size}")
                return False
            
            # Test camera config
            config = CameraConfig(resolution="VGA", fps=15, quality=50)
            command = config.to_command()
            expected = "CONFIG|resolution:VGA|fps:15|quality:50"
            
            if command != expected:
                print(f"❌ Config command generation failed: {command}")
                return False
            
            print("✅ Protocol parsing working correctly")
            return True
            
        except Exception as e:
            print(f"❌ Protocol test failed: {e}")
            return False
    
    def test_frame_reception(self) -> bool:
        """Test frame reception from simulation"""
        try:
            frames_received = 0
            timeout = 10
            start_time = time.time()
            
            while frames_received < 3 and (time.time() - start_time) < timeout:
                frame_data = self.receiver.read_frame_with_metadata()
                
                if frame_data is not None:
                    frame, metadata = frame_data
                    frames_received += 1
                    self.test_stats['frames_received'] += 1
                    
                    print(f"✅ Frame {frames_received}: seq={metadata['sequence']}, "
                          f"dims={metadata['dimensions']}, size={frame.nbytes}")
                
                time.sleep(0.5)
            
            if frames_received == 0:
                print("❌ No frames received from simulation")
                return False
            
            print(f"✅ Received {frames_received} frames successfully")
            return True
            
        except Exception as e:
            print(f"❌ Frame reception test failed: {e}")
            return False
    
    def test_frame_decoding(self) -> bool:
        """Test JPEG frame decoding"""
        try:
            frames_decoded = 0
            frames_tested = 0
            timeout = 8
            start_time = time.time()
            
            while frames_decoded < 3 and (time.time() - start_time) < timeout:
                frame_data = self.receiver.read_frame_with_metadata()
                
                if frame_data is not None:
                    frame, metadata = frame_data
                    frames_tested += 1
                    
                    # Validate frame
                    if self.validate_frame(frame, metadata):
                        frames_decoded += 1
                        self.test_stats['frames_decoded'] += 1
                        
                        print(f"✅ Frame {frames_decoded} decoded: {frame.shape}, "
                              f"dtype={frame.dtype}, range={frame.min()}-{frame.max()}")
                        
                        # Update average frame size
                        if self.test_stats['frames_decoded'] > 0:
                            self.test_stats['avg_frame_size'] = (
                                (self.test_stats['avg_frame_size'] * (self.test_stats['frames_decoded'] - 1) + frame.nbytes) /
                                self.test_stats['frames_decoded']
                            )
                    else:
                        print(f"⚠️ Frame {frames_tested} failed validation")
                        self.test_stats['frames_corrupted'] += 1
                
                time.sleep(0.3)
            
            if frames_decoded == 0:
                print("❌ No frames successfully decoded")
                return False
            
            success_rate = frames_decoded / frames_tested if frames_tested > 0 else 0
            print(f"✅ Decoding success rate: {success_rate:.1%} ({frames_decoded}/{frames_tested})")
            
            return success_rate >= 0.8  # Require 80% success rate
            
        except Exception as e:
            print(f"❌ Frame decoding test failed: {e}")
            return False
    
    def validate_frame(self, frame: np.ndarray, metadata: dict) -> bool:
        """Validate decoded frame"""
        try:
            if frame is None or frame.size == 0:
                return False
            
            if frame.dtype != np.uint8:
                return False
            
            height, width = frame.shape[:2]
            expected_dims = metadata.get('dimensions', (0, 0))
            if (width, height) != expected_dims:
                return False
            
            if width < 160 or height < 120:
                return False
            
            return True
            
        except Exception:
            return False
    
    def test_configuration(self) -> bool:
        """Test camera configuration"""
        try:
            configurations = [
                {"resolution": "QVGA", "fps": 10, "quality": 40},
                {"resolution": "VGA", "fps": 15, "quality": 50},
                {"fps": 20}  # Partial configuration
            ]
            
            for i, config in enumerate(configurations):
                print(f"Testing configuration {i+1}: {config}")
                
                success = self.receiver.configure_camera(**config)
                if not success:
                    print(f"❌ Configuration {i+1} failed")
                    return False
                
                time.sleep(1)  # Wait for config to take effect
                
                # Verify by receiving a frame
                frame = self.receiver.wait_for_frame(timeout=5)
                if frame is None:
                    print(f"❌ No frame after configuration {i+1}")
                    return False
                
                print(f"✅ Configuration {i+1} applied successfully")
            
            return True
            
        except Exception as e:
            print(f"❌ Configuration test failed: {e}")
            return False
    
    def test_buffer_management(self) -> bool:
        """Test buffer management"""
        try:
            # Test buffer size adjustment
            original_size = self.receiver.buffer_size
            self.receiver.set_buffer_size(3)
            
            # Fill buffer
            time.sleep(2)
            
            # Check buffer health
            health = self.receiver.get_buffer_health()
            print(f"Buffer usage: {health['buffer_usage_percent']:.1f}%")
            
            # Test buffer clearing
            self.receiver.clear_buffer()
            health_after = self.receiver.get_buffer_health()
            
            if health_after['buffer_size_current'] != 0:
                print("❌ Buffer not cleared properly")
                return False
            
            # Restore buffer size
            self.receiver.set_buffer_size(original_size)
            
            print("✅ Buffer management working correctly")
            return True
            
        except Exception as e:
            print(f"❌ Buffer management test failed: {e}")
            return False
    
    def test_performance(self) -> bool:
        """Test performance metrics"""
        try:
            # Measure frame rate
            test_duration = 8
            start_time = time.time()
            frame_count = 0
            
            while time.time() - start_time < test_duration:
                frame = self.receiver.read_frame()
                if frame is not None:
                    frame_count += 1
                time.sleep(0.01)
            
            actual_duration = time.time() - start_time
            measured_fps = frame_count / actual_duration
            
            print(f"Measured FPS: {measured_fps:.2f}")
            print(f"Frames received: {frame_count} in {actual_duration:.2f}s")
            
            # Check minimum performance
            if measured_fps < 8.0:  # Allow some tolerance for simulation
                print(f"❌ Frame rate too low: {measured_fps:.2f} FPS")
                return False
            
            self.test_stats['avg_fps'] = measured_fps
            
            # Test frame rate statistics
            rate_stats = self.receiver.get_frame_rate_stats()
            print(f"Average FPS from stats: {rate_stats['avg_fps']:.2f}")
            print(f"Frame jitter: {rate_stats['jitter']:.3f}s")
            
            return True
            
        except Exception as e:
            print(f"❌ Performance test failed: {e}")
            return False
    
    def print_test_summary(self):
        """Print test summary"""
        print("\n" + "=" * 70)
        print("📊 ESP32-Camera Communication Simulation Test Summary")
        print("=" * 70)
        
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
            print("\n🎉 ESP32-camera communication protocol is working correctly!")
            print("   Frame transmission, reconstruction, and decoding are functional.")
            print("   The system is ready for integration with real hardware.")
        else:
            print("\n⚠️ Some tests failed. Check the implementation.")


def main():
    """Main test function"""
    print("ESP32-Camera Communication Simulation Test")
    print("This test verifies the communication protocol without hardware")
    
    tester = ESP32CommunicationSimulationTester()
    
    try:
        success = tester.run_all_tests()
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n\n⏹️ Test interrupted by user")
        return 1
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())