package com.c2c.data.repo

import android.util.Log
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.auth.FirebaseAuthException
import kotlinx.coroutines.tasks.await

class AuthRepository(private val auth: FirebaseAuth = FirebaseAuth.getInstance()) {
    
    private val TAG = "AuthRepository"
    
    suspend fun register(email: String, password: String): Result<String> {
        return try {
            Log.d(TAG, "🔐 Attempting registration for email: $email")
            
            // Validate inputs
            if (email.isBlank()) {
                throw IllegalArgumentException("Email cannot be empty")
            }
            if (password.length < 6) {
                throw IllegalArgumentException("Password must be at least 6 characters")
            }
            
            val result = auth.createUserWithEmailAndPassword(email, password).await()
            val uid = result.user?.uid
            
            if (uid != null) {
                Log.d(TAG, "✅ Registration successful! UID: $uid")
                Result.success(uid)
            } else {
                Log.e(TAG, "❌ Registration failed: User is null")
                Result.failure(Exception("Registration failed: User is null"))
            }
            
        } catch (e: FirebaseAuthException) {
            Log.e(TAG, "❌ Registration failed with Firebase error: ${e.errorCode} - ${e.message}")
            Result.failure(Exception(getFirebaseErrorMessage(e.errorCode)))
        } catch (e: Exception) {
            Log.e(TAG, "❌ Registration failed with error: ${e.message}", e)
            Result.failure(e)
        }
    }
    
    suspend fun login(email: String, password: String): Result<String> {
        return try {
            Log.d(TAG, "🔑 Attempting login for email: $email")
            
            // Validate inputs
            if (email.isBlank()) {
                throw IllegalArgumentException("Email cannot be empty")
            }
            if (password.isBlank()) {
                throw IllegalArgumentException("Password cannot be empty")
            }
            
            val result = auth.signInWithEmailAndPassword(email, password).await()
            val uid = result.user?.uid
            
            if (uid != null) {
                Log.d(TAG, "✅ Login successful! UID: $uid")
                Log.d(TAG, "📧 User email: ${result.user?.email}")
                Log.d(TAG, "🔐 User verified: ${result.user?.isEmailVerified}")
                Result.success(uid)
            } else {
                Log.e(TAG, "❌ Login failed: User is null")
                Result.failure(Exception("Login failed: User is null"))
            }
            
        } catch (e: FirebaseAuthException) {
            Log.e(TAG, "❌ Login failed with Firebase error: ${e.errorCode} - ${e.message}")
            Result.failure(Exception(getFirebaseErrorMessage(e.errorCode)))
        } catch (e: Exception) {
            Log.e(TAG, "❌ Login failed with error: ${e.message}", e)
            Result.failure(e)
        }
    }
    
    fun currentUid(): String? {
        val uid = auth.currentUser?.uid
        Log.d(TAG, "👤 Current user UID: ${uid ?: "Not logged in"}")
        return uid
    }
    
    fun currentUserEmail(): String? {
        val email = auth.currentUser?.email
        Log.d(TAG, "📧 Current user email: ${email ?: "Not logged in"}")
        return email
    }
    
    fun logout() {
        Log.d(TAG, "🚪 Logging out user: ${auth.currentUser?.email}")
        auth.signOut()
        Log.d(TAG, "✅ Logout successful")
    }
    
    private fun getFirebaseErrorMessage(errorCode: String): String {
        return when (errorCode) {
            "ERROR_INVALID_EMAIL" -> "Invalid email address format"
            "ERROR_WRONG_PASSWORD" -> "Incorrect password"
            "ERROR_USER_NOT_FOUND" -> "No account found with this email"
            "ERROR_USER_DISABLED" -> "This account has been disabled"
            "ERROR_TOO_MANY_REQUESTS" -> "Too many failed attempts. Try again later"
            "ERROR_EMAIL_ALREADY_IN_USE" -> "Email address is already registered"
            "ERROR_WEAK_PASSWORD" -> "Password is too weak. Use at least 6 characters"
            "ERROR_NETWORK_REQUEST_FAILED" -> "Network error. Check your internet connection"
            else -> "Authentication failed: $errorCode"
        }
    }
}
