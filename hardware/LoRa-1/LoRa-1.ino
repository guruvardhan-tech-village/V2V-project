#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include <DHT.h>
#include <TinyGPSPlus.h>
#include <HardwareSerial.h>

// --- Pin Definitions ---
#define LORA_SS 5
#define LORA_RST 14
#define LORA_DIO0 2
#define DHTPIN 4
#define DHTTYPE DHT22
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

// --- Component Objects ---
Adafruit_SH1106G display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
DHT dht(DHTPIN, DHTTYPE);
HardwareSerial GPS_Serial(2);
TinyGPSPlus gps;

// --- State Variables ---
unsigned long lastSendTime = 0;
const int sendInterval = 3000;       // Send every 3 seconds
const int listenDuration = 3000;     // Listen for reply for 3 seconds

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  if (!display.begin(0x3C, true)) {
    Serial.println(F("Display not found"));
    for (;;);
  }

  display.setTextColor(SH110X_WHITE);
  dht.begin();
  GPS_Serial.begin(9600, SERIAL_8N1, 16, 17);

  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
  if (!LoRa.begin(433E6)) {
    Serial.println("LoRa init failed!");
    while (1);
  }

  // LoRa Parameters
  LoRa.setSyncWord(0xF3);
  LoRa.setSpreadingFactor(12);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);

  Serial.println("🚗 Car 1 Ready!");
}

void loop() {
  while (GPS_Serial.available() > 0) {
    gps.encode(GPS_Serial.read());
  }

  if (millis() - lastSendTime > sendInterval) {
    lastSendTime = millis();

    float h = dht.readHumidity();
    float t = dht.readTemperature();
    String dataToSend = "";

    if (gps.location.isValid()) {
      dataToSend = "C1|lat:" + String(gps.location.lat(), 6) +
                   ",lng:" + String(gps.location.lng(), 6) +
                   ",temp:" + String(t) + ",hum:" + String(h);
    } else {
      dataToSend = "C1|lat:0,lng:0,temp:" + String(t) + ",hum:" + String(h);
    }

    // --- SEND DATA ---
    LoRa.beginPacket();
    LoRa.print(dataToSend);
    LoRa.endPacket();
    Serial.print("📤 Sent: ");
    Serial.println(dataToSend);

    // --- PREPARE TO RECEIVE REPLY ---
    LoRa.idle();        // return to standby
    delay(300);         // small delay to stabilize
    while (LoRa.parsePacket()) { while (LoRa.available()) LoRa.read(); } // clear RX buffer
    LoRa.receive();     // enable receive mode

    Serial.println("🔎 Listening for reply...");
    unsigned long listenStartTime = millis();
    bool replyReceived = false;

    while (millis() - listenStartTime < listenDuration) {
      int packetSize = LoRa.parsePacket();
      if (packetSize > 0) {
        String receivedData = "";
        while (LoRa.available()) {
          receivedData += (char)LoRa.read();
        }

        Serial.print("✅ Reply Received: ");
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
      Serial.println("❌ No reply received within window.");
    }
  }

  // --- Display Own Status ---
  display.clearDisplay();
  display.setCursor(0, 0);
  display.setTextSize(1);
  display.println("---CAR 1---");
  display.println("STATUS: Sending...");
  display.println("--------------------");
  display.print("GPS: ");
  display.println(gps.location.isValid() ? "FIX" : "SEARCHING...");
  display.print("Temp: ");
  display.print(dht.readTemperature());
  display.println(" C");
  display.display();
}
