# C2C Android App – Architecture Overview

This document explains which languages and technologies are used in the project, what is considered frontend vs backend, and the purpose of each major module and key file.

## 1. Languages & Technologies

### 1.1 Programming languages

- **Kotlin**
  - Used for all application source files (`.kt`).
  - Used to build:
    - UI with Jetpack Compose
    - Navigation
    - Business/domain logic
    - Repository layer
    - Firebase and Google Maps integration

- **Kotlin (Gradle Kotlin DSL)**
  - Used in `build.gradle.kts` and `settings.gradle.kts`.
  - Describes modules, dependencies, plugins, and build configuration.

### 1.2 Other formats

- **XML**
  - Android resources (`res/values/strings.xml`, etc.).
  - Example: app name, Google Maps API key.

- **Markdown (`.md`)**
  - Project documentation: `README.md`, `COMPLETE_FIREBASE_SETUP.md`, `fulldetails.md`, etc.

- **JSON (in Firebase, not as Kotlin files)**
  - Data structure in Firebase Realtime Database / Firestore.
  - Security rules examples in the documentation.

---

## 2. Frontend vs Backend

### 2.1 Frontend (mobile app)

Everything inside this Android project is the **frontend**. It runs on the user’s Android device.

**Frontend technologies:**

- **Language:** Kotlin
- **UI:** Jetpack Compose + Material 3
- **Navigation:** Navigation Compose
- **Maps UI:** Google Maps SDK + `MapView`

**Frontend modules:**

- `:app`
- `:core-common`
- `:domain`
- `:data` (data access layer running on device)
- `:feature-auth`
- `:feature-map`
- `:feature-alerts`
- `:feature-vehicle`
- `:feature-esp32`

The frontend:

- Draws screens and handles user input
- Requests permissions (location, etc.)
- Connects to Firebase and Google services over the network

### 2.2 Backend (services)

The app does **not** have a custom server; it uses managed backend services:

- **Firebase Authentication**
  - Manages user accounts, login, and registration.

- **Cloud Firestore**
  - Document database for user and vehicle data.
  - Example path: `users/{uid}/vehicles/{vehicleId}`.

- **Firebase Realtime Database**
  - Real-time data for:
    - Live vehicles
    - ESP32 telemetry (`esp32_data`)
    - Safety alerts (`accidents`, `traffic`)

- **Firebase Analytics** (optional)
  - Usage metrics and events.

- **Google Maps Platform**
  - Maps SDK for Android (map rendering).
  - Directions API (route calculation).
  - Geocoding (via Android `Geocoder`).

**Why this split?**

- Frontend: Kotlin + Compose provide a modern reactive UI and simple state handling.
- Backend: Firebase gives authentication, realtime sync, and databases without deploying your own server.

---

## 3. Root-level Structure

### 3.1 `settings.gradle.kts`

- Defines plugin repositories (Google, Maven Central, Gradle Plugin Portal).
- Declares all modules in the project:
  - `:app`
  - `:core-common`
  - `:data`
  - `:domain`
  - `:feature-alerts`
  - `:feature-auth`
  - `:feature-esp32`
  - `:feature-map`
  - `:feature-vehicle`

### 3.2 Root `build.gradle.kts`

- Root Gradle configuration file.
- Most plugin versions and configuration are managed in `settings.gradle.kts` via `pluginManagement`.

### 3.3 `README.md`

- High-level project documentation:
  - Overview and features
  - Architecture summary
  - Tech stack (Kotlin, Compose, Firebase, Maps)
  - Project structure
  - Setup and configuration (Firebase, Maps)
  - Testing and ESP32 integration

### 3.4 `fulldetails.md`

- More detailed description of each module and its responsibilities.
- Useful for understanding the overall Clean Architecture layout.

---

## 4. Modules and Responsibilities

### 4.1 `:app` – Application Module

**Folder:** `app/`

This is the **main application module**. It wires together all other modules and contains the entry point.

