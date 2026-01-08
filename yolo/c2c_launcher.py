import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import sys
import subprocess
import requests
import time
import threading
from PIL import Image, ImageTk
import cv2
import numpy as np

# Optional: list serial ports if pyserial is installed
try:
    from serial.tools import list_ports
except ImportError:
    list_ports = None

# ESP32-camera integration imports
try:
    from esp32_camera_receiver import ESP32CameraReceiver
    ESP32_CAMERA_AVAILABLE = True
except ImportError:
    ESP32_CAMERA_AVAILABLE = False
    print("⚠️ ESP32 camera receiver not available")

# Performance monitoring imports (Requirements 7.4)
try:
    from esp32_performance_monitor import (
        get_global_performance_collector, 
        get_global_performance_display,
        initialize_performance_monitoring,
        cleanup_performance_monitoring
    )
    PERFORMANCE_MONITORING_AVAILABLE = True
except ImportError:
    PERFORMANCE_MONITORING_AVAILABLE = False
    print("⚠️ Performance monitoring not available")

DEFAULT_FIREBASE_URL = "https://c2c-cartocar-app-23bb6-default-rtdb.firebaseio.com/"
CONFIG_FILE = "car_config.json"


def get_script_dir():
    return os.path.dirname(os.path.abspath(__file__))


def save_config(cfg):
    cfg_path = os.path.join(get_script_dir(), CONFIG_FILE)
    with open(cfg_path, "w") as f:
        json.dump(cfg, f, indent=2)


def register_or_get_car(firebase_url, reg_number, owner_name, phone):
    """
    Register car in Firebase /cars or reuse existing.
    """
    firebase_url = firebase_url.rstrip("/")
    print(f"[GUI] Registering car {reg_number} in Firebase...")

    # Query existing car by regNumber
    try:
        params = {
            "orderBy": json.dumps("regNumber"),
            "equalTo": json.dumps(reg_number),
        }
        res = requests.get(f"{firebase_url}/cars.json", params=params, timeout=5)
        data = res.json() or {}
    except Exception as e:
        print(f"[GUI] Firebase query failed: {e}")
        data = {}

    car_id = None

    # data is dict: { key: { regNumber: "...", ... }, ... }
    for key, value in data.items():
        if not isinstance(value, dict):
            continue
        if value.get("regNumber") == reg_number:
            car_id = key
            break

    if car_id:
        print(f"[GUI] Existing car found. carId = {car_id}")
    else:
        # Create new car entry
        new_car = {
            "regNumber": reg_number,
            "ownerName": owner_name,
            "phone": phone,
            "createdAt": int(__import__("time").time() * 1000),
        }
        try:
            res = requests.post(f"{firebase_url}/cars.json", json=new_car, timeout=5)
            res.raise_for_status()
            car_id = res.json()["name"]
            print(f"[GUI] New car created. carId = {car_id}")
        except Exception as e:
            raise RuntimeError(f"Failed to create car in Firebase: {e}")

    return car_id


