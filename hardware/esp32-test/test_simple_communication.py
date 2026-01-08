#!/usr/bin/env python3
"""
Simple ESP32-CAM Communication Test
Tests basic serial communication with the simple test firmware
"""

import serial
import time
import sys

def test_esp32_communication(port='COM3', baud=921600):
    """Test basic communication with ESP32-CAM simple firmware"""
    
    print(f"Testing ESP32-CAM communication on {port} at {baud} baud...")
    
    try:
        # Open serial connection
        ser = serial.Serial(port, baud, timeout=2)
        time.sleep(2)  # Wait for ESP32 to boot
        
        print("Serial connection established")
        
        # Clear any existing data
        ser.flushInput()
        ser.flushOutput()
        
        # Read initial boot messages
        print("\n=== Boot Messages ===")
        start_time = time.time()
        while time.time() - start_time < 3:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    print(f"ESP32: {line}")
        
        # Test commands
        test_commands = ['hello', 'status', 'test']
        
        print("\n=== Command Tests ===")
        for cmd in test_commands:
            print(f"\nSending: {cmd}")
            ser.write(f"{cmd}\n".encode())
            time.sleep(0.5)
            
            # Read response
            response_lines = []
            start_time = time.time()
            while time.time() - start_time < 2:
                if ser.in_waiting > 0:
                    line = ser.readline().decode('utf-8', errors='ignore').strip()
                    if line:
                        response_lines.append(line)
                        print(f"ESP32: {line}")
                else:
                    time.sleep(0.1)
            
            if not response_lines:
                print("⚠️ No response received")
        
        # Monitor heartbeat
        print("\n=== Monitoring Heartbeat (15 seconds) ===")
        start_time = time.time()
        heartbeat_count = 0
        
        while time.time() - start_time < 15:
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8', errors='ignore').strip()
                if line:
                    print(f"ESP32: {line}")
                    if "Heartbeat" in line:
                        heartbeat_count += 1
            time.sleep(0.1)
        
        print(f"\nHeartbeats received: {heartbeat_count}")
        
        if heartbeat_count > 0:
            print("✅ ESP32-CAM is working correctly!")
            return True
        else:
            print("⚠️ No heartbeat detected - check firmware upload")
            return False
            
    except serial.SerialException as e:
        print(f"❌ Serial connection error: {e}")
        return False
    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()
            print("Serial connection closed")

def scan_available_ports():
    """Scan for available COM ports"""
    import serial.tools.list_ports
    
    print("Available COM ports:")
    ports = serial.tools.list_ports.comports()
    
    for port in ports:
        print(f"  {port.device}: {port.description}")
        if "CP210" in port.description or "FTDI" in port.description:
            print(f"    ^ This might be your ESP32!")
    
    return [port.device for port in ports]

if __name__ == "__main__":
    print("ESP32-CAM Simple Communication Test")
    print("=" * 40)
    
    # Scan ports first
    available_ports = scan_available_ports()
    
    if not available_ports:
        print("❌ No COM ports found!")
        sys.exit(1)
    
    # Use COM3 by default, or first available port
    test_port = 'COM3' if 'COM3' in available_ports else available_ports[0]
    
    print(f"\nTesting with port: {test_port}")
    print("Make sure you have uploaded the simple test firmware first!")
    print("File: hardware/esp32-test/esp32-test.ino")
    
    input("Press Enter to start test...")
    
    success = test_esp32_communication(test_port)
    
    if success:
        print("\n🎉 Test completed successfully!")
        print("Your ESP32-CAM hardware is working correctly.")
        print("You can now upload the main camera firmware.")
    else:
        print("\n❌ Test failed!")
        print("Troubleshooting steps:")
        print("1. Check USB cable connection")
        print("2. Verify ESP32-CAM is powered (red LED should be on)")
        print("3. Make sure you uploaded the simple test firmware")
        print("4. Try different COM port if available")
        print("5. Check if ESP32-CAM is in programming mode (GPIO0 to GND)")