#include "esp_camera.h"
#include <WiFi.h>
#include <ArduinoJson.h>

// Camera model selection - AI Thinker ESP32-CAM
#define CAMERA_MODEL_AI_THINKER
#include "camera_pins.h"

// Protocol message structure (must be defined before config.h)
struct ProtocolMessage {
  String type;
  String fields;
  
  ProtocolMessage(const String& msgType) : type(msgType) {}
  
  void addField(const String& name, const String& value) {
    if (fields.length() > 0) {
      fields += "|";  // Use literal instead of PROTOCOL_DELIMITER for now
    }
    fields += name + ":" + value;
  }
  
  void addField(const String& name, int value) {
    addField(name, String(value));
  }
  
  void addField(const String& name, uint32_t value) {
    addField(name, String(value));
  }
  
  void addField(const String& name, float value, int decimals = 1) {
    addField(name, String(value, decimals));
  }
  
  String toString() const {
    return type + "|" + fields + "\n";  // Use literals for now
  }
};

// Now include config.h after ProtocolMessage is defined
#include "config.h"

// Frame header structure
struct FrameHeader {
  uint32_t size;
  uint16_t sequence;
  uint32_t timestamp;
  
  FrameHeader(uint32_t frameSize, uint16_t seq) 
    : size(frameSize), sequence(seq), timestamp(millis()) {}
  
  String toProtocolMessage() const {
    ProtocolMessage msg(FRAME_START_MARKER);
    msg.addField(FIELD_SIZE, size);
    msg.addField(FIELD_SEQUENCE, sequence);
    msg.addField(FIELD_TIMESTAMP, timestamp);
    return msg.toString();
  }
};

// Frame footer structure
struct FrameFooter {
  uint16_t sequence;
  uint32_t checksum;
  
  FrameFooter(uint16_t seq, uint32_t crc) 
    : sequence(seq), checksum(crc) {}
  
  String toProtocolMessage() const {
    ProtocolMessage msg(FRAME_END_MARKER);
    msg.addField(FIELD_SEQUENCE, sequence);
    msg.addField(FIELD_CHECKSUM, String(checksum, HEX));
    return msg.toString();
  }
};

// Camera configuration structure
struct CameraConfig {
  framesize_t resolution = DEFAULT_RESOLUTION;
  int fps = DEFAULT_FPS;
  int quality = DEFAULT_JPEG_QUALITY;
  bool initialized = false;
};

// Transmission state tracking
struct TransmissionState {
  bool waitingForAck = false;
  uint16_t lastSequence = 0;
  unsigned long ackTimeout = 0;
  uint8_t retryCount = 0;
  
  void reset() {
    waitingForAck = false;
    lastSequence = 0;
    ackTimeout = 0;
    retryCount = 0;
  }
  
  bool isTimedOut() {
    return waitingForAck && (millis() > ackTimeout);
  }
};

// Camera health metrics structure
struct CameraHealthMetrics {
  uint32_t framesCaptured = 0;
  uint32_t framesFailed = 0;
  uint32_t transmissionErrors = 0;
  uint32_t lastFrameSize = 0;
  uint32_t totalFrameSize = 0;
  uint32_t avgFrameSize = 0;
  unsigned long lastFrameTimestamp = 0;
  
  void updateFrameCapture(uint32_t frameSize) {
    framesCaptured++;
    lastFrameSize = frameSize;
    totalFrameSize += frameSize;
    avgFrameSize = (framesCaptured > 0) ? (totalFrameSize / framesCaptured) : 0;
    lastFrameTimestamp = millis();
  }
  
  void updateFrameFailure() {
    framesFailed++;
  }
  
  void updateTransmissionError() {
    transmissionErrors++;
  }
};

CameraConfig cameraConfig;
TransmissionState transmissionState;
CameraHealthMetrics cameraHealth;
unsigned long lastFrameTime = 0;
unsigned long frameInterval = 1000 / DEFAULT_FPS;
uint16_t sequenceNumber = 0;  // Changed to uint16_t for proper sequence numbering
unsigned long lastStatusTime = 0;

