#!/usr/bin/env python3
"""
ESP32 Camera Performance Monitor Module

This module provides comprehensive performance monitoring and metrics collection
for ESP32-camera integration with the V2V communication system.

Requirements covered:
- 7.4: Monitor and display video processing performance metrics
- 7.1: Maintain minimum 10 FPS for YOLO inference
- 7.3: Automatically reduce frame rate when CPU usage is high
- 7.5: Optimize memory usage for continuous operation
"""

import time
import threading
import queue
from collections import deque
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any, Callable
import json
import csv

# Performance monitoring imports
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("⚠️ psutil not available - system performance monitoring will be limited")

try:
    import matplotlib.pyplot as plt
    import matplotlib.animation as animation
    from matplotlib.dates import DateFormatter
    import numpy as np
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("⚠️ matplotlib not available - performance graphs will be disabled")


@dataclass
class PerformanceMetrics:
    """Performance metrics data structure"""
    timestamp: float
    frame_count: int
    yolo_fps: float
    frame_fps: float
    esp32_fps: float
    buffer_usage_percent: float
    frames_dropped: int
    yolo_processing_time_ms: float
    frame_processing_time_ms: float
    memory_usage_mb: float
    cpu_usage_percent: float
    gpu_usage_percent: float = 0.0
    temperature_celsius: float = 0.0
    network_latency_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)
    
    def to_csv_row(self) -> List[Any]:
        """Convert to CSV row format"""
        return [
            self.timestamp, self.frame_count, self.yolo_fps, self.frame_fps,
            self.esp32_fps, self.buffer_usage_percent, self.frames_dropped,
            self.yolo_processing_time_ms, self.frame_processing_time_ms,
            self.memory_usage_mb, self.cpu_usage_percent, self.gpu_usage_percent,
            self.temperature_celsius, self.network_latency_ms
        ]
    
    @classmethod
    def csv_headers(cls) -> List[str]:
        """Get CSV headers"""
        return [
            'timestamp', 'frame_count', 'yolo_fps', 'frame_fps', 'esp32_fps',
            'buffer_usage_percent', 'frames_dropped', 'yolo_processing_time_ms',
            'frame_processing_time_ms', 'memory_usage_mb', 'cpu_usage_percent',
            'gpu_usage_percent', 'temperature_celsius', 'network_latency_ms'
        ]


