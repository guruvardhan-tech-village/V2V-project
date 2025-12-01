#include <SPI.h>
#include <LoRa.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h> // SH1106 Library
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
const int sendInterval = 2000;
const int ackTimeout = 500; // Wait 500ms for a response

void updateDisplay(String statusMessage, bool received) {
    display.clearDisplay();
    display.setCursor(0, 0);
    display.setTextSize(1);
    
    // Status Header
    display.println("---CAR 1: SENDER---");

    // Display LoRa Status
    if (received) {
        display.println("REPLY RECEIVED:");
        display.println(statusMessage);
    } else {
        display.println("STATUS: Sending...");
        display.println(statusMessage);
    }

    // Display Sensor Data (Always visible)
    display.println("--------------------");
    display.println("MY DATA:");
    display.print("GPS: ");
    display.println(gps.location.isValid() ? "FIX" : "SEARCHING");
    display.print("Temp: ");
    display.print(dht.readTemperature());
    display.println(" C");
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
    LoRa.setSyncWord(0xF3);
    Serial.println("Car 1 Ready!");
}

void loop() {
    while (GPS_Serial.available() > 0) {
        gps.encode(GPS_Serial.read());
    }
    
    // --- SEND LOGIC (Initiator) ---
    if (millis() - lastSendTime > sendInterval) {
        lastSendTime = millis();
        
        float t = dht.readTemperature();
        String dataToSend = String("C1_") + (gps.location.isValid() ? "FIX" : "NOFIX") + 
                            ",LAT:" + String(gps.location.lat(), 4) +
                            ",T:" + String(t);
        
        LoRa.beginPacket();
        LoRa.print(dataToSend);
        LoRa.endPacket();
        Serial.print("Sent: ");
        Serial.println(dataToSend);
        updateDisplay("Sent data to Car 2.", false);

        // --- Active Listening for ACK ---
        unsigned long startTime = millis();
        while (millis() - startTime < ackTimeout) {
            int packetSize = LoRa.parsePacket();
            if (packetSize) {
                String receivedData = "";
                while (LoRa.available()) {
                    receivedData += (char)LoRa.read();
                }
                Serial.print("Reply Received: ");
                Serial.println(receivedData);
                updateDisplay("ACK from Car 2.", true);
                return; // Exit the loop and restart the main loop
            }
        }
        
        // Timeout
        Serial.println("No reply received after timeout.");
        updateDisplay("No reply received.", true);
    }
}