#### Key responsibilities

- Hosts the **single activity** (`MainActivity`).
- Sets up **Compose** and the **navigation graph**.
- Manages global app state: user, alerts, routes, location.
- Listens to Firebase Realtime Database for incoming alerts.

#### Important files

1. `app/src/main/java/com/c2c/app/MainActivity.kt`

- `class MainActivity`:
  - Entry point activity.
  - Calls `setContent { C2CTheme { C2CApp() } }` to start the Compose UI.

- `@Composable fun C2CApp()`:
  - Creates and holds application-wide state:
    - Authentication state: `currentUser`, `userEmail` (from `AuthRepository`).
    - Location permission and `currentLocation` (via FusedLocationProviderClient).
    - Alerts list: `alerts` (list of `AlertUI`).
    - Latest alert and raw latest alert: `latestAlert`, `rawLatestAlert`.
    - Active route polyline: `activeRoute` (list of `LatLng`).
  - Sets up Firebase Realtime Database listeners for:
    - `accidents`
    - `traffic`
  - Converts snapshots into `AlertUI` instances.
  - Filters alerts to show only those on the active route.
  - Decides whether to show `AuthNavigation` (not logged in) or `MainNavigation` (logged in).

- `@Composable fun AuthNavigation(...)`:
  - Navigation graph for:
    - `LoginScreen`
    - `RegisterScreen`
    - `VehicleRegistrationScreen` (post-registration setup)
  - Uses `AuthRepository` to determine the current user and pass IDs/emails forward.

- `@Composable fun MainNavigation(...)`:
  - Main logged-in navigation with bottom navigation bar:
    - Home
    - Profile
    - Map
    - Alerts
  - Shows a **snackbar** whenever a new `rawLatestAlert` comes in (e.g. "[HH:mm] Accident Alert: ...").
  - Hosts screens:
    - `ModernHomeScreen` (home dashboard)
    - `ProfileScreen` (from `feature-vehicle`)
    - `MapWithIncidentsScreen` (wraps map feature)
    - `AlertsScreen` (from `feature-alerts`)
  - Provides logout action.

- `@Composable fun MapWithIncidentsScreen(...)`:
  - Wraps `MapScreen` from `feature-map`.
  - Manages route search (by long pressing on the map or searching text).
  - Shows current route status and distance.
  - Shows an overlay card for significant traffic alerts with an option to open Google Maps.

- Helper functions:
  - `isAlertNearUser(...)`: checks if an alert is within a distance of the user.
  - `isAlertOnRoute(...)`: checks if an alert lies near the active route polyline.
  - `fetchRoute(...)` and `parseRouteFromDirectionsJson(...)`:
    - Call Google Directions API.
    - Parse polyline coordinates and distance.

2. `app/src/main/java/com/c2c/app/FirebaseTestUtils.kt`

- Utility class for **developer testing** of Firebase.
- Key methods:
  - `runAllTests()`:
    - Tests authentication (register, login, logout).
    - Tests Firestore reads/writes.
    - Tests Realtime Database reads/writes.
    - Tests vehicle operations.
  - `generateTestESP32Data(vehicleId: String)`:
    - Writes random ESP32-like telemetry data into `esp32_data/{vehicleId}` in Realtime DB.
  - `printFirebaseStatus()`:
    - Logs current app package, auth user, Firestore/RTDB init status, and current time to Logcat.

---

### 4.2 `:domain` – Domain (Business) Layer

**Folder:** `domain/`

This is a **pure Kotlin module** (no Android-specific dependencies) that contains core business models.

**Key file:**

- `domain/src/main/kotlin/com/c2c/domain/model/Models.kt`

  - `data class Vehicle`:
    - Fields: `id`, `plate`, `model`, `ownerUid`, `year`, `color`, `registrationDate`, `isActive`.

  - `data class Alert`:
    - Fields: `id`, `type`, `lat`, `lon`, `severity`, `message`, `ts`.

  - `data class DeviceConfig`:
    - Fields: `vehicleId`, `ssid`, `password`, `uploadIntervalSec`, `ownerUid`.