class PerformanceCollector:
    """
    Collects performance metrics from various system components.
    Implements Requirements 7.4: Collect frame rate, processing time, and memory usage metrics
    """
    
    def __init__(self, collection_interval: float = 1.0, max_history: int = 300):
        """
        Initialize performance collector.
        
        Args:
            collection_interval: How often to collect metrics (seconds)
            max_history: Maximum number of metrics to keep in memory
        """
        self.collection_interval = collection_interval
        self.max_history = max_history
        
        # Metrics storage
        self.metrics_history: deque = deque(maxlen=max_history)
        self.current_metrics = PerformanceMetrics(
            timestamp=time.time(),
            frame_count=0,
            yolo_fps=0.0,
            frame_fps=0.0,
            esp32_fps=0.0,
            buffer_usage_percent=0.0,
            frames_dropped=0,
            yolo_processing_time_ms=0.0,
            frame_processing_time_ms=0.0,
            memory_usage_mb=0.0,
            cpu_usage_percent=0.0
        )
        
        # Data sources
        self.esp32_receiver = None
        self.yolo_processor = None
        self.system_monitor = None
        
        # Collection control
        self.collecting = False
        self.collection_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Callbacks for real-time updates
        self.update_callbacks: List[Callable[[PerformanceMetrics], None]] = []
        
        # Performance thresholds for alerts
        self.thresholds = {
            'min_yolo_fps': 10.0,
            'max_memory_mb': 500.0,
            'max_cpu_percent': 80.0,
            'max_buffer_usage': 90.0,
            'max_frame_drop_rate': 5.0  # frames per second
        }
        
        # Alert tracking
        self.alerts_active = set()
        self.alert_callbacks: List[Callable[[str, Dict], None]] = []
    
    def set_esp32_receiver(self, receiver):
        """Set ESP32 camera receiver for metrics collection"""
        self.esp32_receiver = receiver
    
    def set_yolo_processor(self, processor):
        """Set YOLO processor for metrics collection"""
        self.yolo_processor = processor
    
    def add_update_callback(self, callback: Callable[[PerformanceMetrics], None]):
        """Add callback for real-time metrics updates"""
        self.update_callbacks.append(callback)
    
    def add_alert_callback(self, callback: Callable[[str, Dict], None]):
        """Add callback for performance alerts"""
        self.alert_callbacks.append(callback)
    
    def start_collection(self):
        """Start performance metrics collection"""
        if self.collecting:
            return
        
        self.collecting = True
        self.stop_event.clear()
        self.collection_thread = threading.Thread(target=self._collection_loop, daemon=True)
        self.collection_thread.start()
        print("📊 Performance metrics collection started")
    
    def stop_collection(self):
        """Stop performance metrics collection"""
        if not self.collecting:
            return
        
        self.collecting = False
        self.stop_event.set()
        
        if self.collection_thread and self.collection_thread.is_alive():
            self.collection_thread.join(timeout=2)
        
        print("📊 Performance metrics collection stopped")
    
    def _collection_loop(self):
        """Main collection loop running in background thread"""
        while not self.stop_event.wait(self.collection_interval):
            try:
                metrics = self._collect_current_metrics()
                self.current_metrics = metrics
                self.metrics_history.append(metrics)
                
                # Check for performance alerts
                self._check_performance_alerts(metrics)
                
                # Notify callbacks
                for callback in self.update_callbacks:
                    try:
                        callback(metrics)
                    except Exception as e:
                        print(f"⚠️ Error in metrics callback: {e}")
                
            except Exception as e:
                print(f"⚠️ Error collecting performance metrics: {e}")
    
    def _collect_current_metrics(self) -> PerformanceMetrics:
        """Collect current performance metrics from all sources"""
        current_time = time.time()
        
        # Initialize with defaults
        metrics = PerformanceMetrics(
            timestamp=current_time,
            frame_count=0,
            yolo_fps=0.0,
            frame_fps=0.0,
            esp32_fps=0.0,
            buffer_usage_percent=0.0,
            frames_dropped=0,
            yolo_processing_time_ms=0.0,
            frame_processing_time_ms=0.0,
            memory_usage_mb=0.0,
            cpu_usage_percent=0.0
        )
        
        # Collect ESP32 camera metrics
        if self.esp32_receiver:
            try:
                esp32_stats = self.esp32_receiver.get_stats()
                buffer_health = self.esp32_receiver.get_buffer_health()
                
                metrics.esp32_fps = esp32_stats.get('recent_fps', 0.0)
                metrics.buffer_usage_percent = buffer_health.get('buffer_usage_percent', 0.0)
                metrics.frames_dropped = esp32_stats.get('frames_dropped', 0)
                metrics.frame_count = esp32_stats.get('frames_received', 0)
                
                # Calculate frame processing time from FPS
                if metrics.esp32_fps > 0:
                    metrics.frame_processing_time_ms = (1.0 / metrics.esp32_fps) * 1000
                
            except Exception as e:
                print(f"⚠️ Error collecting ESP32 metrics: {e}")
        
        # Collect YOLO processing metrics
        if self.yolo_processor and hasattr(self.yolo_processor, 'get_performance_stats'):
            try:
                yolo_stats = self.yolo_processor.get_performance_stats()
                metrics.yolo_fps = yolo_stats.get('fps', 0.0)
                metrics.yolo_processing_time_ms = yolo_stats.get('avg_processing_time_ms', 0.0)
            except Exception as e:
                print(f"⚠️ Error collecting YOLO metrics: {e}")
        
        # Collect system metrics
        if PSUTIL_AVAILABLE:
            try:
                # Memory usage
                process = psutil.Process()
                metrics.memory_usage_mb = process.memory_info().rss / 1024 / 1024
                
                # CPU usage
                metrics.cpu_usage_percent = psutil.cpu_percent(interval=None)
                
                # System temperature (if available)
                try:
                    temps = psutil.sensors_temperatures()
                    if temps:
                        # Get CPU temperature if available
                        for name, entries in temps.items():
                            if 'cpu' in name.lower() or 'core' in name.lower():
                                if entries:
                                    metrics.temperature_celsius = entries[0].current
                                    break
                except:
                    pass  # Temperature monitoring not available
                
            except Exception as e:
                print(f"⚠️ Error collecting system metrics: {e}")
        
        return metrics
    
    def _check_performance_alerts(self, metrics: PerformanceMetrics):
        """Check for performance threshold violations and trigger alerts"""
        alerts_to_trigger = []
        alerts_to_clear = []
        
        # Check YOLO FPS threshold
        alert_key = 'low_yolo_fps'
        if metrics.yolo_fps > 0 and metrics.yolo_fps < self.thresholds['min_yolo_fps']:
            if alert_key not in self.alerts_active:
                alerts_to_trigger.append((alert_key, {
                    'message': f'YOLO FPS below threshold: {metrics.yolo_fps:.1f} < {self.thresholds["min_yolo_fps"]}',
                    'current_value': metrics.yolo_fps,
                    'threshold': self.thresholds['min_yolo_fps'],
                    'severity': 'warning'
                }))
        else:
            if alert_key in self.alerts_active:
                alerts_to_clear.append(alert_key)
        
        # Check memory usage threshold
        alert_key = 'high_memory_usage'
        if metrics.memory_usage_mb > self.thresholds['max_memory_mb']:
            if alert_key not in self.alerts_active:
                alerts_to_trigger.append((alert_key, {
                    'message': f'Memory usage high: {metrics.memory_usage_mb:.1f}MB > {self.thresholds["max_memory_mb"]}MB',
                    'current_value': metrics.memory_usage_mb,
                    'threshold': self.thresholds['max_memory_mb'],
                    'severity': 'warning'
                }))
        else:
            if alert_key in self.alerts_active:
                alerts_to_clear.append(alert_key)
        
        # Check CPU usage threshold
        alert_key = 'high_cpu_usage'
        if metrics.cpu_usage_percent > self.thresholds['max_cpu_percent']:
            if alert_key not in self.alerts_active:
                alerts_to_trigger.append((alert_key, {
                    'message': f'CPU usage high: {metrics.cpu_usage_percent:.1f}% > {self.thresholds["max_cpu_percent"]}%',
                    'current_value': metrics.cpu_usage_percent,
                    'threshold': self.thresholds['max_cpu_percent'],
                    'severity': 'warning'
                }))
        else:
            if alert_key in self.alerts_active:
                alerts_to_clear.append(alert_key)
        
        # Check buffer usage threshold
        alert_key = 'high_buffer_usage'
        if metrics.buffer_usage_percent > self.thresholds['max_buffer_usage']:
            if alert_key not in self.alerts_active:
                alerts_to_trigger.append((alert_key, {
                    'message': f'Buffer usage high: {metrics.buffer_usage_percent:.1f}% > {self.thresholds["max_buffer_usage"]}%',
                    'current_value': metrics.buffer_usage_percent,
                    'threshold': self.thresholds['max_buffer_usage'],
                    'severity': 'warning'
                }))
        else:
            if alert_key in self.alerts_active:
                alerts_to_clear.append(alert_key)
        
        # Trigger new alerts
        for alert_key, alert_data in alerts_to_trigger:
            self.alerts_active.add(alert_key)
            for callback in self.alert_callbacks:
                try:
                    callback(alert_key, alert_data)
                except Exception as e:
                    print(f"⚠️ Error in alert callback: {e}")
        
        # Clear resolved alerts
        for alert_key in alerts_to_clear:
            self.alerts_active.discard(alert_key)
    
    def get_current_metrics(self) -> PerformanceMetrics:
        """Get the most recent performance metrics"""
        return self.current_metrics
    
    def get_metrics_history(self, duration_seconds: Optional[float] = None) -> List[PerformanceMetrics]:
        """
        Get metrics history.
        
        Args:
            duration_seconds: Only return metrics from the last N seconds (optional)
            
        Returns:
            List of performance metrics
        """
        if duration_seconds is None:
            return list(self.metrics_history)
        
        cutoff_time = time.time() - duration_seconds
        return [m for m in self.metrics_history if m.timestamp >= cutoff_time]
    
    def get_performance_summary(self, duration_seconds: float = 300) -> Dict[str, Any]:
        """
        Get performance summary statistics.
        
        Args:
            duration_seconds: Time window for summary (default: 5 minutes)
            
        Returns:
            Dictionary with performance summary
        """
        recent_metrics = self.get_metrics_history(duration_seconds)
        
        if not recent_metrics:
            return {'error': 'No metrics available'}
        
        # Calculate statistics
        yolo_fps_values = [m.yolo_fps for m in recent_metrics if m.yolo_fps > 0]
        frame_fps_values = [m.frame_fps for m in recent_metrics if m.frame_fps > 0]
        esp32_fps_values = [m.esp32_fps for m in recent_metrics if m.esp32_fps > 0]
        memory_values = [m.memory_usage_mb for m in recent_metrics]
        cpu_values = [m.cpu_usage_percent for m in recent_metrics]
        buffer_values = [m.buffer_usage_percent for m in recent_metrics]
        
        def safe_stats(values):
            if not values:
                return {'min': 0, 'max': 0, 'avg': 0, 'current': 0}
            return {
                'min': min(values),
                'max': max(values),
                'avg': sum(values) / len(values),
                'current': values[-1] if values else 0
            }
        
        return {
            'time_window_seconds': duration_seconds,
            'metrics_count': len(recent_metrics),
            'yolo_fps': safe_stats(yolo_fps_values),
            'frame_fps': safe_stats(frame_fps_values),
            'esp32_fps': safe_stats(esp32_fps_values),
            'memory_usage_mb': safe_stats(memory_values),
            'cpu_usage_percent': safe_stats(cpu_values),
            'buffer_usage_percent': safe_stats(buffer_values),
            'total_frames_dropped': sum(m.frames_dropped for m in recent_metrics),
            'active_alerts': list(self.alerts_active),
            'performance_score': self._calculate_performance_score(recent_metrics)
        }
    
    def _calculate_performance_score(self, metrics: List[PerformanceMetrics]) -> float:
        """
        Calculate overall performance score (0-100).
        
        Args:
            metrics: List of performance metrics
            
        Returns:
            Performance score from 0 (poor) to 100 (excellent)
        """
        if not metrics:
            return 0.0
        
        score = 100.0
        
        # YOLO FPS score (40% weight)
        yolo_fps_values = [m.yolo_fps for m in metrics if m.yolo_fps > 0]
        if yolo_fps_values:
            avg_yolo_fps = sum(yolo_fps_values) / len(yolo_fps_values)
            yolo_score = min(100, (avg_yolo_fps / self.thresholds['min_yolo_fps']) * 100)
            score = score * 0.6 + yolo_score * 0.4
        
        # Memory usage score (20% weight)
        memory_values = [m.memory_usage_mb for m in metrics]
        if memory_values:
            avg_memory = sum(memory_values) / len(memory_values)
            memory_score = max(0, 100 - (avg_memory / self.thresholds['max_memory_mb']) * 100)
            score = score * 0.8 + memory_score * 0.2
        
        # CPU usage score (20% weight)
        cpu_values = [m.cpu_usage_percent for m in metrics]
        if cpu_values:
            avg_cpu = sum(cpu_values) / len(cpu_values)
            cpu_score = max(0, 100 - (avg_cpu / self.thresholds['max_cpu_percent']) * 100)
            score = score * 0.8 + cpu_score * 0.2
        
        # Buffer usage score (20% weight)
        buffer_values = [m.buffer_usage_percent for m in metrics]
        if buffer_values:
            avg_buffer = sum(buffer_values) / len(buffer_values)
            buffer_score = max(0, 100 - (avg_buffer / self.thresholds['max_buffer_usage']) * 100)
            score = score * 0.8 + buffer_score * 0.2
        
        return max(0.0, min(100.0, score))
    
    def export_to_csv(self, filename: str, duration_seconds: Optional[float] = None):
        """
        Export metrics to CSV file.
        
        Args:
            filename: Output CSV filename
            duration_seconds: Time window to export (optional, exports all if None)
        """
        metrics = self.get_metrics_history(duration_seconds)
        
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(PerformanceMetrics.csv_headers())
            
            for metric in metrics:
                writer.writerow(metric.to_csv_row())
        
        print(f"📊 Performance metrics exported to {filename} ({len(metrics)} records)")
    
    def export_to_json(self, filename: str, duration_seconds: Optional[float] = None):
        """
        Export metrics to JSON file.
        
        Args:
            filename: Output JSON filename
            duration_seconds: Time window to export (optional, exports all if None)
        """
        metrics = self.get_metrics_history(duration_seconds)
        
        data = {
            'export_timestamp': time.time(),
            'duration_seconds': duration_seconds,
            'metrics_count': len(metrics),
            'metrics': [metric.to_dict() for metric in metrics],
            'summary': self.get_performance_summary(duration_seconds) if duration_seconds else None
        }
        
        with open(filename, 'w') as jsonfile:
            json.dump(data, jsonfile, indent=2)
        
        print(f"📊 Performance metrics exported to {filename} ({len(metrics)} records)")


