package com.c2c.data.repo
import com.c2c.domain.model.DeviceConfig
import com.google.firebase.database.FirebaseDatabase
import kotlinx.coroutines.tasks.await
class DeviceConfigRepository(private val rt: FirebaseDatabase = FirebaseDatabase.getInstance()) {
  suspend fun upsert(config: DeviceConfig) {
    rt.reference.child("devices").child(config.vehicleId).setValue(config).await()
  }
}
