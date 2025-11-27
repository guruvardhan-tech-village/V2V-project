package com.c2c.data.repo

import android.util.Log
import com.c2c.domain.model.Vehicle
import com.google.firebase.firestore.FirebaseFirestore
import kotlinx.coroutines.tasks.await

class VehicleRepository(private val db: FirebaseFirestore = FirebaseFirestore.getInstance()) {
    
    private val TAG = "VehicleRepository"
    
    suspend fun addVehicle(uid: String, vehicle: Vehicle): Result<String> {
        return try {
            Log.d(TAG, "🚗 Adding vehicle: ${vehicle.plate} for user: $uid")
            
            val vehicleId = vehicle.id.ifEmpty { vehicle.plate }
            db.collection("users")
                .document(uid)
                .collection("vehicles")
                .document(vehicleId)
                .set(vehicle)
                .await()
            
            Log.d(TAG, "✅ Vehicle added successfully: ${vehicle.plate}")
            Result.success(vehicleId)
        } catch (e: Exception) {
            Log.e(TAG, "❌ Failed to add vehicle: ${e.message}", e)
            Result.failure(e)
        }
    }
    
    suspend fun getUserVehicles(uid: String): Result<List<Vehicle>> {
        return try {
            Log.d(TAG, "🚗 Fetching vehicles for user: $uid")
            
            val snapshot = db.collection("users")
                .document(uid)
                .collection("vehicles")
                .get()
                .await()
            
            val vehicles = snapshot.documents.mapNotNull { document ->
                document.toObject(Vehicle::class.java)
            }
            
            Log.d(TAG, "✅ Retrieved ${vehicles.size} vehicles for user: $uid")
            Result.success(vehicles)
        } catch (e: Exception) {
            Log.e(TAG, "❌ Failed to fetch vehicles: ${e.message}", e)
            Result.failure(e)
        }
    }
    
    suspend fun deleteVehicle(uid: String, vehicleId: String): Result<Unit> {
        return try {
            Log.d(TAG, "🗑️ Deleting vehicle: $vehicleId for user: $uid")
            
            db.collection("users")
                .document(uid)
                .collection("vehicles")
                .document(vehicleId)
                .delete()
                .await()
            
            Log.d(TAG, "✅ Vehicle deleted successfully: $vehicleId")
            Result.success(Unit)
        } catch (e: Exception) {
            Log.e(TAG, "❌ Failed to delete vehicle: ${e.message}", e)
            Result.failure(e)
        }
    }
    
    suspend fun updateVehicle(uid: String, vehicle: Vehicle): Result<String> {
        return try {
            Log.d(TAG, "✏️ Updating vehicle: ${vehicle.plate} for user: $uid")
            
            val vehicleId = vehicle.id.ifEmpty { vehicle.plate }
            db.collection("users")
                .document(uid)
                .collection("vehicles")
                .document(vehicleId)
                .set(vehicle)
                .await()
            
            Log.d(TAG, "✅ Vehicle updated successfully: ${vehicle.plate}")
            Result.success(vehicleId)
        } catch (e: Exception) {
            Log.e(TAG, "❌ Failed to update vehicle: ${e.message}", e)
            Result.failure(e)
        }
    }
}