**Role:**

- Defines core entities used by the data and UI layers.
- Makes the core logic decoupled from Android UI code and easier to test.

---

### 4.3 `:data` – Data Access Layer

**Folder:** `data/`

Responsible for communication with Firebase services and returning domain models.

#### Files

1. `data/src/main/java/com/c2c/data/repo/AuthRepository.kt`

- Uses `FirebaseAuth` for user authentication.
- Methods:
  - `suspend fun register(email: String, password: String): Result<String>`
  - `suspend fun login(email: String, password: String): Result<String>`
  - `fun currentUid(): String?`
  - `fun currentUserEmail(): String?`
  - `fun logout()`
- Returns Kotlin `Result` so UI can handle success or error cleanly.

2. `data/src/main/java/com/c2c/data/repo/VehicleRepository.kt`

- Uses `FirebaseFirestore` for vehicle data.
- Firestore path: `users/{uid}/vehicles/{vehicleId}`.
- Methods:
  - `suspend fun addVehicle(uid: String, vehicle: Vehicle): Result<String>`
  - `suspend fun getUserVehicles(uid: String): Result<List<Vehicle>>`
  - `suspend fun deleteVehicle(uid: String, vehicleId: String): Result<Unit>`
  - `suspend fun updateVehicle(uid: String, vehicle: Vehicle): Result<String>`

3. `data/src/main/java/com/c2c/data/repo/DeviceConfigRepository.kt`

- Uses `FirebaseDatabase` (Realtime Database) for ESP32 configuration.
- Path: `devices/{vehicleId}`.
- Method:
  - `suspend fun upsert(config: DeviceConfig)` – writes or updates the config.

**Role:**

- Abstracts away all Firebase calls from the UI.
- Implements the Repository pattern.

---

### 4.4 `:core-common` – Shared UI Utilities

**Folder:** `core-common/`

**File:**

- `core-common/src/main/java/com/c2c/core/common/Ui.kt`

  - Example composable:
    - `@Composable fun PrimaryButton(text: String, onClick: () -> Unit)` – a reusable, styled button.

**Role:**

- Contains shared composables and utilities to avoid duplication across feature modules.

---

### 4.5 `:feature-auth` – Authentication UI

**Folder:** `feature-auth/`

**File:**

- `feature-auth/src/main/java/com/c2c/feature/auth/AuthScreens.kt`

  - `@Composable fun LoginScreen(onSuccess: () -> Unit, onNavigateRegister: () -> Unit)`
    - UI for email + password login.
    - Uses `AuthRepository.login`.
    - On success, calls `onSuccess()` to notify the app that login succeeded.

  - `@Composable fun RegisterScreen(onSuccess: () -> Unit)`
    - UI for email, password, and confirm password.
    - Validates that the passwords match.
    - Uses `AuthRepository.register`.
    - On success, calls `onSuccess()` (app then moves to vehicle registration).

**Role:**

- Contains UI and flow for user registration and login.

---

### 4.6 `:feature-map` – Map Rendering

**Folder:** `feature-map/`

**File:**

- `feature-map/src/main/java/com/c2c/feature/map/MapScreen.kt`

  - `data class MapState`:
    - Represents what should be shown on the map: `vehicleId`, `lat`, `lon`, and `routePoints`.

  - `@Composable fun MapScreen(state: MapState, onMapLongClick: (LatLng) -> Unit = {})`
    - Wraps an Android `MapView` in an `AndroidView` for use in Compose.
    - Enables traffic layer.
    - Adds a marker at `lat, lon` if present.
    - Draws a polyline for `routePoints`.
    - Calls `onMapLongClick` when the user long-presses on the map.

  - `@Composable fun rememberMapViewWithLifecycle(): MapView`
    - Creates a `MapView` and wires its lifecycle methods (`onCreate`, `onStart`, etc.) to the Compose lifecycle.

