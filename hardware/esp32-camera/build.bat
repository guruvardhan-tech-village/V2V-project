@echo off
REM Build script for ESP32-Camera firmware using Arduino CLI
REM Make sure Arduino CLI is installed and ESP32 board package is available

echo Building ESP32-Camera firmware...

REM Set the board FQBN (Fully Qualified Board Name) for AI Thinker ESP32-CAM
set BOARD_FQBN=esp32:esp32:esp32cam

REM Check if Arduino CLI is available
arduino-cli version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Arduino CLI not found. Please install Arduino CLI first.
    echo Download from: https://arduino.github.io/arduino-cli/
    pause
    exit /b 1
)

REM Compile the sketch
echo Compiling ESP32-Camera firmware...
arduino-cli compile --fqbn %BOARD_FQBN% esp32-camera.ino

if %errorlevel% equ 0 (
    echo.
    echo Build successful!
    echo.
    echo To upload to ESP32-CAM:
    echo 1. Connect ESP32-CAM to USB-Serial adapter
    echo 2. Put ESP32-CAM in programming mode (connect GPIO0 to GND during power-on)
    echo 3. Run: arduino-cli upload -p COM8 --fqbn %BOARD_FQBN% esp32-camera.ino
    echo 4. Remove GPIO0-GND connection and reset ESP32-CAM
) else (
    echo.
    echo Build failed! Check error messages above.
)

pause