// FPS calculation variables
#define FPS_SAMPLE_COUNT 10
unsigned long frameTimes[FPS_SAMPLE_COUNT];
uint8_t frameTimeIndex = 0;
bool frameTimesInitialized = false;

void setup() {
  Serial.begin(SERIAL_BAUD_RATE);
  Serial.setTimeout(SERIAL_TIMEOUT_MS);
  
  // Wait for serial connection
  delay(2000);
  
  Serial.println("ESP32-Camera initializing...");
  
  // Initialize camera
  if (initializeCamera()) {
    cameraConfig.initialized = true;
    Serial.println("Camera initialized successfully");
    sendStatusMessage();
  } else {
    Serial.println("ERROR: Camera initialization failed");
    cameraConfig.initialized = false;
  }
  
  Serial.println("ESP32-Camera ready for commands");
}

void loop() {
  // Process incoming serial commands
  processSerialCommands();
  
  // Capture and send frames if camera is initialized
  if (cameraConfig.initialized && shouldCaptureFrame()) {
    captureAndSendFrame();
  }
  
  // Send periodic status updates
  if (millis() - lastStatusTime > STATUS_INTERVAL_MS) {
    sendStatusMessage();
    lastStatusTime = millis();
  }
  
  // Small delay to prevent overwhelming the serial port
  delay(10);
}

bool initializeCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = XCLK_FREQ_HZ;
  config.pixel_format = PIXEL_FORMAT;
  
  // Frame buffer settings
  if (psramFound()) {
    config.frame_size = DEFAULT_RESOLUTION;
    config.jpeg_quality = DEFAULT_JPEG_QUALITY;
    config.fb_count = FB_COUNT_WITH_PSRAM;
  } else {
    config.frame_size = FRAMESIZE_SVGA;
    config.jpeg_quality = 12;
    config.fb_count = FB_COUNT_WITHOUT_PSRAM;
  }
  
  // Initialize camera
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x\n", err);
    return false;
  }
  
  // Apply initial configuration
  sensor_t* s = esp_camera_sensor_get();
  if (s != NULL) {
    s->set_framesize(s, cameraConfig.resolution);
    s->set_quality(s, cameraConfig.quality);
    // Additional sensor settings for better performance
    s->set_brightness(s, 0);     // -2 to 2
    s->set_contrast(s, 0);       // -2 to 2
    s->set_saturation(s, 0);     // -2 to 2
    s->set_special_effect(s, 0); // 0 to 6 (0 - No Effect)
    s->set_whitebal(s, 1);       // 0 = disable , 1 = enable
    s->set_awb_gain(s, 1);       // 0 = disable , 1 = enable
    s->set_wb_mode(s, 0);        // 0 to 4 - if awb_gain enabled (0 - Auto, 1 - Sunny, 2 - Cloudy, 3 - Office, 4 - Home)
    s->set_exposure_ctrl(s, 1);  // 0 = disable , 1 = enable
    s->set_aec2(s, 0);           // 0 = disable , 1 = enable
    s->set_ae_level(s, 0);       // -2 to 2
    s->set_aec_value(s, 300);    // 0 to 1200
    s->set_gain_ctrl(s, 1);      // 0 = disable , 1 = enable
    s->set_agc_gain(s, 0);       // 0 to 30
    s->set_gainceiling(s, (gainceiling_t)0);  // 0 to 6
    s->set_bpc(s, 0);            // 0 = disable , 1 = enable
    s->set_wpc(s, 1);            // 0 = disable , 1 = enable
    s->set_raw_gma(s, 1);        // 0 = disable , 1 = enable
    s->set_lenc(s, 1);           // 0 = disable , 1 = enable
    s->set_hmirror(s, 0);        // 0 = disable , 1 = enable
    s->set_vflip(s, 0);          // 0 = disable , 1 = enable
    s->set_dcw(s, 1);            // 0 = disable , 1 = enable
    s->set_colorbar(s, 0);       // 0 = disable , 1 = enable
  }
  
  return true;
}

