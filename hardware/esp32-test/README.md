# ESP32-CAM Hardware Troubleshooting

## Current Issue
Your ESP32-CAM is in a boot loop, sending `mpt 3)` repeatedly. This indicates the device is crashing during boot, likely due to:

1. **Power supply issues** - ESP32-CAM needs stable 5V power
2. **Camera module connection** - Loose camera ribbon cable
3. **PSRAM issues** - Memory problems
4. **Firmware complexity** - Main firmware too complex for current state

## Step-by-Step Troubleshooting

### Step 1: Upload Simple Test Firmware

1. **Open Arduino IDE**
2. **Open the simple test file**: `hardware/esp32-test/esp32-test.ino`
3. **Select board**: ESP32 AI Thinker CAM
4. **Select port**: COM3 (your ESP32-CAM)
5. **Upload the firmware**

### Step 2: Test Basic Communication

Run the Python test script:
```bash
cd hardware/esp32-test
python test_simple_communication.py
```

**Expected output if working:**
```
=== ESP32-CAM Simple Test Starting ===
Hardware: AI Thinker ESP32-CAM
Firmware: Simple Test v1.0
Free heap: 298516
Chip model: ESP32-D0WDQ6
CPU frequency: 240
PSRAM found: YES
=== ESP32-CAM Simple Test Ready ===
```

### Step 3: Hardware Checks

If simple test fails:

1. **Check power supply**:
   - Use 5V power adapter (not USB power)
   - Red LED should be solid on
   - Current should be 200-300mA

2. **Check camera connection**:
   - Disconnect camera ribbon cable
   - Try simple test without camera
   - If works, camera module is faulty

3. **Check programming mode**:
   - Connect GPIO0 to GND during upload
   - Release after upload completes
   - Press reset button

### Step 4: If Simple Test Works

If the simple test firmware works correctly, the issue is with the main camera firmware complexity. We'll need to:

1. **Simplify the main firmware**
2. **Add gradual camera initialization**
3. **Improve error handling**

## Common ESP32-CAM Issues

### Boot Loop Symptoms
- Continuous `mpt 3)` or similar garbage
- Device resets every few seconds
- No proper serial output

### Causes and Solutions

| Issue | Symptoms | Solution |
|-------|----------|----------|
| Power supply | Brown-out resets | Use 5V 2A adapter |
| Camera fault | Boot loop with camera | Disconnect camera, test |
| PSRAM issue | Memory errors | Check PSRAM in code |
| Firmware bug | Crashes on init | Use simple test first |

## Next Steps

1. **Upload simple test firmware**
2. **Run communication test**
3. **If successful**: Gradually add camera features
4. **If failed**: Check hardware connections

## Files in This Directory

- `esp32-test.ino` - Simple test firmware (no camera)
- `test_simple_communication.py` - Python test script
- `README.md` - This troubleshooting guide

## Hardware Specifications

- **Board**: AI Thinker ESP32-CAM
- **Camera**: OV2640 2MP
- **Memory**: 4MB Flash + 8MB PSRAM
- **Power**: 5V via USB or external
- **Programming**: Via USB-to-Serial adapter