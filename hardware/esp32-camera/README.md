# ESP32-Camera Firmware

This firmware enables the ESP32-CAM module to capture JPEG images and stream them over USB serial connection to a laptop for processing by the V2V communication system.

## Hardware Requirements

- AI Thinker ESP32-CAM development board
- OV2640 camera module (included with ESP32-CAM)
- USB to Serial adapter (FTDI or CP2102)
- MicroSD card (optional, not used in this implementation)

## Pin Connections

The AI Thinker ESP32-CAM uses the following pin configuration:
- Camera pins are predefined in `camera_pins.h`
- USB Serial connection via GPIO1 (TX) and GPIO3 (RX)
- Power: 5V via USB or external power supply

## Features

### Camera Capabilities
- JPEG image capture with configurable resolution (QVGA, VGA, SVGA, XGA)
- Adjustable frame rate (5-30 FPS)
- Configurable JPEG quality (10-63)
- Automatic exposure and white balance
- Real-time frame streaming over serial

### Communication Protocol
- Serial communication at 921600 baud rate
- Frame-based protocol with headers and footers
- CRC32 checksum for data integrity
- Sequence numbering for frame ordering
- Command processing for configuration changes

### Supported Commands
```
CONFIG|resolution:VGA|fps:15|quality:50  - Configure camera settings
CAPTURE|mode:continuous                   - Start continuous capture (default mode)
STOP                                      - Stop capture (acknowledgment only)
```

### Status Reporting
The firmware sends periodic status messages every 5 seconds:
```
STATUS|fps:14.2|temp:45.6|free_heap:234567|seq:123
```

## Installation

1. Install Arduino IDE with ESP32 board support
2. Install required libraries:
   - ESP32 Camera library (built-in with ESP32 core)
   - ArduinoJson library (for future enhancements)

3. Select board: "AI Thinker ESP32-CAM"
4. Upload the firmware to ESP32-CAM module

## Configuration

### Default Settings
- Resolution: VGA (640x480)
- Frame Rate: 15 FPS
- JPEG Quality: 50
- Serial Baud Rate: 921600

### Runtime Configuration
Camera settings can be changed via serial commands without restarting the device.

## Frame Protocol

### Frame Structure
```
FRAME_START|size:<bytes>|seq:<sequence_number>
<JPEG_DATA_BINARY>
FRAME_END|seq:<sequence_number>|checksum:<CRC32>
```

### Example Frame Transmission
```
FRAME_START|size:12345|seq:001
[Binary JPEG data - 12345 bytes]
FRAME_END|seq:001|checksum:ABCD1234
```

## Performance

- Typical frame rates: 10-20 FPS depending on resolution and lighting
- Memory usage: ~200KB for frame buffers
- Serial throughput: Up to 115KB/s at 921600 baud
- Frame sizes: 5-30KB typical for VGA JPEG

## Troubleshooting

### Common Issues
1. **Camera initialization failed**: Check power supply and connections
2. **Low frame rate**: Reduce resolution or increase JPEG compression
3. **Serial communication errors**: Verify baud rate and cable connections
4. **Memory allocation errors**: Restart device or reduce frame buffer size

### Debug Output
Enable serial monitor at 921600 baud to see initialization and error messages.

## Integration

This firmware is designed to work with the Python ESP32CameraReceiver class on the laptop side. The receiver handles:
- Serial connection management
- Frame reconstruction from chunks
- JPEG decoding to OpenCV format
- Integration with YOLO processing pipeline

## Future Enhancements

- WiFi streaming capability
- Motion detection
- Multiple camera support
- Advanced image processing filters
- Power management optimizations