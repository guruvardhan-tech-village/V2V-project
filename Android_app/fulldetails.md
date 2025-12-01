# Project C2C_v2 Documentation

This document provides a comprehensive overview of the C2C_v2 project structure, detailing the purpose of each module and key file. This should serve as a guide for any future development or modifications.

## Project Structure

The project follows a modular architecture, separating concerns into different layers and features. This makes the codebase easier to maintain, scale, and test.

### Root Directory

- `settings.gradle.kts`: This file defines the modules included in the project.
- `build.gradle.kts`: The root build file, used for global project configurations.
- `app/`: The main application module.
- `core-common/`: A library for common UI and utility code.
- `data/`: The data layer, responsible for handling data from various sources.
- `domain/`: The domain layer, containing the core business logic.
- `feature-alerts/`: A feature module for handling alerts.
- `feature-auth/`: A feature module for user authentication.
- `feature-esp32/`: A feature module for interacting with ESP32 devices.
- `feature-map/`: A feature module for displaying maps.
- `feature-vehicle/`: A feature module for vehicle-related functionalities.

---

## Modules

### `:app`

- **Folder:** `app/`
- **Purpose:** This is the main application module that brings all the other modules together to create the final Android application (`.apk`).
- **Key Files:**
    - `app/build.gradle.kts`: Declares dependencies on all the feature modules and other libraries required for the app. It also contains the application ID and signing configurations.
    - `app/src/main/java/`: Contains the main application class, activities, and the navigation graph that connects all the features.

### `:core-common`

- **Folder:** `core-common/`
- **Purpose:** This Android library module contains common code that is shared across different feature modules. This can include custom UI components (Composables), utility functions, and extension functions that are not specific to any feature.
- **Key Files:**
    - `core-common/build.gradle.kts`: Includes dependencies for UI libraries like Jetpack Compose.
    - `core-common/src/main/java/`: The source code for shared utilities and UI components.

### `:data`

- **Folder:** `data/`
- **Purpose:** This Android library module is the single source of truth for all the data in the application. It contains repositories that abstract away the data sources (e.g., Firebase, local database, network). It handles the logic for fetching and storing data.
- **Key Files:**
    - `data/build.gradle.kts`: Declares dependencies on data sources like Firebase Firestore, Firebase Realtime Database, and coroutines for asynchronous operations. It also has a dependency on the `:domain` module to use its models.
    - `data/src/main/java/`: Contains repository implementations and data source classes.

### `:domain`

- **Folder:** `domain/`
- **Purpose:** This is a pure Kotlin module, meaning it has no Android framework dependencies. It represents the core business logic of the application. It defines the data models (entities) and the use cases (interactors) that operate on that data. This separation makes the business logic platform-independent and easily testable.
- **Key Files:**
    - `domain/build.gradle.kts`: A simple configuration for a Kotlin JVM module.
    - `domain/src/main/java/`: Contains the data models (e.g., `User`, `Vehicle`) and use cases for the application.

### Feature Modules (`:feature-*`)

These are Android library modules, each representing a distinct feature of the application. This allows for better separation of concerns and makes the features self-contained.

#### `:feature-alerts`

- **Folder:** `feature-alerts/`
- **Purpose:** Manages and displays alerts to the user.
- **Dependencies:** `firebase-database`.

#### `:feature-auth`

- **Folder:** `feature-auth/`
- **Purpose:** Handles all user authentication-related screens and logic, such as login and registration.
- **Dependencies:** `:data`, `:core-common`, `firebase-auth`.

#### `:feature-esp32`

- **Folder:** `feature-esp32/`
- **Purpose:** Contains the functionality to interact with ESP32 microcontrollers, likely for receiving sensor data or controlling hardware.
- **Dependencies:** `:data`, `:domain`, `firebase-database`.

#### `:feature-map`

- **Folder:** `feature-map/`
- **Purpose:** Displays a map and related information.
- **Dependencies:** Google Maps SDK for Android, Maps Compose library.

#### `:feature-vehicle`

- **Folder:** `feature-vehicle/`
- **Purpose:** Manages vehicle-related information and functionalities, such as adding, viewing, and updating vehicle details.
- **Dependencies:** `:data`, `:domain`.


