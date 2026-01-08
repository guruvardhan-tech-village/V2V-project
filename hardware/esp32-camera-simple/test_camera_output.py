#!/usr/bin/env python3
"""
Quick test to verify ESP32-Camera is sending data
Run this AFTER closing Arduino IDE Serial Monitor
"""

import serial
import time
import sys

def test_camera_output(port='COM3', baud=921600):
    """Test if ESP32-Camera is sending frame data"""
    
    print(f"Testing ESP32-Camera output on {port}...")
    print("Make sure Arduino IDE Serial Monitor is CLOSED!")
    
    try:
        # Open serial connection
        ser = serial.Serial(port, baud, timeout=2)
        time.sleep(1)
        
        print("✅ Serial connection established")
        print("📸 Monitoring for camera frames...")
        print("=" * 50)
        
        frame_count = 0
        start_time = time.time()
        
        while time.time() - start_time < 30:  # Monitor for 30 seconds
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                
                if line:
                    print(f"ESP32: {line}")
                    
                    # Count frames
                    if "FRAME_START" in line:
                        frame_count += 1
                        print(f"🎯 Frame #{frame_count} detected!")
                    
                    elif "Frame" in line and "sent" in line:
                        print(f"✅ Frame transmission completed")
                        
                    elif "Camera initialized successfully" in line:
                        print("🎉 Camera is working!")
                        
                    elif "ERROR" in line:
                        print(f"⚠️ Error detected: {line}")
            
            time.sleep(0.1)
        
        print("=" * 50)
        print(f"📊 Test Results:")
        print(f"   Frames detected: {frame_count}")
        print(f"   Test duration: 30 seconds")
        
        if frame_count > 0:
            print("🎉 SUCCESS: ESP32-Camera is working and sending frames!")
            return True
        else:
            print("❌ No frames detected - check camera initialization")
            return False
            
    except serial.SerialException as e:
        print(f"❌ Serial error: {e}")
        print("💡 Make sure Arduino IDE Serial Monitor is closed!")
        return False
    except KeyboardInterrupt:
        print("\n⏹️ Test stopped by user")
        return False
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("🔌 Serial connection closed")

if __name__ == "__main__":
    print("ESP32-Camera Output Test")
    print("=" * 30)
    
    print("\n📋 Instructions:")
    print("1. Make sure ESP32-Camera firmware is uploaded")
    print("2. CLOSE Arduino IDE Serial Monitor")
    print("3. ESP32-Camera should be sending frames automatically")
    
    input("\nPress Enter when ready...")
    
    success = test_camera_output()
    
    if success:
        print("\n🎉 Your ESP32-Camera is working perfectly!")
        print("📸 It's capturing and sending images")
        print("🔄 You can now test with the full Python receiver")
    else:
        print("\n🔧 Troubleshooting:")
        print("- Check if Arduino IDE Serial Monitor is closed")
        print("- Verify ESP32-Camera is powered and connected")
        print("- Try sending 'status' command in Serial Monitor first")