# 🗺️ Your Google Maps Setup - Quick Guide

## 📋 Your App Details
- **Package Name**: `com.c2c.app`
- **SHA-1 Fingerprint**: `CA:29:C3:FC:0C:C5:36:D6:47:5C:84:BA:60:90:31:D7:09:50:99:07`

## ⚡ Quick Setup Steps

### 1. Get Google Maps API Key
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create new project: `C2C-CarToCar-App`
3. Enable **"Maps SDK for Android"** API
4. Create API key from **"Credentials"** section

### 2. Restrict Your API Key
In Google Cloud Console → Credentials → Your API Key:
- **Application restrictions**: Android apps
- **Package name**: `com.c2c.app`  
- **SHA-1 certificate fingerprint**: `CA:29:C3:FC:0C:C5:36:D6:47:5C:84:BA:60:90:31:D7:09:50:99:07`

### 3. Add API Key to App
Edit this file: `app/src/main/res/values/strings.xml`
```xml
<string name="google_maps_key">YOUR_ACTUAL_API_KEY_HERE</string>
```

### 4. Test
Run your app and navigate to the Maps screen!

## 🚨 Remember
- Keep your API key private
- Set up billing alerts in Google Cloud Console
- Monitor your usage (25,000 free map loads per month)