bool shouldCaptureFrame() {
  unsigned long currentTime = millis();
  return (currentTime - lastFrameTime >= frameInterval);
}

void captureAndSendFrame() {
  // Don't send new frames if waiting for acknowledgment
  if (transmissionState.waitingForAck) {
    return;
  }
  
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("ERROR: Camera capture failed");
    cameraHealth.updateFrameFailure();
    return;
  }
  
  // Validate JPEG frame integrity
  if (!validateJPEGFrame(fb->buf, fb->len)) {
    Serial.println("ERROR: Invalid JPEG frame captured");
    cameraHealth.updateFrameFailure();
    esp_camera_fb_return(fb);
    return;
  }
  
  // Update timing and sequence
  lastFrameTime = millis();
  updateFrameTimings();
  sequenceNumber++;
  
  // Handle sequence number overflow (wrap around at 65535)
  if (sequenceNumber == 0) {
    sequenceNumber = 1; // Skip 0 to avoid confusion
  }
  
  // Update health metrics
  cameraHealth.updateFrameCapture(fb->len);
  
  // Calculate CRC32 checksum for frame data
  uint32_t checksum = calculateCRC32(fb->buf, fb->len);
  
  // Create and send frame header
  FrameHeader header(fb->len, sequenceNumber);
  Serial.print(header.toProtocolMessage());
  
  // Send frame data in chunks
  sendFrameDataInChunks(fb->buf, fb->len);
  
  // Create and send frame footer
  FrameFooter footer(sequenceNumber, checksum);
  Serial.print(footer.toProtocolMessage());
  
  // Set up transmission state for acknowledgment tracking
  transmissionState.waitingForAck = true;
  transmissionState.lastSequence = sequenceNumber;
  transmissionState.ackTimeout = millis() + ACK_TIMEOUT_MS;
  transmissionState.retryCount = 0;
  
  // Release frame buffer
  esp_camera_fb_return(fb);
}

void processSerialCommands() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    if (command.startsWith(CONFIG_MARKER)) {
      processConfigCommand(command);
    } else if (command.startsWith(ACK_MARKER)) {
      processAckCommand(command);
    } else if (command.startsWith(NACK_MARKER)) {
      processNackCommand(command);
    } else if (command.startsWith(RETRY_MARKER)) {
      processRetryCommand(command);
    } else if (command == "CAPTURE|mode:continuous") {
      // Already in continuous mode by default
      Serial.println("ACK: Continuous capture mode active");
    } else if (command == "STOP") {
      // Stop continuous capture (not implemented in this basic version)
      Serial.println("ACK: Stop command received");
    } else {
      Serial.printf("ERROR: Unknown command: %s\n", command.c_str());
    }
  }
  
  // Check for transmission timeouts
  if (transmissionState.isTimedOut()) {
    handleTransmissionTimeout();
  }
}

void processAckCommand(const String& command) {
  // Parse ACK|seq:123
  String seqStr = extractParameter(command, "seq:");
  uint16_t ackSequence = seqStr.toInt();
  
  if (transmissionState.waitingForAck && ackSequence == transmissionState.lastSequence) {
    // Frame acknowledged successfully
    transmissionState.reset();
  }
}

void processNackCommand(const String& command) {
  // Parse NACK|seq:123|reason:checksum_error
  String seqStr = extractParameter(command, "seq:");
  uint16_t nackSequence = seqStr.toInt();
  
  if (transmissionState.waitingForAck && nackSequence == transmissionState.lastSequence) {
    // Update transmission error count
    cameraHealth.updateTransmissionError();
    
    // Frame rejected, retry if possible
    if (transmissionState.retryCount < MAX_TRANSMISSION_RETRIES) {
      transmissionState.retryCount++;
      retransmitLastFrame();
    } else {
      // Max retries exceeded, reset and continue
      Serial.printf("ERROR: Max retries exceeded for sequence %d\n", nackSequence);
      transmissionState.reset();
    }
  }
}

