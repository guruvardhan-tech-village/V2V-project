plugins {
    id("com.android.library")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.c2c.data"
    compileSdk = 36

    defaultConfig {
        minSdk = 24
        targetSdk = 36
        // versionCode/Name are NOT needed for library modules
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    // ⛔ Data layer does not need Compose UI:
    // buildFeatures { compose = true }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions { jvmTarget = "17" }
}

dependencies {
    implementation(project(":domain"))

    implementation("androidx.core:core-ktx:1.17.0")

    // Coroutines (Firebase tasks -> await())
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-core:1.9.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")

    // Firebase
    implementation(platform("com.google.firebase:firebase-bom:33.7.0"))
    implementation("com.google.firebase:firebase-auth-ktx")
    implementation("com.google.firebase:firebase-firestore-ktx")
    implementation("com.google.firebase:firebase-database-ktx")
}
