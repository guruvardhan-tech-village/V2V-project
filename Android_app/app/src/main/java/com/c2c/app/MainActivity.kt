package com.c2c.app

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.location.Geocoder
import android.location.Location
import android.net.Uri
import android.os.Bundle
import android.os.Looper
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.*
import com.c2c.data.repo.AuthRepository
import com.c2c.data.repo.VehicleRepository
import com.c2c.feature.auth.*
import com.c2c.feature.vehicle.*
import com.c2c.feature.map.*
import com.c2c.feature.alerts.*
import com.c2c.feature.esp32.*
import com.google.android.gms.location.LocationCallback
import com.google.android.gms.location.LocationRequest
import com.google.android.gms.location.LocationResult
import com.google.android.gms.location.LocationServices
import com.google.android.gms.location.Priority
import com.google.android.gms.maps.model.LatLng
import com.google.firebase.database.ChildEventListener
import com.google.firebase.database.DataSnapshot
import com.google.firebase.database.DatabaseError
import com.google.firebase.database.FirebaseDatabase
import com.google.maps.android.PolyUtil
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale
import java.text.SimpleDateFormat
import java.util.Date
class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            C2CTheme {
                C2CApp()
            }
        }
    }
}

// Navigation items for bottom navigation
sealed class Screen(val route: String, val title: String, val icon: androidx.compose.ui.graphics.vector.ImageVector) {
    object Home : Screen("home", "Home", Icons.Default.Home)
    object Profile : Screen("profile", "Profile", Icons.Default.Person)
    object Map : Screen("map", "Map", Icons.Default.Map)
    object Alerts : Screen("alerts", "Alerts", Icons.Default.Warning)
}

val bottomNavItems = listOf(
    Screen.Home,
    Screen.Profile,
    Screen.Map,
    Screen.Alerts
)

