package com.c2c.app

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
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
    onLogout: () -> Unit
) {
    val navController = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = navBackStackEntry?.destination
    
    // Top app bar with user info and logout
    Scaffold(
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
                    onNavigateToMap = { navController.navigate(Screen.Map.route) },
                    onNavigateToAlerts = { navController.navigate(Screen.Alerts.route) },
                    onNavigateToProfile = { navController.navigate(Screen.Profile.route) },
                    onLogout = onLogout
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
                MapScreen(MapState("LIVE_DATA", 12.9716, 77.5946))
            }
            
            composable(Screen.Alerts.route) {
                AlertsScreen(
                    alerts = getSampleAlerts(),
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
    onNavigateToMap: () -> Unit,
    onNavigateToAlerts: () -> Unit,
    onNavigateToProfile: () -> Unit,
    onLogout: () -> Unit
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

// Helper function for sample alerts
fun getSampleAlerts(): List<com.c2c.feature.alerts.AlertUI> {
    return listOf(
        com.c2c.feature.alerts.AlertUI("Traffic Alert", "Heavy traffic ahead on Highway 1"),
        com.c2c.feature.alerts.AlertUI("Accident Alert", "Vehicle accident reported 2km ahead"),
        com.c2c.feature.alerts.AlertUI("Weather Alert", "Foggy conditions - Drive carefully")
    )
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