class PerformanceDisplay:
    """
    Displays performance metrics in real-time.
    Implements Requirements 7.4: Display performance information in UI
    """
    
    def __init__(self, collector: PerformanceCollector):
        """
        Initialize performance display.
        
        Args:
            collector: Performance metrics collector
        """
        self.collector = collector
        self.display_active = False
        
        # Console display settings
        self.console_update_interval = 5.0  # Update console every 5 seconds
        self.last_console_update = 0.0
        
        # Register for metrics updates
        self.collector.add_update_callback(self._on_metrics_update)
        self.collector.add_alert_callback(self._on_performance_alert)
    
    def _on_metrics_update(self, metrics: PerformanceMetrics):
        """Handle metrics update for console display"""
        current_time = time.time()
        
        if current_time - self.last_console_update >= self.console_update_interval:
            self._update_console_display(metrics)
            self.last_console_update = current_time
    
    def _on_performance_alert(self, alert_key: str, alert_data: Dict):
        """Handle performance alerts"""
        severity = alert_data.get('severity', 'info')
        message = alert_data.get('message', 'Performance alert')
        
        if severity == 'warning':
            print(f"⚠️ PERFORMANCE ALERT: {message}")
        elif severity == 'error':
            print(f"❌ PERFORMANCE ERROR: {message}")
        else:
            print(f"ℹ️ PERFORMANCE INFO: {message}")
    
    def _update_console_display(self, metrics: PerformanceMetrics):
        """Update console performance display"""
        print("\n" + "="*60)
        print("📊 ESP32-CAMERA PERFORMANCE METRICS")
        print("="*60)
        print(f"Timestamp: {time.strftime('%H:%M:%S', time.localtime(metrics.timestamp))}")
        print(f"Frame Count: {metrics.frame_count}")
        print(f"YOLO FPS: {metrics.yolo_fps:.1f}")
        print(f"ESP32 FPS: {metrics.esp32_fps:.1f}")
        print(f"Buffer Usage: {metrics.buffer_usage_percent:.1f}%")
        print(f"Frames Dropped: {metrics.frames_dropped}")
        print(f"Memory Usage: {metrics.memory_usage_mb:.1f} MB")
        print(f"CPU Usage: {metrics.cpu_usage_percent:.1f}%")
        
        if metrics.temperature_celsius > 0:
            print(f"Temperature: {metrics.temperature_celsius:.1f}°C")
        
        # Performance summary
        summary = self.collector.get_performance_summary(60)  # Last minute
        if 'performance_score' in summary:
            score = summary['performance_score']
            if score >= 80:
                status = "🟢 EXCELLENT"
            elif score >= 60:
                status = "🟡 GOOD"
            elif score >= 40:
                status = "🟠 FAIR"
            else:
                status = "🔴 POOR"
            
            print(f"Performance Score: {score:.1f}/100 {status}")
        
        if self.collector.alerts_active:
            print(f"Active Alerts: {len(self.collector.alerts_active)}")
            for alert in self.collector.alerts_active:
                print(f"  - {alert}")
        
        print("="*60)
    
    def start_display(self):
        """Start performance display"""
        self.display_active = True
        print("📊 Performance display started")
    
    def stop_display(self):
        """Stop performance display"""
        self.display_active = False
        print("📊 Performance display stopped")
    
    def print_performance_report(self, duration_minutes: int = 5):
        """
        Print detailed performance report.
        
        Args:
            duration_minutes: Time window for report in minutes
        """
        duration_seconds = duration_minutes * 60
        summary = self.collector.get_performance_summary(duration_seconds)
        
        print("\n" + "="*80)
        print(f"📊 ESP32-CAMERA PERFORMANCE REPORT ({duration_minutes} minutes)")
        print("="*80)
        
        if 'error' in summary:
            print(f"❌ {summary['error']}")
            return
        
        print(f"Time Window: {duration_minutes} minutes ({summary['metrics_count']} data points)")
        print(f"Performance Score: {summary['performance_score']:.1f}/100")
        print()
        
        # YOLO Performance
        yolo = summary['yolo_fps']
        print(f"YOLO Processing:")
        print(f"  Current: {yolo['current']:.1f} FPS")
        print(f"  Average: {yolo['avg']:.1f} FPS")
        print(f"  Range: {yolo['min']:.1f} - {yolo['max']:.1f} FPS")
        print()
        
        # ESP32 Performance
        esp32 = summary['esp32_fps']
        print(f"ESP32 Camera:")
        print(f"  Current: {esp32['current']:.1f} FPS")
        print(f"  Average: {esp32['avg']:.1f} FPS")
        print(f"  Range: {esp32['min']:.1f} - {esp32['max']:.1f} FPS")
        print()
        
        # Memory Usage
        memory = summary['memory_usage_mb']
        print(f"Memory Usage:")
        print(f"  Current: {memory['current']:.1f} MB")
        print(f"  Average: {memory['avg']:.1f} MB")
        print(f"  Peak: {memory['max']:.1f} MB")
        print()
        
        # CPU Usage
        cpu = summary['cpu_usage_percent']
        print(f"CPU Usage:")
        print(f"  Current: {cpu['current']:.1f}%")
        print(f"  Average: {cpu['avg']:.1f}%")
        print(f"  Peak: {cpu['max']:.1f}%")
        print()
        
        # Buffer Usage
        buffer = summary['buffer_usage_percent']
        print(f"Buffer Usage:")
        print(f"  Current: {buffer['current']:.1f}%")
        print(f"  Average: {buffer['avg']:.1f}%")
        print(f"  Peak: {buffer['max']:.1f}%")
        print()
        
        print(f"Total Frames Dropped: {summary['total_frames_dropped']}")
        
        if summary['active_alerts']:
            print(f"\nActive Alerts: {len(summary['active_alerts'])}")
            for alert in summary['active_alerts']:
                print(f"  - {alert}")
        else:
            print("\n✅ No active performance alerts")
        
        print("="*80)


