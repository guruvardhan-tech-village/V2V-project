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
const double DEFAULT_LAT = 12.976668529069483;
const double DEFAULT_LNG = 77.483177479548;

double g_lastLat = DEFAULT_LAT;
double g_lastLng = DEFAULT_LNG;
bool g_gpsValid = false;

// Car ID (will update from Python)
String CAR_ID = "C2";

// ----- FUNCTIONS -----

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
    Serial.print("📡 [Car2] LoRa TX #");
    Serial.print(i + 1);
    Serial.print(": ");
    Serial.println(msg);
    delay(80);       // small gap
    LoRa.receive();  // back to RX ASAP
    delay(40);
  }
}
void drawStatus(const char *status)
{
  display.clearDisplay();
  display.setCursor(0, 0);
  display.setTextSize(1);
  display.println(("---" + CAR_ID + "---").c_str());
  display.println(status);
  display.println("-------------------");
  display.print("GPS: ");
  display.println(g_gpsValid ? "FIX" : "East West Institute Of Technology");
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
  LoRa.receive();  // default: listening

  Serial.println("🚙 Car 2 Ready (RX mode)!");
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

  // ---------- RECEIVE LoRa MESSAGE ----------
  int packet = LoRa.parsePacket();
  if (packet > 0) {
    String data = "";
    while (LoRa.available()) data += (char)LoRa.read();

    Serial.print("📥 [Car2] LoRa RX: ");
    Serial.println(data);

    display.clearDisplay();
    display.setCursor(0, 0);
    display.setTextSize(1);
    display.println(("---" + CAR_ID + "---").c_str());

    if (data.indexOf("ALERT|ACCIDENT") >= 0) {
      display.println("🚨 ACCIDENT ALERT");
    } else if (data.indexOf("ALERT|TRAFFIC") >= 0) {
      display.println("🚦 TRAFFIC ALERT");
    } else {
      display.println("V2V MSG:");
    }
    display.println("-------------------");
    display.println(data);
    display.display();

    // Forward to laptop as V2V message
    Serial.print("LORA_RX|");
    Serial.println(data);

    delay(2000);
    drawStatus("Listening...");
    LoRa.receive();
  }

  // ---------- RECEIVE COMMANDS FROM UI/YOLO ----------
  if (Serial.available()) {
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    if (cmd.length() == 0) return;

    Serial.print("💻 [Car2] CMD: ");
    Serial.println(cmd);

    // Update ID: SETID|KA04NF3177
    if (cmd.startsWith("SETID|")) {
      CAR_ID = cmd.substring(6);
      CAR_ID.trim();
      Serial.println("🔧 Car2 ID set to: " + CAR_ID);
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
