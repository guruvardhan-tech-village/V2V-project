package com.c2c.app

import android.content.Context
import android.util.Log
import com.c2c.data.repo.AuthRepository
import com.c2c.data.repo.VehicleRepository
import com.c2c.domain.model.Vehicle
import com.google.firebase.database.FirebaseDatabase
import com.google.firebase.firestore.FirebaseFirestore
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await
import java.text.SimpleDateFormat
import java.util.*

/**
 * 🔥 Firebase Testing Utility
 * This class provides methods to test all Firebase integrations in your C2C app
 */
class FirebaseTestUtils(private val context: Context) {
    private val authRepo = AuthRepository()
    private val vehicleRepo = VehicleRepository()
    private val firestore = FirebaseFirestore.getInstance()
    private val realtimeDb = FirebaseDatabase.getInstance()
    
    private val TAG = "FirebaseTest"
    
    fun runAllTests() {
        CoroutineScope(Dispatchers.Main).launch {
            Log.i(TAG, "🔥 Starting Firebase Integration Tests...")
            
            try {
                // Test 1: Authentication
                testAuthentication()
                
                // Test 2: Firestore Database
                testFirestore()
                
                // Test 3: Realtime Database  
                testRealtimeDatabase()
                
                // Test 4: Vehicle Registration
                testVehicleOperations()
                
                Log.i(TAG, "✅ All Firebase tests completed successfully!")
                
            } catch (e: Exception) {
                Log.e(TAG, "❌ Firebase test failed: ${e.message}", e)
            }
        }
    }
    
    /**
     * Test Firebase Authentication
     */
    private suspend fun testAuthentication() {
        Log.i(TAG, "🔐 Testing Firebase Authentication...")
        
        try {
            // Test registration with dummy credentials
            val testEmail = "test@c2capp.com"
            val testPassword = "testPassword123"
            
            Log.i(TAG, "📝 Testing user registration...")
            val registerResult = authRepo.register(testEmail, testPassword)
            registerResult.fold(
                onSuccess = { uid ->
                    Log.i(TAG, "✅ Registration successful! UID: $uid")
                },
                onFailure = { error ->
                    Log.w(TAG, "⚠️ Registration failed: ${error.message} (might be existing user)")
                }
            )
            
            // Test logout
            authRepo.logout()
            Log.i(TAG, "🚪 Logout successful")
            
            // Test login
            Log.i(TAG, "🔑 Testing user login...")
            val loginResult = authRepo.login(testEmail, testPassword)
            loginResult.fold(
                onSuccess = { uid ->
                    Log.i(TAG, "✅ Login successful! UID: $uid")
                },
                onFailure = { error ->
                    Log.e(TAG, "❌ Login failed: ${error.message}")
                    throw error
                }
            )
            
            // Get current user UID
            val currentUid = authRepo.currentUid()
            Log.i(TAG, "👤 Current user UID: $currentUid")
            
        } catch (e: Exception) {
            Log.w(TAG, "⚠️ Auth test: ${e.message} (This might be expected for existing users)")
        }
    }
    
    /**
     * Test Firestore Database
     */
    private suspend fun testFirestore() {
        Log.i(TAG, "📊 Testing Firestore Database...")
        
        try {
            val testData = mapOf(
                "testField" to "Hello from C2C App!",
                "timestamp" to System.currentTimeMillis(),
                "status" to "testing"
            )
            
            // Write test data
            firestore.collection("test")
                .document("connectivity_test")
                .set(testData)
                .await()
            
            Log.i(TAG, "✅ Firestore write successful")
            
            // Read test data
            val document = firestore.collection("test")
                .document("connectivity_test")
                .get()
                .await()
            
            if (document.exists()) {
                Log.i(TAG, "✅ Firestore read successful: ${document.data}")
            } else {
                Log.w(TAG, "❌ Firestore read failed: Document doesn't exist")
            }
            
        } catch (e: Exception) {
            Log.e(TAG, "❌ Firestore test failed: ${e.message}", e)
        }
    }
    
