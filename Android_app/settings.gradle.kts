pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
    plugins {
        id("com.android.application") version "8.13.1" apply false
        id("com.android.library") version "8.13.1" apply false
        id("org.jetbrains.kotlin.android") version "1.9.22" apply false
        id("org.jetbrains.kotlin.jvm") version "1.9.22" apply false
        id("org.jetbrains.kotlin.plugin.compose") version "1.6.21" apply false
        id("com.google.gms.google-services") version "4.4.2" apply false
        id("com.google.android.libraries.mapsplatform.secrets-gradle-plugin") version "2.0.1" apply false
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "C2C_v2"
include(":app")
include(":core-common")
include(":data")
include(":domain")
include(":feature-alerts")
include(":feature-auth")
include(":feature-esp32")
include(":feature-map")
include(":feature-vehicle")
