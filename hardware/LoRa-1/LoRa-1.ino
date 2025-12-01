#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include <DHT.h>
#include <TinyGPSPlus.h>
#include <HardwareSerial.h>

// --- Pin Definitions ---
#define LORA_SS     5
#define LORA_RST    14
#define LORA_DIO0   2
#define DHTPIN      4
#define DHTTYPE     DHT22
#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT 64

// --- Component Objects ---
Adafruit_SH1106G display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
DHT dht(DHTPIN, DHTTYPE);
HardwareSerial GPS_Serial(2);  // RX2/TX2 on ESP32
TinyGPSPlus gps;

// --- State Variables ---
unsigned long lastSendTime   = 0;
const int     sendInterval   = 3000;   // Send every 3 seconds
const int     listenDuration = 3000;   // LoRa listen window (ms)

// Default GPS for indoor testing (Kottigepalya example)
const double DEFAULT_LAT = 12.987861; //12.987861, 77.513966
const double DEFAULT_LNG = 77.513966;

// these are what we *actually* send
double g_lastLat  = DEFAULT_LAT;
double g_lastLng  = DEFAULT_LNG;
bool   g_gpsValid = false;

// This ID will appear in LoRa messages
const char* CAR_ID = "C1";   // (optional: you can later sync this with regNumber from laptop)

// --------- OLED helper ----------
void showStatusScreen(const char* statusLine)
{
  display.clearDisplay();
  display.setCursor(0, 0);
  display.setTextSize(1);
  display.println("---CAR 1---");
  display.println(statusLine);
  display.println("--------------------");

  display.print("GPS: ");
  display.println(g_gpsValid ? "FIX" : "DEFAULT");

  display.print("Lat: ");
  display.println(g_lastLat, 6);
  display.print("Lng: ");
  display.println(g_lastLng, 6);

  display.print("Temp: ");
  display.print(dht.readTemperature());
  display.println(" C");

  display.display();
}

void setup() {
  Serial.begin(115200);        // USB serial to laptop
  Wire.begin(21, 22);

  if (!display.begin(0x3C, true)) {
    Serial.println(F("Display not found"));
    for (;;);
  }

  display.setTextColor(SH110X_WHITE);
  dht.begin();
  GPS_Serial.begin(9600, SERIAL_8N1, 16, 17);  // RX=16, TX=17 for GPS module

  // LoRa setup
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
  if (!LoRa.begin(433E6)) {
    Serial.println("LoRa init failed!");
    while (1);
  }

  LoRa.setSyncWord(0xF3);
  LoRa.setSpreadingFactor(12);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);

  Serial.println("🚗 Car 1 Ready!");
  showStatusScreen("STATUS: Booting...");
}

void loop() {
  // --- GPS update ---
  while (GPS_Serial.available() > 0) {
    gps.encode(GPS_Serial.read());
  }

  unsigned long now = millis();

  // ----------------------------------------------------------------
  // 1) Periodically send sensor data over LoRa AND Serial to laptop
  // ----------------------------------------------------------------
  if (now - lastSendTime > (unsigned long)sendInterval) {
    lastSendTime = now;

    float h = dht.readHumidity();
    float t = dht.readTemperature();

    double lat, lng;

    if (gps.location.isValid()) {
      lat = gps.location.lat();
      lng = gps.location.lng();
      g_gpsValid = true;
    } else {
      lat = DEFAULT_LAT;
      lng = DEFAULT_LNG;
      g_gpsValid = false;
    }

    // update globals for display
    g_lastLat = lat;
    g_lastLng = lng;

    String loraPayload;
    String serialPayload;

    // LoRa payload (for V2V / other cars)
    loraPayload  = String(CAR_ID) + "|lat:" + String(lat, 6);
    loraPayload += ",lng:" + String(lng, 6);
    loraPayload += ",temp:" + String(t);
    loraPayload += ",hum:" + String(h);

    // Serial payload (for laptop Python script)
    serialPayload  = "SENSOR|lat:" + String(lat, 6);
    serialPayload += ",lng:" + String(lng, 6);
    serialPayload += ",temp:" + String(t);
    serialPayload += ",hum:" + String(h);

    // --- SEND DATA OVER LoRa ---
    LoRa.beginPacket();
    LoRa.print(loraPayload);
    LoRa.endPacket();
    Serial.print("📤 LoRa Sent: ");
    Serial.println(loraPayload);

    // --- SEND DATA OVER Serial to laptop ---
    Serial.println(serialPayload);  // Python expects "SENSOR|..."

    // --- PREPARE TO RECEIVE LoRa REPLY ---
    LoRa.idle();
    delay(300);
    while (LoRa.parsePacket()) {
      while (LoRa.available()) LoRa.read();
    }
    LoRa.receive();

    Serial.println("🔎 Listening for LoRa reply...");
    unsigned long listenStartTime = millis();
    bool replyReceived = false;

    while (millis() - listenStartTime < (unsigned long)listenDuration) {
      int packetSize = LoRa.parsePacket();
      if (packetSize > 0) {
        String receivedData = "";
        while (LoRa.available()) {
          receivedData += (char)LoRa.read();
        }

        Serial.print("✅ Reply Received (LoRa): ");
        Serial.println(receivedData);

        // Forward to laptop in a machine-readable way
        Serial.print("LORA_RX|");
        Serial.println(receivedData);

        display.clearDisplay();
        display.setCursor(0, 0);
        display.setTextSize(1);
        display.println("REPLY RECEIVED:");
        display.println(receivedData);
        display.display();

        replyReceived = true;
        delay(1500);
        break;
      }
    }

    if (!replyReceived) {
      Serial.println("❌ No LoRa reply received within window.");
    }

    // After sending + listening, return to status screen
    showStatusScreen("STATUS: Sending...");
  }

  // ----------------------------------------------------------------
  // 2) Check for commands from laptop (YOLO alerts)
  // ----------------------------------------------------------------
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd.length() > 0) {
      Serial.print("💻 CMD from laptop: ");
      Serial.println(cmd);
    }

    if (cmd.startsWith("CMD|ACCIDENT")) {
      display.clearDisplay();
      display.setCursor(0, 0);
      display.setTextSize(1);
      display.println("---CAR 1---");
      display.println("ALERT: ACCIDENT!");
      display.println("--------------------");
      display.print("Lat:");
      display.println(g_lastLat, 6);
      display.print("Lng:");
      display.println(g_lastLng, 6);
      display.display();

      LoRa.beginPacket();
      LoRa.print("ALERT|ACCIDENT|from:");
      LoRa.print(CAR_ID);
      LoRa.endPacket();
      Serial.println("📡 LoRa Accident alert broadcast");
    }
    else if (cmd.startsWith("CMD|TRAFFIC")) {
      String level = "UNKNOWN";
      int idx = cmd.indexOf("level:");
      if (idx >= 0) {
        level = cmd.substring(idx + 6);
        level.trim();
      }

      display.clearDisplay();
      display.setCursor(0, 0);
      display.setTextSize(1);
      display.println("---CAR 1---");
      display.println("TRAFFIC ALERT!");
      display.print("LEVEL: ");
      display.println(level);
      display.print("Lat:");
      display.println(g_lastLat, 6);
      display.print("Lng:");
      display.println(g_lastLng, 6);
      display.display();

      LoRa.beginPacket();
      LoRa.print("ALERT|TRAFFIC|");
      LoRa.print(level);
      LoRa.print("|from:");
      LoRa.print(CAR_ID);
      LoRa.endPacket();
      Serial.println("📡 LoRa Traffic alert broadcast");
    }
  }
}