void processRetryCommand(const String& command) {
  // Parse RETRY|seq:123
  String seqStr = extractParameter(command, "seq:");
  uint16_t retrySequence = seqStr.toInt();
  
  if (retrySequence == transmissionState.lastSequence) {
    retransmitLastFrame();
  }
}

void handleTransmissionTimeout() {
  // Update transmission error count
  cameraHealth.updateTransmissionError();
  
  if (transmissionState.retryCount < MAX_TRANSMISSION_RETRIES) {
    transmissionState.retryCount++;
    Serial.printf("TIMEOUT: Retrying frame %d (attempt %d)\n", 
                  transmissionState.lastSequence, transmissionState.retryCount);
    retransmitLastFrame();
  } else {
    Serial.printf("ERROR: Transmission timeout for sequence %d\n", transmissionState.lastSequence);
    transmissionState.reset();
  }
}

void retransmitLastFrame() {
  // For now, just reset the transmission state and let the next frame be sent
  // In a more sophisticated implementation, we would cache the last frame
  transmissionState.waitingForAck = false;
  transmissionState.ackTimeout = millis() + ACK_TIMEOUT_MS;
  transmissionState.waitingForAck = true;
}

void processConfigCommand(const String& command) {
  // Parse CONFIG|resolution:VGA|fps:15|quality:50
  bool configChanged = false;
  String errorMessage = "";
  
  // Validate camera is initialized before applying configuration
  if (!cameraConfig.initialized) {
    Serial.println("ERROR: Camera not initialized, cannot apply configuration");
    return;
  }
  
  if (command.indexOf("resolution:") != -1) {
    String resStr = extractParameter(command, "resolution:");
    framesize_t newRes = parseResolution(resStr);
    
    // Validate resolution parameter
    if (isValidResolution(resStr)) {
      if (newRes != cameraConfig.resolution) {
        cameraConfig.resolution = newRes;
        configChanged = true;
      }
    } else {
      errorMessage += "Invalid resolution: " + resStr + " ";
    }
  }
  
  if (command.indexOf("fps:") != -1) {
    String fpsStr = extractParameter(command, "fps:");
    int newFps = fpsStr.toInt();
    
    // Validate FPS range
    if (newFps >= MIN_FPS && newFps <= MAX_FPS) {
      if (newFps != cameraConfig.fps) {
        cameraConfig.fps = newFps;
        frameInterval = 1000 / newFps;
        configChanged = true;
      }
    } else {
      errorMessage += "Invalid FPS: " + String(newFps) + " (range: " + String(MIN_FPS) + "-" + String(MAX_FPS) + ") ";
    }
  }
  
  if (command.indexOf("quality:") != -1) {
    String qualityStr = extractParameter(command, "quality:");
    int newQuality = qualityStr.toInt();
    
    // Validate JPEG quality range
    if (newQuality >= MIN_JPEG_QUALITY && newQuality <= MAX_JPEG_QUALITY) {
      if (newQuality != cameraConfig.quality) {
        cameraConfig.quality = newQuality;
        configChanged = true;
      }
    } else {
      errorMessage += "Invalid quality: " + String(newQuality) + " (range: " + String(MIN_JPEG_QUALITY) + "-" + String(MAX_JPEG_QUALITY) + ") ";
    }
  }
  
  // Report errors if any validation failed
  if (errorMessage.length() > 0) {
    Serial.println("ERROR: " + errorMessage);
    return;
  }
  
  // Apply configuration changes if any were made
  if (configChanged) {
    if (applyCameraConfiguration()) {
      // Send confirmation with current configuration
      sendConfigurationConfirmation();
    } else {
      Serial.println("ERROR: Failed to apply camera configuration");
    }
  } else {
    Serial.println("ACK: No configuration changes needed");
    // Still send current configuration for confirmation
    sendConfigurationConfirmation();
  }
}