# Global performance monitor instance
_global_performance_collector: Optional[PerformanceCollector] = None
_global_performance_display: Optional[PerformanceDisplay] = None


def get_global_performance_collector() -> PerformanceCollector:
    """Get or create global performance collector instance"""
    global _global_performance_collector
    if _global_performance_collector is None:
        _global_performance_collector = PerformanceCollector()
    return _global_performance_collector


def get_global_performance_display() -> PerformanceDisplay:
    """Get or create global performance display instance"""
    global _global_performance_display
    if _global_performance_display is None:
        collector = get_global_performance_collector()
        _global_performance_display = PerformanceDisplay(collector)
    return _global_performance_display


def initialize_performance_monitoring(esp32_receiver=None, yolo_processor=None, 
                                    enable_display: bool = True, 
                                    collection_interval: float = 1.0) -> PerformanceCollector:
    """
    Initialize performance monitoring for ESP32-camera system.
    
    Args:
        esp32_receiver: ESP32 camera receiver instance
        yolo_processor: YOLO processor instance
        enable_display: Whether to enable console display
        collection_interval: Metrics collection interval in seconds
        
    Returns:
        Performance collector instance
    """
    collector = get_global_performance_collector()
    collector.collection_interval = collection_interval
    
    if esp32_receiver:
        collector.set_esp32_receiver(esp32_receiver)
    
    if yolo_processor:
        collector.set_yolo_processor(yolo_processor)
    
    collector.start_collection()
    
    if enable_display:
        display = get_global_performance_display()
        display.start_display()
    
    print("📊 ESP32-camera performance monitoring initialized")
    return collector


