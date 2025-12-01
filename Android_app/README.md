# 🚗 C2C - Car-to-Car Communication System

[![Android](https://img.shields.io/badge/Platform-Android-green.svg)](https://developer.android.com)
[![Kotlin](https://img.shields.io/badge/Language-Kotlin-blue.svg)](https://kotlinlang.org)
[![Firebase](https://img.shields.io/badge/Backend-Firebase-orange.svg)](https://firebase.google.com)
[![Jetpack Compose](https://img.shields.io/badge/UI-Jetpack%20Compose-brightgreen.svg)](https://developer.android.com/jetpack/compose)

A modern Android application enabling real-time vehicle-to-vehicle communication for enhanced road safety and traffic awareness. Built with Kotlin and Jetpack Compose, integrated with Firebase for real-time data synchronization and ESP32 hardware support.

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Usage](#usage)
- [ESP32 Integration](#esp32-integration)
- [Contributing](#contributing)
- [License](#license)

## Overview

C2C (Car-to-Car) is a comprehensive vehicle communication platform that leverages modern Android development practices to create a robust, scalable solution for real-time vehicle data sharing. The application facilitates:

- **Real-time vehicle tracking** via Google Maps integration
- **Safety alerts** and emergency notifications
- **ESP32 hardware integration** for IoT-enabled vehicles
- **User authentication** and profile management
- **Firebase-powered** backend for seamless data synchronization

## Features

### Core Functionality

- 🔐 **Secure Authentication** - Email/password authentication with Firebase Auth
- 🗺️ **Live Map Tracking** - Real-time vehicle location visualization with traffic overlay
- ⚠️ **Smart Alerts System** - Instant notifications for traffic, accidents, and weather conditions
- 🚘 **Vehicle Management** - Register and manage multiple vehicles per user
- 👤 **User Profiles** - Personalized dashboard with vehicle statistics
- 🔧 **ESP32 Integration** - Hardware support for IoT-enabled vehicle monitoring
- 📊 **Real-time Database** - Firebase Firestore and Realtime Database for instant data sync
- 🆘 **Emergency Services** - Quick access to emergency calling (108)

### User Experience

- Modern Material 3 Design
- Responsive bottom navigation
- Personalized welcome dashboard
- Quick action shortcuts
- Developer testing tools
- Offline capability support

## Architecture

This project follows **Clean Architecture** principles with clear separation of concerns:

```
C2C_v2/
├── app/                    # Main application module
│   ├── MainActivity.kt     # Entry point & navigation
│   └── FirebaseTestUtils.kt
├── domain/                 # Business logic & models
│   └── Models.kt
├── data/                   # Data layer & repositories
│   ├── AuthRepository.kt
│   ├── VehicleRepository.kt
│   └── DeviceConfigRepository.kt
├── core-common/            # Shared utilities
│   └── Ui.kt
└── features/               # Feature modules
    ├── feature-auth/       # Authentication screens
    ├── feature-map/        # Map visualization
    ├── feature-alerts/     # Alert management
    ├── feature-vehicle/    # Vehicle registration
    └── feature-esp32/      # ESP32 setup
```

### Design Patterns

- **MVVM** (Model-View-ViewModel) for UI layer
- **Repository Pattern** for data abstraction
- **Single Activity Architecture** with Jetpack Navigation
- **Modular Architecture** for scalability

## Tech Stack

### Android Development
- **Language**: Kotlin 1.9+
- **UI Framework**: Jetpack Compose 1.9.3
- **Navigation**: Navigation Compose 2.9.5
- **Material Design**: Material 3 (1.4.0)
- **Minimum SDK**: 24 (Android 7.0)
- **Target SDK**: 36

### Backend & Services
- **Firebase Authentication** - User management
- **Cloud Firestore** - Document-based database
- **Firebase Realtime Database** - Real-time data sync
- **Firebase Analytics** - Usage tracking
- **Google Maps SDK** (19.2.0) - Location services

### Build Tools
- **Gradle**: Kotlin DSL (KTS)
- **Android Gradle Plugin**: 8.x
- **Compile SDK**: 36

## Getting Started

### Prerequisites

Before you begin, ensure you have:

- Android Studio Hedgehog (2023.1.1) or later
- JDK 17 or higher
- Android SDK with API level 36
- A Firebase account
- Google Cloud Console access

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/guruvardhan-tech-village/Car-to-car-app.git
   cd Car-to-car-app
   ```

2. **Firebase Setup**
   
   Follow the comprehensive guide in [`COMPLETE_FIREBASE_SETUP.md`](COMPLETE_FIREBASE_SETUP.md) to:
   - Create a Firebase project
   - Enable Authentication, Firestore, and Realtime Database
   - Download `google-services.json`
   - Configure Google Cloud Console
   - Set up Google Maps API

3. **Add Firebase Configuration**
   
   Place your `google-services.json` in:
   ```
   app/google-services.json
   ```

4. **Configure Google Maps API**
   
   Add your Maps API key to `app/src/main/res/values/strings.xml`:
   ```xml
   <string name="google_maps_key">YOUR_API_KEY_HERE</string>
   ```

5. **Build the project**
   ```bash
   ./gradlew build
   ```

6. **Run on device/emulator**
   - Connect an Android device or start an emulator
   - Click "Run" in Android Studio or use:
   ```bash
   ./gradlew installDebug
   ```

## Project Structure

### Modular Organization

```
├── app/                          # Application module
│   ├── build.gradle.kts
│   ├── google-services.json      # Firebase config (not in repo)
│   └── src/main/
│       ├── AndroidManifest.xml
│       ├── java/com/c2c/app/
│       │   ├── MainActivity.kt
│       │   └── FirebaseTestUtils.kt
│       └── res/
│           └── values/strings.xml
│
├── domain/                       # Domain layer
│   └── src/main/kotlin/com/c2c/domain/
│       └── model/Models.kt
│
├── data/                         # Data layer
│   └── src/main/java/com/c2c/data/repo/
│       ├── AuthRepository.kt
│       ├── VehicleRepository.kt
│       └── DeviceConfigRepository.kt
│
├── feature-auth/                 # Authentication feature
│   └── src/main/java/com/c2c/feature/auth/
│       └── AuthScreens.kt
│
├── feature-map/                  # Map feature
│   └── src/main/java/com/c2c/feature/map/
│       └── MapScreen.kt
│
├── feature-alerts/               # Alerts feature
│   └── src/main/java/com/c2c/feature/alerts/
│       └── AlertsScreen.kt
│
├── feature-vehicle/              # Vehicle management
│   └── src/main/java/com/c2c/feature/vehicle/
│       ├── VehicleRegistrationScreen.kt
│       └── ProfileScreen.kt
│
└── feature-esp32/                # ESP32 integration
    └── src/main/java/com/c2c/feature/esp32/
        └── Esp32SetupScreen.kt
```

## Configuration

### Firebase Configuration Files

Ensure these files are properly configured:

1. **`google-services.json`** - Firebase Android configuration
2. **`strings.xml`** - Google Maps API key
3. **Firebase Console** - Enable required services:
   - Authentication (Email/Password)
   - Cloud Firestore
   - Realtime Database
   - Firebase Analytics

### Security Rules

Update Firebase security rules for production:

**Firestore Rules** (`firestore.rules`):
```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    match /users/{userId}/{document=**} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
    match /alerts/{alertId} {
      allow read, write: if request.auth != null;
    }
  }
}
```

**Realtime Database Rules** (`database.rules.json`):
```json
{
  "rules": {
    "users": {
      "$uid": {
        ".read": "$uid === auth.uid",
        ".write": "$uid === auth.uid"
      }
    },
    "vehicles": {
      ".read": "auth != null",
      ".write": "auth != null"
    }
  }
}
```

## Usage

### First Time Setup

1. **Launch the app** - Opens to login screen
2. **Register account** - Create account with email/password
3. **Add vehicle** - Register your first vehicle
4. **Enable permissions** - Grant location and notification permissions
5. **Start using** - Access live map, alerts, and profile

### Main Features

#### Home Dashboard
- Personalized welcome screen
- Quick actions: Map, Alerts, Profile
- Live status: vehicles, connection, safety
- Emergency call button
- Firebase testing tools (development)

#### Live Map
- Real-time vehicle location tracking
- Traffic overlay visualization
- Vehicle markers with IDs
- Auto-zoom to vehicle location

#### Alerts System
- Real-time safety notifications
- Traffic alerts
- Accident warnings
- Weather conditions
- Emergency services access

#### Profile Management
- View registered vehicles
- Add/remove vehicles
- Update user information
- Logout functionality

### Developer Tools

Access testing utilities from the home dashboard:

- **🔥 Test Firebase** - Verify Firebase integration
- **🔧 ESP32 Data** - Generate test ESP32 data

Check Android Studio Logcat for test results (filter: `FirebaseTest`).

## ESP32 Integration

The application supports ESP32 microcontrollers for hardware-based vehicle monitoring.

### Hardware Requirements
- ESP32 Development Board
- GPS Module (NEO-6M or similar)
- Power supply (5V)
- USB cable for programming

### ESP32 Features
- Real-time GPS data transmission
- Vehicle speed monitoring
- Sensor data collection
- WiFi connectivity to Firebase

### Setup Guide
Refer to `feature-esp32/` module for:
- ESP32 firmware code
- Hardware connection diagrams
- Configuration instructions

## Testing

### Firebase Integration Test

Run comprehensive Firebase tests:

```kotlin
// In app, click "Test Firebase" button or programmatically:
val testUtils = FirebaseTestUtils(context)
testUtils.runAllTests()
```

Tests include:
- ✅ Authentication (register/login)
- ✅ Firestore connectivity
- ✅ Realtime Database writes
- ✅ Data retrieval

### Manual Testing Checklist

- [ ] User registration and login
- [ ] Vehicle addition and removal
- [ ] Map loading with traffic overlay
- [ ] Alert notifications
- [ ] Emergency call functionality
- [ ] Profile updates
- [ ] Logout and re-login

## Contributing

Contributions are welcome! Please follow these guidelines:

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Commit your changes**
   ```bash
   git commit -m 'Add amazing feature'
   ```
4. **Push to the branch**
   ```bash
   git push origin feature/amazing-feature
   ```
5. **Open a Pull Request**

### Code Standards
- Follow Kotlin coding conventions
- Use meaningful variable/function names
- Add comments for complex logic
- Write unit tests for new features
- Ensure all existing tests pass

## License

This project is licensed under the MIT License - see the [LICENSE](./LICENSE) file for details.

## Support & Contact

For questions, issues, or suggestions:

- **GitHub Issues**: [Report a bug](https://github.com/guruvardhan-tech-village/Car-to-car-app/issues)
- **Email**: [Your contact email]
- **Documentation**: See additional `.md` files in the repository

## Acknowledgments

- **Firebase** - Backend infrastructure
- **Google Maps Platform** - Location services
- **Jetpack Compose** - Modern Android UI
- **Material Design** - Design guidelines
- **ESP32 Community** - Hardware support

---

## Additional Documentation

- [Complete Firebase Setup Guide](COMPLETE_FIREBASE_SETUP.md)
- [Google Maps Setup](GOOGLE_MAPS_SETUP.md)
- [Firebase Testing Guide](FIREBASE_TESTING_GUIDE.md)
- [Login Debug Guide](LOGIN_DEBUG_GUIDE.md)
- [User Dashboard Features](USER_DASHBOARD_FEATURES.md)

---

**Made with ❤️ by Guruvardhan Tech Village**

*Building safer roads through connected vehicles*
