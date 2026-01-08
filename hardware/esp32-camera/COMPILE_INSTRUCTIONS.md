# ESP32-Camera Firmware Compilation Instructions

## Prerequisites

1. **Arduino IDE** installed with ESP32 board support
2. **ESP32 Board Package** installed:
   - File → Preferences → Additional Board Manager URLs
   - Add: `https://dl.espressif.com/dl/package_esp32_index.json`
   - Tools → Board → Boards Manager → Search "ESP32" → Install

## Required Libraries

Install these libraries via Arduino IDE Library Manager:
- **ArduinoJson** (by Benoit Blanchon)
- **ESP32** board package (includes esp_camera.h)

## Compilation Steps

1. **Open the firmware:**
   ```
   File → Open → hardware/esp32-camera/esp32-camera.ino
   ```

2. **Select board:**
   ```
   Tools → Board → ESP32 Arduino → AI Thinker ESP32-CAM
   ```

3. **Select port:**
   ```
   Tools → Port → COM3 (or your ESP32-CAM port)
   ```

4. **Configure settings:**
   ```
   Tools → Partition Scheme → Huge APP (3MB No OTA/1MB SPIFFS)
   Tools → CPU Frequency → 240MHz (WiFi/BT)
   Tools → Flash Frequency → 80MHz
   Tools → Flash Mode → QIO
   Tools → Flash Size → 4MB (32Mb)
   ```

5. **Upload:**
   ```
   Click the Upload button (→) or press Ctrl+U
   ```

## Troubleshooting

### If compilation fails:
1. **Check ESP32 board package version** (use latest stable)
2. **Verify all libraries are installed**
3. **Try different partition scheme** if memory issues occur

### If upload fails:
1. **Put ESP32-CAM in programming mode:**
   - Connect GPIO0 to GND
   - Press reset button
   - Start upload
   - Remove GPIO0-GND connection after upload starts

2. **Check serial connection:**
   - Ensure USB-to-Serial adapter is working
   - Try different baud rate in Tools → Upload Speed

### Common Issues:
- **"Camera model not selected"** → Verify `#define CAMERA_MODEL_AI_THINKER` is uncommented
- **"esp_camera.h not found"** → Install ESP32 board package
- **"ArduinoJson.h not found"** → Install ArduinoJson library
- **Upload timeout** → Put ESP32-CAM in programming mode

## Testing After Upload

1. **Open Serial Monitor** (Tools → Serial Monitor)
2. **Set baud rate to 921600**
3. **Reset ESP32-CAM**
4. **You should see:** "ESP32-Camera initializing..." and "ESP32-Camera ready for commands"

## Next Steps

After successful upload:
```bash
cd yolo
python test_esp32_communication.py --port COM3
```

Should now show successful connection and communication!