def cleanup_performance_monitoring():
    """Cleanup performance monitoring resources"""
    global _global_performance_collector, _global_performance_display
    
    if _global_performance_display:
        _global_performance_display.stop_display()
        _global_performance_display = None
    
    if _global_performance_collector:
        _global_performance_collector.stop_collection()
        _global_performance_collector = None
    
    print("📊 Performance monitoring cleanup completed")


if __name__ == "__main__":
    """Test performance monitoring functionality"""
    import sys
    import random
    
    print("Testing ESP32 Performance Monitor...")
    
    # Create test collector
    collector = PerformanceCollector(collection_interval=0.5)
    display = PerformanceDisplay(collector)
    
    # Start monitoring
    collector.start_collection()
    display.start_display()
    
    # Simulate metrics for 30 seconds
    print("Simulating performance data for 30 seconds...")
    start_time = time.time()
    
    try:
        while time.time() - start_time < 30:
            # Simulate some processing
            time.sleep(0.1)
            
            # Add some random variation to test alerts
            if random.random() < 0.1:  # 10% chance
                # Simulate high CPU usage
                collector.current_metrics.cpu_usage_percent = 85.0
            
            if random.random() < 0.05:  # 5% chance
                # Simulate low YOLO FPS
                collector.current_metrics.yolo_fps = 8.0
    
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    
    # Print final report
    display.print_performance_report(1)  # Last minute
    
    # Export test data
    collector.export_to_csv("test_performance_metrics.csv")
    collector.export_to_json("test_performance_metrics.json")
    
    # Cleanup
    collector.stop_collection()
    display.stop_display()
    
    print("✅ Performance monitor test completed")