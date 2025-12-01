package com.c2c.feature.vehicle

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.c2c.data.repo.AuthRepository
import com.c2c.data.repo.VehicleRepository
import com.c2c.domain.model.Vehicle
import kotlinx.coroutines.launch

@Composable
fun VehicleRegistrationScreen(onDone: () -> Unit) {
    val auth = remember { AuthRepository() }
    val repo = remember { VehicleRepository() }
    var plate by remember { mutableStateOf("") }
    var model by remember { mutableStateOf("") }
    var brand by remember { mutableStateOf("") }
    var year by remember { mutableStateOf("") }
    var color by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var isLoading by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    
    Column(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        Text(
            "Vehicle Registration",
            style = MaterialTheme.typography.headlineSmall
        )
        
        OutlinedTextField(
            value = plate,
            onValueChange = { plate = it.uppercase(); error = null },
            label = { Text("License Plate Number") },
            placeholder = { Text("e.g., KA01AB1234") },
            modifier = Modifier.fillMaxWidth(),
            enabled = !isLoading
        )
        
        OutlinedTextField(
            value = brand,
            onValueChange = { brand = it; error = null },
            label = { Text("Brand") },
            placeholder = { Text("e.g., Honda, Toyota, Maruti") },
            modifier = Modifier.fillMaxWidth(),
            enabled = !isLoading
        )
        
        OutlinedTextField(
            value = model,
            onValueChange = { model = it; error = null },
            label = { Text("Model") },
            placeholder = { Text("e.g., City, Camry, Swift") },
            modifier = Modifier.fillMaxWidth(),
            enabled = !isLoading
        )
        
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            OutlinedTextField(
                value = year,
                onValueChange = { if (it.length <= 4 && it.all { char -> char.isDigit() }) { year = it; error = null } },
                label = { Text("Year") },
                placeholder = { Text("2023") },
                modifier = Modifier.weight(1f),
                enabled = !isLoading
            )
            
            OutlinedTextField(
                value = color,
                onValueChange = { color = it; error = null },
                label = { Text("Color") },
                placeholder = { Text("White") },
                modifier = Modifier.weight(1f),
                enabled = !isLoading
            )
        }
        
        Button(
            onClick = {
                scope.launch {
                    isLoading = true
                    error = null
                    
                    try {
                        val uid = auth.currentUid()
                        if (uid == null) {
                            error = "Please log in first"
                            isLoading = false
                            return@launch
                        }
                        
                        if (plate.isBlank()) {
                            error = "License plate is required"
                            isLoading = false
                            return@launch
                        }
                        
                        val vehicle = Vehicle(
                            id = plate,
                            plate = plate,
                            model = "$brand $model".trim(),
                            ownerUid = uid,
                            year = year.toIntOrNull() ?: 0,
                            color = color
                        )
                        
                        val result = repo.addVehicle(uid, vehicle)
                        result.fold(
                            onSuccess = {
                                isLoading = false
                                onDone()
                            },
                            onFailure = { throwable ->
                                isLoading = false
                                error = throwable.message
                            }
                        )
                        
                    } catch (t: Throwable) {
                        isLoading = false
                        error = t.message
                    }
                }
            },
            modifier = Modifier.fillMaxWidth(),
            enabled = !isLoading && plate.isNotBlank() && (brand.isNotBlank() || model.isNotBlank())
        ) {
            if (isLoading) {
                CircularProgressIndicator(modifier = Modifier.size(20.dp))
            } else {
                Text("Register Vehicle")
            }
        }
        
        if (error != null) {
            Text(
                text = "Error: $error",
                color = MaterialTheme.colorScheme.error,
                modifier = Modifier.fillMaxWidth()
            )
        }
    }
}
