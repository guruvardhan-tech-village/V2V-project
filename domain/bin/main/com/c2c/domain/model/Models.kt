package com.c2c.domain.model
data class Vehicle(
    val id: String = "",
    val plate: String = "",
    val model: String = "",
    val ownerUid: String = "",
    val year: Int = 0,
    val color: String = "",
    val registrationDate: Long = System.currentTimeMillis(),
    val isActive: Boolean = true
)
data class Alert(val id:String="", val type:String="", val lat:Double=0.0, val lon:Double=0.0, val severity:Int=0, val message:String="", val ts:Long=0L)
data class DeviceConfig(val vehicleId:String="", val ssid:String="", val password:String="", val uploadIntervalSec:Int=5, val ownerUid:String="")
