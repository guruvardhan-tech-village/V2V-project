package com.c2c.feature.alerts
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Simple UI model for alerts shown in the app.
 *
 * lat/lon allow map features to highlight where an incident occurred.
 */
data class AlertUI(
    val title: String,
    val message: String,
    val lat: Double? = null,
    val lon: Double? = null,
    val isAccident: Boolean = false,
    val trafficLevel: String? = null,
    val timestamp: Long? = null,
)

@Composable
fun AlertsScreen(alerts: List<AlertUI>, onEmergencyCall: () -> Unit) {
  Column(Modifier.fillMaxSize().padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
    Text("Road Alerts", style = MaterialTheme.typography.headlineSmall)
    alerts.forEach {
      Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
          Text(it.title, style = MaterialTheme.typography.titleMedium)
          Text(it.message, style = MaterialTheme.typography.bodyMedium)
          if (it.lat != null && it.lon != null) {
            Spacer(Modifier.height(4.dp))
            Text(
              text = "Location: ${it.lat}, ${it.lon}",
              style = MaterialTheme.typography.bodySmall,
              color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
            )
          }
          it.timestamp?.let { ts ->
            Spacer(Modifier.height(4.dp))
            Text(
              text = "Time: ${formatAlertTimestamp(ts)}",
              style = MaterialTheme.typography.bodySmall,
              color = MaterialTheme.colorScheme.onSurface.copy(alpha = 0.7f)
            )
          }
        }
      }
    }
    Spacer(Modifier.weight(1f))
    Button(onClick = onEmergencyCall, modifier = Modifier.fillMaxWidth()) { Text("Emergency Call (108)") }
  }
}

private fun formatAlertTimestamp(timestamp: Long): String {
  val formatter = SimpleDateFormat("HH:mm, dd MMM", Locale.getDefault())
  return formatter.format(Date(timestamp))
}
