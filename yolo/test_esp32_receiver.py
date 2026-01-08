#!/usr/bin/env python3
"""
Basic test for ESP32CameraReceiver functionality
This test verifies the core functionality without requiring actual hardware
"""

import time
import numpy as np
from esp32_camera_receiver import ESP32CameraReceiver, ESP32CameraCapture, CameraConfig, FrameMetadata

def test_camera_config():
    """Test CameraConfig class"""
    print("Testing CameraConfig...")
    
    # Test default config
    config = CameraConfig()
    assert config.resolution == "VGA"
    assert config.fps == 15
    assert config.quality == 50
    
    # Test command generation
    command = config.to_command()
    expected = "CONFIG|resolution:VGA|fps:15|quality:50"
    assert command == expected, f"Expected {expected}, got {command}"
    
    # Test custom config
    config = CameraConfig(resolution="QVGA", fps=30, quality=40)
    command = config.to_command()
    expected = "CONFIG|resolution:QVGA|fps:30|quality:40"
    assert command == expected, f"Expected {expected}, got {command}"
    
    print("✅ CameraConfig tests passed")

def test_frame_metadata():
    """Test FrameMetadata class"""
    print("Testing FrameMetadata...")
    
    # Test parsing frame header
    header = "FRAME_START|size:12345|seq:001"
    metadata = FrameMetadata.from_header(header)
    
    assert metadata.sequence == 1
    assert metadata.size == 12345
    assert metadata.checksum == ''
    
    print("✅ FrameMetadata tests passed")

def test_receiver_initialization():
    """Test ESP32CameraReceiver initialization"""
    print("Testing ESP32CameraReceiver initialization...")
    
    receiver = ESP32CameraReceiver(port="COM8", baud=921600, buffer_size=5)
    
    assert receiver.port == "COM8"
    assert receiver.baud == 921600
    assert receiver.buffer_size == 5
    assert not receiver.connected
    assert receiver.frame_buffer.maxsize == 5
    
    # Test stats
    stats = receiver.get_stats()
    assert stats['connected'] == False
    assert stats['frames_received'] == 0
    assert stats['port'] == "COM8"
    
    print("✅ ESP32CameraReceiver initialization tests passed")

def test_capture_wrapper():
    """Test ESP32CameraCapture wrapper"""
    print("Testing ESP32CameraCapture wrapper...")
    
    capture = ESP32CameraCapture(port="COM8")
    
    assert not capture.isOpened()
    
    # Test property setting (should not crash)
    capture.set(1, 30)  # FPS
    capture.set(3, 640)  # Width
    
    # Test property getting
    fps = capture.get(1)
    assert isinstance(fps, float)
    
    print("✅ ESP32CameraCapture tests passed")

def test_buffer_management():
    """Test buffer management functionality"""
    print("Testing buffer management...")
    
    receiver = ESP32CameraReceiver(buffer_size=3)
    
    # Test buffer size change
    receiver.set_buffer_size(5)
    assert receiver.buffer_size == 5
    
    # Test invalid buffer size
    receiver.set_buffer_size(0)  # Should not change
    assert receiver.buffer_size == 5
    
    # Test buffer health
    health = receiver.get_buffer_health()
    assert 'buffer_usage_percent' in health
    assert 'recent_fps' in health
    
    # Test frame rate stats
    rate_stats = receiver.get_frame_rate_stats()
    assert 'current_fps' in rate_stats
    assert 'avg_fps' in rate_stats
    
    print("✅ Buffer management tests passed")

def test_validation_methods():
    """Test frame validation methods"""
    print("Testing validation methods...")
    
    receiver = ESP32CameraReceiver()
    
    # Test JPEG header validation with valid data
    receiver.current_frame_data = bytearray([0xFF, 0xD8, 0x00, 0x00, 0xFF, 0xD9])
    assert receiver._validate_jpeg_header() == True
    
    # Test JPEG header validation with invalid data
    receiver.current_frame_data = bytearray([0x00, 0x00, 0x00, 0x00])
    assert receiver._validate_jpeg_header() == False
    
    # Test dimension validation
    assert receiver._validate_frame_dimensions(640, 480) == True
    assert receiver._validate_frame_dimensions(5, 5) == False  # Too small
    assert receiver._validate_frame_dimensions(3000, 3000) == False  # Too large
    
    # Test frame content validation
    frame = np.ones((100, 100, 3), dtype=np.uint8) * 128
    assert receiver._validate_frame_content(frame) == True
    
    # Test empty frame
    empty_frame = np.array([])
    assert receiver._validate_frame_content(empty_frame) == False
    
    print("✅ Validation methods tests passed")

def run_all_tests():
    """Run all tests"""
    print("Running ESP32CameraReceiver tests...\n")
    
    try:
        test_camera_config()
        test_frame_metadata()
        test_receiver_initialization()
        test_capture_wrapper()
        test_buffer_management()
        test_validation_methods()
        
        print("\n🎉 All tests passed successfully!")
        return True
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)