String extractParameter(const String& command, const String& param) {
  int startIndex = command.indexOf(param);
  if (startIndex == -1) return "";
  
  startIndex += param.length();
  int endIndex = command.indexOf('|', startIndex);
  if (endIndex == -1) endIndex = command.length();
  
  return command.substring(startIndex, endIndex);
}

framesize_t parseResolution(const String& resStr) {
  if (resStr == "QVGA") return FRAMESIZE_QVGA;
  else if (resStr == "VGA") return FRAMESIZE_VGA;
  else if (resStr == "SVGA") return FRAMESIZE_SVGA;
  else if (resStr == "XGA") return FRAMESIZE_XGA;
  else return FRAMESIZE_VGA; // Default
}

bool isValidResolution(const String& resStr) {
  return (resStr == "QVGA" || resStr == "VGA" || resStr == "SVGA" || resStr == "XGA");
}

String resolutionToString(framesize_t resolution) {
  switch (resolution) {
    case FRAMESIZE_QVGA: return "QVGA";
    case FRAMESIZE_VGA: return "VGA";
    case FRAMESIZE_SVGA: return "SVGA";
    case FRAMESIZE_XGA: return "XGA";
    default: return "VGA";
  }
}

void sendConfigurationConfirmation() {
  ProtocolMessage configMsg("CONFIG_ACK");
  configMsg.addField("resolution", resolutionToString(cameraConfig.resolution));
  configMsg.addField("fps", cameraConfig.fps);
  configMsg.addField("quality", cameraConfig.quality);
  configMsg.addField("initialized", cameraConfig.initialized ? "true" : "false");
  
  Serial.print(configMsg.toString());
}

bool applyCameraConfiguration() {
  sensor_t* s = esp_camera_sensor_get();
  if (s == NULL) {
    Serial.println("ERROR: Cannot get camera sensor for configuration");
    return false;
  }
  
  // Apply resolution setting
  if (s->set_framesize(s, cameraConfig.resolution) != 0) {
    Serial.println("ERROR: Failed to set camera resolution");
    return false;
  }
  
  // Apply JPEG quality setting
  if (s->set_quality(s, cameraConfig.quality) != 0) {
    Serial.println("ERROR: Failed to set JPEG quality");
    return false;
  }
  
  // Update frame interval based on FPS
  frameInterval = 1000 / cameraConfig.fps;
  
  Serial.println("Camera configuration applied successfully");
  return true;
}

bool validateJPEGFrame(const uint8_t* data, size_t length) {
  // Check minimum JPEG size
  if (length < 10) {
    return false;
  }
  
  // Check JPEG header (SOI marker: 0xFF 0xD8)
  if (data[0] != 0xFF || data[1] != 0xD8) {
    return false;
  }
  
  // Check JPEG footer (EOI marker: 0xFF 0xD9)
  if (length >= 2 && (data[length-2] != 0xFF || data[length-1] != 0xD9)) {
    return false;
  }
  
  return true;
}

void sendFrameDataInChunks(const uint8_t* data, size_t length) {
  const size_t chunkSize = CHUNK_SIZE;
  size_t totalSent = 0;
  uint16_t chunkNumber = 0;
  
  while (totalSent < length) {
    size_t remainingBytes = length - totalSent;
    size_t bytesToSend = (remainingBytes > chunkSize) ? chunkSize : remainingBytes;
    
    // Send chunk data
    Serial.write(data + totalSent, bytesToSend);
    totalSent += bytesToSend;
    chunkNumber++;
    
    // Small delay to prevent buffer overflow and allow receiver to process
    delay(1);
    
    // Yield to prevent watchdog timeout on large frames
    if (chunkNumber % 10 == 0) {
      yield();
    }
  }
}

