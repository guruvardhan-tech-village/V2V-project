pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

plugins {
    id("org.gradle.toolchains.foojay-resolver-convention") version "0.8.0"
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
include(":feature-alerts")
include(":feature-auth")
include(":feature-esp32")
include(":feature-map")
include(":feature-vehicle")
include(":domain")
