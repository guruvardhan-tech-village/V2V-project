#include "esp_camera.h"

// Camera model selection - AI Thinker ESP32-CAM
#define CAMERA_MODEL_AI_THINKER

// AI Thinker ESP32-CAM pin definitions
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27

#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// Configuration
#define SERIAL_BAUD_RATE 921600
#define DEFAULT_FPS 10
#define CHUNK_SIZE 1024

// Global variables
bool cameraInitialized = false;
unsigned long lastFrameTime = 0;
unsigned long frameInterval = 1000 / DEFAULT_FPS;
uint16_t sequenceNumber = 0;

void setup() {
  Serial.begin(SERIAL_BAUD_RATE);
  delay(2000);
  
  // Clear any existing serial buffer
  while (Serial.available()) {
    Serial.read();
  }
  
  Serial.println("=== ESP32-Camera Simple Starting ===");
  Serial.println("Hardware: AI Thinker ESP32-CAM");
  Serial.println("Firmware: Simple Camera v1.0");
  Serial.flush();
  
  // Check PSRAM
  Serial.print("PSRAM found: ");
  Serial.println(psramFound() ? "YES" : "NO");
  
  if (psramFound()) {
    Serial.print("PSRAM size: ");
    Serial.println(ESP.getPsramSize());
  }
  Serial.flush();
  
  // Initialize camera with error handling
  Serial.println("Initializing camera...");
  Serial.flush();
  
  if (initializeCamera()) {
    cameraInitialized = true;
    Serial.println("Camera initialized successfully!");
  } else {
    cameraInitialized = false;
    Serial.println("Camera initialization failed - running without camera");
  }
  Serial.flush();
  
  Serial.println("=== ESP32-Camera Ready ===");
  Serial.println("Commands: capture, status, start, stop, hello, test");
  Serial.flush();
}

void loop() {
  // Process serial commands
  processSerialCommands();
  
  // Capture frames if camera is working
  if (cameraInitialized && shouldCaptureFrame()) {
    captureAndSendFrame();
  }
  
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
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  
  // Conservative settings to avoid crashes
  if (psramFound()) {
    config.frame_size = FRAMESIZE_VGA;  // 640x480
    config.jpeg_quality = 12;
    config.fb_count = 2;
    Serial.println("Using PSRAM - VGA resolution");
  } else {
    config.frame_size = FRAMESIZE_QVGA; // 320x240
    config.jpeg_quality = 15;
    config.fb_count = 1;
    Serial.println("No PSRAM - QVGA resolution");
  }
  
  // Initialize camera with error handling
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x\n", err);
    return false;
  }
  
  // Get sensor and apply basic settings
  sensor_t* s = esp_camera_sensor_get();
  if (s != NULL) {
    // Basic sensor settings
    s->set_brightness(s, 0);     // -2 to 2
    s->set_contrast(s, 0);       // -2 to 2
    s->set_saturation(s, 0);     // -2 to 2
    s->set_whitebal(s, 1);       // enable auto white balance
    s->set_awb_gain(s, 1);       // enable AWB gain
    s->set_exposure_ctrl(s, 1);  // enable AEC
    s->set_gain_ctrl(s, 1);      // enable AGC
    s->set_lenc(s, 1);           // enable lens correction
    s->set_hmirror(s, 0);        // 0 = disable, 1 = enable
    s->set_vflip(s, 0);          // 0 = disable, 1 = enable
    
    Serial.println("Camera sensor configured");
  }
  
  return true;
}

bool shouldCaptureFrame() {
  unsigned long currentTime = millis();
  return (currentTime - lastFrameTime >= frameInterval);
}

