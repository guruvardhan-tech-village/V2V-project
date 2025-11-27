package com.c2c.feature.esp32
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import com.c2c.data.repo.DeviceConfigRepository
import com.c2c.domain.model.DeviceConfig
import kotlinx.coroutines.launch

@Composable
fun Esp32SetupScreen() {
  val repo = remember { DeviceConfigRepository() }
  var vehicleId by remember { mutableStateOf("") }
  var ssid by remember { mutableStateOf("") }
  var password by remember { mutableStateOf("") }
  var interval by remember { mutableStateOf("5") }
  var status by remember { mutableStateOf<String?>(null) }
  val scope = rememberCoroutineScope()

  Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
    Text("ESP32 Device Setup", style = MaterialTheme.typography.headlineSmall)
    OutlinedTextField(vehicleId, { vehicleId = it }, label = { Text("Vehicle ID") }, modifier = Modifier.fillMaxWidth())
    OutlinedTextField(ssid, { ssid = it }, label = { Text("Wi-Fi SSID") }, modifier = Modifier.fillMaxWidth())
    OutlinedTextField(password, { password = it }, label = { Text("Wi-Fi Password") }, modifier = Modifier.fillMaxWidth())
    OutlinedTextField(interval, { interval = it }, label = { Text("Upload Interval (sec)") }, modifier = Modifier.fillMaxWidth())
    Button(onClick = { scope.launch {
      try {
        val cfg = DeviceConfig(vehicleId = vehicleId, ssid = ssid, password = password, uploadIntervalSec = interval.toIntOrNull() ?: 5, ownerUid = "")
        repo.upsert(cfg)
        status = "Configuration uploaded for $vehicleId âœ…"
      } catch (t: Throwable) { status = "Error: ${t.message}" }
    } }, modifier = Modifier.fillMaxWidth()) { Text("Upload to Cloud") }
    if (status != null) Text(status!!)
  }
}
