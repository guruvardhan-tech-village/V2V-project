plugins {
    // Use version from settings.gradle.kts pluginManagement to avoid duplicate plugin loading
    kotlin("jvm")
}

java {
    toolchain {
        languageVersion.set(JavaLanguageVersion.of(17))
    }
}

dependencies {
    implementation(kotlin("stdlib"))
}