void captureAndSendFrame() {
  lastFrameTime = millis();
  sequenceNumber++;
  
  // Capture frame
  camera_fb_t* fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("ERROR: Camera capture failed");
    return;
  }
  
  // Validate JPEG
  if (fb->len < 10 || fb->buf[0] != 0xFF || fb->buf[1] != 0xD8) {
    Serial.println("ERROR: Invalid JPEG frame");
    esp_camera_fb_return(fb);
    return;
  }
  
  // Send frame header
  Serial.printf("FRAME_START|size:%d|seq:%d|timestamp:%lu\n", 
                fb->len, sequenceNumber, millis());
  
  // Send frame data in chunks
  sendFrameDataInChunks(fb->buf, fb->len);
  
  // Send frame footer
  Serial.printf("FRAME_END|seq:%d|size:%d\n", sequenceNumber, fb->len);
  
  // Release frame buffer
  esp_camera_fb_return(fb);
  
  Serial.printf("Frame %d sent (%d bytes)\n", sequenceNumber, fb->len);
}

void sendFrameDataInChunks(const uint8_t* data, size_t length) {
  size_t totalSent = 0;
  uint16_t chunkNumber = 0;
  
  while (totalSent < length) {
    size_t remainingBytes = length - totalSent;
    size_t bytesToSend = (remainingBytes > CHUNK_SIZE) ? CHUNK_SIZE : remainingBytes;
    
    // Send chunk data
    Serial.write(data + totalSent, bytesToSend);
    totalSent += bytesToSend;
    chunkNumber++;
    
    // Small delay to prevent buffer overflow
    delay(1);
    
    // Yield every 10 chunks to prevent watchdog timeout
    if (chunkNumber % 10 == 0) {
      yield();
    }
  }
}

void processSerialCommands() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    
    // Clear any remaining buffer
    while (Serial.available()) {
      Serial.read();
    }
    
    if (command == "capture") {
      if (cameraInitialized) {
        Serial.println("Capturing single frame...");
        Serial.flush();
        captureAndSendFrame();
      } else {
        Serial.println("ERROR: Camera not initialized");
        Serial.flush();
      }
    }
    else if (command == "status") {
      sendStatusMessage();
    }
    else if (command == "start") {
      Serial.println("ACK: Continuous capture mode active");
      Serial.flush();
    }
    else if (command == "stop") {
      Serial.println("ACK: Stop command received");
      Serial.flush();
    }
    else if (command == "hello") {
      Serial.println("Hello from ESP32-Camera!");
      Serial.flush();
    }
    else if (command == "test") {
      runDiagnostics();
    }
    else if (command.length() > 0) {
      Serial.printf("Unknown command: %s\n", command.c_str());
      Serial.println("Available commands: capture, status, start, stop, hello, test");
      Serial.flush();
    }
  }
}

void sendStatusMessage() {
  Serial.println("=== ESP32-Camera Status ===");
  Serial.printf("Camera initialized: %s\n", cameraInitialized ? "YES" : "NO");
  Serial.printf("Sequence number: %d\n", sequenceNumber);
  Serial.printf("Free heap: %d bytes\n", ESP.getFreeHeap());
  Serial.printf("PSRAM found: %s\n", psramFound() ? "YES" : "NO");
  if (psramFound()) {
    Serial.printf("PSRAM size: %d bytes\n", ESP.getPsramSize());
  }
  Serial.printf("CPU frequency: %d MHz\n", ESP.getCpuFreqMHz());
  Serial.printf("Temperature: %.1f°C\n", temperatureRead());
  Serial.printf("Uptime: %lu seconds\n", millis() / 1000);
  Serial.println("=== End Status ===");
  Serial.flush();
}

void runDiagnostics() {
  Serial.println("=== Running Diagnostics ===");
  
  // Memory test
  Serial.print("Memory test: ");
  void* ptr = malloc(1024);
  if (ptr) {
    free(ptr);
    Serial.println("PASS");
  } else {
    Serial.println("FAIL");
  }
  
  // Camera test
  Serial.print("Camera test: ");
  if (cameraInitialized) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (fb) {
      Serial.printf("PASS (captured %d bytes)\n", fb->len);
      esp_camera_fb_return(fb);
    } else {
      Serial.println("FAIL (capture failed)");
    }
  } else {
    Serial.println("SKIP (not initialized)");
  }
  
  // Temperature test
  Serial.printf("Temperature: %.1f°C\n", temperatureRead());
  
  Serial.println("=== Diagnostics Complete ===");
}