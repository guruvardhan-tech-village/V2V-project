// Simple ESP32-CAM test firmware
// This tests basic functionality without camera initialization
// Use this to verify ESP32-CAM hardware is working before uploading main firmware

void setup() {
  Serial.begin(921600);
  delay(2000);
  
  Serial.println("=== ESP32-CAM Simple Test Starting ===");
  Serial.println("Hardware: AI Thinker ESP32-CAM");
  Serial.println("Firmware: Simple Test v1.0");
  Serial.println("Purpose: Basic hardware verification");
  
  // Test basic functionality
  Serial.print("Free heap: ");
  Serial.println(ESP.getFreeHeap());
  
  Serial.print("Chip model: ");
  Serial.println(ESP.getChipModel());
  
  Serial.print("CPU frequency: ");
  Serial.println(ESP.getCpuFreqMHz());
  
  Serial.print("PSRAM found: ");
  Serial.println(psramFound() ? "YES" : "NO");
  
  if (psramFound()) {
    Serial.print("PSRAM size: ");
    Serial.println(ESP.getPsramSize());
  }
  
  Serial.println("=== ESP32-CAM Simple Test Ready ===");
  Serial.println("Commands: 'hello', 'status', 'test'");
  Serial.println("If you see this message, ESP32-CAM hardware is working!");
}

void loop() {
  // Echo any received data
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    
    Serial.print("Received: ");
    Serial.println(input);
    
    if (input == "hello") {
      Serial.println("Hello from ESP32-CAM!");
    } else if (input == "status") {
      Serial.println("Status: Running OK");
      Serial.print("Uptime: ");
      Serial.print(millis() / 1000);
      Serial.println(" seconds");
      Serial.print("Free heap: ");
      Serial.println(ESP.getFreeHeap());
    } else if (input == "test") {
      Serial.println("Running basic tests...");
      
      // Test memory
      Serial.print("Heap test: ");
      void* ptr = malloc(1024);
      if (ptr) {
        free(ptr);
        Serial.println("PASS");
      } else {
        Serial.println("FAIL");
      }
      
      // Test temperature sensor
      Serial.print("Temperature: ");
      Serial.print(temperatureRead());
      Serial.println("°C");
      
      Serial.println("Basic tests completed");
    }
  }
  
  // Heartbeat every 10 seconds
  static unsigned long lastHeartbeat = 0;
  if (millis() - lastHeartbeat > 10000) {
    Serial.println("Heartbeat: ESP32-CAM alive");
    lastHeartbeat = millis();
  }
  
  delay(100);
}