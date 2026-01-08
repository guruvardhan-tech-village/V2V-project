#!/usr/bin/env python3
"""
Simple test script to verify ESP32-camera serial communication
This script can be used to test the firmware before full integration
"""

import serial
import time
import sys

def test_esp32_camera_communication(port="COM8", baud=921600):
    """Test basic communication with ESP32-camera"""
    try:
        # Open serial connection
        print(f"Connecting to {port} at {baud} baud...")
        ser = serial.Serial(port, baud, timeout=1)
        time.sleep(2)  # Wait for ESP32 to initialize
        
        print("Connected! Listening for messages...")
        
        # Listen for status messages and frames
        frame_count = 0
        start_time = time.time()
        
        while True:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                
                if line.startswith("STATUS"):
                    print(f"Status: {line}")
                elif line.startswith("FRAME_START"):
                    frame_count += 1
                    print(f"Frame {frame_count} started: {line}")
                elif line.startswith("FRAME_END"):
                    print(f"Frame {frame_count} completed: {line}")
                elif line.startswith("ERROR"):
                    print(f"Error: {line}")
                elif line.startswith("ESP32-Camera"):
                    print(f"Init: {line}")
                elif line and not line.startswith("ACK"):
                    print(f"Message: {line}")
            
            # Test configuration command every 30 seconds
            if time.time() - start_time > 30:
                print("Sending test configuration command...")
                ser.write(b"CONFIG|resolution:VGA|fps:10|quality:40\n")
                start_time = time.time()
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except serial.SerialException as e:
        print(f"Serial error: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("Serial connection closed")

if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else "COM8"
    test_esp32_camera_communication(port)