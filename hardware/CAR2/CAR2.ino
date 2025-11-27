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

// --- Display State Variables ---
unsigned long messageDisplayTime = 0;
const int displayDuration = 3000; // Display received message for 3 seconds
String receivedMessage = "Waiting for Car 1...";
bool messageReceivedFlag = false;

// Function to draw the CURRENT status of Car 2
void drawOwnStatus() {
    display.clearDisplay();
    display.setCursor(0, 0);
    display.setTextSize(1);
    
    display.println("---CAR 2: RESPONDER---");
    display.println("STATUS: Listening...");

    // My GPS Data
    display.println("--------------------");
    display.println("MY GPS:");
    display.print("Fix: ");
    display.println(gps.location.isValid() ? "YES" : "NO");
    if (gps.location.isValid()) {
        display.print("Lat: ");
        display.println(gps.location.lat(), 4);
        display.print("Lng: ");
        display.println(gps.location.lng(), 4);
    } else {
        display.println("Waiting for Satellites...");
    }

    // My Temp Data
    display.println("--------------------");
    display.print("Temp: ");
    display.print(dht.readTemperature());
    display.println(" C");
    display.display();
}

// Function to draw the RECEIVED message
void drawReceivedMessage() {
    display.clearDisplay();
    display.setCursor(0, 0);
    display.setTextSize(1);
    display.println("---RECEIVED FROM CAR 1---");
    display.println("-------------------------");
    
    // Display the received message, wrapped if necessary
    display.setTextSize(1);
    display.println(receivedMessage);
    display.display();
}


void onReceive(int packetSize) {
    if (packetSize == 0) return;
    
    String incoming = "";
    while (LoRa.available()) {
        incoming += (char)LoRa.read();
    }
    
    // Save the message and set the flag/timer
    receivedMessage = incoming;
    messageDisplayTime = millis(); // Start the 3-second display timer
    messageReceivedFlag = true;

    Serial.print("Received from Car 1: ");
    Serial.println(incoming);
    
    // Send immediate acknowledgment (ACK) reply
    String reply = "C2: ACK";
    LoRa.beginPacket();
    LoRa.print(reply);
    LoRa.endPacket();
    Serial.print("Sent Reply: ");
    Serial.println(reply);
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
    Serial.println("Car 2 Ready!");
}

void loop() {
    while (GPS_Serial.available() > 0) {
        gps.encode(GPS_Serial.read());
    }

    // Check for incoming packets and handle reply
    onReceive(LoRa.parsePacket());

    // --- DISPLAY LOGIC (State Machine) ---
    if (messageReceivedFlag) {
        // State 1: Show received message for 3 seconds
        if (millis() - messageDisplayTime < displayDuration) {
            drawReceivedMessage();
        } else {
            // Timer expired, switch back to normal status display
            drawOwnStatus();
            messageReceivedFlag = false; // Reset the flag
        }
    } else {
        // State 2: Show own status (default state)
        drawOwnStatus();
    }
}