@Composable
fun C2CApp() {
    val authRepo = remember { AuthRepository() }
    var currentUser by remember { mutableStateOf(authRepo.currentUid()) }
    var userEmail by remember { mutableStateOf(authRepo.currentUserEmail()) }

    val context = LocalContext.current

    // Location state for "near-me" alert filtering
    var hasLocationPermission by remember { mutableStateOf(false) }
    var currentLocation by remember { mutableStateOf<Location?>(null) }

    val fusedLocationClient = remember {
        LocationServices.getFusedLocationProviderClient(context)
    }

    // Runtime permission launcher for location
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { permissions ->
        hasLocationPermission =
            permissions[Manifest.permission.ACCESS_FINE_LOCATION] == true ||
                    permissions[Manifest.permission.ACCESS_COARSE_LOCATION] == true
    }

    // Check and request location permission once
    LaunchedEffect(Unit) {
        val fineGranted = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_FINE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED
        val coarseGranted = ContextCompat.checkSelfPermission(
            context,
            Manifest.permission.ACCESS_COARSE_LOCATION
        ) == PackageManager.PERMISSION_GRANTED

        if (fineGranted || coarseGranted) {
            hasLocationPermission = true
        } else {
            permissionLauncher.launch(
                arrayOf(
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION
                )
            )
        }
    }

    // Callback to receive continuous location updates while the app is in use
    val locationCallback = remember {
        object : LocationCallback() {
            override fun onLocationResult(result: LocationResult) {
                val last = result.lastLocation
                if (last != null) {
                    currentLocation = last
                }
            }
        }
    }

    // Start location updates when permission is available, and stop on dispose
    DisposableEffect(hasLocationPermission) {
        if (!hasLocationPermission) {
            onDispose { }
        } else {
            // Try to get a last known location immediately
            try {
                fusedLocationClient.lastLocation.addOnSuccessListener { location ->
                    if (location != null) {
                        currentLocation = location
                    }
                }
            } catch (_: SecurityException) {
                // Permission may have been revoked while running
            }

            val request = LocationRequest.Builder(
                Priority.PRIORITY_HIGH_ACCURACY,
                5_000L // 5 seconds
            )
                .setMinUpdateDistanceMeters(50f)
                .build()

            try {
                fusedLocationClient.requestLocationUpdates(
                    request,
                    locationCallback,
                    Looper.getMainLooper()
                )
            } catch (_: SecurityException) {
                // Permission may have been revoked while running
            }

            onDispose {
                fusedLocationClient.removeLocationUpdates(locationCallback)
            }
        }
    }

    // Live alerts coming from Firebase (accidents + traffic)
    val alerts = remember { mutableStateListOf<AlertUI>() }
    var latestAlert by remember { mutableStateOf<AlertUI?>(null) }
    var rawLatestAlert by remember { mutableStateOf<AlertUI?>(null) }

    // Active route polyline used for filtering alerts that are "on your way"
    var activeRoute by remember { mutableStateOf<List<LatLng>>(emptyList()) }

    // Attach Firebase Realtime Database listeners once
    val db = remember { FirebaseDatabase.getInstance() }
    DisposableEffect(Unit) {
        val accidentsRef = db.getReference("accidents")
        val trafficRef = db.getReference("traffic")

        val accidentListener = object : ChildEventListener {
            override fun onChildAdded(snapshot: DataSnapshot, previousChildName: String?) {
                val reg = snapshot.child("regNumber").getValue(String::class.java) ?: "Unknown vehicle"
                val locationName = snapshot.child("locationName").getValue(String::class.java) ?: "Unknown location"
                val lat = snapshot.child("latitude").getValue(Double::class.java)
                val lon = snapshot.child("longitude").getValue(Double::class.java)
                val severity = snapshot.child("severity").getValue(String::class.java) ?: "UNKNOWN"
                val ts = snapshot.child("timestamp").getValue(Long::class.java)

                val message = "Accident ($severity) near $locationName from $reg"
                val alert = AlertUI(
                    title = "Accident Alert",
                    message = message,
                    lat = lat,
                    lon = lon,
                    isAccident = true,
                    trafficLevel = null,
                    timestamp = ts,
                )
                alerts.add(0, alert)
                rawLatestAlert = alert
            }

            override fun onChildChanged(snapshot: DataSnapshot, previousChildName: String?) {}
            override fun onChildRemoved(snapshot: DataSnapshot) {}
            override fun onChildMoved(snapshot: DataSnapshot, previousChildName: String?) {}
            override fun onCancelled(error: DatabaseError) {}
        }

        val trafficListener = object : ChildEventListener {
            override fun onChildAdded(snapshot: DataSnapshot, previousChildName: String?) {
                val reg = snapshot.child("regNumber").getValue(String::class.java) ?: "Unknown vehicle"
                val locationName = snapshot.child("locationName").getValue(String::class.java) ?: "Unknown location"
                val level = snapshot.child("level").getValue(String::class.java) ?: "UNKNOWN"
                val lat = snapshot.child("latitude").getValue(Double::class.java)
                val lon = snapshot.child("longitude").getValue(Double::class.java)
                val ts = snapshot.child("timestamp").getValue(Long::class.java)

                val message = "Traffic $level near $locationName from $reg"
                val alert = AlertUI(
                    title = "Traffic Alert",
                    message = message,
                    lat = lat,
                    lon = lon,
                    isAccident = false,
                    trafficLevel = level,
                    timestamp = ts,
                )
                alerts.add(0, alert)
                rawLatestAlert = alert
            }

            override fun onChildChanged(snapshot: DataSnapshot, previousChildName: String?) {}
            override fun onChildRemoved(snapshot: DataSnapshot) {}
            override fun onChildMoved(snapshot: DataSnapshot, previousChildName: String?) {}
            override fun onCancelled(error: DatabaseError) {}
        }

        accidentsRef.addChildEventListener(accidentListener)
        trafficRef.addChildEventListener(trafficListener)

        onDispose {
            accidentsRef.removeEventListener(accidentListener)
            trafficRef.removeEventListener(trafficListener)
        }
    }

    // Only surface alerts that lie close to the active route polyline.
    LaunchedEffect(rawLatestAlert, activeRoute) {
        if (activeRoute.isEmpty()) {
            latestAlert = null
        } else {
            val incoming = rawLatestAlert
            if (incoming != null && isAlertOnRoute(incoming, activeRoute)) {
                latestAlert = incoming
            }
        }
    }

    // Listen to auth state changes
    LaunchedEffect(Unit) {
        // This will trigger recomposition when auth state changes
        currentUser = authRepo.currentUid()
        userEmail = authRepo.currentUserEmail()
    }

    if (currentUser != null) {
        MainNavigation(
            currentUserId = currentUser!!,
            currentUserEmail = userEmail ?: "Unknown User",
            alerts = alerts,
            latestAlert = latestAlert,
            rawLatestAlert = rawLatestAlert,
            currentLocation = currentLocation,
            activeRoute = activeRoute,
            onRouteChanged = { activeRoute = it },
            onLogout = {
                authRepo.logout()
                currentUser = null
                userEmail = null
            }
        )
    } else {
        AuthNavigation(
            onLoginSuccess = { userId, email ->
                currentUser = userId
                userEmail = email
            }
        )
    }
}