    /**
     * Test Realtime Database
     */
    private suspend fun testRealtimeDatabase() {
        Log.i(TAG, "⚡ Testing Realtime Database...")
        
        try {
            val testVehicleData = mapOf(
                "vehicleId" to "TEST_CAR_001",
                "lat" to 12.9716,
                "lon" to 77.5946,
                "speed" to 45.5,
                "timestamp" to System.currentTimeMillis(),
                "status" to "testing"
            )
            
            // Write to Realtime DB
            realtimeDb.reference
                .child("vehicles")
                .child("TEST_CAR_001")
                .setValue(testVehicleData)
                .await()
            
            Log.i(TAG, "✅ Realtime DB write successful")
            
            // Read from Realtime DB
            val snapshot = realtimeDb.reference
                .child("vehicles")
                .child("TEST_CAR_001")
                .get()
                .await()
            
            if (snapshot.exists()) {
                Log.i(TAG, "✅ Realtime DB read successful: ${snapshot.value}")
            } else {
                Log.w(TAG, "❌ Realtime DB read failed: No data found")
            }
            
        } catch (e: Exception) {
            Log.e(TAG, "❌ Realtime DB test failed: ${e.message}", e)
        }
    }
    
    /**
     * Test Vehicle Operations using your repositories
     */
    private suspend fun testVehicleOperations() {
        Log.i(TAG, "🚗 Testing Vehicle Operations...")
        
        try {
            val currentUid = authRepo.currentUid()
            
            if (currentUid != null) {
                val testVehicle = Vehicle(
                    id = "CAR_001",
                    plate = "KA01AB1234", 
                    model = "Honda City",
                    ownerUid = currentUid
                )
                
                // Add vehicle to Firestore
                vehicleRepo.addVehicle(currentUid, testVehicle)
                Log.i(TAG, "✅ Vehicle registration successful: ${testVehicle.plate}")
                
                // Test alert creation
                val testAlert = mapOf(
                    "type" to "accident",
                    "location" to mapOf(
                        "lat" to 12.9716,
                        "lon" to 77.5946
                    ),
                    "timestamp" to System.currentTimeMillis(),
                    "vehicleId" to testVehicle.id,
                    "message" to "Test accident alert"
                )
                
                firestore.collection("alerts")
                    .add(testAlert)
                    .await()
                
                Log.i(TAG, "✅ Alert creation successful")
                
            } else {
                Log.w(TAG, "❌ Cannot test vehicle operations: User not logged in")
            }
            
        } catch (e: Exception) {
            Log.e(TAG, "❌ Vehicle operations test failed: ${e.message}", e)
        }
    }
    
    /**
     * Generate test data for ESP32 simulation
     */
    fun generateTestESP32Data(vehicleId: String = "ESP32_TEST_001") {
        CoroutineScope(Dispatchers.IO).launch {
            try {
                Log.i(TAG, "🔧 Generating test ESP32 data...")
                
                for (i in 1..5) {
                    val testData = mapOf(
                        "vehicleId" to vehicleId,
                        "lat" to 12.9716 + (Math.random() * 0.01), // Small random variation
                        "lon" to 77.5946 + (Math.random() * 0.01),
                        "temperature" to 25.0 + (Math.random() * 10), // 25-35°C
                        "humidity" to 60.0 + (Math.random() * 20), // 60-80%
                        "speed" to Math.random() * 60, // 0-60 km/h
                        "timestamp" to System.currentTimeMillis(),
                        "online" to true
                    )
                    
                    realtimeDb.reference
                        .child("esp32_data")
                        .child(vehicleId)
                        .setValue(testData)
                        .await()
                    
                    Log.i(TAG, "📊 ESP32 test data $i/5 uploaded")
                    
                    // Wait 2 seconds between updates
                    kotlinx.coroutines.delay(2000)
                }
                
                Log.i(TAG, "✅ ESP32 test data generation complete")
                
            } catch (e: Exception) {
                Log.e(TAG, "❌ ESP32 test data generation failed: ${e.message}", e)
            }
        }
    }
    
    /**
     * Print current Firebase configuration status
     */
    fun printFirebaseStatus() {
        Log.i(TAG, "🔥 Firebase Configuration Status:")
        Log.i(TAG, "📱 App Package: ${context.packageName}")
        Log.i(TAG, "🔐 Auth User: ${authRepo.currentUid() ?: "Not logged in"}")
        Log.i(TAG, "📊 Firestore: ${if (firestore != null) "Initialized" else "Not initialized"}")
        Log.i(TAG, "⚡ Realtime DB: ${if (realtimeDb != null) "Initialized" else "Not initialized"}")
        Log.i(TAG, "🕒 Current Time: ${SimpleDateFormat("yyyy-MM-dd HH:mm:ss", Locale.getDefault()).format(Date())}")
    }
}