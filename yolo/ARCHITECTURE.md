# System Architecture Documentation

## Overview
This document describes the architecture of the Vehicle Accident Detection System using YOLOv8, ESP32, and Google Cloud.

## System Components

### 1. Vehicle A (Your Car)

#### ESP32-CAM
- **Function**: Captures video feed
- **Output**: MJPEG stream
- **Connection**: Wi-Fi to Laptop

#### Laptop
- **Function**: Runs YOLOv8 model for accident detection
- **Input**: MJPEG stream from ESP32-CAM
- **Output**: Accident/Traffic detection JSON
- **Connection**: Wi-Fi to Cloud, USB/Serial to ESP32

#### ESP32 (Main Controller)
- **Function**: 
  - GPS tracking
  - Weather sensor data collection
  - LoRa communication (V2V)
  - BLE communication (to Android app)
- **Input**: Detection data from Laptop
- **Output**: 
  - LoRa broadcasts to nearby vehicles
  - BLE data to Android App A
  - HTTPS uploads to Cloud

#### Android App A
- **Function**: User interface and control
- **Input**: 
  - BLE data from ESP32
  - Cloud data from Firestore
  - Push notifications from FCM
- **Output**: User commands, data writes to Firestore

### 2. Other Nearby Vehicles

#### ESP32 LoRa
- **Function**: Receives LoRa broadcasts from Vehicle A
- **Output**: Alert data to Android Apps

#### Android Apps
- **Function**: Display alerts to nearby drivers
- **Input**: Alerts from ESP32 LoRa

### 3. Google Cloud Infrastructure

#### Firebase Auth
- **Function**: User authentication
- **Integration**: All cloud services

#### Firestore Database
- **Function**: Store accident reports, traffic data, user data
- **Access**: Read/Write from Android App A, Cloud Functions

#### Cloud Storage
- **Function**: Store media files (images/videos)
- **Access**: Cloud Functions

#### Cloud Run / Cloud Functions
- **Function**: 
  - Process incoming data from Vehicle A
  - Trigger on Firestore updates
  - Publish events to Pub/Sub
  - Send notifications via FCM
- **Input**: HTTPS requests from Laptop/ESP32/App
- **Output**: Processed data to Firestore, notifications to FCM

#### Pub/Sub
- **Function**: Event-driven messaging
- **Input**: Events from Cloud Run
- **Output**: Triggers Cloud Functions

#### Firebase Cloud Messaging (FCM)
- **Function**: Push notifications
- **Input**: Messages from Cloud Run
- **Output**: Notifications to Android App A

## Data Flow

### 1. Local Processing Flow
```
ESP32-CAM → MJPEG Stream → Laptop (YOLOv8) → Detection JSON → ESP32 → BLE → Android App A
```

### 2. Vehicle-to-Vehicle (V2V) Flow
```
ESP32 (Vehicle A) → LoRa Broadcast → ESP32 LoRa (Nearby) → Android Apps (Nearby)
```

### 3. Cloud Upload Flow
```
Laptop → HTTPS → Cloud Run → Firestore
ESP32 → HTTPS → Cloud Run → Firestore
Android App A → SDK → Firestore
```

### 4. Cloud Processing Flow
```
Cloud Run → Firestore (Write)
Firestore → Cloud Run (Trigger)
Cloud Run → Pub/Sub → Cloud Run (Process)
Cloud Run → FCM → Android App A (Notification)
```

### 5. Cloud to App Flow
```
Firestore → Android App A (Real-time updates)
FCM → Android App A (Push notifications)
```

## Communication Protocols

### LoRa (Long Range)
- **Purpose**: Vehicle-to-Vehicle communication
- **Range**: ~5-15 km (depending on conditions)
- **Advantage**: Works without internet
- **Use Case**: Immediate accident alerts to nearby vehicles

### BLE (Bluetooth Low Energy)
- **Purpose**: Local communication between ESP32 and Android App
- **Range**: ~10 meters
- **Advantage**: Low power, fast connection
- **Use Case**: Real-time data display in vehicle

### Wi-Fi / HTTPS
- **Purpose**: Cloud communication
- **Advantage**: Secure, reliable
- **Use Case**: Data upload, cloud synchronization

### Firebase SDK
- **Purpose**: Direct database access from Android App
- **Advantage**: Real-time updates, offline support
- **Use Case**: Data reads/writes from mobile app

## Security Considerations

1. **Authentication**: Firebase Auth for user authentication
2. **Encryption**: HTTPS for all cloud communications
3. **Authorization**: Firestore security rules
4. **Data Privacy**: User data stored securely in Firestore

## Scalability

1. **Cloud Run**: Auto-scales based on load
2. **Firestore**: Handles multiple concurrent vehicles
3. **Pub/Sub**: Processes events asynchronously
4. **LoRa**: Supports multiple vehicles in range

## Cost Optimization (Free-tier Friendly)

1. **Firebase**: Free tier includes:
   - 50K reads/day
   - 20K writes/day
   - 1 GB storage
   - 10 GB transfer/month

2. **Cloud Run**: Free tier includes:
   - 2 million requests/month
   - 360,000 GB-seconds compute time

3. **Cloud Storage**: Free tier includes:
   - 5 GB storage
   - 1 GB egress/month

4. **Pub/Sub**: Free tier includes:
   - 10 GB messaging/month

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    EDGE (Vehicle A)                         │
│  ESP32-CAM → Laptop (YOLOv8) → ESP32 → Android App A      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ LoRa (V2V)
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              NEARBY VEHICLES (Edge)                         │
│              ESP32 LoRa → Android Apps                     │
└─────────────────────────────────────────────────────────────┘
                       │
                       │ HTTPS / SDK
                       │
┌──────────────────────▼──────────────────────────────────────┐
│                  CLOUD (Google Cloud)                       │
│  Cloud Run → Firestore → Pub/Sub → FCM                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ FCM / Real-time Updates
                       │
┌──────────────────────▼──────────────────────────────────────┐
│              ANDROID APP A (Client)                         │
│         (Receives updates and notifications)                │
└─────────────────────────────────────────────────────────────┘
```

## Technology Stack Summary

| Component | Technology |
|-----------|-----------|
| Video Capture | ESP32-CAM |
| Accident Detection | YOLOv8 (PyTorch) |
| Microcontroller | ESP32 |
| Communication | LoRa, BLE, Wi-Fi |
| Mobile App | Android (Java/Kotlin) |
| Backend | Google Cloud Run / Functions |
| Database | Firestore |
| Storage | Cloud Storage |
| Messaging | Pub/Sub, FCM |
| Authentication | Firebase Auth |

## Benefits

1. **Real-time Detection**: Local YOLOv8 processing for immediate response
2. **Offline Capable**: LoRa works without internet
3. **Scalable**: Cloud services handle multiple vehicles
4. **Cost-effective**: Uses free-tier services
5. **Reliable**: Multiple communication channels (LoRa, BLE, Cloud)
6. **User-friendly**: Android app for easy monitoring

## Future Enhancements

1. **Multi-vehicle coordination**: Enhanced V2V communication
2. **Machine learning improvements**: Better accident detection accuracy
3. **Edge computing**: More processing on ESP32
4. **Blockchain**: Immutable accident records
5. **IoT integration**: More sensor data collection

