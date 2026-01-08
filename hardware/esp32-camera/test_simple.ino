// Simple ESP32-CAM test firmware
// This tests basic functionality without camera

void setup() {
  Serial.begin(921600);
  delay(2000);
  
  Serial.println("ESP32-CAM Simple Test Starting...");
  Serial.println("Hardware: AI Thinker ESP32-CAM");
  Serial.println("Firmware: Simple Test v1.0");
  
  // Test basic functionality
  Serial.print("Free heap: ");
  Serial.println(ESP.getFreeHeap());
  
  Serial.print("Chip model: ");
  Serial.println(ESP.getChipModel());
  
  Serial.print("CPU frequency: ");
  Serial.println(ESP.getCpuFreqMHz());
  
  Serial.println("ESP32-CAM Simple Test Ready!");
  Serial.println("Type 'hello' to test communication");
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
    }
  }
  
  delay(100);
}