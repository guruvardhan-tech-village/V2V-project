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
unsigned long messageDisplayTime = 0;
const int displayDuration = 3000;
String receivedMessage = "Waiting for Car 1...";
bool messageReceivedFlag = false;

void drawOwnStatus() {
  display.clearDisplay();
  display.setCursor(0, 0);
  display.setTextSize(1);
  display.println("---CAR 2---");
  display.println("STATUS: Listening...");
  display.println("--------------------");
  display.print("GPS: ");
  display.println(gps.location.isValid() ? "FIX" : "SEARCHING...");
  display.print("Temp: ");
  display.print(dht.readTemperature());
  display.println(" C");
  display.display();
}

void drawReceivedMessage() {
  display.clearDisplay();
  display.setCursor(0, 0);
  display.setTextSize(1);
  display.println("---RECEIVED FROM C1---");
  display.println(receivedMessage);
  display.display();
}

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

  // --- Ensure Both Match ---
  LoRa.setSyncWord(0xF3);
  LoRa.setSpreadingFactor(12);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);

  LoRa.receive();  // start listening immediately
  Serial.println("🚙 Car 2 Ready and Listening!");
}

void loop() {
  while (GPS_Serial.available() > 0) {
    gps.encode(GPS_Serial.read());
  }

  int packetSize = LoRa.parsePacket();
  if (packetSize) {
    String incoming = "";
    while (LoRa.available()) {
      incoming += (char)LoRa.read();
    }

    receivedMessage = incoming;
    messageDisplayTime = millis();
    messageReceivedFlag = true;

    Serial.print("📩 Received from Car 1: ");
    Serial.println(incoming);

    // --- Compose Reply ---
    float h = dht.readHumidity();
    float t = dht.readTemperature();
    String replyData = "";
    if (gps.location.isValid()) {
      replyData = "C2|lat:" + String(gps.location.lat(), 6) +
                  ",lng:" + String(gps.location.lng(), 6) +
                  ",temp:" + String(t) + ",hum:" + String(h);
    } else {
      replyData = "C2|lat:0,lng:0,temp:" + String(t) + ",hum:" + String(h);
    }

    delay(250);  // wait for Car 1 to switch to RX
    LoRa.beginPacket();
    LoRa.print(replyData);
    LoRa.endPacket();
    LoRa.receive();  // stay in receive mode for next round

    Serial.print("📤 Sent Reply: ");
    Serial.println(replyData);
  }

  // --- Display Updates ---
  if (messageReceivedFlag && (millis() - messageDisplayTime < displayDuration)) {
    drawReceivedMessage();
  } else {
    drawOwnStatus();
    messageReceivedFlag = false;
  }
}
