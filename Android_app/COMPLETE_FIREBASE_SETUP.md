# 🔥 Complete Firebase Setup Guide for C2C App

## 📧 Step 1: Google Account Setup

### Option A: Use Existing Google Account
- Use your primary Gmail account (e.g., `yourname@gmail.com`)
- This will be used for both Firebase Console AND Google Cloud Console

### Option B: Create New Google Account (Recommended for Projects)
1. Go to [accounts.google.com](https://accounts.google.com/signup)
2. Create new account: `yourname.c2cproject@gmail.com`
3. This keeps your project separate from personal account

## 🔥 Step 2: Create Firebase Project

### 2.1 Access Firebase Console
1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Sign in with your Google account
3. Click **"Create a project"** or **"Add project"**

### 2.2 Project Configuration
```
✏️ Project Name: C2C-CarToCar-System
📝 Project ID: c2c-cartocar-system (will be auto-generated)
🌍 Location: Choose closest region (e.g., asia-south1 for India)
📊 Enable Google Analytics: YES (recommended)
```

### 2.3 Analytics Configuration (if enabled)
```
📊 Analytics Account: Create new account
📍 Country: India (or your country)
✅ Accept Analytics terms
```

Click **"Create project"** → Wait 1-2 minutes

## 📱 Step 3: Add Android App to Firebase

### 3.1 Add App
1. In Firebase Console, click **"Add app"** → Select **Android** icon
2. **Register app**:
   ```
   📱 Android package name: com.c2c.app
   🏷️ App nickname: C2C Android App
   🔐 Debug signing certificate SHA-1: (copy from below)
   ```

### 3.2 Get SHA-1 Certificate (IMPORTANT!)
Open terminal in your project directory and run:
```bash
keytool -list -v -keystore "%USERPROFILE%\.android\debug.keystore" -alias androiddebugkey -storepass android -keypass android
```

**Copy this SHA-1 fingerprint**: `CA:29:C3:FC:0C:C5:36:D6:47:5C:84:BA:60:90:31:D7:09:50:99:07`

### 3.3 Download Configuration File
1. Click **"Register app"**
2. **Download** `google-services.json`
3. **IMPORTANT**: Place this file in your project at:
   ```
   C2C_v2/app/google-services.json
   ```

## ⚙️ Step 4: Enable Firebase Services

### 4.1 Authentication Setup
1. In Firebase Console → **Authentication**
2. Click **"Get started"**
3. Go to **"Sign-in method"** tab
4. **Enable Email/Password**:
   - Click on **"Email/Password"**
   - Toggle **"Enable"** → Save
5. **Optional**: Enable other methods (Google Sign-In, etc.)

### 4.2 Firestore Database Setup
1. In Firebase Console → **Firestore Database**
2. Click **"Create database"**
3. **Security rules**: Start in **test mode** (we'll secure later)
   ```javascript
   rules_version = '2';
   service cloud.firestore {
     match /databases/{database}/documents {
       match /{document=**} {
         allow read, write: if request.time < timestamp.date(2024, 12, 31);
       }
     }
   }
   ```
4. **Location**: Choose closest region
   ```
   🌍 Recommended for India: asia-south1 (Mumbai)
   🌍 Alternative: us-central1 (if Mumbai not available)
   ```

### 4.3 Realtime Database Setup
1. In Firebase Console → **Realtime Database**
2. Click **"Create Database"**
3. **Location**: Same as Firestore
4. **Security rules**: Start in **test mode**
   ```json
   {
     "rules": {
       ".read": "auth != null",
       ".write": "auth != null"
     }
   }
   ```

### 4.4 Storage Setup (Optional - for ESP32 images/videos)
1. In Firebase Console → **Storage**
2. Click **"Get started"**
3. **Security rules**: Test mode initially
4. **Location**: Same as other services

## 🌐 Step 5: Connect Google Cloud Console

### 5.1 Access Google Cloud Console
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. **Sign in with the SAME Google account** used for Firebase
3. You should see your Firebase project listed

### 5.2 Enable Required APIs
In Google Cloud Console, go to **"APIs & Services"** → **"Library"**

**Enable these APIs for Maps integration:**
- ✅ **Maps SDK for Android**
- ✅ **Places API** (optional - for location search)
- ✅ **Directions API** (optional - for route planning)
- ✅ **Geocoding API** (optional - for address conversion)

### 5.3 Create Maps API Key
1. Go to **"APIs & Services"** → **"Credentials"**
2. Click **"+ CREATE CREDENTIALS"** → **"API key"**
3. **Copy the API key** (save it safely!)
4. **Restrict the API key**:
   - Click on the API key to edit
   - **Application restrictions** → **Android apps**
   - **Add an item**:
     ```
     Package name: com.c2c.app
     SHA-1: CA:29:C3:FC:0C:C5:36:D6:47:5C:84:BA:60:90:31:D7:09:50:99:07
     ```
   - **API restrictions** → **Restrict key**
   - Select: Maps SDK for Android, Places API, Directions API

## 📝 Step 6: Update Your App Configuration

### 6.1 Add Google Maps API Key
Edit: `app/src/main/res/values/strings.xml`
```xml
<string name="google_maps_key">AIzaSyYourActualAPIKeyHere</string>
```

### 6.2 Verify google-services.json
Check that your `app/google-services.json` contains:
```json
{
  "project_info": {
    "project_id": "your-project-id",
    "project_number": "123456789"
  },
  "client": [{
    "client_info": {
      "android_client_info": {
        "package_name": "com.c2c.app"
      }
    }
  }]
}
```

## 🧪 Step 7: Test Your Setup

### 7.1 Build and Run App
```bash
./gradlew build
# Run app in Android Studio
```

### 7.2 Test Firebase Integration
1. Open your C2C app
2. Navigate to Home Dashboard
3. Click **"🔥 Test Firebase Integration"**
4. Check Android Studio Logcat (filter: `FirebaseTest`)

**Expected logs:**
```
🔥 Starting Firebase Integration Tests...
🔐 Testing Firebase Authentication...
✅ Registration successful! UID: ABC123...
📊 Testing Firestore Database...
✅ Firestore write successful
⚡ Testing Realtime Database...
✅ Realtime DB write successful
✅ All Firebase tests completed successfully!
```

### 7.3 Verify in Firebase Console
1. **Authentication** → Should see `test@c2capp.com` user
2. **Firestore** → Should see `test/connectivity_test` document
3. **Realtime Database** → Should see `vehicles/TEST_CAR_001` data

## 🔒 Step 8: Security & Production Setup

### 8.1 Update Firestore Rules (After testing)
```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Users can only access their own data
    match /users/{userId}/{document=**} {
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }
    
    // Alerts are readable by all authenticated users
    match /alerts/{alertId} {
      allow read: if request.auth != null;
      allow write: if request.auth != null;
    }
  }
}
```

### 8.2 Update Realtime Database Rules
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
    },
    "esp32_data": {
      ".read": "auth != null",
      ".write": "auth != null"
    }
  }
}
```

## 💰 Step 9: Billing & Quotas Setup

### 9.1 Set up Billing (Important!)
1. In Google Cloud Console → **Billing**
2. **Link billing account** (even for free tier)
3. **Set up billing alerts**:
   - Budget: $10/month initially
   - Alerts at 50%, 90%, 100%

### 9.2 Monitor Usage
- **Firebase Console** → **Usage and billing**
- **Google Cloud Console** → **APIs & Services** → **Quotas**

**Free Tier Limits:**
- 🔐 **Authentication**: 10,000 phone auths/month
- 📊 **Firestore**: 50K reads, 20K writes, 20K deletes/day
- ⚡ **Realtime DB**: 100 concurrent connections, 1GB transferred/month
- 🗺️ **Maps**: 28,000 map loads/month

## 🆘 Troubleshooting

### Common Issues:

**1. "Default FirebaseApp is not initialized"**
```
Solution: Ensure google-services.json is in app/ directory
Check: Build → Rebuild Project
```

**2. "API key not valid"**
```
Solution: 
- Verify API key is correct in strings.xml
- Check API key restrictions in Google Cloud Console
- Ensure SHA-1 fingerprint matches
```

**3. "Permission denied" in Firebase**
```
Solution:
- Check Firebase security rules
- Ensure user is authenticated
- Verify database rules allow read/write
```

**4. "Project not found"**
```
Solution:
- Ensure same Google account for Firebase & Google Cloud
- Check project ID matches in google-services.json
```

## 📞 Need Help?

If you encounter issues:
1. **Check Firebase Console** → **Project Overview** for setup status
2. **Google Cloud Console** → **APIs & Services** → **Dashboard** for API usage
3. **Android Studio Logcat** with filter `Firebase` or `FirebaseTest`
4. **Firebase Documentation**: [firebase.google.com/docs](https://firebase.google.com/docs)

---

## ✅ Final Checklist

- [ ] Created Firebase project with same Google account as Google Cloud
- [ ] Added Android app with correct package name (`com.c2c.app`)
- [ ] Downloaded and placed `google-services.json` in `/app` directory  
- [ ] Added SHA-1 fingerprint to Firebase project
- [ ] Enabled Authentication (Email/Password)
- [ ] Created Firestore database in test mode
- [ ] Created Realtime database in test mode
- [ ] Enabled Maps SDK for Android in Google Cloud Console
- [ ] Created and restricted Maps API key
- [ ] Added API key to `strings.xml`
- [ ] Tested Firebase integration in app
- [ ] Verified data appears in Firebase Console

**🎉 Your Firebase is now fully configured for your C2C Car-to-Car Communication app!**