**Role:**

- Encapsulates all direct interaction with `MapView` and Google Maps.

---

### 4.7 `:feature-alerts` – Alerts UI

**Folder:** `feature-alerts/`

**File:**

- `feature-alerts/src/main/java/com/c2c/feature/alerts/AlertsScreen.kt`

  - `data class AlertUI`:
    - UI model used by the app for alerts.
    - Fields: `title`, `message`, `lat`, `lon`, `isAccident`, `trafficLevel`, `timestamp`.

  - `@Composable fun AlertsScreen(alerts: List<AlertUI>, onEmergencyCall: () -> Unit)`
    - Shows a scrollable list of alerts as cards.
    - Each card displays:
      - Alert title
      - Message
      - Optional location (lat, lon)
      - Optional time, formatted from `timestamp`
    - Bottom button triggers `onEmergencyCall` (usually dials 108).

**Role:**

- Visual list and details of alerts for the dedicated Alerts tab.

---

### 4.8 `:feature-vehicle` – Vehicle Management

**Folder:** `feature-vehicle/`

**Files:**

1. `feature-vehicle/src/main/java/com/c2c/feature/vehicle/VehicleRegistrationScreen.kt`

  - `@Composable fun VehicleRegistrationScreen(onDone: () -> Unit)`
    - Collects vehicle information from the user:
      - License plate, brand, model, year, color.
    - Validates inputs (non-empty, year numeric, etc.).
    - Uses `AuthRepository.currentUid()` to ensure the user is logged in.
    - Creates `Vehicle` object and calls `VehicleRepository.addVehicle`.
    - On success, calls `onDone()` to navigate back.

2. `feature-vehicle/src/main/java/com/c2c/feature/vehicle/ProfileScreen.kt`

  - `@Composable fun ProfileScreen(...)`
    - Shows user profile and list of registered vehicles.
    - Uses `VehicleRepository.getUserVehicles` to fetch data.
    - Supports:
      - Adding a new vehicle (`onAddVehicle`)
      - Editing a vehicle (`onEditVehicle` callback)
      - Deleting a vehicle (`onDeleteVehicle` using `VehicleRepository.deleteVehicle`)
    - Also includes an "Account Settings" section with items like Notifications, Privacy, Help.

**Role:**

- Manages all vehicle-related UI: viewing, adding, updating, and deleting vehicles.

---

### 4.9 `:feature-esp32` – ESP32 Setup

**Folder:** `feature-esp32/`

**File:**

- `feature-esp32/src/main/java/com/c2c/feature/esp32/Esp32SetupScreen.kt`

  - `@Composable fun Esp32SetupScreen()`
    - UI for configuring ESP32 devices:
      - Vehicle ID
      - Wi-Fi SSID
      - Wi-Fi password
      - Upload interval (seconds)
    - On "Upload to Cloud":
      - Builds a `DeviceConfig` instance.
      - Uses `DeviceConfigRepository.upsert` to write it into Realtime DB under `devices/{vehicleId}`.
    - Shows a status message for success or error.

**Role:**

- Lets the user configure ESP32 settings from the app so the device can retrieve them from Firebase.

---

## 5. High-Level Data Flow

Conceptual flow:

```text
User taps UI (Compose screen)
      ↓
Feature module composable (e.g., LoginScreen, VehicleRegistrationScreen)
      ↓
Repository (AuthRepository, VehicleRepository, DeviceConfigRepository)
      ↓
Firebase service (Auth, Firestore, Realtime Database)
      ↓
Data/Events
      ↓
Compose state is updated (e.g., alerts list, vehicle list)
      ↓
UI recomposes and shows new information
```

---

This document should give you a clear picture of what languages are used, what counts as frontend vs backend, and what each main module and file is responsible for in your C2C Android app.