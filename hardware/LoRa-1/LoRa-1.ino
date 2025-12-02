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

// --- Objects ---
Adafruit_SH1106G display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);
DHT dht(DHTPIN, DHTTYPE);
HardwareSerial GPS_Serial(2);
TinyGPSPlus gps;

// --- Timings ---
unsigned long lastSerialSend = 0;
const unsigned long SERIAL_INTERVAL = 3000;   // ms

// --- Default GPS (Car 1 indoor test: Kottigepalya) ---
const double DEFAULT_LAT = 12.987861;
const double DEFAULT_LNG = 77.513966;

double g_lastLat = DEFAULT_LAT;
double g_lastLng = DEFAULT_LNG;
bool   g_gpsValid = false;

// Car ID – will be updated from laptop using:  SETID|KA04NF3177
String CAR_ID = "C1";

// ------------- Helpers -------------

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

  display.print("Temp: ");
  display.print(dht.readTemperature());
  display.println(" C");

  display.display();
}

String extractField(const String &src, const String &key)
{
  int idx = src.indexOf(key + ":");
  if (idx < 0) return "";
  int start = idx + key.length() + 1;
  int end = src.indexOf('|', start);
  if (end < 0) end = src.length();
  String val = src.substring(start, end);
  val.trim();
  return val;
}

void broadcastLoRa(const String &msg, int repeatCount)
{
  for (int i = 0; i < repeatCount; i++) {
    LoRa.idle();
    delay(10);
    LoRa.beginPacket();
    LoRa.print(msg);
    LoRa.endPacket();
    Serial.print("📡 [Car1] LoRa TX #");
    Serial.print(i + 1);
    Serial.print(": ");
    Serial.println(msg);
    delay(80);       // small gap
    LoRa.receive();  // back to RX ASAP
    delay(40);
  }
}

// ------------- Setup -------------

void setup() {
  Serial.begin(115200);

  Wire.begin(21, 22);
  Wire.setClock(100000);   // reduce glitch risk

  if (!display.begin(0x3C, true)) {
    Serial.println("OLED init failed");
    while (1);
  }
  display.setTextColor(SH110X_WHITE);

  dht.begin();
  GPS_Serial.begin(9600, SERIAL_8N1, 16, 17);

  // LoRa init
  LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
  if (!LoRa.begin(433E6)) {
    Serial.println("LoRa init failed!");
    while (1);
  }
  LoRa.setSyncWord(0xF3);
  LoRa.setSpreadingFactor(12);
  LoRa.setSignalBandwidth(125E3);
  LoRa.setCodingRate4(5);
  LoRa.receive();  // default: listening

  Serial.println("🚗 Car 1 Ready (RX mode)!");
  drawStatus("Booting...");
}

// ------------- Loop -------------

void loop() {
  // GPS update
  while (GPS_Serial.available()) {
    gps.encode(GPS_Serial.read());
  }

  // ---------- 1) Periodic SENSOR data to laptop (Serial only) ----------
  unsigned long now = millis();
  if (now - lastSerialSend > SERIAL_INTERVAL) {
    lastSerialSend = now;

    float h = dht.readHumidity();
    float t = dht.readTemperature();

    if (gps.location.isValid()) {
      g_lastLat = gps.location.lat();
      g_lastLng = gps.location.lng();
      g_gpsValid = true;
    } else {
      g_lastLat = DEFAULT_LAT;
      g_lastLng = DEFAULT_LNG;
      g_gpsValid = false;
    }

    String serialPayload = "SENSOR|lat:" + String(g_lastLat, 6) +
                           ",lng:" + String(g_lastLng, 6) +
                           ",temp:" + String(t) +
                           ",hum:" + String(h);

    Serial.println(serialPayload);   // Python reads this
    drawStatus("Sending...");
  }

  // ---------- 2) LoRa RX from other cars ----------
  int packetSize = LoRa.parsePacket();
  if (packetSize > 0) {
    String msg = "";
    while (LoRa.available()) {
      msg += (char)LoRa.read();
    }

    Serial.print("📥 [Car1] LoRa RX: ");
    Serial.println(msg);

    display.clearDisplay();
    display.setCursor(0, 0);
    display.setTextSize(1);
    display.println(("---" + CAR_ID + "---").c_str());

    if (msg.indexOf("ALERT|ACCIDENT") >= 0) {
      display.println("🚨 ACCIDENT ALERT");
    } else if (msg.indexOf("ALERT|TRAFFIC") >= 0) {
      display.println("🚦 TRAFFIC ALERT");
    } else {
      display.println("V2V MSG:");
    }
    display.println("-------------------");
    display.println(msg);
    display.display();

    // Forward to laptop as V2V message
    Serial.print("LORA_RX|");
    Serial.println(msg);

    delay(2000);
    drawStatus("Listening...");
    LoRa.receive();
  }

  // ---------- 3) Commands from laptop (YOLO/UI) ----------
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() == 0) return;

    Serial.print("💻 [Car1] CMD: ");
    Serial.println(cmd);

    // Update ID: SETID|KA04NF3177
    if (cmd.startsWith("SETID|")) {
      CAR_ID = cmd.substring(6);
      CAR_ID.trim();
      Serial.println("🔧 Car1 ID set to: " + CAR_ID);
      drawStatus("ID Updated");
      return;
    }

    // CMD|ACCIDENT|severity:HIGH|loc:Magadi Road, Kottigepalya
    if (cmd.startsWith("CMD|ACCIDENT")) {
      String loc = extractField(cmd, "loc");
      if (loc.length() == 0) loc = "Unknown";

      display.clearDisplay();
      display.setCursor(0, 0);
      display.setTextSize(1);
      display.println("ACCIDENT ALERT");
      display.print("Car: ");
      display.println(CAR_ID);
      display.print("Loc: ");
      display.println(loc);
      display.display();

      String alertMsg = "ALERT|ACCIDENT|loc:" + loc + "|from:" + CAR_ID;

      // Send 3–4 times (here: 4 times)
      broadcastLoRa(alertMsg, 4);
      LoRa.receive();   // back to listening
      return;
    }

    // CMD|TRAFFIC|level:HIGH|loc:Magadi Road, Kottigepalya
    if (cmd.startsWith("CMD|TRAFFIC")) {
      String loc   = extractField(cmd, "loc");
      String level = extractField(cmd, "level");
      if (loc.length() == 0)   loc   = "Unknown";
      if (level.length() == 0) level = "UNKNOWN";

      display.clearDisplay();
      display.setCursor(0, 0);
      display.setTextSize(1);
      display.println("TRAFFIC ALERT");
      display.print("Level: ");
      display.println(level);
      display.print("Loc: ");
      display.println(loc);
      display.display();

      String alertMsg = "ALERT|TRAFFIC|level:" + level + "|loc:" + loc + "|from:" + CAR_ID;

      broadcastLoRa(alertMsg, 4);
      LoRa.receive();
      return;
    }
  }
}
