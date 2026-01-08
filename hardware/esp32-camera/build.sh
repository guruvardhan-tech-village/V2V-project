#!/bin/bash
# Build script for ESP32-Camera firmware using Arduino CLI
# Make sure Arduino CLI is installed and ESP32 board package is available

echo "Building ESP32-Camera firmware..."

# Set the board FQBN (Fully Qualified Board Name) for AI Thinker ESP32-CAM
BOARD_FQBN="esp32:esp32:esp32cam"

# Check if Arduino CLI is available
if ! command -v arduino-cli &> /dev/null; then
    echo "Error: Arduino CLI not found. Please install Arduino CLI first."
    echo "Download from: https://arduino.github.io/arduino-cli/"
    exit 1
fi

# Compile the sketch
echo "Compiling ESP32-Camera firmware..."
arduino-cli compile --fqbn "$BOARD_FQBN" esp32-camera.ino

if [ $? -eq 0 ]; then
    echo ""
    echo "Build successful!"
    echo ""
    echo "To upload to ESP32-CAM:"
    echo "1. Connect ESP32-CAM to USB-Serial adapter"
    echo "2. Put ESP32-CAM in programming mode (connect GPIO0 to GND during power-on)"
    echo "3. Run: arduino-cli upload -p /dev/ttyUSB0 --fqbn $BOARD_FQBN esp32-camera.ino"
    echo "   (Replace /dev/ttyUSB0 with your actual serial port)"
    echo "4. Remove GPIO0-GND connection and reset ESP32-CAM"
else
    echo ""
    echo "Build failed! Check error messages above."
    exit 1
fi