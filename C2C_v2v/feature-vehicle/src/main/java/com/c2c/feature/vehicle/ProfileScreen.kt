package com.c2c.feature.vehicle

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.DirectionsCar
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.ExitToApp
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Help
import androidx.compose.material.icons.filled.Info
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Language
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.ChevronRight
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.c2c.data.repo.AuthRepository
import com.c2c.data.repo.VehicleRepository
import com.c2c.domain.model.Vehicle
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.*

@Composable
fun ProfileScreen(
    currentUserId: String? = null,
    currentUserEmail: String? = null,
    onAddVehicle: () -> Unit,
    onEditVehicle: (Vehicle) -> Unit = {},
    onLogout: () -> Unit
) {
    val authRepo = remember { AuthRepository() }
    val vehicleRepo = remember { VehicleRepository() }
    var vehicles by remember { mutableStateOf<List<Vehicle>>(emptyList()) }
    var isLoading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    
    val currentUser = currentUserId ?: authRepo.currentUid()
    val userEmail = currentUserEmail ?: authRepo.currentUserEmail() ?: "User"
    
    // Load vehicles when screen opens
    LaunchedEffect(currentUser) {
        if (currentUser != null) {
            scope.launch {
                val result = vehicleRepo.getUserVehicles(currentUser)
                result.fold(
                    onSuccess = { vehicleList ->
                        vehicles = vehicleList
                        isLoading = false
                    },
                    onFailure = { throwable ->
                        error = throwable.message
                        isLoading = false
                    }
                )
            }
        } else {
            isLoading = false
        }
    }
    
    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // Profile Header
        item {
            ProfileHeader(
                userEmail = userEmail,
                onLogout = onLogout
            )
        }
        
        // Vehicles Section
        item {
            VehiclesSection(
                vehicles = vehicles,
                isLoading = isLoading,
                error = error,
                onAddVehicle = onAddVehicle,
                onEditVehicle = onEditVehicle,
                onDeleteVehicle = { vehicle ->
                    scope.launch {
                        currentUser?.let { uid ->
                            vehicleRepo.deleteVehicle(uid, vehicle.id).fold(
                                onSuccess = {
                                    vehicles = vehicles.filter { it.id != vehicle.id }
                                },
                                onFailure = { throwable ->
                                    error = throwable.message
                                }
                            )
                        }
                    }
                }
            )
        }
        
        // Account Settings Section  
        item {
            AccountSettingsSection()
        }
    }
}

@Composable
private fun ProfileHeader(
    userEmail: String,
    onLogout: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(20.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column {
                    Text(
                        text = "Welcome Back!",
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold
                    )
                    Text(
                        text = userEmail,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                    )
                }
                
                IconButton(onClick = onLogout) {
                    Icon(
                        Icons.Default.ExitToApp,
                        contentDescription = "Logout",
                        tint = MaterialTheme.colorScheme.onPrimaryContainer
                    )
                }
            }
        }
    }
}

