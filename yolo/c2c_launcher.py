import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import os
import sys
import subprocess
import requests

# Optional: list serial ports if pyserial is installed
try:
    from serial.tools import list_ports
except ImportError:
    list_ports = None

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
        self.source_entry = ttk.Entry(frm, width=30)
        self.source_entry.insert(0, "0")  # default webcam
        self.source_entry.grid(row=7, column=1, sticky="w")

        def choose_video():
            path = filedialog.askopenfilename(
                title="Select video file",
                filetypes=[("Video files", "*.mp4 *.avi *.mkv *.mov *.m4v *.webm"), ("All files", "*.*")]
            )
            if path:
                self.source_entry.delete(0, tk.END)
                self.source_entry.insert(0, path)

        self.btn_video = ttk.Button(frm, text="Browse Video...", command=choose_video)
        self.btn_video.grid(row=7, column=2, sticky="w")

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
        source = self.source_entry.get().strip()
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