@Composable
fun AuthNavigation(
    onLoginSuccess: (String, String) -> Unit = { _, _ -> }
) {
    val navController = rememberNavController()
    val authRepo = remember { AuthRepository() }
    
    NavHost(
        navController = navController,
        startDestination = "login"
    ) {
        composable("login") {
            LoginScreen(
                onSuccess = {
                    // Check if user has vehicles, if not go to vehicle setup
                    val userId = authRepo.currentUid()
                    val userEmail = authRepo.currentUserEmail() ?: "Unknown User"
                    if (userId != null) {
                        onLoginSuccess(userId, userEmail)
                    }
                },
                onNavigateRegister = { navController.navigate("register") }
            )
        }
        
        composable("register") {
            RegisterScreen(
                onSuccess = { 
                    navController.navigate("vehicle_setup") 
                }
            )
        }
        
        composable("vehicle_setup") {
            VehicleRegistrationScreen(
                onDone = {
                    // After successful vehicle registration, trigger login success
                    val userId = authRepo.currentUid()
                    val userEmail = authRepo.currentUserEmail() ?: "Unknown User"
                    if (userId != null) {
                        onLoginSuccess(userId, userEmail)
                    }
                }
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainNavigation(
    currentUserId: String,
    currentUserEmail: String,
    alerts: List<AlertUI>,
    latestAlert: AlertUI?,
    rawLatestAlert: AlertUI?,
    currentLocation: Location?,
    activeRoute: List<LatLng>,
    onRouteChanged: (List<LatLng>) -> Unit,
    onLogout: () -> Unit
) {
    val navController = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = navBackStackEntry?.destination

    val snackbarHostState = remember { SnackbarHostState() }

    // Show a quick popup like WhatsApp for every new alert from Firebase
    LaunchedEffect(rawLatestAlert) {
        rawLatestAlert?.let { alert ->
            val timeLabel = alert.timestamp?.let { ts ->
                val formatter = SimpleDateFormat("HH:mm", Locale.getDefault())
                formatter.format(Date(ts))
            }
            val msg = if (timeLabel != null) {
                "[$timeLabel] ${alert.title}: ${alert.message}"
            } else {
                "${alert.title}: ${alert.message}"
            }
            snackbarHostState.showSnackbar(message = msg)
        }
    }

    // Top app bar with user info and logout
    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        topBar = {
            TopAppBar(
                title = { 
                    Column {
                        Text(
                            text = "C2C Dashboard",
                            style = MaterialTheme.typography.titleMedium
                        )
                        Text(
                            text = "Welcome, ${currentUserEmail.substringBefore("@")}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                        )
                    }
                },
                actions = {
                    IconButton(onClick = onLogout) {
                        Icon(
                            Icons.Default.ExitToApp,
                            contentDescription = "Logout",
                            tint = MaterialTheme.colorScheme.onSurface
                        )
                    }
                }
            )
        },
        bottomBar = {
            NavigationBar {
                bottomNavItems.forEach { screen ->
                    NavigationBarItem(
                        icon = { Icon(screen.icon, contentDescription = screen.title) },
                        label = { Text(screen.title) },
                        selected = currentDestination?.hierarchy?.any { it.route == screen.route } == true,
                        onClick = {
                            navController.navigate(screen.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        }
                    )
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = Screen.Home.route,
            modifier = Modifier.padding(innerPadding)
        ) {
            composable(Screen.Home.route) {
                ModernHomeScreen(
                    currentUserId = currentUserId,
                    currentUserEmail = currentUserEmail,
                    currentLocation = currentLocation,
                    onNavigateToMap = { navController.navigate(Screen.Map.route) },
                    onNavigateToAlerts = { navController.navigate(Screen.Alerts.route) },
                    onNavigateToProfile = { navController.navigate(Screen.Profile.route) },
                    onLogout = onLogout,
                    onRouteChanged = onRouteChanged,
                )
            }
            
            composable(Screen.Profile.route) {
                ProfileScreen(
                    currentUserId = currentUserId,
                    currentUserEmail = currentUserEmail,
                    onAddVehicle = { navController.navigate("add_vehicle") },
                    onLogout = onLogout
                )
            }
            
            composable(Screen.Map.route) {
                MapWithIncidentsScreen(
                    latestAlert = latestAlert,
                    currentLocation = currentLocation,
                    activeRoute = activeRoute,
                    onRouteChanged = onRouteChanged,
                )
            }
            
            composable(Screen.Alerts.route) {
                AlertsScreen(
                    alerts = alerts,
                    onEmergencyCall = {
                        val intent = Intent(Intent.ACTION_DIAL, Uri.parse("tel:108"))
                        navController.context.startActivity(intent)
                    }
                )
            }
            
            composable("add_vehicle") {
                VehicleRegistrationScreen(
                    onDone = { navController.popBackStack() }
                )
            }
            
            composable("esp32_setup") {
                Esp32SetupScreen()
            }
        }
    }
}

@Composable
fun ModernHomeScreen(
    currentUserId: String,
    currentUserEmail: String,
    currentLocation: Location?,
    onNavigateToMap: () -> Unit,
    onNavigateToAlerts: () -> Unit,
    onNavigateToProfile: () -> Unit,
    onLogout: () -> Unit,
    onRouteChanged: (List<LatLng>) -> Unit,
) {
    val context = LocalContext.current
    
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(16.dp)
    ) {
        // Personalized Welcome Header
        item {
            PersonalizedWelcomeHeader(
                userEmail = currentUserEmail,
                onLogout = onLogout
            )
        }
        
        // Quick Actions
        item {
            QuickActionsSection(
                onNavigateToMap = onNavigateToMap,
                onNavigateToAlerts = onNavigateToAlerts,
                onNavigateToProfile = onNavigateToProfile
            )
        }
        
        // Simple route planner from current location to destination
        item {
            RoutePlannerSection(
                currentLocation = currentLocation,
                onRouteChanged = onRouteChanged,
                onNavigateToMap = onNavigateToMap,
            )
        }
        
        // User-specific Live Status
        item {
            UserSpecificStatusSection(currentUserId = currentUserId)
        }
        
        // Emergency Actions
        item {
            EmergencySection(context = context)
        }
        
        // Firebase Testing (Development)
        item {
            DeveloperSection(
                context = context,
                currentUserId = currentUserId
            )
        }
    }
}

@Composable
private fun RoutePlannerSection(
    currentLocation: Location?,
    onRouteChanged: (List<LatLng>) -> Unit,
    onNavigateToMap: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()

    var destinationQuery by remember { mutableStateOf("") }
    var isRequestingRoute by remember { mutableStateOf(false) }
    var routeError by remember { mutableStateOf<String?>(null) }

    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = "Plan your route",
                style = MaterialTheme.typography.titleLarge,
            )

            Text(
                text = if (currentLocation != null) {
                    "Starting point: Your current location"
                } else {
                    "Starting point: waiting for GPS location..."
                },
                style = MaterialTheme.typography.bodySmall,
            )

            OutlinedTextField(
                value = destinationQuery,
                onValueChange = { destinationQuery = it },
                label = { Text("Destination (area, place, or address)") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
            )

            Button(
                onClick = {
                    val origin = currentLocation
                    if (origin == null) {
                        routeError = "Waiting for GPS location before creating a route"
                        return@Button
                    }
                    if (destinationQuery.isBlank()) {
                        routeError = "Please enter a destination."
                        return@Button
                    }
                    scope.launch {
                        isRequestingRoute = true
                        routeError = null
                        try {
                            val destLatLng = geocodeDestination(context, destinationQuery)
                            if (destLatLng == null) {
                                routeError = "Could not find that place. Try a more specific name."
                            } else {
                                val routeInfo = fetchRoute(
                                    originLat = origin.latitude,
                                    originLon = origin.longitude,
                                    destLat = destLatLng.latitude,
                                    destLon = destLatLng.longitude,
                                )
                                if (routeInfo.points.isEmpty()) {
                                    routeError = "No route found. Try another destination."
                                } else {
                                    onRouteChanged(routeInfo.points)
                                    // Open the map screen showing this route
                                    onNavigateToMap()
                                }
                            }
                        } catch (e: Exception) {
                            routeError = "Unable to set route. Please try again."
                        } finally {
                            isRequestingRoute = false
                        }
                    }
                },
                enabled = !isRequestingRoute,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text("Search route on map")
            }

            if (isRequestingRoute) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }

            routeError?.let { error ->
                Text(
                    text = error,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
        }
    }
}

@Composable
private fun WelcomeHeader() {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(20.dp)
        ) {
            Text(
                text = "C2C Dashboard",
                style = MaterialTheme.typography.headlineMedium,
                color = MaterialTheme.colorScheme.onPrimaryContainer
            )
            Text(
                text = "Car-to-Car Communication System",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.7f)
            )
        }
    }
}

@Composable
private fun PersonalizedWelcomeHeader(
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
                        style = MaterialTheme.typography.headlineMedium,
                        color = MaterialTheme.colorScheme.onPrimaryContainer
                    )
                    Text(
                        text = userEmail.substringBefore("@"),
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.9f)
                    )
                    Text(
                        text = "Your personal C2C Dashboard",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onPrimaryContainer.copy(alpha = 0.7f)
                    )
                }
                
                // Quick logout button in header
                OutlinedButton(
                    onClick = onLogout,
                    colors = ButtonDefaults.outlinedButtonColors(
                        contentColor = MaterialTheme.colorScheme.onPrimaryContainer
                    )
                ) {
                    Icon(
                        Icons.Default.ExitToApp,
                        contentDescription = "Logout",
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Logout")
                }
            }
        }
    }
}