@Composable
private fun VehiclesSection(
    vehicles: List<Vehicle>,
    isLoading: Boolean,
    error: String?,
    onAddVehicle: () -> Unit,
    onEditVehicle: (Vehicle) -> Unit,
    onDeleteVehicle: (Vehicle) -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "My Vehicles",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold
                )
                
                IconButton(onClick = onAddVehicle) {
                    Icon(
                        Icons.Default.Add,
                        contentDescription = "Add Vehicle",
                        tint = MaterialTheme.colorScheme.primary
                    )
                }
            }
            
            Spacer(modifier = Modifier.height(12.dp))
            
            when {
                isLoading -> {
                    Box(
                        modifier = Modifier.fillMaxWidth().padding(32.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        CircularProgressIndicator()
                    }
                }
                
                error != null -> {
                    Text(
                        text = "Error loading vehicles: $error",
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.padding(16.dp)
                    )
                }
                
                vehicles.isEmpty() -> {
                    EmptyVehiclesState(onAddVehicle = onAddVehicle)
                }
                
                else -> {
                    vehicles.forEach { vehicle ->
                        VehicleCard(
                            vehicle = vehicle,
                            onEdit = { onEditVehicle(vehicle) },
                            onDelete = { onDeleteVehicle(vehicle) }
                        )
                        Spacer(modifier = Modifier.height(8.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun EmptyVehiclesState(onAddVehicle: () -> Unit) {
    Column(
        modifier = Modifier.fillMaxWidth().padding(32.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Icon(
            Icons.Default.DirectionsCar,
            contentDescription = null,
            modifier = Modifier.size(64.dp),
            tint = MaterialTheme.colorScheme.outline
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        Text(
            text = "No vehicles registered",
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
        )
        
        Text(
            text = "Add your first vehicle to get started",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
        )
        
        Spacer(modifier = Modifier.height(16.dp))
        
        Button(
            onClick = onAddVehicle,
            modifier = Modifier.fillMaxWidth()
        ) {
            Icon(Icons.Default.Add, contentDescription = null)
            Spacer(modifier = Modifier.width(8.dp))
            Text("Add Your First Vehicle")
        }
    }
}

@Composable
private fun VehicleCard(
    vehicle: Vehicle,
    onEdit: () -> Unit,
    onDelete: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = vehicle.plate,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                    
                    Text(
                        text = vehicle.model,
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                    )
                    
                    if (vehicle.year > 0 && vehicle.color.isNotBlank()) {
                        Text(
                            text = "${vehicle.year} • ${vehicle.color}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.5f)
                        )
                    }
                }
                
                Row {
                    IconButton(onClick = onEdit) {
                        Icon(
                            Icons.Default.Edit,
                            contentDescription = "Edit Vehicle",
                            modifier = Modifier.size(20.dp)
                        )
                    }
                    
                    IconButton(onClick = onDelete) {
                        Icon(
                            Icons.Default.Delete,
                            contentDescription = "Delete Vehicle",
                            modifier = Modifier.size(20.dp),
                            tint = MaterialTheme.colorScheme.error
                        )
                    }
                }
            }
            
            // Registration date
            Text(
                text = "Registered: ${formatDate(vehicle.registrationDate)}",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.4f),
                modifier = Modifier.padding(top = 8.dp)
            )
        }
    }
}

@Composable  
private fun AccountSettingsSection() {
    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Text(
                text = "Account Settings",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold
            )
            
            Spacer(modifier = Modifier.height(12.dp))
            
            SettingsItem(
                icon = Icons.Default.Person,
                title = "Profile Information",
                subtitle = "Update your personal details"
            )
            
            SettingsItem(
                icon = Icons.Default.Notifications,
                title = "Notifications", 
                subtitle = "Manage alert preferences"
            )
            
            SettingsItem(
                icon = Icons.Default.Security,
                title = "Privacy & Security",
                subtitle = "Account security settings"
            )
            
            SettingsItem(
                icon = Icons.Default.Help,
                title = "Help & Support",
                subtitle = "Get help with the app"
            )
        }
    }
}

@Composable
private fun SettingsItem(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    subtitle: String
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            icon,
            contentDescription = null,
            modifier = Modifier.size(24.dp),
            tint = MaterialTheme.colorScheme.primary
        )
        
        Spacer(modifier = Modifier.width(16.dp))
        
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                style = MaterialTheme.typography.bodyLarge
            )
            
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
            )
        }
        
        Icon(
            Icons.Default.ChevronRight,
            contentDescription = null,
            modifier = Modifier.size(20.dp),
            tint = MaterialTheme.colorScheme.outline
        )
    }
}

private fun formatDate(timestamp: Long): String {
    val format = SimpleDateFormat("MMM dd, yyyy", Locale.getDefault())
    return format.format(Date(timestamp))
}