# 🚀 Quick Setup Reference Card

## 📧 **IMPORTANT: Use Same Google Account**
- **Firebase Console**: [console.firebase.google.com](https://console.firebase.google.com)
- **Google Cloud Console**: [console.cloud.google.com](https://console.cloud.google.com)
- ✅ **Use the SAME Gmail account for both!**

---

## 🔑 **Your Project Details**
```
📱 Package Name: com.c2c.app
🔐 SHA-1 Fingerprint: CA:29:C3:FC:0C:C5:36:D6:47:5C:84:BA:60:90:31:D7:09:50:99:07
📊 Current Project ID: car-to-car-f53c2
🌍 Recommended Region: asia-south1 (Mumbai)
```

---

## ⚡ **Step-by-Step Checklist**

### 🔥 Firebase Console Setup
- [ ] 1. Go to [Firebase Console](https://console.firebase.google.com)
- [ ] 2. Create project: `C2C-CarToCar-System`
- [ ] 3. Add Android app with package: `com.c2c.app`
- [ ] 4. Add SHA-1: `CA:29:C3:FC:0C:C5:36:D6:47:5C:84:BA:60:90:31:D7:09:50:99:07`
- [ ] 5. Download `google-services.json` → Place in `/app` folder
- [ ] 6. Enable **Authentication** → Email/Password
- [ ] 7. Create **Firestore Database** (test mode)
- [ ] 8. Create **Realtime Database** (test mode)

### 🗺️ Google Cloud Console Setup
- [ ] 9. Go to [Google Cloud Console](https://console.cloud.google.com)
- [ ] 10. Select your Firebase project (same account!)
- [ ] 11. Enable **Maps SDK for Android** API
- [ ] 12. Create **API Key** → Restrict to Android apps
- [ ] 13. Add restrictions: package `com.c2c.app` + SHA-1 fingerprint
- [ ] 14. Copy API key → Replace in `strings.xml`

### 📱 App Configuration
- [ ] 15. Build project: `.\gradlew build`
- [ ] 16. Run app → Test Firebase integration
- [ ] 17. Check logs: Filter `FirebaseTest` in Android Studio

---

## 🧪 **Quick Test Commands**

### Get SHA-1 Fingerprint:
```bash
keytool -list -v -keystore "%USERPROFILE%\.android\debug.keystore" -alias androiddebugkey -storepass android -keypass android
```

### Build App:
```bash
.\gradlew build --no-daemon
```

---

## 🔍 **Troubleshooting Quick Fixes**

**Firebase not initialized?**
→ Check `google-services.json` is in `/app` directory

**Maps not loading?**
→ Verify API key in `strings.xml` and restrictions in Google Cloud Console

**Permission denied?**
→ Enable test mode in Firebase Database rules

**Same account issues?**
→ Sign out from all Google services, sign in with one account for both Firebase and Google Cloud

---

## 📊 **Expected Test Results**

When you click "🔥 Test Firebase Integration" in your app:
```
✅ Registration successful! UID: ABC123...
✅ Firestore write successful
✅ Realtime DB write successful  
✅ Vehicle registration successful: KA01AB1234
✅ All Firebase tests completed successfully!
```

**Check Firebase Console for:**
- Authentication → `test@c2capp.com` user
- Firestore → `test/connectivity_test` document  
- Realtime DB → `vehicles/TEST_CAR_001` data

---

## 🆘 **Need Help?**
1. Check `COMPLETE_FIREBASE_SETUP.md` for detailed instructions
2. Check `FIREBASE_TESTING_GUIDE.md` for testing help
3. Filter Android Studio logs by `FirebaseTest` or `Firebase`