@Composable
private fun QuickActionsSection(
    onNavigateToMap: () -> Unit,
    onNavigateToAlerts: () -> Unit,
    onNavigateToProfile: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Text(
                text = "Quick Actions",
                style = MaterialTheme.typography.titleLarge,
                modifier = Modifier.padding(bottom = 12.dp)
            )
            
            LazyRow(
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                item {
                    QuickActionCard(
                        icon = Icons.Default.Map,
                        title = "Live Map",
                        subtitle = "View traffic & alerts",
                        onClick = onNavigateToMap
                    )
                }
                
                item {
                    QuickActionCard(
                        icon = Icons.Default.Warning,
                        title = "Alerts",
                        subtitle = "Safety notifications",
                        onClick = onNavigateToAlerts
                    )
                }
                
                item {
                    QuickActionCard(
                        icon = Icons.Default.Person,
                        title = "Profile",
                        subtitle = "Vehicles & settings",
                        onClick = onNavigateToProfile
                    )
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun QuickActionCard(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    subtitle: String,
    onClick: () -> Unit
) {
    ElevatedCard(
        onClick = onClick,
        modifier = Modifier
            .width(140.dp)
            .height(100.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(16.dp),
            verticalArrangement = Arrangement.SpaceBetween
        ) {
            Icon(
                icon,
                contentDescription = title,
                tint = MaterialTheme.colorScheme.primary,
                modifier = Modifier.size(24.dp)
            )
            
            Column {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleSmall
                )
                Text(
                    text = subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                )
            }
        }
    }
}

@Composable
private fun LiveStatusSection() {
    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Text(
                text = "Live Status",
                style = MaterialTheme.typography.titleLarge,
                modifier = Modifier.padding(bottom = 12.dp)
            )
            
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                StatusItem(
                    icon = Icons.Default.DirectionsCar,
                    title = "Vehicles",
                    value = "2 Active",
                    color = MaterialTheme.colorScheme.primary
                )
                
                StatusItem(
                    icon = Icons.Default.Wifi,
                    title = "Connection",
                    value = "Online",
                    color = MaterialTheme.colorScheme.tertiary
                )
                
                StatusItem(
                    icon = Icons.Default.Shield,
                    title = "Safety",
                    value = "Active",
                    color = MaterialTheme.colorScheme.secondary
                )
            }
        }
    }
}

