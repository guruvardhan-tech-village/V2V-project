#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include <DHT.h>
#include <TinyGPSPlus.h>
#include <HardwareSerial.h>

// --- Pin Definitions ---
#define LORA_SS      5
#define LORA_RST     14
#define LORA_DIO0    2
#define DHTPIN       4
#define DHTTYPE      DHT22
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

// --- Component Objects ---
Adafruit_SH1106G display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
DHT dht(DHTPIN, DHTTYPE);
HardwareSerial GPS_Serial(2);
TinyGPSPlus gps;

// --- Timing ---
unsigned long lastSendTime = 0;
const int sendInterval = 3000;
const int listenDuration = 3000;
unsigned long lastRefresh = 0;

// --- Default GPS ---
const double DEFAULT_LAT = 12.988500;
const double DEFAULT_LNG = 77.515200;

double g_lastLat = DEFAULT_LAT;
double g_lastLng = DEFAULT_LNG;
bool g_gpsValid = false;

// Car ID (will update from Python)
String CAR_ID = "C2";

// ----- FUNCTIONS -----
void drawStatus(const char *status)
{
  display.clearDisplay();
  display.setCursor(0, 0);
  display.setTextSize(1);
  display.println(("---" + CAR_ID + "---").c_str());
  display.println(status);
  display.println("-------------------");
  display.print("GPS: ");
  display.println(g_gpsValid ? "FIX" : "DEFAULT");
  display.print("Lat: ");
  display.println(g_lastLat, 6);
  display.print("Lng: ");
  display.println(g_lastLng, 6);
  display.display();
}

void setup() {
  Serial.begin(115200);
  Wire.begin(21, 22);
  Wire.setClock(100000);   // prevent display glitch

  if (!display.begin(0x3C, true)) {
    Serial.println("OLED Err");
    while (1);
  }
  display.setTextColor(SH110X_WHITE);

  dht.begin();
  GPS_Serial.begin(9600, SERIAL_8N1, 16, 17);

  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
  if (!LoRa.begin(433E6)) {
    Serial.println("LoRa failed");
    while (1);
  }
  LoRa.setSyncWord(0xF3);
  LoRa.setSpreadingFactor(12);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);

  Serial.println("🚙 Car 2 Ready!");
  drawStatus("Booting...");
}

void loop() {
  while (GPS_Serial.available()) gps.encode(GPS_Serial.read());
  unsigned long now = millis();

  // ---------- SEND SENSOR PACKET ----------
  if (now - lastSendTime > sendInterval) {
    lastSendTime = now;

    float h = dht.readHumidity();
    float t = dht.readTemperature();

    if (gps.location.isValid()) {
      g_lastLat = gps.location.lat();
      g_lastLng = gps.location.lng();
      g_gpsValid = true;
    } else {
      g_gpsValid = false;
    }

    String payload = CAR_ID + "|lat:" + String(g_lastLat, 6) +
                     ",lng:" + String(g_lastLng, 6) +
                     ",temp:" + String(t) + ",hum:" + String(h);

    LoRa.beginPacket();
    LoRa.print(payload);
    LoRa.endPacket();

    Serial.print("📤 LoRa Sent: ");
    Serial.println(payload);

    LoRa.idle();
    delay(250);
    LoRa.receive();
    drawStatus("Sending...");
  }

  // ---------- RECEIVE LoRa MESSAGE ----------
  int packet = LoRa.parsePacket();
  if (packet > 0) {
    String data = "";
    while (LoRa.available()) data += (char)LoRa.read();

    Serial.print("📥 LoRa RX: ");
    Serial.println(data);

    display.clearDisplay();
    display.setCursor(0, 0);
    display.println(("---" + CAR_ID + "---").c_str());

    if (data.indexOf("ACCIDENT") >= 0) {
      display.println("🚨 ACCIDENT ALERT");
    } else if (data.indexOf("TRAFFIC") >= 0) {
      display.println("🚦 TRAFFIC ALERT");
    }
    display.println(data);
    display.display();
    delay(2000);
  }

  // ---------- RECEIVE COMMANDS FROM UI/YOLO ----------
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();

    if (cmd.startsWith("SETID|")) {
      CAR_ID = cmd.substring(6);
      Serial.println("ID Updated to: " + CAR_ID);
      drawStatus("ID Updated");
    }

    if (cmd.startsWith("CMD|ACCIDENT")) {
      display.clearDisplay();
      display.setCursor(0, 0);
      display.println("⚠ ACCIDENT ALERT");
      display.println(cmd);
      display.display();
    }
  }
}
