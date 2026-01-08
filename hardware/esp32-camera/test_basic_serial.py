#!/usr/bin/env python3
"""
Basic serial test to check ESP32 communication at different baud rates
"""

import serial
import time
import sys

def test_baud_rates(port="COM3"):
    """Test different baud rates to find working communication"""
    baud_rates = [115200, 921600, 460800, 230400, 57600, 9600]
    
    for baud in baud_rates:
        print(f"\nTesting {port} at {baud} baud...")
        try:
            ser = serial.Serial(port, baud, timeout=2)
            time.sleep(2)  # Wait for connection
            
            # Send a simple command
            ser.write(b"STATUS\n")
            time.sleep(1)
            
            # Check for any response
            response_count = 0
            start_time = time.time()
            
            while time.time() - start_time < 5:  # 5 second test
                if ser.in_waiting > 0:
                    data = ser.read(ser.in_waiting)
                    try:
                        text = data.decode('utf-8', errors='ignore')
                        if text.strip():
                            print(f"  Received: {repr(text)}")
                            response_count += 1
                    except:
                        print(f"  Received binary: {data}")
                        response_count += 1
                
                time.sleep(0.1)
            
            ser.close()
            
            if response_count > 0:
                print(f"✅ Communication working at {baud} baud ({response_count} responses)")
                return baud
            else:
                print(f"❌ No response at {baud} baud")
                
        except Exception as e:
            print(f"❌ Error at {baud} baud: {e}")
    
    return None

if __name__ == "__main__":
    port = sys.argv[1] if len(sys.argv) > 1 else "COM3"
    working_baud = test_baud_rates(port)
    
    if working_baud:
        print(f"\n✅ ESP32 is responding at {working_baud} baud")
    else:
        print(f"\n❌ No communication established with ESP32 on {port}")
        print("Check:")
        print("1. ESP32 is connected and powered")
        print("2. Correct COM port")
        print("3. ESP32 firmware is loaded and running")
        print("4. No other applications using the port")