@Composable
private fun UserSpecificStatusSection(currentUserId: String) {
    val vehicleRepo = remember { VehicleRepository() }
    var vehicleCount by remember { mutableStateOf(0) }
    var isLoading by remember { mutableStateOf(true) }
    
    // Load user's vehicle count
    LaunchedEffect(currentUserId) {
        vehicleRepo.getUserVehicles(currentUserId).fold(
            onSuccess = { vehicles ->
                vehicleCount = vehicles.size
                isLoading = false
            },
            onFailure = {
                isLoading = false
            }
        )
    }
    
    Card(
        modifier = Modifier.fillMaxWidth()
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Text(
                text = "Your Status",
                style = MaterialTheme.typography.titleLarge,
                modifier = Modifier.padding(bottom = 12.dp)
            )
            
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly
            ) {
                StatusItem(
                    icon = Icons.Default.DirectionsCar,
                    title = "My Vehicles",
                    value = if (isLoading) "Loading..." else "$vehicleCount Registered",
                    color = MaterialTheme.colorScheme.primary
                )
                
                StatusItem(
                    icon = Icons.Default.Wifi,
                    title = "Connection",
                    value = "Online",
                    color = MaterialTheme.colorScheme.tertiary
                )
                
                StatusItem(
                    icon = Icons.Default.Shield,
                    title = "Safety",
                    value = "Protected",
                    color = MaterialTheme.colorScheme.secondary
                )
            }
        }
    }
}

