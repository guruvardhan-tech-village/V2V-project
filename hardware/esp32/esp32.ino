#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h> // Correct library for your display
#include <DHT.h>
#include <TinyGPSPlus.h>
#include <HardwareSerial.h>

// --- LoRa Pin Definitions ---
#define LORA_SS 5
#define LORA_RST 14
#define LORA_DIO0 2

// --- OLED Display Definitions ---
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

// Create display object for SH1106
Adafruit_SH1106G display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// --- DHT22 Sensor Definitions ---
#define DHTPIN 4
#define DHTTYPE DHT22
DHT dht(DHTPIN, DHTTYPE);

// --- GPS Definitions ---
HardwareSerial GPS_Serial(2); // Use UART2 for GPS (Pins 16 & 17)
TinyGPSPlus gps;

unsigned long lastSendTime = 0;
const int sendInterval = 2000;  // Send data every 2 seconds

void setup() {
    Serial.begin(115200);
    while (!Serial);

    // Initialize OLED with the correct library and address
    Wire.begin(21, 22);
    if (!display.begin(0x3C, true)) {
        Serial.println(F("Display not found"));
        for (;;);
    }
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SH110X_WHITE);

    // Initialize DHT22
    dht.begin();
    
    // Initialize GPS
    GPS_Serial.begin(9600, SERIAL_8N1, 16, 17);

    // Initialize LoRa
    LoRa.setPins(LORA_SS, LORA_RST, LORA_DIO0);
    if (!LoRa.begin(433E6)) {
        Serial.println("LoRa init failed!");
        while (1);
    }
    LoRa.setSyncWord(0xF3);
    Serial.println("LoRa Initialized OK!");
}

void loop() {
    // Read GPS data
    while (GPS_Serial.available() > 0) {
        gps.encode(GPS_Serial.read());
    }

    // --- LoRa Send/Receive Logic ---
    int packetSize = LoRa.parsePacket();
    if (packetSize) {
        String receivedData = "";
        while (LoRa.available()) {
            receivedData += (char)LoRa.read();
        }
        
        Serial.print("Received from Car 1: ");
        Serial.println(receivedData);
    }

    if (millis() - lastSendTime > sendInterval) {
        lastSendTime = millis();
        
        float h = dht.readHumidity();
        float t = dht.readTemperature();
        
        String dataToSend = "";
        if (gps.location.isValid()) {
            dataToSend = "lat:" + String(gps.location.lat(), 6) +
                         ",lng:" + String(gps.location.lng(), 6) +
                         ",temp:" + String(t) + 
                         ",hum:" + String(h);
        } else {
            dataToSend = String("lat:0,lng:0") + ",temp:" + String(t) + ",hum:" + String(h);
        }

        LoRa.beginPacket();
        LoRa.print(dataToSend);
        LoRa.endPacket();
        Serial.print("Sent LoRa packet: ");
        Serial.println(dataToSend);
    }

    // --- OLED Display Update ---
    display.clearDisplay();
    display.setCursor(0, 0);

    display.println("---Car 2 Status---");
    if (gps.location.isValid()) {
        display.println("GPS: FIX");
        display.print("Lat: ");
        display.println(gps.location.lat(), 4);
        display.print("Lng: ");
        display.println(gps.location.lng(), 4);
    } else {
        display.println("GPS: Searching...");
        display.println("Waiting for Satellites");
    }

    display.println("--------------------");
    display.println("LoRa: OK");
    display.print("Sent: ");
    display.println(LoRa.endPacket());
    display.println("Received: ");
    display.println(LoRa.parsePacket());

    display.println("--------------------");
    display.print("Temp: ");
    display.print(dht.readTemperature());
    display.println(" C");
    display.print("Humid: ");
    display.print(dht.readHumidity());
    display.println(" %");

    display.display();
}