class C2CLauncher(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("C2C V2V Module Launcher")
        self.geometry("550x450")
        self.resizable(False, False)

        # handle child process
        self.proc = None

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _build_ui(self):
        pad = 8

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=pad, pady=pad)

        # --- Car & user details ---
        ttk.Label(frm, text="Car / User Details", font=("Segoe UI", 11, "bold")).grid(
            row=0, column=0, columnspan=3, sticky="w", pady=(0, 4)
        )

        ttk.Label(frm, text="Car Registration *").grid(row=1, column=0, sticky="w")
        self.reg_entry = ttk.Entry(frm, width=20)
        self.reg_entry.grid(row=1, column=1, sticky="w")

        ttk.Label(frm, text="Owner Name").grid(row=2, column=0, sticky="w")
        self.owner_entry = ttk.Entry(frm, width=20)
        self.owner_entry.grid(row=2, column=1, sticky="w")

        ttk.Label(frm, text="Phone").grid(row=3, column=0, sticky="w")
        self.phone_entry = ttk.Entry(frm, width=20)
        self.phone_entry.grid(row=3, column=1, sticky="w")

        ttk.Label(frm, text="Bluetooth MAC (optional)").grid(row=4, column=0, sticky="w")
        self.bt_entry = ttk.Entry(frm, width=20)
        self.bt_entry.grid(row=4, column=1, sticky="w")

        # --- Firebase ---
        ttk.Label(frm, text="Firebase URL").grid(row=5, column=0, sticky="w", pady=(10, 0))
        self.fb_entry = ttk.Entry(frm, width=40)
        self.fb_entry.insert(0, DEFAULT_FIREBASE_URL)
        self.fb_entry.grid(row=5, column=1, columnspan=2, sticky="w", pady=(10, 0))

        # --- Serial & camera ---
        ttk.Label(frm, text="ESP32 Serial Port").grid(row=6, column=0, sticky="w", pady=(10, 0))

        self.serial_combo = ttk.Combobox(frm, width=15)
        ports = []
        if list_ports is not None:
            try:
                ports = [p.device for p in list_ports.comports()]
            except Exception:
                ports = []
        if not ports:
            ports = ["COM3", "COM4", "COM5"]
        self.serial_combo["values"] = ports
        self.serial_combo.set(ports[0])
        self.serial_combo.grid(row=6, column=1, sticky="w", pady=(10, 0))

        ttk.Label(frm, text="Camera / Video Source").grid(row=7, column=0, sticky="w")
        
        # Video source selection dropdown
        self.source_combo = ttk.Combobox(frm, width=25, state="readonly")
        video_sources = [
            "Webcam 0",
            "Webcam 1", 
            "ESP32-Camera (COM3)",
            "Video File..."
        ]
        self.source_combo["values"] = video_sources
        self.source_combo.set("Webcam 0")  # default
        self.source_combo.bind("<<ComboboxSelected>>", self.on_video_source_changed)
        self.source_combo.grid(row=7, column=1, sticky="w")

        def choose_video():
            path = filedialog.askopenfilename(
                title="Select video file",
                filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov *.m4v *.webm"), ("All files", "*.*")]
            )
            if path:
                # Add custom video file option
                current_values = list(self.source_combo["values"])
                if "Custom Video File" not in current_values:
                    current_values.append("Custom Video File")
                    self.source_combo["values"] = current_values
                self.source_combo.set("Custom Video File")
                self.custom_video_path = path

        self.btn_video = ttk.Button(frm, text="Browse Video...", command=choose_video)
        self.btn_video.grid(row=7, column=2, sticky="w")
        
        # Store custom video path
        self.custom_video_path = None
        
        # ESP32-Camera configuration controls (initially hidden)
        self.esp32_config_frame = ttk.LabelFrame(frm, text="ESP32-Camera Configuration", padding=5)
        
        # Resolution setting
        ttk.Label(self.esp32_config_frame, text="Resolution:").grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.esp32_resolution_combo = ttk.Combobox(self.esp32_config_frame, width=10, state="readonly")
        self.esp32_resolution_combo["values"] = ["QVGA", "VGA", "SVGA", "XGA"]
        self.esp32_resolution_combo.set("VGA")
        self.esp32_resolution_combo.bind("<<ComboboxSelected>>", self.on_esp32_config_changed)
        self.esp32_resolution_combo.grid(row=0, column=1, sticky="w", padx=(0, 10))
        
        # FPS setting
        ttk.Label(self.esp32_config_frame, text="FPS:").grid(row=0, column=2, sticky="w", padx=(0, 5))
        self.esp32_fps_combo = ttk.Combobox(self.esp32_config_frame, width=8, state="readonly")
        self.esp32_fps_combo["values"] = ["5", "10", "15", "20", "25", "30"]
        self.esp32_fps_combo.set("15")
        self.esp32_fps_combo.bind("<<ComboboxSelected>>", self.on_esp32_config_changed)
        self.esp32_fps_combo.grid(row=0, column=3, sticky="w", padx=(0, 10))
        
        # Quality setting
        ttk.Label(self.esp32_config_frame, text="Quality:").grid(row=1, column=0, sticky="w", padx=(0, 5))
        self.esp32_quality_scale = ttk.Scale(self.esp32_config_frame, from_=10, to=63, orient="horizontal", length=100)
        self.esp32_quality_scale.set(50)
        self.esp32_quality_scale.grid(row=1, column=1, columnspan=2, sticky="w", padx=(0, 10))
        self.esp32_quality_scale.configure(command=self.update_quality_label)
        
        self.esp32_quality_label = ttk.Label(self.esp32_config_frame, text="50")
        self.esp32_quality_label.grid(row=1, column=3, sticky="w")
        
        # Apply configuration button
        self.esp32_apply_btn = ttk.Button(self.esp32_config_frame, text="Apply Config", command=self.apply_esp32_config)
        self.esp32_apply_btn.grid(row=2, column=0, columnspan=1, sticky="w", pady=(5, 0))
        
        # Configuration management buttons
        self.esp32_export_btn = ttk.Button(self.esp32_config_frame, text="Export", command=self.export_esp32_config)
        self.esp32_export_btn.grid(row=2, column=1, sticky="w", padx=(5, 0), pady=(5, 0))
        
        self.esp32_import_btn = ttk.Button(self.esp32_config_frame, text="Import", command=self.import_esp32_config)
        self.esp32_import_btn.grid(row=2, column=2, sticky="w", padx=(5, 0), pady=(5, 0))
        
        # Live preview controls
        self.esp32_preview_var = tk.BooleanVar(value=False)
        self.esp32_preview_check = ttk.Checkbutton(
            self.esp32_config_frame, 
            text="Live Preview", 
            variable=self.esp32_preview_var,
            command=self.toggle_esp32_preview
        )
        self.esp32_preview_check.grid(row=2, column=3, sticky="w", padx=(10, 0), pady=(5, 0))
        
        # Connection status with enhanced indicators
        status_frame = ttk.Frame(self.esp32_config_frame)
        status_frame.grid(row=3, column=0, columnspan=4, sticky="ew", pady=(5, 0))
        
        self.esp32_status_label = ttk.Label(status_frame, text="Status: Not connected", 
                                          font=("Segoe UI", 9, "italic"))
        self.esp32_status_label.pack(side="left")
        
        # Status indicator LED-style
        self.esp32_status_indicator = tk.Canvas(status_frame, width=12, height=12, highlightthickness=0)
        self.esp32_status_indicator.pack(side="left", padx=(5, 0))
        self.esp32_status_circle = self.esp32_status_indicator.create_oval(2, 2, 10, 10, fill="gray", outline="")
        
        # Detailed status button
        self.esp32_details_btn = ttk.Button(status_frame, text="Details", command=self.show_esp32_details)
        self.esp32_details_btn.pack(side="right")
        
        # Error history button
        self.esp32_errors_btn = ttk.Button(status_frame, text="Errors", command=self.show_esp32_errors)
        self.esp32_errors_btn.pack(side="right", padx=(0, 5))
        
        # Performance metrics button (Requirements 7.4)
        self.esp32_performance_btn = ttk.Button(status_frame, text="Performance", command=self.show_esp32_performance)
        self.esp32_performance_btn.pack(side="right", padx=(0, 5))
        
        # Initially hide ESP32 config frame
        # Will be shown when ESP32-Camera is selected
        
        # ESP32-Camera receiver instance
        self.esp32_receiver = None
        
        # Performance monitoring (Requirements 7.4)
        self.performance_collector = None
        self.performance_display = None
        
        # Enhanced status and error tracking (Requirements 8.2, 8.5)
        self.esp32_status_history = []
        self.esp32_error_history = []
        self.esp32_connection_attempts = 0
        self.esp32_last_successful_connection = None
        
        # Live preview window management
        self.esp32_preview_window = None
        self.esp32_preview_label = None
        self.esp32_preview_active = False
        self.esp32_preview_thread = None
        self.esp32_preview_stop_event = threading.Event()
        
        # Load saved ESP32-camera configuration
        self.load_esp32_config()

        # --- Toggles ---
        self.var_accident = tk.BooleanVar(value=True)
        self.var_traffic = tk.BooleanVar(value=True)
        self.var_display = tk.BooleanVar(value=True)
        self.var_bt = tk.BooleanVar(value=False)

        chk_frame = ttk.Frame(frm)
        chk_frame.grid(row=8, column=0, columnspan=3, sticky="w", pady=(10, 0))

        ttk.Checkbutton(chk_frame, text="Enable Accident Detection", variable=self.var_accident).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Checkbutton(chk_frame, text="Enable Traffic Analysis", variable=self.var_traffic).grid(
            row=0, column=1, sticky="w", padx=(15, 0)
        )
        ttk.Checkbutton(chk_frame, text="Show Video Window", variable=self.var_display).grid(
            row=1, column=0, sticky="w"
        )
        ttk.Checkbutton(chk_frame, text="Connect via Bluetooth", variable=self.var_bt).grid(
            row=1, column=1, sticky="w", padx=(15, 0)
        )

        # --- Model paths (optional) ---
        ttk.Label(frm, text="Accident Model .pt").grid(row=9, column=0, sticky="w", pady=(10, 0))
        self.accident_entry = ttk.Entry(frm, width=40)
        self.accident_entry.insert(0, r"C:\Users\Somashekar A\Desktop\Major Pro\yolo\accident\v1\weights\best.pt")
        self.accident_entry.grid(row=9, column=1, columnspan=2, sticky="w", pady=(10, 0))

        ttk.Label(frm, text="Traffic Model .pt").grid(row=10, column=0, sticky="w")
        self.traffic_entry = ttk.Entry(frm, width=40)
        self.traffic_entry.insert(0, "yolov8s.pt")
        self.traffic_entry.grid(row=10, column=1, columnspan=2, sticky="w")

        # --- Start & Stop buttons (Option A) ---
        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=11, column=0, columnspan=3, pady=(20, 0), sticky="w")

        self.start_btn = ttk.Button(btn_frame, text="Start C2C Module", command=self.on_start)
        self.start_btn.grid(row=0, column=0, padx=(0, 10))

        self.stop_btn = ttk.Button(btn_frame, text="Stop C2C Module", command=self.on_stop, state="disabled")
        self.stop_btn.grid(row=0, column=1)

        # Status hint
        self.status_label = ttk.Label(frm, text="Status: Idle", font=("Segoe UI", 9, "italic"))
        self.status_label.grid(row=12, column=0, columnspan=3, sticky="w", pady=(8, 0))

        ttk.Label(frm, text="* Required field", font=("Segoe UI", 8, "italic")).grid(
            row=13, column=0, columnspan=3, sticky="w", pady=(4, 0)
        )

    def on_video_source_changed(self, event=None):
        """Handle video source selection change"""
        selected = self.source_combo.get()
        
        if selected == "ESP32-Camera (COM3)":
            # Show ESP32 configuration controls
            self.esp32_config_frame.grid(row=8, column=0, columnspan=3, sticky="ew", pady=(10, 0))
            # Try to connect to ESP32-camera for status
            self.connect_esp32_camera()
        else:
            # Hide ESP32 configuration controls
            self.esp32_config_frame.grid_remove()
            # Disconnect ESP32-camera if connected
            self.disconnect_esp32_camera()
    
    def update_quality_label(self, value):
        """Update quality label when scale changes"""
        quality_value = int(float(value))
        self.esp32_quality_label.config(text=str(quality_value))
        # Trigger configuration change callback
        self.on_esp32_config_changed()
    
    def on_esp32_config_changed(self, event=None):
        """Handle ESP32-camera configuration changes (Requirements 8.4)"""
        # Enable apply button to indicate changes need to be applied
        if hasattr(self, 'esp32_apply_btn'):
            self.esp32_apply_btn.config(state="normal")
            
            # Update button text to indicate pending changes
            current_text = self.esp32_apply_btn.cget("text")
            if not current_text.endswith("*"):
                self.esp32_apply_btn.config(text="Apply Config*")
    
    def reset_apply_button_text(self):
        """Reset apply button text after successful configuration"""
        if hasattr(self, 'esp32_apply_btn'):
            self.esp32_apply_btn.config(text="Apply Config")
    
    def connect_esp32_camera(self):
        """Connect to ESP32-camera and update status with comprehensive error logging"""
        try:
            self.esp32_connection_attempts += 1
            self.log_esp32_status(f"Connection attempt #{self.esp32_connection_attempts}", "info")
            
            # Import ESP32CameraReceiver here to avoid import issues if not available
            from esp32_camera_receiver import ESP32CameraReceiver
            from esp32_logger import get_global_logger
            
            if self.esp32_receiver is None:
                self.esp32_receiver = ESP32CameraReceiver(port="COM3", baud=921600)
                
                # Set up error logging callback for UI updates (Requirements 8.5)
                if hasattr(self.esp32_receiver, 'logger') and self.esp32_receiver.logger:
                    self.esp32_receiver.logger.add_status_callback(self._on_esp32_error_logged)
                
                # Initialize performance monitoring (Requirements 7.4)
                if PERFORMANCE_MONITORING_AVAILABLE:
                    try:
                        self.performance_collector = initialize_performance_monitoring(
                            esp32_receiver=self.esp32_receiver,
                            enable_display=False,  # We'll handle display in UI
                            collection_interval=2.0  # Collect every 2 seconds
                        )
                        print("📊 Performance monitoring initialized for ESP32-camera")
                    except Exception as e:
                        print(f"⚠️ Failed to initialize performance monitoring: {e}")
                        self.performance_collector = None
                else:
                    self.performance_collector = None
            
            # Update status to show connecting
            self.esp32_status_label.config(text="Status: Connecting...", foreground="orange")
            self.update_esp32_status_indicator('connecting')
            self.log_esp32_status("Attempting connection to COM3", "info")
            self.update()  # Force UI update
            
            if self.esp32_receiver.connect():
                # Connection successful
                self.esp32_last_successful_connection = time.time()
                self.log_esp32_status("Connection established successfully", "success")
                
                # Get camera information and display
                self.display_camera_info()
                self.esp32_apply_btn.config(state="normal")
                self.update_esp32_status_indicator('connected')
                print("✅ Connected to ESP32-camera")
            else:
                # Connection failed
                error_msg = "Connection failed - device not responding"
                self.esp32_status_label.config(text="Status: Connection failed ❌", foreground="red")
                self.update_esp32_status_indicator('error')
                self.esp32_apply_btn.config(state="disabled")
                self.log_esp32_error(error_msg, {
                    'port': 'COM3',
                    'baud': 921600,
                    'attempt': self.esp32_connection_attempts
                })
                print("❌ Failed to connect to ESP32-camera")
                
        except ImportError:
            error_msg = "ESP32 module not found"
            self.esp32_status_label.config(text=f"Status: {error_msg} ❌", foreground="red")
            self.update_esp32_status_indicator('error')
            self.esp32_apply_btn.config(state="disabled")
            self.log_esp32_error(error_msg, {'error_type': 'import_error'})
            print(f"❌ {error_msg}")
        except Exception as e:
            error_msg = f"Error connecting to ESP32-camera: {str(e)[:50]}..."
            self.esp32_status_label.config(text=f"Status: {error_msg}", foreground="red")
            self.update_esp32_status_indicator('error')
            self.esp32_apply_btn.config(state="disabled")
            self.log_esp32_error(str(e), {
                'error_type': 'connection_exception',
                'attempt': self.esp32_connection_attempts,
                'full_error': str(e)
            })
            print(f"❌ Error connecting to ESP32-camera: {e}")
    
    def _on_esp32_error_logged(self, error_record):
        """Handle ESP32 error logging for UI status updates (Requirements 8.5)"""
        try:
            # Update status label with error information
            error_msg = error_record.message[:50] + "..." if len(error_record.message) > 50 else error_record.message
            
            if error_record.severity.value in ['high', 'critical']:
                # Show critical errors prominently
                self.esp32_status_label.config(
                    text=f"Status: ERROR - {error_msg}",
                    foreground="red"
                )
            elif error_record.category.value == 'connection':
                # Show connection errors
                self.esp32_status_label.config(
                    text=f"Status: Connection issue - {error_msg}",
                    foreground="orange"
                )
            else:
                # Show other errors as warnings
                current_text = self.esp32_status_label.cget("text")
                if not current_text.startswith("Status: ERROR"):
                    self.esp32_status_label.config(
                        text=f"Status: Warning - {error_msg}",
                        foreground="orange"
                    )
            
            # Schedule status restoration after 5 seconds for non-critical errors
            if error_record.severity.value not in ['high', 'critical']:
                self.after(5000, self._restore_normal_status)
                
        except Exception as e:
            print(f"⚠️ Error in ESP32 error callback: {e}")
    
    def _restore_normal_status(self):
        """Restore normal status display after showing error"""
        if self.esp32_receiver and self.esp32_receiver.is_connected():
            self.update_camera_status()
        elif self.esp32_receiver and self.esp32_receiver.is_using_fallback():
            self.esp32_status_label.config(text="Status: Using fallback webcam 📹", foreground="orange")
    
    def display_camera_info(self):
        """Display camera connection status and information"""
        if not self.esp32_receiver or not self.esp32_receiver.is_connected():
            return
        
        try:
            # Get camera statistics
            stats = self.esp32_receiver.get_stats()
            
            # Update status with connection info
            status_text = f"Status: Connected ✅ | Port: {stats['port']} | Baud: {stats['baud']}"
            self.esp32_status_label.config(text=status_text, foreground="green")
            self.update_esp32_status_indicator('connected')
            
            # Log successful connection
            self.log_esp32_status(f"Camera connected successfully on {stats['port']}", "success")
            
            # Schedule periodic status updates
            self.after(2000, self.update_camera_status)  # Update every 2 seconds
            
        except Exception as e:
            print(f"⚠️ Error getting camera info: {e}")
            self.esp32_status_label.config(text="Status: Connected ✅", foreground="green")
            self.update_esp32_status_indicator('connected')
            self.log_esp32_error(f"Error getting camera info: {str(e)}", {'stage': 'display_info'})
    
    def update_camera_status(self):
        """Periodically update camera status information (Requirements 8.5)"""
        if not self.esp32_receiver:
            return
        
        try:
            # Check if connection is still active or using fallback
            if not self.esp32_receiver.is_connected() and not self.esp32_receiver.is_using_fallback():
                # Connection lost, check for recovery
                self.log_esp32_status("Connection lost, checking for recovery", "warning")
                self.update_esp32_status_indicator('error')
                self.check_esp32_connection()
                return
            
            stats = self.esp32_receiver.get_stats()
            buffer_health = self.esp32_receiver.get_buffer_health()
            
            # Update status with real-time info
            fps = buffer_health.get('recent_fps', 0)
            buffer_usage = buffer_health.get('buffer_usage_percent', 0)
            frames_received = stats.get('frames_received', 0)
            connection_errors = stats.get('connection_errors', 0)
            
            # Check if using fallback
            if self.esp32_receiver.is_using_fallback():
                status_text = f"Status: Fallback webcam 📹 | FPS: {fps:.1f} | Frames: {frames_received}"
                self.esp32_status_label.config(text=status_text, foreground="orange")
                self.update_esp32_status_indicator('fallback')
                self.log_esp32_status("Using fallback webcam", "warning")
            else:
                # Enhanced status display with performance metrics (Requirements 7.4)
                status_text = f"Status: Connected ✅ | FPS: {fps:.1f} | Buffer: {buffer_usage:.0f}% | Frames: {frames_received}"
                
                # Add performance metrics if available
                if self.performance_collector:
                    try:
                        current_metrics = self.performance_collector.get_current_metrics()
                        memory_mb = current_metrics.memory_usage_mb
                        cpu_percent = current_metrics.cpu_usage_percent
                        
                        # Add memory and CPU info to status
                        status_text += f" | Mem: {memory_mb:.0f}MB | CPU: {cpu_percent:.0f}%"
                        
                        # Check for performance alerts
                        if hasattr(self.performance_collector, 'alerts_active') and self.performance_collector.alerts_active:
                            status_text += f" | ⚠️ {len(self.performance_collector.alerts_active)} alerts"
                    except Exception as e:
                        print(f"⚠️ Error getting performance metrics for status: {e}")
                
                if connection_errors > 0:
                    status_text += f" | Errors: {connection_errors}"
                
                self.esp32_status_label.config(text=status_text, foreground="green")
                self.update_esp32_status_indicator('connected')
                
                # Log status periodically (every 10 updates)
                if frames_received % 50 == 0 and frames_received > 0:
                    self.log_esp32_status(f"Receiving frames normally - FPS: {fps:.1f}", "info")
            
            # Continue updating if still connected or using fallback
            if self.esp32_receiver.is_connected() or self.esp32_receiver.is_using_fallback():
                self.after(2000, self.update_camera_status)
            
        except Exception as e:
            print(f"⚠️ Error updating camera status: {e}")
            self.log_esp32_error(f"Status update error: {str(e)}", {'stage': 'status_update'})
            # Check connection on error
            self.check_esp32_connection()
    
    def disconnect_esp32_camera(self):
        """Disconnect from ESP32-camera"""
        # Stop preview if active
        if hasattr(self, 'esp32_preview_active') and self.esp32_preview_active:
            self.stop_esp32_preview()
        
        if self.esp32_receiver:
            try:
                self.esp32_receiver.disconnect()
                self.esp32_status_label.config(text="Status: Disconnected", foreground="gray")
                self.update_esp32_status_indicator('disconnected')
                self.esp32_apply_btn.config(state="disabled")
                self.log_esp32_status("Disconnected from ESP32-camera", "info")
                print("📡 Disconnected from ESP32-camera")
            except Exception as e:
                self.log_esp32_error(f"Error during disconnect: {str(e)}", {'stage': 'disconnect'})
                print(f"⚠️ Error disconnecting ESP32-camera: {e}")
    
    def check_esp32_connection(self):
        """Check ESP32-camera connection and attempt reconnection if needed (Requirements 6.1)"""
        if not self.esp32_receiver:
            return
        
        try:
            if not self.esp32_receiver.is_connected() and not self.esp32_receiver.is_using_fallback():
                # Connection lost, attempt reconnection with error handler
                self.esp32_status_label.config(text="Status: Reconnecting...", foreground="orange")
                self.update()
                
                # The error handler will manage automatic reconnection
                if hasattr(self.esp32_receiver, 'error_handler') and self.esp32_receiver.error_handler:
                    # Error handler will manage reconnection automatically
                    pass
                else:
                    # Fallback to manual reconnection
                    if self.esp32_receiver.connect():
                        self.display_camera_info()
                        self.esp32_apply_btn.config(state="normal")
                        print("🔄 ESP32-camera reconnected successfully")
                    else:
                        self.esp32_status_label.config(text="Status: Reconnection failed ❌", foreground="red")
                        self.esp32_apply_btn.config(state="disabled")
                        print("❌ ESP32-camera reconnection failed")
                        
                        # Schedule another reconnection attempt
                        self.after(5000, self.check_esp32_connection)  # Try again in 5 seconds
            elif self.esp32_receiver.is_using_fallback():
                # Update status to show fallback mode
                self.esp32_status_label.config(text="Status: Using fallback webcam 📹", foreground="orange")
                self.esp32_apply_btn.config(state="disabled")
            
        except Exception as e:
            print(f"⚠️ Error checking ESP32-camera connection: {e}")
            self.esp32_status_label.config(text="Status: Connection error ❌", foreground="red")
            self.esp32_apply_btn.config(state="disabled")
    
    def apply_esp32_config(self):
        """Apply ESP32-camera configuration"""
        if not self.esp32_receiver or not self.esp32_receiver.is_connected():
            messagebox.showerror("Error", "ESP32-camera is not connected")
            return
        
        try:
            resolution = self.esp32_resolution_combo.get()
            fps = int(self.esp32_fps_combo.get())
            quality = int(self.esp32_quality_scale.get())
            
            # Validate configuration values
            if not self.validate_esp32_config(resolution, fps, quality):
                return
            
            # Update status to show configuration in progress
            original_text = self.esp32_status_label.cget("text")
            self.esp32_status_label.config(text="Status: Applying configuration...", foreground="orange")
            self.esp32_apply_btn.config(state="disabled")
            self.update()
            
            success = self.esp32_receiver.configure_camera(
                resolution=resolution,
                fps=fps,
                quality=quality
            )
            
            if success:
                # Save configuration to preferences
                self.save_esp32_config()
                
                # Reset apply button text
                self.reset_apply_button_text()
                
                messagebox.showinfo("Success", 
                    f"Configuration applied successfully:\n"
                    f"Resolution: {resolution}\n"
                    f"FPS: {fps}\n"
                    f"Quality: {quality}")
                print(f"✅ ESP32-camera configured: {resolution}, {fps}FPS, Q{quality}")
                
                # Restore status and re-enable button
                self.esp32_status_label.config(text=original_text, foreground="green")
                self.esp32_apply_btn.config(state="normal")
                
            else:
                messagebox.showerror("Error", "Failed to apply configuration to ESP32-camera")
                print("❌ Failed to apply ESP32-camera configuration")
                
                # Restore status and re-enable button
                self.esp32_status_label.config(text=original_text, foreground="green")
                self.esp32_apply_btn.config(state="normal")
                
        except ValueError as e:
            messagebox.showerror("Error", f"Invalid configuration value: {str(e)}")
            print(f"❌ Invalid ESP32-camera configuration: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Configuration error: {str(e)}")
            print(f"❌ ESP32-camera configuration error: {e}")
            
            # Restore button state on error
            self.esp32_apply_btn.config(state="normal")
    
    def validate_esp32_config(self, resolution: str, fps: int, quality: int) -> bool:
        """Validate ESP32-camera configuration parameters"""
        # Validate resolution
        valid_resolutions = ["QVGA", "VGA", "SVGA", "XGA"]
        if resolution not in valid_resolutions:
            messagebox.showerror("Error", f"Invalid resolution: {resolution}")
            return False
        
        # Validate FPS range (Requirements 5.2)
        if not (5 <= fps <= 30):
            messagebox.showerror("Error", f"FPS must be between 5 and 30, got: {fps}")
            return False
        
        # Validate quality range (Requirements 5.3)
        if not (10 <= quality <= 63):
            messagebox.showerror("Error", f"Quality must be between 10 and 63, got: {quality}")
            return False
        
        return True
    
    def save_esp32_config(self, resolution: str = None, fps: int = None, quality: int = None):
        """
        Save ESP32-camera configuration to preferences (Requirements 5.5)
        Enhanced with comprehensive settings persistence and validation
        """
        try:
            # Load existing configuration to preserve other settings
            config_data = self.load_full_esp32_config()
            
            # Update only provided parameters
            if resolution is not None:
                config_data["esp32_camera"]["resolution"] = resolution
            if fps is not None:
                config_data["esp32_camera"]["fps"] = fps
            if quality is not None:
                config_data["esp32_camera"]["quality"] = quality
            
            # Add metadata for configuration tracking
            config_data["esp32_camera"]["last_updated"] = int(time.time())
            config_data["esp32_camera"]["version"] = "1.0"
            
            # Get current UI state for comprehensive persistence
            if hasattr(self, 'esp32_resolution_combo'):
                config_data["esp32_camera"]["resolution"] = self.esp32_resolution_combo.get()
            if hasattr(self, 'esp32_fps_combo'):
                config_data["esp32_camera"]["fps"] = int(self.esp32_fps_combo.get())
            if hasattr(self, 'esp32_quality_scale'):
                config_data["esp32_camera"]["quality"] = int(self.esp32_quality_scale.get())
            
            # Add connection preferences
            config_data["esp32_camera"]["auto_connect"] = True
            config_data["esp32_camera"]["fallback_enabled"] = True
            
            # Save to configuration file with backup
            config_path = os.path.join(get_script_dir(), "esp32_camera_config.json")
            backup_path = os.path.join(get_script_dir(), "esp32_camera_config.json.backup")
            
            # Create backup of existing config
            if os.path.exists(config_path):
                import shutil
                shutil.copy2(config_path, backup_path)
            
            # Write new configuration
            with open(config_path, "w") as f:
                json.dump(config_data, f, indent=2)
            
            print(f"💾 ESP32-camera configuration saved to {config_path}")
            
            # Validate saved configuration
            if not self._validate_saved_config(config_path):
                print("⚠️ Configuration validation failed, restoring backup")
                if os.path.exists(backup_path):
                    shutil.copy2(backup_path, config_path)
                    
        except Exception as e:
            print(f"❌ Failed to save ESP32-camera configuration: {e}")
            # Try to restore from backup if available
            backup_path = os.path.join(get_script_dir(), "esp32_camera_config.json.backup")
            if os.path.exists(backup_path):
                try:
                    import shutil
                    config_path = os.path.join(get_script_dir(), "esp32_camera_config.json")
                    shutil.copy2(backup_path, config_path)
                    print("🔄 Configuration restored from backup")
                except Exception as restore_error:
                    print(f"❌ Failed to restore configuration backup: {restore_error}")
    
    def load_esp32_config(self):
        """
        Load ESP32-camera configuration from preferences (Requirements 5.5)
        Enhanced with validation and error recovery
        """
        try:
            config_data = self.load_full_esp32_config()
            esp32_config = config_data.get("esp32_camera", {})
            
            # Validate configuration before applying
            if not self._validate_config_data(esp32_config):
                print("⚠️ Invalid configuration detected, using defaults")
                esp32_config = self._get_default_esp32_config()
            
            # Apply saved configuration to UI with validation
            if "resolution" in esp32_config and hasattr(self, 'esp32_resolution_combo'):
                resolution = esp32_config["resolution"]
                if resolution in self.esp32_resolution_combo["values"]:
                    self.esp32_resolution_combo.set(resolution)
                else:
                    print(f"⚠️ Invalid resolution '{resolution}', using default")
                    self.esp32_resolution_combo.set("VGA")
            
            if "fps" in esp32_config and hasattr(self, 'esp32_fps_combo'):
                fps_str = str(esp32_config["fps"])
                if fps_str in self.esp32_fps_combo["values"]:
                    self.esp32_fps_combo.set(fps_str)
                else:
                    print(f"⚠️ Invalid FPS '{fps_str}', using default")
                    self.esp32_fps_combo.set("15")
            
            if "quality" in esp32_config and hasattr(self, 'esp32_quality_scale'):
                quality = esp32_config["quality"]
                if 10 <= quality <= 63:
                    self.esp32_quality_scale.set(quality)
                    self.update_quality_label(quality)
                else:
                    print(f"⚠️ Invalid quality '{quality}', using default")
                    self.esp32_quality_scale.set(50)
                    self.update_quality_label(50)
            
            # Apply connection preferences
            self.esp32_auto_connect = esp32_config.get("auto_connect", True)
            self.esp32_fallback_enabled = esp32_config.get("fallback_enabled", True)
            
            print(f"📂 ESP32-camera configuration loaded successfully")
            
        except Exception as e:
            print(f"⚠️ Failed to load ESP32-camera configuration: {e}")
            # Use default values if loading fails
            self._apply_default_esp32_config()
    
    def load_full_esp32_config(self) -> dict:
        """Load complete ESP32-camera configuration with error handling"""
        config_path = os.path.join(get_script_dir(), "esp32_camera_config.json")
        
        try:
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️ Error reading configuration file: {e}")
            # Try backup file
            backup_path = config_path + ".backup"
            if os.path.exists(backup_path):
                try:
                    with open(backup_path, "r") as f:
                        print("🔄 Loading configuration from backup")
                        return json.load(f)
                except Exception as backup_error:
                    print(f"⚠️ Backup configuration also corrupted: {backup_error}")
        
        # Return default configuration structure
        return self._get_default_config_structure()
    
    def _get_default_config_structure(self) -> dict:
        """Get default configuration structure"""
        return {
            "esp32_camera": self._get_default_esp32_config(),
            "ui_preferences": {
                "auto_connect_on_selection": True,
                "show_advanced_status": False,
                "status_update_interval": 2000
            },
            "metadata": {
                "created": int(time.time()),
                "version": "1.0"
            }
        }
    
    def _get_default_esp32_config(self) -> dict:
        """Get default ESP32-camera configuration"""
        return {
            "resolution": "VGA",
            "fps": 15,
            "quality": 50,
            "port": "COM3",
            "baud": 921600,
            "auto_connect": True,
            "fallback_enabled": True,
            "buffer_size": 10,
            "connection_timeout": 5.0,
            "retry_attempts": 3
        }
    
    def _validate_config_data(self, config: dict) -> bool:
        """Validate ESP32-camera configuration data"""
        try:
            # Check required fields
            required_fields = ["resolution", "fps", "quality"]
            for field in required_fields:
                if field not in config:
                    return False
            
            # Validate resolution
            valid_resolutions = ["QVGA", "VGA", "SVGA", "XGA"]
            if config["resolution"] not in valid_resolutions:
                return False
            
            # Validate FPS range
            fps = config["fps"]
            if not isinstance(fps, int) or not (5 <= fps <= 30):
                return False
            
            # Validate quality range
            quality = config["quality"]
            if not isinstance(quality, int) or not (10 <= quality <= 63):
                return False
            
            return True
            
        except Exception:
            return False
    
    def _validate_saved_config(self, config_path: str) -> bool:
        """Validate that saved configuration file is readable and valid"""
        try:
            with open(config_path, "r") as f:
                config_data = json.load(f)
            
            esp32_config = config_data.get("esp32_camera", {})
            return self._validate_config_data(esp32_config)
            
        except Exception:
            return False
    
    def _apply_default_esp32_config(self):
        """Apply default ESP32-camera configuration to UI"""
        try:
            if hasattr(self, 'esp32_resolution_combo'):
                self.esp32_resolution_combo.set("VGA")
            if hasattr(self, 'esp32_fps_combo'):
                self.esp32_fps_combo.set("15")
            if hasattr(self, 'esp32_quality_scale'):
                self.esp32_quality_scale.set(50)
                self.update_quality_label(50)
            
            print("🔧 Applied default ESP32-camera configuration")
            
        except Exception as e:
            print(f"⚠️ Error applying default configuration: {e}")
    
    def export_esp32_config(self, export_path: str = None) -> bool:
        """
        Export ESP32-camera configuration to external file
        
        Args:
            export_path: Optional path for export file
            
        Returns:
            True if export successful
        """
        try:
            if not export_path:
                from tkinter import filedialog
                export_path = filedialog.asksaveasfilename(
                    title="Export ESP32-Camera Configuration",
                    defaultextension=".json",
                    filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
                )
                
            if not export_path:
                return False
            
            config_data = self.load_full_esp32_config()
            
            # Add export metadata
            config_data["export_info"] = {
                "exported_at": int(time.time()),
                "exported_by": "C2C Launcher",
                "version": "1.0"
            }
            
            with open(export_path, "w") as f:
                json.dump(config_data, f, indent=2)
            
            print(f"📤 ESP32-camera configuration exported to {export_path}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to export configuration: {e}")
            return False
    
    def import_esp32_config(self, import_path: str = None) -> bool:
        """
        Import ESP32-camera configuration from external file
        
        Args:
            import_path: Optional path for import file
            
        Returns:
            True if import successful
        """
        try:
            if not import_path:
                from tkinter import filedialog
                import_path = filedialog.askopenfilename(
                    title="Import ESP32-Camera Configuration",
                    filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
                )
                
            if not import_path or not os.path.exists(import_path):
                return False
            
            # Load and validate imported configuration
            with open(import_path, "r") as f:
                imported_data = json.load(f)
            
            esp32_config = imported_data.get("esp32_camera", {})
            if not self._validate_config_data(esp32_config):
                print("❌ Invalid configuration in import file")
                return False
            
            # Apply imported configuration
            if "resolution" in esp32_config:
                self.esp32_resolution_combo.set(esp32_config["resolution"])
            if "fps" in esp32_config:
                self.esp32_fps_combo.set(str(esp32_config["fps"]))
            if "quality" in esp32_config:
                self.esp32_quality_scale.set(esp32_config["quality"])
                self.update_quality_label(esp32_config["quality"])
            
            # Save the imported configuration
            self.save_esp32_config()
            
            print(f"📥 ESP32-camera configuration imported from {import_path}")
            return True
            
        except Exception as e:
            print(f"❌ Failed to import configuration: {e}")
            return False
    
    def toggle_esp32_preview(self):
        """Toggle ESP32-camera live preview (Requirements 8.3)"""
        if self.esp32_preview_var.get():
            self.start_esp32_preview()
        else:
            self.stop_esp32_preview()
    
    def start_esp32_preview(self):
        """Start ESP32-camera live preview window"""
        if not self.esp32_receiver or not self.esp32_receiver.is_connected():
            messagebox.showerror("Error", "ESP32-camera is not connected")
            self.esp32_preview_var.set(False)
            return
        
        if self.esp32_preview_active:
            return  # Already active
        
        try:
            # Create preview window
            self.esp32_preview_window = tk.Toplevel(self)
            self.esp32_preview_window.title("ESP32-Camera Live Preview")
            self.esp32_preview_window.geometry("640x480")
            self.esp32_preview_window.protocol("WM_DELETE_WINDOW", self.close_esp32_preview)
            
            # Create preview label for video display
            self.esp32_preview_label = ttk.Label(self.esp32_preview_window)
            self.esp32_preview_label.pack(expand=True, fill="both")
            
            # Add status label
            self.esp32_preview_status = ttk.Label(
                self.esp32_preview_window, 
                text="Initializing preview...", 
                font=("Segoe UI", 9, "italic")
            )
            self.esp32_preview_status.pack(side="bottom", pady=5)
            
            # Add control frame
            control_frame = ttk.Frame(self.esp32_preview_window)
            control_frame.pack(side="bottom", fill="x", padx=5, pady=5)
            
            # Add snapshot button
            snapshot_btn = ttk.Button(control_frame, text="Take Snapshot", command=self.take_esp32_snapshot)
            snapshot_btn.pack(side="left", padx=(0, 5))
            
            # Add recording button (placeholder for future enhancement)
            record_btn = ttk.Button(control_frame, text="Record", command=self.toggle_esp32_recording, state="disabled")
            record_btn.pack(side="left", padx=(0, 5))
            
            # Add close button
            close_btn = ttk.Button(control_frame, text="Close Preview", command=self.close_esp32_preview)
            close_btn.pack(side="right")
            
            # Start preview thread
            self.esp32_preview_active = True
            self.esp32_preview_stop_event.clear()
            self.esp32_preview_thread = threading.Thread(target=self._esp32_preview_loop, daemon=True)
            self.esp32_preview_thread.start()
            
            print("📹 ESP32-camera live preview started")
            
        except Exception as e:
            print(f"❌ Failed to start ESP32-camera preview: {e}")
            messagebox.showerror("Error", f"Failed to start preview: {str(e)}")
            self.esp32_preview_var.set(False)
    
    def stop_esp32_preview(self):
        """Stop ESP32-camera live preview"""
        self.esp32_preview_active = False
        
        if self.esp32_preview_thread and self.esp32_preview_thread.is_alive():
            self.esp32_preview_stop_event.set()
            self.esp32_preview_thread.join(timeout=2)
        
        if self.esp32_preview_window:
            self.esp32_preview_window.destroy()
            self.esp32_preview_window = None
            self.esp32_preview_label = None
        
        print("📹 ESP32-camera live preview stopped")
    
    def close_esp32_preview(self):
        """Close ESP32-camera preview window"""
        self.esp32_preview_var.set(False)
        self.stop_esp32_preview()
    
    def _esp32_preview_loop(self):
        """Main loop for ESP32-camera preview display"""
        frame_count = 0
        last_fps_time = time.time()
        fps_display = 0.0
        
        while self.esp32_preview_active and not self.esp32_preview_stop_event.is_set():
            try:
                if not self.esp32_receiver or not self.esp32_receiver.is_connected():
                    # Check for fallback mode
                    if self.esp32_receiver and self.esp32_receiver.is_using_fallback():
                        self._update_preview_status("Using fallback webcam")
                        # Get frame from fallback
                        fallback_cap = self.esp32_receiver.get_fallback_capture()
                        if fallback_cap:
                            ret, frame = fallback_cap.read()
                            if ret and frame is not None:
                                self._display_preview_frame(frame, fps_display)
                    else:
                        self._update_preview_status("Connection lost - attempting reconnection...")
                        time.sleep(1)
                    continue
                
                # Get frame from ESP32-camera
                frame_data = self.esp32_receiver.read_frame_with_metadata()
                
                if frame_data is not None:
                    frame, metadata = frame_data
                    
                    # Calculate FPS
                    frame_count += 1
                    current_time = time.time()
                    if current_time - last_fps_time >= 1.0:
                        fps_display = frame_count / (current_time - last_fps_time)
                        frame_count = 0
                        last_fps_time = current_time
                    
                    # Display frame
                    self._display_preview_frame(frame, fps_display, metadata)
                    
                    # Update status
                    status_text = f"Live | FPS: {fps_display:.1f} | {metadata['dimensions'][0]}x{metadata['dimensions'][1]}"
                    self._update_preview_status(status_text)
                    
                else:
                    # No frame available
                    self._update_preview_status("Waiting for frames...")
                    time.sleep(0.1)
                
                # Small delay to prevent excessive CPU usage
                time.sleep(0.033)  # ~30 FPS max display rate
                
            except Exception as e:
                print(f"⚠️ Error in preview loop: {e}")
                self._update_preview_status(f"Preview error: {str(e)[:50]}...")
                time.sleep(0.5)
    
    def _display_preview_frame(self, frame, fps=0.0, metadata=None):
        """Display frame in preview window"""
        try:
            if not self.esp32_preview_label or not self.esp32_preview_window:
                return
            
            # Resize frame to fit preview window while maintaining aspect ratio
            preview_width = 640
            preview_height = 480
            
            h, w = frame.shape[:2]
            aspect_ratio = w / h
            
            if aspect_ratio > preview_width / preview_height:
                # Width is limiting factor
                new_width = preview_width
                new_height = int(preview_width / aspect_ratio)
            else:
                # Height is limiting factor
                new_height = preview_height
                new_width = int(preview_height * aspect_ratio)
            
            # Resize frame
            resized_frame = cv2.resize(frame, (new_width, new_height))
            
            # Add FPS overlay
            if fps > 0:
                cv2.putText(resized_frame, f"FPS: {fps:.1f}", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # Add metadata overlay if available
            if metadata:
                seq_text = f"Seq: {metadata.get('sequence', 'N/A')}"
                cv2.putText(resized_frame, seq_text, (10, 60), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Convert BGR to RGB for Tkinter
            rgb_frame = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
            
            # Convert to PIL Image and then to PhotoImage
            pil_image = Image.fromarray(rgb_frame)
            photo = ImageTk.PhotoImage(pil_image)
            
            # Update label in main thread
            def update_label():
                if self.esp32_preview_label and self.esp32_preview_window:
                    self.esp32_preview_label.configure(image=photo)
                    self.esp32_preview_label.image = photo  # Keep a reference
            
            self.after_idle(update_label)
            
        except Exception as e:
            print(f"⚠️ Error displaying preview frame: {e}")
    
    def _update_preview_status(self, status_text):
        """Update preview status label"""
        try:
            def update_status():
                if self.esp32_preview_status and self.esp32_preview_window:
                    self.esp32_preview_status.configure(text=status_text)
            
            self.after_idle(update_status)
            
        except Exception as e:
            print(f"⚠️ Error updating preview status: {e}")
    
    def take_esp32_snapshot(self):
        """Take a snapshot from ESP32-camera preview"""
        try:
            if not self.esp32_receiver or not self.esp32_receiver.is_connected():
                messagebox.showerror("Error", "ESP32-camera is not connected")
                return
            
            # Get current frame
            frame_data = self.esp32_receiver.read_frame_with_metadata()
            if frame_data is None:
                messagebox.showerror("Error", "No frame available for snapshot")
                return
            
            frame, metadata = frame_data
            
            # Ask user for save location
            timestamp = int(time.time())
            default_name = f"esp32_snapshot_{timestamp}.jpg"
            
            file_path = filedialog.asksaveasfilename(
                title="Save Snapshot",
                defaultextension=".jpg",
                initialvalue=default_name,
                filetypes=[
                    ("JPEG files", "*.jpg"),
                    ("PNG files", "*.png"),
                    ("All files", "*.*")
                ]
            )
            
            if file_path:
                # Save frame
                success = cv2.imwrite(file_path, frame)
                if success:
                    messagebox.showinfo("Success", f"Snapshot saved to:\n{file_path}")
                    print(f"📸 Snapshot saved: {file_path}")
                else:
                    messagebox.showerror("Error", "Failed to save snapshot")
                    print("❌ Failed to save snapshot")
            
        except Exception as e:
            print(f"❌ Error taking snapshot: {e}")
            messagebox.showerror("Error", f"Failed to take snapshot: {str(e)}")
    
    def toggle_esp32_recording(self):
        """Toggle ESP32-camera recording (placeholder for future enhancement)"""
        messagebox.showinfo("Feature Not Available", 
                           "Video recording feature will be available in a future update.")
    
    def update_esp32_status_indicator(self, status_type: str):
        """
        Update ESP32-camera status indicator LED (Requirements 8.2, 8.5)
        
        Args:
            status_type: 'connected', 'connecting', 'error', 'disconnected', 'fallback'
        """
        try:
            color_map = {
                'connected': '#00FF00',      # Green
                'connecting': '#FFA500',     # Orange
                'error': '#FF0000',          # Red
                'disconnected': '#808080',   # Gray
                'fallback': '#FFFF00'        # Yellow
            }
            
            color = color_map.get(status_type, '#808080')
            self.esp32_status_indicator.itemconfig(self.esp32_status_circle, fill=color)
            
        except Exception as e:
            print(f"⚠️ Error updating status indicator: {e}")
    
    def log_esp32_status(self, status_message: str, status_type: str = "info"):
        """
        Log ESP32-camera status with timestamp (Requirements 8.5)
        
        Args:
            status_message: Status message to log
            status_type: Type of status ('info', 'warning', 'error', 'success')
        """
        try:
            timestamp = time.time()
            status_entry = {
                'timestamp': timestamp,
                'message': status_message,
                'type': status_type,
                'formatted_time': time.strftime('%H:%M:%S', time.localtime(timestamp))
            }
            
            self.esp32_status_history.append(status_entry)
            
            # Keep only last 100 status entries
            if len(self.esp32_status_history) > 100:
                self.esp32_status_history = self.esp32_status_history[-100:]
            
            print(f"📊 ESP32 Status [{status_type.upper()}]: {status_message}")
            
        except Exception as e:
            print(f"⚠️ Error logging ESP32 status: {e}")
    
    def log_esp32_error(self, error_message: str, error_details: dict = None):
        """
        Log ESP32-camera error with details (Requirements 8.5)
        
        Args:
            error_message: Error message
            error_details: Additional error details dictionary
        """
        try:
            timestamp = time.time()
            error_entry = {
                'timestamp': timestamp,
                'message': error_message,
                'details': error_details or {},
                'formatted_time': time.strftime('%H:%M:%S', time.localtime(timestamp)),
                'connection_attempt': self.esp32_connection_attempts
            }
            
            self.esp32_error_history.append(error_entry)
            
            # Keep only last 50 error entries
            if len(self.esp32_error_history) > 50:
                self.esp32_error_history = self.esp32_error_history[-50:]
            
            # Update status indicator
            self.update_esp32_status_indicator('error')
            
            print(f"❌ ESP32 Error: {error_message}")
            if error_details:
                print(f"   Details: {error_details}")
            
        except Exception as e:
            print(f"⚠️ Error logging ESP32 error: {e}")
    
    def show_esp32_details(self):
        """Show detailed ESP32-camera status information (Requirements 8.2)"""
        try:
            # Create details window
            details_window = tk.Toplevel(self)
            details_window.title("ESP32-Camera Details")
            details_window.geometry("600x500")
            details_window.resizable(True, True)
            
            # Create notebook for tabs
            notebook = ttk.Notebook(details_window)
            notebook.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Connection Status Tab
            status_frame = ttk.Frame(notebook)
            notebook.add(status_frame, text="Connection Status")
            
            # Status information
            status_text = tk.Text(status_frame, wrap="word", height=15)
            status_scrollbar = ttk.Scrollbar(status_frame, orient="vertical", command=status_text.yview)
            status_text.configure(yscrollcommand=status_scrollbar.set)
            
            status_text.pack(side="left", fill="both", expand=True)
            status_scrollbar.pack(side="right", fill="y")
            
            # Populate status information
            status_info = self._get_detailed_status_info()
            status_text.insert("1.0", status_info)
            status_text.config(state="disabled")
            
            # Statistics Tab
            stats_frame = ttk.Frame(notebook)
            notebook.add(stats_frame, text="Statistics")
            
            stats_text = tk.Text(stats_frame, wrap="word", height=15)
            stats_scrollbar = ttk.Scrollbar(stats_frame, orient="vertical", command=stats_text.yview)
            stats_text.configure(yscrollcommand=stats_scrollbar.set)
            
            stats_text.pack(side="left", fill="both", expand=True)
            stats_scrollbar.pack(side="right", fill="y")
            
            # Populate statistics
            if self.esp32_receiver:
                stats_info = self._format_receiver_stats()
                stats_text.insert("1.0", stats_info)
            else:
                stats_text.insert("1.0", "ESP32-camera receiver not initialized")
            stats_text.config(state="disabled")
            
            # Configuration Tab
            config_frame = ttk.Frame(notebook)
            notebook.add(config_frame, text="Configuration")
            
            config_text = tk.Text(config_frame, wrap="word", height=15)
            config_scrollbar = ttk.Scrollbar(config_frame, orient="vertical", command=config_text.yview)
            config_text.configure(yscrollcommand=config_scrollbar.set)
            
            config_text.pack(side="left", fill="both", expand=True)
            config_scrollbar.pack(side="right", fill="y")
            
            # Populate configuration
            config_info = self._get_current_configuration()
            config_text.insert("1.0", config_info)
            config_text.config(state="disabled")
            
            # Add refresh button
            refresh_btn = ttk.Button(details_window, text="Refresh", 
                                   command=lambda: self._refresh_details_window(details_window, notebook))
            refresh_btn.pack(pady=5)
            
        except Exception as e:
            print(f"❌ Error showing ESP32 details: {e}")
            messagebox.showerror("Error", f"Failed to show details: {str(e)}")
    
    def show_esp32_errors(self):
        """Show ESP32-camera error history (Requirements 8.5)"""
        try:
            # Create error window
            error_window = tk.Toplevel(self)
            error_window.title("ESP32-Camera Error History")
            error_window.geometry("700x400")
            error_window.resizable(True, True)
            
            # Create main frame
            main_frame = ttk.Frame(error_window)
            main_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Error list with treeview
            columns = ("Time", "Message", "Details")
            error_tree = ttk.Treeview(main_frame, columns=columns, show="headings", height=15)
            
            # Configure columns
            error_tree.heading("Time", text="Time")
            error_tree.heading("Message", text="Error Message")
            error_tree.heading("Details", text="Details")
            
            error_tree.column("Time", width=80, minwidth=80)
            error_tree.column("Message", width=300, minwidth=200)
            error_tree.column("Details", width=200, minwidth=150)
            
            # Add scrollbar
            error_scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=error_tree.yview)
            error_tree.configure(yscrollcommand=error_scrollbar.set)
            
            error_tree.pack(side="left", fill="both", expand=True)
            error_scrollbar.pack(side="right", fill="y")
            
            # Populate error history
            for error_entry in reversed(self.esp32_error_history):  # Most recent first
                details_str = str(error_entry.get('details', {}))
                if len(details_str) > 50:
                    details_str = details_str[:47] + "..."
                
                error_tree.insert("", "end", values=(
                    error_entry['formatted_time'],
                    error_entry['message'],
                    details_str
                ))
            
            # Add control buttons
            button_frame = ttk.Frame(error_window)
            button_frame.pack(fill="x", padx=10, pady=5)
            
            clear_btn = ttk.Button(button_frame, text="Clear History", command=self._clear_error_history)
            clear_btn.pack(side="left")
            
            export_btn = ttk.Button(button_frame, text="Export Log", command=self._export_error_log)
            export_btn.pack(side="left", padx=(5, 0))
            
            close_btn = ttk.Button(button_frame, text="Close", command=error_window.destroy)
            close_btn.pack(side="right")
            
            # Show summary
            if self.esp32_error_history:
                summary_text = f"Total errors: {len(self.esp32_error_history)} | " \
                              f"Last error: {self.esp32_error_history[-1]['formatted_time']}"
            else:
                summary_text = "No errors recorded"
            
            summary_label = ttk.Label(error_window, text=summary_text, font=("Segoe UI", 9, "italic"))
            summary_label.pack(pady=5)
            
        except Exception as e:
            print(f"❌ Error showing ESP32 error history: {e}")
            messagebox.showerror("Error", f"Failed to show error history: {str(e)}")
    
    def show_esp32_performance(self):
        """Show ESP32-camera performance metrics (Requirements 7.4)"""
        try:
            if not PERFORMANCE_MONITORING_AVAILABLE:
                messagebox.showwarning("Performance Monitoring", 
                                     "Performance monitoring is not available.\n"
                                     "Please install required dependencies (psutil, matplotlib).")
                return
            
            if not self.performance_collector:
                messagebox.showwarning("Performance Monitoring", 
                                     "Performance monitoring is not initialized.\n"
                                     "Please connect to ESP32-camera first.")
                return
            
            # Create performance window
            perf_window = tk.Toplevel(self)
            perf_window.title("ESP32-Camera Performance Metrics")
            perf_window.geometry("800x600")
            perf_window.resizable(True, True)
            
            # Create notebook for tabs
            notebook = ttk.Notebook(perf_window)
            notebook.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Current Metrics Tab
            current_frame = ttk.Frame(notebook)
            notebook.add(current_frame, text="Current Metrics")
            
            # Current metrics display
            current_text = tk.Text(current_frame, wrap="word", height=20, font=("Consolas", 10))
            current_scrollbar = ttk.Scrollbar(current_frame, orient="vertical", command=current_text.yview)
            current_text.configure(yscrollcommand=current_scrollbar.set)
            
            current_text.pack(side="left", fill="both", expand=True)
            current_scrollbar.pack(side="right", fill="y")
            
            # Performance Summary Tab
            summary_frame = ttk.Frame(notebook)
            notebook.add(summary_frame, text="Performance Summary")
            
            summary_text = tk.Text(summary_frame, wrap="word", height=20, font=("Consolas", 10))
            summary_scrollbar = ttk.Scrollbar(summary_frame, orient="vertical", command=summary_text.yview)
            summary_text.configure(yscrollcommand=summary_scrollbar.set)
            
            summary_text.pack(side="left", fill="both", expand=True)
            summary_scrollbar.pack(side="right", fill="y")
            
            # Memory Usage Tab
            memory_frame = ttk.Frame(notebook)
            notebook.add(memory_frame, text="Memory Usage")
            
            memory_text = tk.Text(memory_frame, wrap="word", height=20, font=("Consolas", 10))
            memory_scrollbar = ttk.Scrollbar(memory_frame, orient="vertical", command=memory_text.yview)
            memory_text.configure(yscrollcommand=memory_scrollbar.set)
            
            memory_text.pack(side="left", fill="both", expand=True)
            memory_scrollbar.pack(side="right", fill="y")
            
            # Populate performance data
            self._update_performance_display(current_text, summary_text, memory_text)
            
            # Add control buttons
            button_frame = ttk.Frame(perf_window)
            button_frame.pack(fill="x", padx=10, pady=5)
            
            refresh_btn = ttk.Button(button_frame, text="Refresh", 
                                   command=lambda: self._update_performance_display(current_text, summary_text, memory_text))
            refresh_btn.pack(side="left")
            
            export_csv_btn = ttk.Button(button_frame, text="Export CSV", 
                                      command=self._export_performance_csv)
            export_csv_btn.pack(side="left", padx=(5, 0))
            
            export_json_btn = ttk.Button(button_frame, text="Export JSON", 
                                       command=self._export_performance_json)
            export_json_btn.pack(side="left", padx=(5, 0))
            
            # Auto-refresh checkbox
            auto_refresh_var = tk.BooleanVar(value=True)
            auto_refresh_cb = ttk.Checkbutton(button_frame, text="Auto-refresh (5s)", 
                                            variable=auto_refresh_var)
            auto_refresh_cb.pack(side="left", padx=(10, 0))
            
            close_btn = ttk.Button(button_frame, text="Close", command=perf_window.destroy)
            close_btn.pack(side="right")
            
            # Auto-refresh functionality
            def auto_refresh():
                if auto_refresh_var.get() and perf_window.winfo_exists():
                    try:
                        self._update_performance_display(current_text, summary_text, memory_text)
                        perf_window.after(5000, auto_refresh)  # Refresh every 5 seconds
                    except tk.TclError:
                        pass  # Window was closed
            
            # Start auto-refresh
            perf_window.after(5000, auto_refresh)
            
        except Exception as e:
            print(f"❌ Error showing ESP32 performance metrics: {e}")
            messagebox.showerror("Error", f"Failed to show performance metrics: {str(e)}")
    
    def _update_performance_display(self, current_text, summary_text, memory_text):
        """Update performance display with current metrics"""
        try:
            # Clear existing content
            current_text.config(state="normal")
            summary_text.config(state="normal")
            memory_text.config(state="normal")
            
            current_text.delete("1.0", tk.END)
            summary_text.delete("1.0", tk.END)
            memory_text.delete("1.0", tk.END)
            
            if not self.performance_collector:
                current_text.insert("1.0", "Performance collector not available")
                summary_text.insert("1.0", "Performance collector not available")
                memory_text.insert("1.0", "Performance collector not available")
                return
            
            # Current metrics
            current_metrics = self.performance_collector.get_current_metrics()
            current_info = self._format_current_metrics(current_metrics)
            current_text.insert("1.0", current_info)
            
            # Performance summary (last 5 minutes)
            summary = self.performance_collector.get_performance_summary(300)
            summary_info = self._format_performance_summary(summary)
            summary_text.insert("1.0", summary_info)
            
            # Memory usage details
            if self.esp32_receiver:
                memory_stats = self.esp32_receiver.get_memory_stats()
                memory_info = self._format_memory_stats(memory_stats)
                memory_text.insert("1.0", memory_info)
            else:
                memory_text.insert("1.0", "ESP32 receiver not available")
            
            # Make text read-only
            current_text.config(state="disabled")
            summary_text.config(state="disabled")
            memory_text.config(state="disabled")
            
        except Exception as e:
            print(f"⚠️ Error updating performance display: {e}")
    
    def _format_current_metrics(self, metrics) -> str:
        """Format current performance metrics for display"""
        lines = []
        lines.append("ESP32-Camera Performance Metrics")
        lines.append("=" * 40)
        lines.append("")
        lines.append(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(metrics.timestamp))}")
        lines.append("")
        
        lines.append("Frame Processing:")
        lines.append(f"  Frame Count: {metrics.frame_count}")
        lines.append(f"  YOLO FPS: {metrics.yolo_fps:.1f}")
        lines.append(f"  Frame FPS: {metrics.frame_fps:.1f}")
        lines.append(f"  ESP32 FPS: {metrics.esp32_fps:.1f}")
        lines.append(f"  Frames Dropped: {metrics.frames_dropped}")
        lines.append("")
        
        lines.append("Processing Times:")
        lines.append(f"  YOLO Processing: {metrics.yolo_processing_time_ms:.1f} ms")
        lines.append(f"  Frame Processing: {metrics.frame_processing_time_ms:.1f} ms")
        lines.append("")
        
        lines.append("System Resources:")
        lines.append(f"  Memory Usage: {metrics.memory_usage_mb:.1f} MB")
        lines.append(f"  CPU Usage: {metrics.cpu_usage_percent:.1f}%")
        lines.append(f"  Buffer Usage: {metrics.buffer_usage_percent:.1f}%")
        
        if metrics.temperature_celsius > 0:
            lines.append(f"  Temperature: {metrics.temperature_celsius:.1f}°C")
        
        if metrics.gpu_usage_percent > 0:
            lines.append(f"  GPU Usage: {metrics.gpu_usage_percent:.1f}%")
        
        return "\n".join(lines)
    
    def _format_performance_summary(self, summary) -> str:
        """Format performance summary for display"""
        if 'error' in summary:
            return f"Error: {summary['error']}"
        
        lines = []
        lines.append("Performance Summary (Last 5 Minutes)")
        lines.append("=" * 40)
        lines.append("")
        lines.append(f"Data Points: {summary['metrics_count']}")
        lines.append(f"Performance Score: {summary['performance_score']:.1f}/100")
        lines.append("")
        
        # YOLO Performance
        yolo = summary['yolo_fps']
        lines.append("YOLO Processing:")
        lines.append(f"  Current: {yolo['current']:.1f} FPS")
        lines.append(f"  Average: {yolo['avg']:.1f} FPS")
        lines.append(f"  Range: {yolo['min']:.1f} - {yolo['max']:.1f} FPS")
        lines.append("")
        
        # ESP32 Performance
        esp32 = summary['esp32_fps']
        lines.append("ESP32 Camera:")
        lines.append(f"  Current: {esp32['current']:.1f} FPS")
        lines.append(f"  Average: {esp32['avg']:.1f} FPS")
        lines.append(f"  Range: {esp32['min']:.1f} - {esp32['max']:.1f} FPS")
        lines.append("")
        
        # Memory Usage
        memory = summary['memory_usage_mb']
        lines.append("Memory Usage:")
        lines.append(f"  Current: {memory['current']:.1f} MB")
        lines.append(f"  Average: {memory['avg']:.1f} MB")
        lines.append(f"  Peak: {memory['max']:.1f} MB")
        lines.append("")
        
        # CPU Usage
        cpu = summary['cpu_usage_percent']
        lines.append("CPU Usage:")
        lines.append(f"  Current: {cpu['current']:.1f}%")
        lines.append(f"  Average: {cpu['avg']:.1f}%")
        lines.append(f"  Peak: {cpu['max']:.1f}%")
        lines.append("")
        
        lines.append(f"Total Frames Dropped: {summary['total_frames_dropped']}")
        
        if summary['active_alerts']:
            lines.append("")
            lines.append("Active Performance Alerts:")
            for alert in summary['active_alerts']:
                lines.append(f"  - {alert}")
        
        return "\n".join(lines)
    
    def _format_memory_stats(self, memory_stats) -> str:
        """Format memory statistics for display"""
        lines = []
        lines.append("Memory Usage Details")
        lines.append("=" * 25)
        lines.append("")
        
        lines.append(f"Current Memory: {memory_stats['current_memory_mb']:.1f} MB")
        lines.append(f"Peak Memory: {memory_stats['peak_memory_mb']:.1f} MB")
        lines.append(f"Frame Buffer Memory: {memory_stats['frame_buffer_memory_mb']:.1f} MB")
        lines.append("")
        
        lines.append("Memory Management:")
        lines.append(f"  Memory Leaks Detected: {memory_stats['memory_leaks_detected']}")
        lines.append(f"  Garbage Collections: {memory_stats['gc_collections']}")
        lines.append(f"  Memory Cleanups: {memory_stats['memory_cleanup_count']}")
        lines.append("")
        
        lines.append("Efficiency Metrics:")
        lines.append(f"  Frames per MB: {memory_stats['frames_per_mb']:.2f}")
        lines.append(f"  Total Frames Processed: {memory_stats['total_frames_processed']}")
        lines.append(f"  Buffer Usage: {memory_stats['buffer_usage_percent']:.1f}%")
        lines.append("")
        
        lines.append(f"psutil Available: {'Yes' if memory_stats['psutil_available'] else 'No'}")
        
        return "\n".join(lines)
    
    def _export_performance_csv(self):
        """Export performance metrics to CSV file"""
        try:
            if not self.performance_collector:
                messagebox.showwarning("Export", "Performance collector not available")
                return
            
            filename = filedialog.asksaveasfilename(
                title="Export Performance Metrics",
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
            )
            
            if filename:
                self.performance_collector.export_to_csv(filename, duration_seconds=3600)  # Last hour
                messagebox.showinfo("Export", f"Performance metrics exported to:\n{filename}")
                
        except Exception as e:
            print(f"❌ Error exporting performance CSV: {e}")
            messagebox.showerror("Export Error", f"Failed to export CSV: {str(e)}")
    
    def _export_performance_json(self):
        """Export performance metrics to JSON file"""
        try:
            if not self.performance_collector:
                messagebox.showwarning("Export", "Performance collector not available")
                return
            
            filename = filedialog.asksaveasfilename(
                title="Export Performance Metrics",
                defaultextension=".json",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            
            if filename:
                self.performance_collector.export_to_json(filename, duration_seconds=3600)  # Last hour
                messagebox.showinfo("Export", f"Performance metrics exported to:\n{filename}")
                
        except Exception as e:
            print(f"❌ Error exporting performance JSON: {e}")
            messagebox.showerror("Export Error", f"Failed to export JSON: {str(e)}")
    
    def _get_detailed_status_info(self) -> str:
        """Get detailed status information for display"""
        try:
            info_lines = []
            info_lines.append("ESP32-Camera Connection Status")
            info_lines.append("=" * 40)
            info_lines.append("")
            
            # Connection information
            if self.esp32_receiver:
                info_lines.append(f"Port: {self.esp32_receiver.port}")
                info_lines.append(f"Baud Rate: {self.esp32_receiver.baud}")
                info_lines.append(f"Connected: {'Yes' if self.esp32_receiver.is_connected() else 'No'}")
                info_lines.append(f"Using Fallback: {'Yes' if self.esp32_receiver.is_using_fallback() else 'No'}")
            else:
                info_lines.append("Receiver: Not initialized")
            
            info_lines.append("")
            info_lines.append(f"Connection Attempts: {self.esp32_connection_attempts}")
            
            if self.esp32_last_successful_connection:
                last_conn_time = time.strftime('%Y-%m-%d %H:%M:%S', 
                                             time.localtime(self.esp32_last_successful_connection))
                info_lines.append(f"Last Successful Connection: {last_conn_time}")
            else:
                info_lines.append("Last Successful Connection: Never")
            
            info_lines.append("")
            info_lines.append("Recent Status History:")
            info_lines.append("-" * 25)
            
            # Show last 10 status entries
            recent_status = self.esp32_status_history[-10:] if self.esp32_status_history else []
            for status_entry in reversed(recent_status):
                info_lines.append(f"[{status_entry['formatted_time']}] {status_entry['type'].upper()}: {status_entry['message']}")
            
            if not recent_status:
                info_lines.append("No status history available")
            
            return "\n".join(info_lines)
            
        except Exception as e:
            return f"Error generating status info: {str(e)}"
    
    def _format_receiver_stats(self) -> str:
        """Format receiver statistics for display"""
        try:
            if not self.esp32_receiver:
                return "ESP32-camera receiver not available"
            
            stats = self.esp32_receiver.get_stats()
            buffer_health = self.esp32_receiver.get_buffer_health()
            
            info_lines = []
            info_lines.append("ESP32-Camera Statistics")
            info_lines.append("=" * 30)
            info_lines.append("")
            
            # Frame statistics
            info_lines.append("Frame Statistics:")
            info_lines.append(f"  Frames Received: {stats.get('frames_received', 0)}")
            info_lines.append(f"  Frames Dropped: {stats.get('frames_dropped', 0)}")
            info_lines.append(f"  Frames Corrupted: {stats.get('frames_corrupted', 0)}")
            info_lines.append(f"  Current FPS: {stats.get('recent_fps', 0):.1f}")
            info_lines.append(f"  Last Reported FPS: {stats.get('last_fps', 0):.1f}")
            info_lines.append("")
            
            # Buffer statistics
            info_lines.append("Buffer Statistics:")
            info_lines.append(f"  Buffer Usage: {buffer_health.get('buffer_usage_percent', 0):.1f}%")
            info_lines.append(f"  Buffer Size: {buffer_health.get('buffer_size_current', 0)}/{buffer_health.get('buffer_size_max', 0)}")
            info_lines.append(f"  Buffer Overflows: {stats.get('buffer_overflows', 0)}")
            info_lines.append(f"  Average Frame Interval: {buffer_health.get('avg_frame_interval', 0):.3f}s")
            info_lines.append("")
            
            # Connection statistics
            info_lines.append("Connection Statistics:")
            info_lines.append(f"  Connection Errors: {stats.get('connection_errors', 0)}")
            info_lines.append(f"  Reconnection Attempts: {stats.get('reconnection_attempts', 0)}")
            
            if 'error_handler_state' in stats:
                info_lines.append(f"  Error Handler State: {stats['error_handler_state']}")
                info_lines.append(f"  Success Rate: {stats.get('connection_success_rate', 0):.1%}")
            
            return "\n".join(info_lines)
            
        except Exception as e:
            return f"Error formatting receiver stats: {str(e)}"
    
    def _get_current_configuration(self) -> str:
        """Get current configuration information"""
        try:
            info_lines = []
            info_lines.append("ESP32-Camera Configuration")
            info_lines.append("=" * 35)
            info_lines.append("")
            
            # Current UI settings
            info_lines.append("Current Settings:")
            if hasattr(self, 'esp32_resolution_combo'):
                info_lines.append(f"  Resolution: {self.esp32_resolution_combo.get()}")
            if hasattr(self, 'esp32_fps_combo'):
                info_lines.append(f"  FPS: {self.esp32_fps_combo.get()}")
            if hasattr(self, 'esp32_quality_scale'):
                info_lines.append(f"  Quality: {int(self.esp32_quality_scale.get())}")
            
            info_lines.append("")
            
            # Saved configuration
            try:
                config_data = self.load_full_esp32_config()
                esp32_config = config_data.get("esp32_camera", {})
                
                info_lines.append("Saved Configuration:")
                info_lines.append(f"  Resolution: {esp32_config.get('resolution', 'N/A')}")
                info_lines.append(f"  FPS: {esp32_config.get('fps', 'N/A')}")
                info_lines.append(f"  Quality: {esp32_config.get('quality', 'N/A')}")
                info_lines.append(f"  Port: {esp32_config.get('port', 'N/A')}")
                info_lines.append(f"  Baud Rate: {esp32_config.get('baud', 'N/A')}")
                info_lines.append(f"  Auto Connect: {esp32_config.get('auto_connect', 'N/A')}")
                info_lines.append(f"  Fallback Enabled: {esp32_config.get('fallback_enabled', 'N/A')}")
                
                if 'last_updated' in esp32_config:
                    last_updated = time.strftime('%Y-%m-%d %H:%M:%S', 
                                               time.localtime(esp32_config['last_updated']))
                    info_lines.append(f"  Last Updated: {last_updated}")
                
            except Exception as e:
                info_lines.append(f"Error loading saved configuration: {str(e)}")
            
            return "\n".join(info_lines)
            
        except Exception as e:
            return f"Error getting configuration info: {str(e)}"
    
    def _refresh_details_window(self, window, notebook):
        """Refresh details window content"""
        try:
            # Get current tab
            current_tab = notebook.index(notebook.select())
            
            # Close and recreate window
            window.destroy()
            self.show_esp32_details()
            
        except Exception as e:
            print(f"⚠️ Error refreshing details window: {e}")
    
    def _clear_error_history(self):
        """Clear ESP32-camera error history"""
        try:
            result = messagebox.askyesno("Clear Error History", 
                                       "Are you sure you want to clear all error history?")
            if result:
                self.esp32_error_history.clear()
                messagebox.showinfo("Success", "Error history cleared")
                print("🗑️ ESP32-camera error history cleared")
        except Exception as e:
            print(f"❌ Error clearing error history: {e}")
    
    def _export_error_log(self):
        """Export ESP32-camera error log to file"""
        try:
            if not self.esp32_error_history:
                messagebox.showinfo("No Data", "No error history to export")
                return
            
            # Ask for save location
            timestamp = int(time.time())
            default_name = f"esp32_error_log_{timestamp}.txt"
            
            file_path = filedialog.asksaveasfilename(
                title="Export Error Log",
                defaultextension=".txt",
                initialvalue=default_name,
                filetypes=[
                    ("Text files", "*.txt"),
                    ("JSON files", "*.json"),
                    ("All files", "*.*")
                ]
            )
            
            if file_path:
                # Export as text file
                with open(file_path, "w") as f:
                    f.write("ESP32-Camera Error Log\n")
                    f.write("=" * 30 + "\n\n")
                    
                    for error_entry in self.esp32_error_history:
                        f.write(f"[{error_entry['formatted_time']}] {error_entry['message']}\n")
                        if error_entry.get('details'):
                            f.write(f"  Details: {error_entry['details']}\n")
                        f.write(f"  Connection Attempt: {error_entry.get('connection_attempt', 'N/A')}\n")
                        f.write("\n")
                
                messagebox.showinfo("Success", f"Error log exported to:\n{file_path}")
                print(f"📤 Error log exported: {file_path}")
                
        except Exception as e:
            print(f"❌ Error exporting error log: {e}")
            messagebox.showerror("Error", f"Failed to export error log: {str(e)}")

    def get_video_source_string(self):
        """Convert UI selection to source string for accident_traffic.py"""
        selected = self.source_combo.get()
        
        if selected == "Webcam 0":
            return "0"
        elif selected == "Webcam 1":
            return "1"
        elif selected == "ESP32-Camera (COM3)":
            return "ESP32_CAM:COM3"
        elif selected == "Video File...":
            return filedialog.askopenfilename(
                title="Select video file",
                filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov *.m4v *.webm"), ("All files", "*.*")]
            ) or "0"  # fallback to webcam if cancelled
        elif selected == "Custom Video File" and self.custom_video_path:
            return self.custom_video_path
        else:
            return "0"  # fallback to webcam

    def on_start(self):
        # Prevent multiple instances
        if self.proc is not None and self.proc.poll() is None:
            messagebox.showwarning("Already running", "C2C module is already running.")
            return

        reg = self.reg_entry.get().strip().upper()
        owner = self.owner_entry.get().strip()
        phone = self.phone_entry.get().strip()
        bt_mac = self.bt_entry.get().strip()
        firebase_url = self.fb_entry.get().strip()
        serial_port = self.serial_combo.get().strip()
        source = self.get_video_source_string()  # Use new method
        acc_model = self.accident_entry.get().strip()
        traffic_model = self.traffic_entry.get().strip()

        if not reg:
            messagebox.showerror("Error", "Car registration number is required.")
            return

        if not firebase_url:
            messagebox.showerror("Error", "Firebase URL is required.")
            return

        # Register / get carId from Firebase
        try:
            car_id = register_or_get_car(firebase_url, reg, owner, phone)
        except Exception as e:
            messagebox.showerror("Firebase Error", str(e))
            return

        # Build config and save to car_config.json
        cfg = {
            "carId": car_id,
            "regNumber": reg,
            "ownerName": owner,
            "phone": phone,
            "bluetoothMac": bt_mac if bt_mac else None,
        }
        save_config(cfg)

        # Build command to run accident_traffic.py
        script_dir = get_script_dir()
        script_path = os.path.join(script_dir, "accident_traffic.py")

        cmd = [sys.executable, script_path,
               "--firebase-url", firebase_url,
               "--serial-port", serial_port,
               "--source", source]

        if self.var_accident.get():
            cmd.append("--enable-accident")
        if self.var_traffic.get():
            cmd.append("--enable-traffic")
        if self.var_display.get():
            cmd.append("--display")
        if self.var_bt.get():
            cmd.append("--enable-bluetooth")

        # Custom model paths
        if acc_model:
            cmd.extend(["--accident-weights", acc_model])
        if traffic_model and traffic_model != "yolov8s.pt":
            cmd.extend(["--traffic-model", traffic_model])

        # Start the process
        try:
            self.proc = subprocess.Popen(cmd, cwd=script_dir)
            self.stop_btn.config(state="normal")
            self.status_label.config(text="Status: Running accident_traffic.py")
            messagebox.showinfo(
                "Started",
                "C2C Accident+Traffic module started.\n\n"
                "Check the terminal / console window for logs."
            )
        except Exception as e:
            self.proc = None
            self.stop_btn.config(state="disabled")
            self.status_label.config(text="Status: Failed to start")
            messagebox.showerror("Error starting script", str(e))

    def on_stop(self):
        if self.proc is None or self.proc.poll() is not None:
            messagebox.showinfo("Not running", "C2C module is not currently running.")
            self.stop_btn.config(state="disabled")
            self.status_label.config(text="Status: Idle")
            return

        try:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None
            self.stop_btn.config(state="disabled")
            self.status_label.config(text="Status: Stopped")
            messagebox.showinfo("Stopped", "C2C Accident+Traffic module has been stopped.")
        except Exception as e:
            messagebox.showerror("Error stopping script", str(e))

    def on_close(self):
        # Stop ESP32 preview if active
        if hasattr(self, 'esp32_preview_active') and self.esp32_preview_active:
            self.stop_esp32_preview()
        
        # Cleanup performance monitoring (Requirements 7.4)
        if PERFORMANCE_MONITORING_AVAILABLE and self.performance_collector:
            try:
                cleanup_performance_monitoring()
                print("📊 Performance monitoring cleanup completed")
            except Exception as e:
                print(f"⚠️ Error cleaning up performance monitoring: {e}")
        
        # Disconnect ESP32-camera if connected
        self.disconnect_esp32_camera()
        
        # Try to stop child process if running
        if self.proc is not None and self.proc.poll() is None:
            try:
                self.proc.terminate()
                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            except Exception:
                pass
        self.destroy()


if __name__ == "__main__":
    app = C2CLauncher()
    app.mainloop()