@Composable
private fun StatusItem(
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    title: String,
    value: String,
    color: androidx.compose.ui.graphics.Color
) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Icon(
            icon,
            contentDescription = title,
            tint = color,
            modifier = Modifier.size(28.dp)
        )
        
        Spacer(modifier = Modifier.height(4.dp))
        
        Text(
            text = value,
            style = MaterialTheme.typography.labelLarge,
            color = color
        )
        
        Text(
            text = title,
            style = MaterialTheme.typography.labelSmall,
            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
        )
    }
}

@Composable
private fun EmergencySection(context: android.content.Context) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.errorContainer
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp)
        ) {
            Text(
                text = "Emergency",
                style = MaterialTheme.typography.titleLarge,
                color = MaterialTheme.colorScheme.onErrorContainer,
                modifier = Modifier.padding(bottom = 12.dp)
            )
            
            Button(
                onClick = { 
                    context.startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:108")))
                },
                modifier = Modifier.fillMaxWidth(),
                colors = ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.error
                )
            ) {
                Icon(
                    Icons.Default.Phone,
                    contentDescription = null,
                    modifier = Modifier.size(20.dp)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text("Emergency Call (108)")
            }
        }
    }
}

@Composable
private fun DeveloperSection(
    context: android.content.Context,
    currentUserId: String
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
                    text = "Developer Tools",
                    style = MaterialTheme.typography.titleMedium
                )
                Text(
                    text = "User: ${currentUserId.take(8)}...",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.6f)
                )
            }
            
            Spacer(modifier = Modifier.height(8.dp))
            
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                OutlinedButton(
                    onClick = {
                        val testUtils = FirebaseTestUtils(context)
                        testUtils.printFirebaseStatus()
                        testUtils.runAllTests()
                    },
                    modifier = Modifier.weight(1f)
                ) {
                    Text("🔥 Test Firebase")
                }
                
                OutlinedButton(
                    onClick = {
                        val testUtils = FirebaseTestUtils(context)
                        testUtils.generateTestESP32Data()
                    },
                    modifier = Modifier.weight(1f)
                ) {
                    Text("🔧 ESP32 Data")
                }
            }
        }
    }
}

@Composable 
fun C2CTheme(content: @Composable () -> Unit) {
    MaterialTheme {
        content()
    }
}

private const val ROUTE_ALERT_DISTANCE_METERS = 500.0

data class RouteInfo(
    val points: List<LatLng>,
    val distanceMeters: Int?,
)

private fun isAlertNearUser(
    alert: AlertUI,
    currentLocation: Location?,
    maxDistanceMeters: Float = 2_000f,
): Boolean {
    val userLocation = currentLocation ?: return false
    val alertLat = alert.lat ?: return false
    val alertLon = alert.lon ?: return false

    val results = FloatArray(1)
    Location.distanceBetween(
        userLocation.latitude,
        userLocation.longitude,
        alertLat,
        alertLon,
        results,
    )
    return results[0] <= maxDistanceMeters
}

private fun isAlertOnRoute(
    alert: AlertUI,
    routePoints: List<LatLng>,
    maxDistanceMeters: Double = ROUTE_ALERT_DISTANCE_METERS,
): Boolean {
    if (routePoints.size < 2) return false
    val lat = alert.lat ?: return false
    val lon = alert.lon ?: return false
    val point = LatLng(lat, lon)
    return PolyUtil.isLocationOnPath(point, routePoints, false, maxDistanceMeters)
}

private suspend fun fetchRoute(
    originLat: Double,
    originLon: Double,
    destLat: Double,
    destLon: Double,
): RouteInfo = withContext(Dispatchers.IO) {
    val apiKey = BuildConfig.MAPS_API_KEY
    if (apiKey.isNullOrBlank() || apiKey == "null") {
        return@withContext RouteInfo(emptyList(), null)
    }

    val urlString =
        "https://maps.googleapis.com/maps/api/directions/json?" +
                "origin=$originLat,$originLon&destination=$destLat,$destLon&key=$apiKey"

    val url = URL(urlString)
    val connection = (url.openConnection() as HttpURLConnection).apply {
        requestMethod = "GET"
        connectTimeout = 10_000
        readTimeout = 10_000
    }

    try {
        val response = connection.inputStream.bufferedReader().use { it.readText() }
        parseRouteFromDirectionsJson(response)
    } catch (_: Exception) {
        RouteInfo(emptyList(), null)
    } finally {
        connection.disconnect()
    }
}

