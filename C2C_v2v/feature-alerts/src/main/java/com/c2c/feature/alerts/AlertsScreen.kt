package com.c2c.feature.alerts
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp

data class AlertUI(val title:String, val message:String)

@Composable
fun AlertsScreen(alerts: List<AlertUI>, onEmergencyCall: () -> Unit) {
  Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
    Text("Road Alerts", style = MaterialTheme.typography.headlineSmall)
    alerts.forEach {
      Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
          Text(it.title, style = MaterialTheme.typography.titleMedium)
          Text(it.message, style = MaterialTheme.typography.bodyMedium)
        }
      }
    }
    Spacer(Modifier.weight(1f))
    Button(onClick = onEmergencyCall, modifier = Modifier.fillMaxWidth()) { Text("Emergency Call (108)") }
  }
}