void sendStatusMessage() {
  // Calculate current FPS based on actual frame timing
  float actualFps = calculateActualFPS();
  
  // Get system information
  uint32_t freeHeap = ESP.getFreeHeap();
  uint32_t totalHeap = ESP.getHeapSize();
  uint32_t usedHeap = totalHeap - freeHeap;
  float heapUsagePercent = (float)usedHeap / totalHeap * 100.0;
  
  // Get temperature (internal sensor)
  float temperature = temperatureRead();
  
  // Get camera health metrics
  CameraHealthMetrics health = getCameraHealthMetrics();
  
  // Create comprehensive status message
  ProtocolMessage statusMsg(STATUS_MARKER);
  
  // Performance metrics
  statusMsg.addField(FIELD_FPS, actualFps, 1);
  statusMsg.addField("target_fps", cameraConfig.fps);
  statusMsg.addField("frame_interval", frameInterval);
  statusMsg.addField(FIELD_SEQUENCE, sequenceNumber);
  
  // System health metrics
  statusMsg.addField(FIELD_TEMP, temperature, 1);
  statusMsg.addField(FIELD_FREE_HEAP, freeHeap);
  statusMsg.addField("heap_usage_percent", heapUsagePercent, 1);
  statusMsg.addField("uptime_ms", millis());
  
  // Camera configuration status
  statusMsg.addField("resolution", resolutionToString(cameraConfig.resolution));
  statusMsg.addField("quality", cameraConfig.quality);
  statusMsg.addField("camera_initialized", cameraConfig.initialized ? "true" : "false");
  
  // Camera health metrics
  statusMsg.addField("frames_captured", health.framesCaptured);
  statusMsg.addField("frames_failed", health.framesFailed);
  statusMsg.addField("transmission_errors", health.transmissionErrors);
  statusMsg.addField("last_frame_size", health.lastFrameSize);
  statusMsg.addField("avg_frame_size", health.avgFrameSize);
  
  // Transmission state
  statusMsg.addField("waiting_for_ack", transmissionState.waitingForAck ? "true" : "false");
  statusMsg.addField("retry_count", transmissionState.retryCount);
  
  Serial.print(statusMsg.toString());
}

uint32_t calculateCRC32(const uint8_t* data, size_t length) {
  uint32_t crc = 0xFFFFFFFF;
  
  for (size_t i = 0; i < length; i++) {
    crc ^= data[i];
    for (int j = 0; j < 8; j++) {
      if (crc & 1) {
        crc = (crc >> 1) ^ 0xEDB88320;
      } else {
        crc >>= 1;
      }
    }
  }
  
  return ~crc;
}

float calculateActualFPS() {
  if (!frameTimesInitialized) {
    return 0.0;
  }
  
  // Calculate average time between frames
  unsigned long totalTime = 0;
  uint8_t validSamples = 0;
  
  for (int i = 0; i < FPS_SAMPLE_COUNT - 1; i++) {
    if (frameTimes[i] > 0 && frameTimes[i + 1] > 0) {
      totalTime += (frameTimes[i + 1] - frameTimes[i]);
      validSamples++;
    }
  }
  
  if (validSamples == 0) {
    return 0.0;
  }
  
  float avgInterval = (float)totalTime / validSamples;
  return (avgInterval > 0) ? (1000.0 / avgInterval) : 0.0;
}

void updateFrameTimings() {
  frameTimes[frameTimeIndex] = millis();
  frameTimeIndex = (frameTimeIndex + 1) % FPS_SAMPLE_COUNT;
  
  // Mark as initialized once we've filled the array at least once
  if (frameTimeIndex == 0) {
    frameTimesInitialized = true;
  }
}

CameraHealthMetrics getCameraHealthMetrics() {
  return cameraHealth;
}