private fun parseRouteFromDirectionsJson(json: String): RouteInfo {
    return try {
        val root = JSONObject(json)
        val routes = root.optJSONArray("routes") ?: return RouteInfo(emptyList(), null)
        if (routes.length() == 0) return RouteInfo(emptyList(), null)
        val route = routes.getJSONObject(0)

        val polyObj = route.optJSONObject("overview_polyline")
        val encoded = polyObj?.optString("points", "") ?: ""
        val points = if (encoded.isEmpty()) emptyList() else PolyUtil.decode(encoded)

        var distanceMeters: Int? = null
        val legs = route.optJSONArray("legs")
        if (legs != null && legs.length() > 0) {
            val leg0 = legs.getJSONObject(0)
            val distanceObj = leg0.optJSONObject("distance")
            distanceMeters = distanceObj?.optInt("value")
        }

        RouteInfo(points, distanceMeters)
    } catch (_: Exception) {
        RouteInfo(emptyList(), null)
    }
}

@Composable
private fun MapWithIncidentsScreen(
    latestAlert: AlertUI?,
    currentLocation: Location?,
    activeRoute: List<LatLng>,
    onRouteChanged: (List<LatLng>) -> Unit,
) {
    val context = LocalContext.current
    val defaultLat = 12.9716
    val defaultLon = 77.5946

    val scope = rememberCoroutineScope()
    var isRequestingRoute by remember { mutableStateOf(false) }
    var routeError by remember { mutableStateOf<String?>(null) }
    var destinationQuery by remember { mutableStateOf("") }
    var routeDistanceMeters by remember { mutableStateOf<Int?>(null) }

    // Prefer centering on the user's current device location when available.
    // Only fall back to latest alert or default city if we don't have GPS yet.
    val state = if (currentLocation != null) {
        MapState(
            vehicleId = "YOU",
            lat = currentLocation.latitude,
            lon = currentLocation.longitude,
            routePoints = activeRoute,
        )
    } else if (latestAlert?.lat != null && latestAlert.lon != null) {
        MapState(
            vehicleId = latestAlert.title,
            lat = latestAlert.lat,
            lon = latestAlert.lon,
            routePoints = activeRoute,
        )
    } else {
        MapState("LIVE_DATA", defaultLat, defaultLon, routePoints = activeRoute)
    }

    Box(Modifier.fillMaxSize()) {
        MapScreen(
            state = state,
            onMapLongClick = { destLatLng ->
                val origin = currentLocation
                if (origin == null) {
                    routeError = "Waiting for GPS location before creating a route"
                    return@MapScreen
                }
                scope.launch {
                    isRequestingRoute = true
                    routeError = null
                    try {
                        val routeInfo = fetchRoute(
                            originLat = origin.latitude,
                            originLon = origin.longitude,
                            destLat = destLatLng.latitude,
                            destLon = destLatLng.longitude,
                        )
                        if (routeInfo.points.isEmpty()) {
                            routeError = "No route found. Try another point."
                        } else {
                            onRouteChanged(routeInfo.points)
                            routeDistanceMeters = routeInfo.distanceMeters
                        }
                    } catch (e: Exception) {
                        routeError = "Unable to fetch route. Please try again."
                    } finally {
                        isRequestingRoute = false
                    }
                }
            },
        )

        // Small route status card in the top-left
        Card(
            modifier = Modifier
                .align(Alignment.TopStart)
                .padding(16.dp),
        ) {
            Column(modifier = Modifier.padding(12.dp)) {
                Text("Route", style = MaterialTheme.typography.titleMedium)

                OutlinedTextField(
                    value = destinationQuery,
                    onValueChange = { destinationQuery = it },
                    label = { Text("Destination (e.g. Sumanahalli)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(modifier = Modifier.height(4.dp))
                Button(
                    onClick = {
                        val origin = currentLocation
                        if (origin == null) {
                            routeError = "Waiting for GPS location before creating a route"
                            return@Button
                        }
                        if (destinationQuery.isBlank()) {
                            routeError = "Please enter a destination."
                            return@Button
                        }
                        scope.launch {
                            isRequestingRoute = true
                            routeError = null
                            try {
                                val destLatLng = geocodeDestination(context, destinationQuery)
                                if (destLatLng == null) {
                                    routeError = "Could not find that place. Try a more specific name."
                                } else {
                                    val routeInfo = fetchRoute(
                                        originLat = origin.latitude,
                                        originLon = origin.longitude,
                                        destLat = destLatLng.latitude,
                                        destLon = destLatLng.longitude,
                                    )
                                    if (routeInfo.points.isEmpty()) {
                                        routeError = "No route found. Try another destination."
                                    } else {
                                        onRouteChanged(routeInfo.points)
                                        routeDistanceMeters = routeInfo.distanceMeters
                                    }
                                }
                            } catch (e: Exception) {
                                routeError = "Unable to set route. Please try again."
                            } finally {
                                isRequestingRoute = false
                            }
                        }
                    },
                    enabled = !isRequestingRoute,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text("Set route")
                }

                Spacer(modifier = Modifier.height(8.dp))

                if (activeRoute.isEmpty()) {
                    Text(
                        text = "Long-press on the map or enter a destination to set a route.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                } else {
                    Text(
                        text = "Route active. Long-press another point or enter a new destination to change it.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    TextButton(onClick = {
                        onRouteChanged(emptyList())
                        routeDistanceMeters = null
                    }) {
                        Text("Clear route")
                    }
                }

                routeDistanceMeters?.let { meters ->
                    Spacer(modifier = Modifier.height(4.dp))
                    val km = meters / 1000.0
                    Text(
                        text = "Distance: ${"%.1f".format(km)} km",
                        style = MaterialTheme.typography.bodySmall,
                    )
                }

                if (isRequestingRoute) {
                    Spacer(modifier = Modifier.height(8.dp))
                    LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
                }

                routeError?.let { error ->
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = error,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
        }

        // For accidents we only show a snackbar (configured in MainNavigation).
        // Here we draw an overlay card ONLY for significant traffic alerts,
        // so the driver can choose an alternate route.
        val isHighTraffic = latestAlert != null && !latestAlert.isAccident &&
            (latestAlert.trafficLevel == "HIGH" || latestAlert.trafficLevel == "MEDIUM")

        if (isHighTraffic && latestAlert?.lat != null && latestAlert.lon != null) {
            Card(
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .padding(16.dp),
            ) {
                Column(modifier = Modifier.padding(12.dp)) {
                    Text(latestAlert.title, style = MaterialTheme.typography.titleMedium)
                    Text(latestAlert.message, style = MaterialTheme.typography.bodyMedium)
                    latestAlert.timestamp?.let { ts ->
                        val formatter = SimpleDateFormat("HH:mm, dd MMM", Locale.getDefault())
                        val formatted = formatter.format(Date(ts))
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(
                            text = "Time: $formatted",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
                        )
                    }
                    Spacer(modifier = Modifier.height(8.dp))

                    Button(
                        onClick = {
                            // For high traffic, open Google Maps so user can choose an alternate route
                            val uri = Uri.parse("google.navigation:q=${latestAlert.lat},${latestAlert.lon}")
                            val intent = Intent(Intent.ACTION_VIEW, uri).apply {
                                setPackage("com.google.android.apps.maps")
                            }
                            context.startActivity(intent)
                        },
                        modifier = Modifier.fillMaxWidth()
                    ) {
                        Text("Open Google Maps for alternate route")
                    }
                }
            }
        }
    }
}

private suspend fun geocodeDestination(
    context: android.content.Context,
    query: String,
): LatLng? = withContext(Dispatchers.IO) {
    try {
        val geocoder = Geocoder(context, Locale.getDefault())
        val results = geocoder.getFromLocationName(query, 1)
        if (results.isNullOrEmpty()) {
            null
        } else {
            val addr = results[0]
            LatLng(addr.latitude, addr.longitude)
        }
    } catch (_: Exception) {
        null
    }
}

@Composable
fun HomeMenu(onMap: () -> Unit, onAlerts: () -> Unit, onEsp32: () -> Unit) {
  val ctx = LocalContext.current
  Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
    Text("C2C Dashboard", style = MaterialTheme.typography.headlineSmall)
    Button(onClick = onMap, modifier = Modifier.fillMaxWidth()) { Text("Open Map") }
    Button(onClick = onAlerts, modifier = Modifier.fillMaxWidth()) { Text("View Alerts") }
    Button(onClick = onEsp32, modifier = Modifier.fillMaxWidth()) { Text("ESP32 Setup") }
    
    // 🔥 Firebase Testing Buttons
    Button(
      onClick = { 
        val testUtils = FirebaseTestUtils(ctx)
        testUtils.printFirebaseStatus()
        testUtils.runAllTests()
      }, 
      modifier = Modifier.fillMaxWidth()
    ) { Text("🔥 Test Firebase Integration") }
    
    Button(
      onClick = { 
        val testUtils = FirebaseTestUtils(ctx)
        testUtils.generateTestESP32Data()
      }, 
      modifier = Modifier.fillMaxWidth()
    ) { Text("🔧 Generate ESP32 Test Data") }
    
    Button(onClick = { ctx.startActivity(Intent(Intent.ACTION_DIAL, Uri.parse("tel:108"))) }, modifier = Modifier.fillMaxWidth()) { Text("Emergency Call (108)") }
  }
}
