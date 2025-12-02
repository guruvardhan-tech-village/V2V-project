# ProGuard / R8 rules for C2C app
# This file is intentionally minimal. Add keep rules here if you see any
# class-not-found / reflection-related issues in release builds.

# Keep Firebase model classes and avoid stripping needed annotations
-keep class com.google.firebase.** { *; }
-keep class com.google.android.gms.** { *; }

# Keep Kotlin metadata
-keepclassmembers class kotlin.Metadata { *; }
