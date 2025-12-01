#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include <DHT.h>
#include <TinyGPSPlus.h>
#include <HardwareSerial.h>

// ---------- Pin Definitions ----------
#define LORA_SS 5
#define LORA_RST 14
#define LORA_DIO0 2
#define DHTPIN 4
#define DHTTYPE DHT22
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

// ---------- Objects ----------
Adafruit_SH1106G display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
DHT dht(DHTPIN, DHTTYPE);
HardwareSerial GPS_Serial(2);
TinyGPSPlus gps;

// ---------- UI + Display ----------
unsigned long lastMsgTime = 0;
const unsigned long messageDuration = 6000;
String lastAlert = "";
bool hasAlert = false;

// ---------- Helper Functions ----------
void showStatusScreen() {
  display.clearDisplay();
  display.setCursor(0, 0);
  display.setTextSize(1);
  display.println("🚙 CAR 2 Listening...");
  display.println("----------------------");
  display.print("GPS: ");
  display.println(gps.location.isValid() ? "FIX" : "SEARCHING");
  display.print("Temp: ");
  display.print(dht.readTemperature());
  display.println(" C");

  display.display();
}

void showAlertScreen() {
  display.clearDisplay();
  display.setCursor(0, 0);
  display.setTextSize(1);
  display.println("⚠  V2V ALERT RECEIVED");
  display.println("----------------------");
  display.println(lastAlert);
  display.display();
}

String parseForKey(String data, String key) {
  int idx = data.indexOf(key + ":");
  if (idx < 0) return "";
  int start = idx + key.length() + 1;
  int end = data.indexOf("|", start);
  if (end < 0) end = data.length();
  return data.substring(start, end);
}

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);

  if (!display.begin(0x3C, true)) {
    Serial.println(F("Display init failed"));
    while (1);
  }
  display.setTextColor(SH110X_WHITE);

  dht.begin();
  GPS_Serial.begin(9600, SERIAL_8N1, 16, 17);

  // LoRa Setup
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
  if (!LoRa.begin(433E6)) {
    Serial.println("LoRa init failed!");
    while (1);
  }
  LoRa.setSyncWord(0xF3);
  LoRa.setSpreadingFactor(12);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);
  LoRa.receive();

  Serial.println("🚙 CAR 2 READY - LISTENING");
}

void loop() {
  while (GPS_Serial.available()) gps.encode(GPS_Serial.read());

  int packetSize = LoRa.parsePacket();
  if (packetSize) {
    String incoming = "";
    while (LoRa.available()) incoming += (char)LoRa.read();

    Serial.println("📩 Received: " + incoming);

    // ---------- Process Commands from Car 1 ----------
    if (incoming.startsWith("CMD|")) {

      bool isAcc = incoming.indexOf("ACCIDENT") >= 0;
      bool isTraffic = incoming.indexOf("TRAFFIC") >= 0;

      String loc = parseForKey(incoming, "loc");
      if (loc == "") loc = "Unknown";

      if (isAcc) {
        lastAlert = "🚨 ACCIDENT\nNear: " + loc;
      } else if (isTraffic) {
        String level = parseForKey(incoming, "level");
        lastAlert = "🚦 TRAFFIC " + level + "\nAt: " + loc;
      } else {
        lastAlert = incoming;
      }

      hasAlert = true;
      lastMsgTime = millis();

      Serial.println("📟 Parsed Alert: " + lastAlert);
    }

    // ---------- Prepare Reply to Car 1 ----------
    float h = dht.readHumidity();
    float t = dht.readTemperature();
    String reply = "";

    if (gps.location.isValid()) {
      reply = "C2|lat:" + String(gps.location.lat(), 6) +
              ",lng:" + String(gps.location.lng(), 6) +
              ",temp:" + String(t) + ",hum:" + String(h);
    } else {
      reply = "C2|lat:0,lng:0,temp:" + String(t) + ",hum:" + String(h);
    }

    delay(250);
    LoRa.beginPacket();
    LoRa.print(reply);
    LoRa.endPacket();
    LoRa.receive();

    Serial.println("📤 Reply Sent: " + reply);
  }

  // ---------- UI Display Logic ----------
  if (hasAlert && millis() - lastMsgTime < messageDuration) {
    showAlertScreen();
  } else {
    hasAlert = false;
    showStatusScreen();
  }
}
