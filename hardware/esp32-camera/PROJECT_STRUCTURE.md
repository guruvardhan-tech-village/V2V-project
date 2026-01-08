# ESP32-Camera Project Structure

This directory contains the complete ESP32-camera firmware for the V2V communication system integration.

## File Structure

```
hardware/esp32-camera/
├── esp32-camera.ino          # Main Arduino sketch file
├── camera_pins.h             # Pin definitions for AI Thinker ESP32-CAM
├── config.h                  # Configuration constants and settings
├── README.md                 # Comprehensive documentation
├── PROJECT_STRUCTURE.md      # This file - project organization
├── build.bat                 # Windows build script (Arduino CLI)
├── build.sh                  # Linux/Mac build script (Arduino CLI)
└── test_serial.py            # Python test script for serial communication
```

## Key Components

### Core Files
- **esp32-camera.ino**: Main firmware implementing camera capture, serial communication, and command processing
- **camera_pins.h**: Hardware-specific pin definitions for the AI Thinker ESP32-CAM board
- **config.h**: Centralized configuration constants for easy customization

### Documentation
- **README.md**: Complete setup, usage, and troubleshooting guide
- **PROJECT_STRUCTURE.md**: This file explaining project organization

### Build Tools
- **build.bat**: Windows batch script for Arduino CLI compilation
- **build.sh**: Unix shell script for Arduino CLI compilation (Linux/Mac)

### Testing
- **test_serial.py**: Python script to test serial communication with the ESP32-camera

## Development Workflow

1. **Setup**: Install Arduino IDE or Arduino CLI with ESP32 board support
2. **Configuration**: Modify config.h if needed for custom settings
3. **Build**: Use build scripts or Arduino IDE to compile
4. **Upload**: Flash firmware to ESP32-CAM module
5. **Test**: Use test_serial.py to verify communication

## Hardware Requirements

- AI Thinker ESP32-CAM development board
- USB to Serial adapter (FTDI, CP2102, etc.)
- Jumper wires for programming mode
- MicroUSB cable for power/programming

## Integration Points

This firmware is designed to integrate with:
- Python ESP32CameraReceiver class (laptop side)
- C2C launcher GUI application
- YOLO accident detection system
- Existing V2V communication infrastructure

## Configuration Options

All major settings are defined in config.h:
- Serial baud rate (default: 921600)
- Camera resolution (default: VGA)
- Frame rate (default: 15 FPS)
- JPEG quality (default: 50)
- Buffer sizes and timeouts

## Next Steps

After completing this firmware foundation:
1. Implement frame transmission protocol (Task 2)
2. Add camera configuration commands (Task 3)
3. Create Python receiver class (Task 4)
4. Integrate with C2C launcher (Task 6)
5. Connect to YOLO processing (Task 7)