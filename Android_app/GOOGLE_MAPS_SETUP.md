# 🗺️ Google Maps API Setup Guide

## Step 1: Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Click **"Select a project"** → **"New Project"**
3. Enter project name: `C2C-CarToCar-App`
4. Click **"Create"**

## Step 2: Enable Maps API

1. In the Google Cloud Console, go to **"APIs & Services"** → **"Library"**
2. Search for and enable these APIs:
   - ✅ **Maps SDK for Android**
   - ✅ **Places API** (optional, for address search)
   - ✅ **Directions API** (optional, for route planning)

## Step 3: Create API Key

1. Go to **"APIs & Services"** → **"Credentials"**
2. Click **"+ CREATE CREDENTIALS"** → **"API key"**
3. Copy the generated API key (keep it safe!)

## Step 4: Restrict API Key (Security)

1. Click on your API key to edit it
2. Under **"Application restrictions"**:
   - Select **"Android apps"**
   - Click **"+ Add an item"**
   - Package name: `com.c2c.app`
   - SHA-1 certificate fingerprint: (get from next step)

## Step 5: Get SHA-1 Fingerprint

Run this command in your project directory:
```bash
# For debug keystore (development)
keytool -list -v -keystore "%USERPROFILE%\.android\debug.keystore" -alias androiddebugkey -storepass android -keypass android

# Look for "SHA1:" in the output and copy that value
```

## Step 6: Add API Key to Your App

1. Open `app/src/main/res/values/strings.xml`
2. Replace `YOUR_API_KEY_HERE` with your actual API key:

```xml
<string name="google_maps_key">AIzaSyC4YourActualAPIKeyHere</string>
```

## Step 7: Test Maps

Build and run your app. Navigate to the Maps screen to verify it loads correctly.

## 🚨 Important Security Notes

- Never commit API keys to version control
- Use environment variables or build variants for production
- Restrict API keys to specific packages and SHA-1 fingerprints
- Monitor usage in Google Cloud Console

## 💰 Pricing Information

- Google Maps API has free tier: 25,000 map loads per month
- After free tier: $7 per 1,000 additional map loads
- Set up billing alerts to monitor usage

## 🔧 Troubleshooting

### Map shows gray screen:
- Check if API key is correct
- Verify SHA-1 fingerprint matches
- Check if Maps SDK for Android is enabled

### "This app isn't authorized" error:
- Add your package name and SHA-1 fingerprint to API key restrictions
- Wait 5-10 minutes for changes to propagate

### No internet connection:
- Add INTERNET permission to AndroidManifest.xml (already done)
- Check device internet connection
- 
  AIzaSyDWrWFt5RPlulSwkfOCm2cJ0JRtNrO7P8c