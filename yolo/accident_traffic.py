#!/usr/bin/env python3
"""
accident_traffic.py

- Runs YOLO for accident + traffic detection
- Talks to ESP32 over Serial:
    * reads SENSOR|lat:..,lng:..,temp:..,hum:..
    * receives LORA_RX|... from ESP32 (LoRa messages)
    * sends CMD|ACCIDENT / CMD|TRAFFIC to ESP32
- Pushes data to Firebase Realtime DB via REST
- One-time car & user registration (stored in car_config.json)
- Optional Bluetooth link to Android app (for alerts + config)
"""

import argparse
import os
import time
import json
import re
from collections import defaultdict
from typing import List, Tuple, Optional

import cv2
import numpy as np
import requests
import serial
from ultralytics import YOLO

# ---------- OPTIONAL Bluetooth (PyBluez) ----------
try:
    import bluetooth  # pybluez
except ImportError:
    bluetooth = None

# ------------------- CONFIG -------------------

GOOGLE_API_KEY = "AIzaSyBRGvOre2tZpCpDWx89Y16YiVIMpZ8nReY"   # <-- put your real key here
GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

DEFAULT_FIREBASE_URL = "https://c2c-cartocar-app-23bb6-default-rtdb.firebaseio.com/"
CONFIG_FILE = "car_config.json"  # saved next to this script

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".m4v", ".webm"}
VEHICLE_NAMES = {"car", "bus", "truck", "motorcycle", "bicycle"}
VEHICLE_CLASS_IDS = [1, 2, 3, 5, 7]  # COCO: bicycle=1, car=2, motorcycle=3, bus=5, truck=7


# ------------------- BASIC HELPERS -------------------

def check_internet() -> bool:
    """Simple ping to check if we are online."""
    try:
        requests.get("https://www.google.com", timeout=2)
        return True
    except Exception:
        return False


def is_video(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in VIDEO_EXTS


def safe_imshow(title, frame):
    try:
        cv2.imshow(title, frame)
        return True
    except cv2.error:
        return False


def iou_xyxy(a, b) -> float:
    """
    Compute IoU between two boxes in (x1, y1, x2, y2) format.
    """
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    # Intersection box
    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    iw = max(0, ix2 - ix1)
    ih = max(0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0:
        return 0.0

    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    return inter / max(area_a + area_b - inter, 1e-6)



def geocode_location(lat, lng) -> str:
    """
    Try to return something like:
      'Magadi Road, Kottigepalya'
    instead of just a random layout / POI.
    """
    if lat is None or lng is None:
        return "Unknown"

    params = {
        "latlng": f"{lat},{lng}",
        "key": GOOGLE_API_KEY,
        # Focus results on road / address when possible
        "result_type": "route|street_address|sublocality"
    }

    try:
        r = requests.get(GEOCODE_URL, params=params, timeout=4).json()
        if "results" not in r or not r["results"]:
            return "Unknown"

        result = r["results"][0]
        comps = result.get("address_components", [])

        road = None
        area = None
        city = None

        for c in comps:
            types = c.get("types", [])
            name = c.get("long_name", "")

            if "route" in types and not road:
                road = name  # e.g. "Magadi Road"

            if ("sublocality" in types or "sublocality_level_1" in types or
                "neighborhood" in types) and not area:
                area = name  # e.g. "Kottigepalya"

            if "locality" in types and not city:
                city = name  # e.g. "Bengaluru"

        # Build a nice label
        if road and area:
            return f"{road}, {area}"
        if road and city:
            return f"{road}, {city}"
        if area and city:
            return f"{area}, {city}"
        if road:
            return road
        if area:
            return area

        # Fallback to full formatted address
        return result.get("formatted_address", "Unknown")

    except Exception as e:
        print("geocode_location error:", e)
        return "Unknown"

# ------------------- ACCIDENT SMOOTHER -------------------

class AccidentSmoother:
    """
    - 'on' if an accident-class box appears for >= rise_frames
    - 'off' when no accident boxes for >= fall_frames
    - maintains a persistent best_box using IoU + confidence
    """
    def __init__(self, rise_frames=3, fall_frames=6, iou_match=0.3):
        self.rise_frames = rise_frames
        self.fall_frames = fall_frames
        self.iou_match = iou_match
        self.acc_count = 0
        self.noacc_count = 0
        self.state_on = False
        self.best_box = None
        self.best_conf = 0.0
        self.last_seen_time = 0.0

    def update(self, acc_boxes: List[Tuple[int, int, int, int]], acc_confs: List[float]):
        now = time.time()
        if acc_boxes:
            max_idx = int(np.argmax(acc_confs))
            cur_box = acc_boxes[max_idx]
            cur_conf = float(acc_confs[max_idx])

            if (
                self.best_box is None
                or iou_xyxy(self.best_box, cur_box) < self.iou_match
                or cur_conf > self.best_conf
            ):
                self.best_box = cur_box
                self.best_conf = cur_conf

            self.acc_count += 1
            self.noacc_count = 0
            self.last_seen_time = now

            if not self.state_on and self.acc_count >= self.rise_frames:
                self.state_on = True
        else:
            self.acc_count = 0
            self.noacc_count += 1
            if self.state_on and self.noacc_count >= self.fall_frames:
                self.state_on = False
                self.best_box = None
                self.best_conf = 0.0

        return self.state_on, self.best_box, self.best_conf


# ------------------- GEO / ROI HELPERS -------------------

def norm_to_abs(rect_str, W, H):
    x1, y1, x2, y2 = [float(v) for v in rect_str.split(",")]
    return int(x1 * W), int(y1 * H), int(x2 * W), int(y2 * H)


def intersect(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    return (ix2 > ix1) and (iy2 > iy1)


def open_capture(src_str: str):
    use_cam = src_str.isdigit() and not os.path.exists(src_str)
    if use_cam:
        cam_idx = int(src_str)
        cap = cv2.VideoCapture(cam_idx, cv2.CAP_DSHOW)  # Windows-friendly
        if not cap.isOpened():
            cap.release()
            cap = cv2.VideoCapture(cam_idx)  # fallback
        return cap, True
    else:
        return cv2.VideoCapture(src_str), False


# ------------------- SERIAL PARSING -------------------

def parse_sensor_line(line: str):
    """
    Expected ESP32 format over Serial:
      SENSOR|lat:12.973800,lng:77.594600,temp:29.4,hum:65.2
    """
    line = line.strip()
    if not line.startswith("SENSOR|"):
        return None
    payload = line.split("|", 1)[1]
    parts = payload.split(",")
    data = {}
    for p in parts:
        if ":" in p:
            k, v = p.split(":", 1)
            data[k.strip()] = v.strip()
    try:
        lat = float(data.get("lat", 0.0))
        lng = float(data.get("lng", 0.0))
        temp = float(data.get("temp", 0.0))
        hum = float(data.get("hum", 0.0))
        return lat, lng, temp, hum
    except Exception:
        return None


def parse_lora_rx_line(line: str) -> Optional[str]:
    """
    Expected ESP32 format:
      LORA_RX|ALERT|ACCIDENT|from:C1
    We just return everything after 'LORA_RX|'
    """
    line = line.strip()
    if not line.startswith("LORA_RX|"):
        return None
    return line.split("|", 1)[1]


# ------------------- CONFIG (CAR + USER) -------------------

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    return None


def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


def sanitize_reg(reg_number: str) -> str:
    """CarId = regNumber with only A–Z,0–9 so same reg → same node."""
    return re.sub(r'[^A-Z0-9]', '', reg_number.upper())


def register_if_needed(firebase_url: str):
    """
    Registration via console ONLY if car_config.json does not exist.
    When you use the GUI (c2c_launcher.py), it will already create car_config.json,
    so this will just load it.
    """
    cfg = load_config()
    if cfg:
        print(f"Using existing car config from {CONFIG_FILE}: {cfg}")
        return cfg

    # Fallback: console registration
    reg_number = input("Enter car registration number (e.g., KA01AB1234): ").strip().upper()
    owner_name = input("Enter driver/owner name: ").strip()
    phone = input("Enter phone number (optional): ").strip()
    bt_mac = input("Enter Bluetooth MAC (optional): ").strip()

    firebase_url = firebase_url.rstrip("/")
    car_id = sanitize_reg(reg_number)

    car_data = {
        "carId": car_id,
        "regNumber": reg_number,
        "ownerName": owner_name,
        "phone": phone,
        "bluetoothMac": bt_mac,
        "createdAt": int(time.time() * 1000),
    }

    try:
        res = requests.put(f"{firebase_url}/cars/{car_id}.json", json=car_data, timeout=5)
        res.raise_for_status()
        print(f"Car registered/updated with ID: {car_id}")
    except Exception as e:
        print(f"Firebase failed: {e}")
        raise

    cfg = car_data.copy()
    save_config(cfg)
    return cfg


# ------------------- FIREBASE HELPERS (REST) -------------------

def update_vehicle_state(firebase_url, car_id, reg_number,
                         lat, lng, location_name,
                         traffic_level, is_accident):
    data = {
        "regNumber": reg_number,
        "latitude": lat,
        "longitude": lng,
        "locationName": location_name,
        "trafficLevel": traffic_level,   # "LOW"/"MEDIUM"/"HIGH" or None
        "isAccident": bool(is_accident),
        "lastUpdate": int(time.time() * 1000),
    }
    try:
        requests.put(f"{firebase_url}/vehicles/{car_id}.json", json=data, timeout=3)
    except Exception as e:
        print(f"⚠️ Failed to update vehicle state: {e}")


def log_accident(firebase_url, car_id, reg_number,
                 lat, lng, location_name,
                 severity, conf):
    data = {
        "carId": car_id,
        "regNumber": reg_number,
        "latitude": lat,
        "longitude": lng,
        "locationName": location_name,
        "severity": severity,   # "HIGH" / "MEDIUM" etc
        "confidence": float(conf),
        "timestamp": int(time.time() * 1000),
        "source": "YOLO+laptop",
    }
    try:
        requests.post(f"{firebase_url}/accidents.json", json=data, timeout=3)
    except Exception as e:
        print(f"⚠️ Failed to log accident: {e}")


def log_traffic_event(firebase_url, car_id, reg_number,
                      lat, lng, location_name,
                      level, density, crossings):
    data = {
        "carId": car_id,
        "regNumber": reg_number,
        "latitude": lat,
        "longitude": lng,
        "locationName": location_name,
        "level": level,       # "LOW"/"MEDIUM"/"HIGH"
        "density": int(density),
        "crossings": int(crossings),
        "timestamp": int(time.time() * 1000),
        "source": "YOLO+laptop",
    }
    try:
        requests.post(f"{firebase_url}/traffic.json", json=data, timeout=3)
    except Exception as e:
        print(f"⚠️ Failed to log traffic: {e}")


def log_v2v_message(firebase_url, car_id, reg_number,
                    lat, lng, location_name,
                    raw_payload: str):
    """
    Stores LoRa messages that this module receives from other cars.
    """
    data = {
        "carId": car_id,
        "regNumber": reg_number,
        "latitude": lat,
        "longitude": lng,
        "locationName": location_name,
        "payload": raw_payload,
        "timestamp": int(time.time() * 1000),
        "source": "LoRa+ESP32",
    }
    try:
        requests.post(f"{firebase_url}/v2v_messages.json", json=data, timeout=3)
    except Exception as e:
        print(f"⚠️ Failed to log v2v message: {e}")


# ------------------- BLUETOOTH HELPERS -------------------

def connect_bluetooth_if_configured(cfg):
    """
    Tries to connect to Android app over Bluetooth (SPP).
    Requires:
      - 'bluetoothMac' in config
      - pybluez installed
    Returns: socket or None
    """
    mac = cfg.get("bluetoothMac")
    if not mac:
        print("No Bluetooth MAC in config; skipping Bluetooth connection to app.")
        return None

    if bluetooth is None:
        print("pybluez not installed; skipping Bluetooth.")
        return None

    sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    try:
        print(f"Connecting to Bluetooth device {mac} on RFCOMM channel 1...")
        sock.connect((mac, 1))
        print(f"✅ Connected to app over Bluetooth ({mac})")
        # Send initial config
        msg = json.dumps({
            "type": "config",
            "carId": cfg["carId"],
            "regNumber": cfg["regNumber"],
            "ownerName": cfg.get("ownerName"),
            "phone": cfg.get("phone"),
        }) + "\n"
        sock.send(msg.encode("utf-8"))
        return sock
    except Exception as e:
        print(f"⚠️ Could not connect to Bluetooth device {mac}: {e}")
        return None


def send_bt_alert(sock,
                  kind: str,
                  reg_number: str,
                  lat: float,
                  lng: float,
                  location_name: str,
                  extra=None):
    """
    Sends a small JSON alert over Bluetooth to the app.
    kind: "ACCIDENT" or "TRAFFIC"
    """
    if sock is None:
        return
    payload = {
        "type": "alert",
        "kind": kind,
        "regNumber": reg_number,
        "lat": lat,
        "lng": lng,
        "locationName": location_name,
        "extra": extra or {},
        "timestamp": int(time.time() * 1000),
    }
    try:
        sock.send((json.dumps(payload) + "\n").encode("utf-8"))
    except Exception as e:
        print("⚠️ Bluetooth send failed:", e)


# ------------------- ARGUMENTS -------------------

def parse_args():
    ap = argparse.ArgumentParser("Road AI: Accident Detection + Traffic Analysis (YOLO + ESP32 + Firebase)")

    # Common
    ap.add_argument("--source", type=str, default="0", help="0=webcam or path to video")
    ap.add_argument("--imgsz", type=int, default=640, help="inference size")
    ap.add_argument("--display", action="store_true", help="show window")
    ap.add_argument("--show-fps", action="store_true", help="overlay live FPS")
    ap.add_argument("--save", type=str, default="", help="optional output mp4 path")
    ap.add_argument("--fps_out", type=int, default=25, help="save FPS")

    # Accident
    ap.add_argument("--enable-accident", action="store_true", help="run accident detector")
    ap.add_argument("--accident-weights", type=str,
                    default=r"C:\Users\Somashekar A\Desktop\Major Pro\yolo\accident\v1\weights\best.pt",
                    help="path to trained accident YOLO .pt")
    ap.add_argument("--accident-conf", type=float, default=0.35)
    ap.add_argument("--accident-iou", type=float, default=0.5)
    ap.add_argument("--accident-device", type=str, default=None, help="CUDA id like 0, or cpu")
    ap.add_argument("--rise-frames", type=int, default=3)
    ap.add_argument("--fall-frames", type=int, default=6)

    # Traffic
    ap.add_argument("--enable-traffic", action="store_true", help="run traffic analysis")
    ap.add_argument("--traffic-model", type=str, default="yolov8s.pt", help="YOLOv8 model or path to .pt")
    ap.add_argument("--traffic-conf", type=float, default=0.35)
    ap.add_argument("--traffic-iou", type=float, default=0.5)
    ap.add_argument("--traffic-device", type=str, default=None, help="CUDA id like 0, or cpu")
    ap.add_argument("--tracker", default="botsort.yaml")
    ap.add_argument("--line", type=str, default="0.15,0.80,0.85,0.80", help="count line x1,y1,x2,y2 (normalized 0..1)")
    ap.add_argument("--roi", type=str, default="0.25,0.35,0.75,0.95", help="density ROI x1,y1,x2,y2 (normalized 0..1)")

    # Integration
    ap.add_argument("--firebase-url", type=str, default=DEFAULT_FIREBASE_URL, help="Firebase Realtime DB base URL")
    ap.add_argument("--serial-port", type=str, default="COM4", help="ESP32 serial port, e.g. COM8 or /dev/ttyUSB0")
    ap.add_argument("--serial-baud", type=int, default=115200, help="ESP32 serial baud rate")
    ap.add_argument("--enable-bluetooth", action="store_true", help="try to connect to phone app via Bluetooth")

    return ap.parse_args()


# ------------------- MAIN -------------------

def main():
    args = parse_args()

    if not args.enable_accident and not args.enable_traffic:
        print("⚠️ Nothing to do. Use --enable-accident and/or --enable-traffic.")
        return

    firebase_url = args.firebase_url.rstrip("/")

    # --- One-time car registration / config ---
    config = register_if_needed(firebase_url)
    CAR_ID = config["carId"]
    REG_NUMBER = config["regNumber"]
    print(f"✅ Using CAR_ID={CAR_ID}, REG={REG_NUMBER}")

    # --- Bluetooth (optional) ---
    bt_sock = None  # type: ignore
    if args.enable_bluetooth:
        bt_sock = connect_bluetooth_if_configured(config)

    # --- Serial to ESP32 ---
    try:
        esp32 = serial.Serial(args.serial_port, args.serial_baud, timeout=0.1)
        print(f"✅ Connected to ESP32 on {args.serial_port} @ {args.serial_baud}")
    except Exception as e:
        print(f"❌ Could not open serial {args.serial_port}: {e}")
        print("   👉 Close Arduino Serial Monitor / any other app using this COM port and try again.")
        esp32 = None

    last_lat, last_lng = 0.0, 0.0
    last_temp, last_hum = None, None
    last_upload_time = 0.0
    last_location_name = "Unknown"

    # Offline / trigger state
    last_traffic_level = None
    accident_sent = False
    offline_events = []  # list of dicts {"type": "accident"/"traffic", ...}
    internet_ok = True
    last_net_check = 0.0
    NET_CHECK_INTERVAL = 10.0  # seconds

    # Open video/camera
    cap, is_cam = open_capture(args.source)
    if not cap or not cap.isOpened():
        print("❌ Could not open video/camera source")
        return

    if is_cam:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
    in_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    # Prepare writer
    writer = None
    if args.save:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(args.save, fourcc, args.fps_out or in_fps, (W, H))
        if not writer.isOpened():
            print("⚠️ Failed to open writer; disabling save.")
            writer = None

    # Models and state
    accident_model = None
    accident_names = {}
    accident_ids = set()
    smoother = None

    if args.enable_accident:
        print("Loading accident model...")
        accident_model = YOLO(args.accident_weights)
        accident_names = accident_model.names if hasattr(accident_model, "names") else {}
        for i, n in accident_names.items():
            s = str(n).lower()
            if ("accident" in s) or ("collision" in s) or ("fire" in s) or ("smoke" in s):
                accident_ids.add(int(i))
        if not accident_ids and 0 in accident_names:
            accident_ids.add(0)
        smoother = AccidentSmoother(rise_frames=args.rise_frames, fall_frames=args.fall_frames)
        print(f"Accident classes: {accident_ids}")

    traffic_model = None
    lx1 = ly1 = lx2 = ly2 = 0
    rx1 = ry1 = rx2 = ry2 = 0
    roi_box = (0, 0, 0, 0)
    count_y = 0
    total_crossings = 0
    prev_cy = {}  # id -> previous centroid y
    last_count_frame = defaultdict(int)
    cooldown = 5  # frames
    density = 0   # current vehicles in ROI

    if args.enable_traffic:
        print("Loading traffic model...")
        traffic_model = YOLO(args.traffic_model)
        lx1, ly1, lx2, ly2 = norm_to_abs(args.line, W, H)
        rx1, ry1, rx2, ry2 = norm_to_abs(args.roi, W, H)
        count_y = ly1
        roi_box = (rx1, ry1, rx2, ry2)

    print("✅ Running. Press 'q' to quit.")
    gui = args.display
    t0, frames = time.time(), 0

    def flush_offline():
        nonlocal offline_events
        if not offline_events:
            return
        print(f"📡 Internet restored – uploading {len(offline_events)} buffered events...")
        for ev in offline_events:
            if ev["type"] == "accident":
                log_accident(firebase_url, CAR_ID, REG_NUMBER,
                             ev["lat"], ev["lng"], ev["locationName"],
                             ev["severity"], ev["conf"])
            elif ev["type"] == "traffic":
                log_traffic_event(firebase_url, CAR_ID, REG_NUMBER,
                                  ev["lat"], ev["lng"], ev["locationName"],
                                  ev["level"], ev["density"], ev["crossings"])
        offline_events = []

    # ------------------- MAIN LOOP -------------------
    while True:
        now = time.time()

        # --- internet check + offline flush ---
        if now - last_net_check > NET_CHECK_INTERVAL:
            last_net_check = now
            new_status = check_internet()
            if new_status and not internet_ok:
                internet_ok = True
                flush_offline()
            else:
                internet_ok = new_status

        # --- Read frame ---
        ok, frame = cap.read()
        if not ok:
            break
        frames += 1

        # --- Read from ESP32 (non-blocking) ---
        if esp32 is not None:
            try:
                while esp32.in_waiting:
                    raw = esp32.readline().decode(errors="ignore")
                    raw = raw.strip()
                    if not raw:
                        continue
                    parsed = parse_sensor_line(raw)
                    if parsed:
                        last_lat, last_lng, last_temp, last_hum = parsed
                        continue
                    lora_msg = parse_lora_rx_line(raw)
                    if lora_msg:
                        print("LoRa RX from ESP32:", lora_msg)
                        if last_lat or last_lng:
                            log_v2v_message(firebase_url, CAR_ID, REG_NUMBER,
                                            last_lat, last_lng, last_location_name,
                                            lora_msg)
            except Exception as e:
                print("Serial error:", e)

        accident_detected = False
        best_conf = 0.0
        traffic_level = None  # "LOW"/"MEDIUM"/"HIGH"

        # === Accident detection ===
        if args.enable_accident and accident_model is not None:
            res = accident_model.predict(
                frame,
                imgsz=args.imgsz,
                conf=args.accident_conf,
                iou=args.accident_iou,
                device=args.accident_device if args.accident_device is not None else None,
                verbose=False
            )

            accident_boxes, accident_confs = [], []
            if res and len(res):
                r = res[0]
                if r.boxes is not None and len(r.boxes) > 0:
                    xyxy = r.boxes.xyxy.cpu().numpy()
                    cls = r.boxes.cls.cpu().numpy().astype(int)
                    conf = r.boxes.conf.cpu().numpy()
                    for (x1, y1, x2, y2), c, p in zip(xyxy, cls, conf):
                        x1i, y1i, x2i, y2i = map(int, (x1, y1, x2, y2))
                        label = accident_names.get(int(c), str(c))
                        is_acc = (int(c) in accident_ids)
                        color = (0, 0, 255) if is_acc else (0, 200, 0)
                        cv2.rectangle(frame, (x1i, y1i), (x2i, y2i), color, 2)
                        cv2.putText(frame, f"{label} {p:.2f}",
                                    (x1i, max(0, y1i - 6)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                        if is_acc:
                            accident_boxes.append((x1i, y1i, x2i, y2i))
                            accident_confs.append(float(p))

            state_on, best_box, best_conf = smoother.update(accident_boxes, accident_confs)
            accident_detected = state_on

            if state_on and best_box is not None:
                bx1, by1, bx2, by2 = best_box
                cv2.rectangle(frame, (bx1, by1), (bx2, by2), (0, 0, 255), 3)
                cv2.putText(frame, f"ACCIDENT DETECTED ({best_conf:.2f})",
                            (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
            else:
                cv2.putText(frame, "NO ACCIDENT",
                            (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 200, 0), 3)

        # === Traffic analysis (tracking + density + crossing) ===
        if args.enable_traffic and traffic_model is not None:
            cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (255, 255, 0), 2)
            cv2.line(frame, (lx1, ly1), (lx2, ly2), (0, 255, 255), 2)

            results = traffic_model.track(
                frame,
                imgsz=args.imgsz,
                conf=args.traffic_conf,
                iou=args.traffic_iou,
                tracker=args.tracker,
                persist=True,
                classes=VEHICLE_CLASS_IDS,
                device=args.traffic_device if args.traffic_device is not None else None,
                verbose=False
            )

            density = 0
            if results and getattr(results[0], "boxes", None) is not None:
                boxes = results[0].boxes
                xyxy = boxes.xyxy.cpu().numpy() if boxes.xyxy is not None else np.empty((0, 4))
                cls = boxes.cls.cpu().numpy().astype(int) if boxes.cls is not None else np.empty((0,), dtype=int)
                ids = (boxes.id.cpu().numpy().astype(int)
                       if boxes.id is not None else np.full((len(xyxy),), -1, dtype=int))
                names = results[0].names

                for (x1, y1, x2, y2), c, tid in zip(xyxy, cls, ids):
                    label = names.get(int(c), str(c)) if isinstance(names, dict) else str(c)
                    if label not in VEHICLE_NAMES:
                        continue
                    x1i, y1i, x2i, y2i = map(int, (x1, y1, x2, y2))
                    cv2.rectangle(frame, (x1i, y1i), (x2i, y2i), (0, 255, 0), 2)
                    cv2.putText(frame, f"{label}#{tid}",
                                (x1i, max(0, y1i - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                    if intersect((x1i, y1i, x2i, y2i), roi_box):
                        density += 1

                    cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                    pcy = prev_cy.get(tid, None)
                    prev_cy[tid] = cy
                    if pcy is None:
                        continue
                    crossed = (pcy < count_y <= cy) or (pcy > count_y >= cy)
                    if crossed:
                        if frames - last_count_frame[tid] >= cooldown:
                            total_crossings += 1
                            last_count_frame[tid] = frames

                cv2.putText(frame, f"Vehicles crossed: {total_crossings}",
                            (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)

                if density <= 3:
                    traffic_level = "LOW"
                    color = (0, 255, 0)
                elif density <= 8:
                    traffic_level = "MEDIUM"
                    color = (0, 255, 255)
                else:
                    traffic_level = "HIGH"
                    color = (0, 0, 255)

                cv2.putText(frame, f"Traffic: {traffic_level} (Vehicles in ROI: {density})",
                            (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
            else:
                cv2.putText(frame, f"Vehicles crossed: {total_crossings}",
                            (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
                cv2.putText(frame, f"Vehicles in ROI: 0",
                            (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)

        # === EVENT-BASED TRIGGERS (ACCIDENT / TRAFFIC) ===

        # Accident event: trigger only when it turns ON
        if accident_detected and not accident_sent:
            print("🚨 Accident event triggered")
            accident_sent = True

            # Get location name
            location_name = last_location_name
            if internet_ok and (last_lat or last_lng):
                location_name = geocode_location(last_lat, last_lng)
                last_location_name = location_name

            # Tell ESP32 → LoRa
            if esp32 is not None:
                try:
                    cmd = f"CMD|ACCIDENT|severity:HIGH|loc:{location_name}\n"
                    esp32.write(cmd.encode())
                except Exception as e:
                    print("Serial write error (ACCIDENT CMD):", e)

            # Firebase + Bluetooth (or buffer if offline)
            if internet_ok:
                log_accident(firebase_url, CAR_ID, REG_NUMBER,
                             last_lat, last_lng, location_name,
                             severity="HIGH", conf=best_conf)
                send_bt_alert(bt_sock, "ACCIDENT", REG_NUMBER,
                              last_lat, last_lng, location_name,
                              extra={"confidence": best_conf})
            else:
                offline_events.append({
                    "type": "accident",
                    "lat": last_lat,
                    "lng": last_lng,
                    "locationName": location_name,
                    "severity": "HIGH",
                    "conf": best_conf,
                })

        if not accident_detected and accident_sent:
            # accident cleared; next accident will trigger again
            accident_sent = False

        # Traffic event: fire when level changes to MEDIUM/HIGH
        if traffic_level in ("MEDIUM", "HIGH") and traffic_level != last_traffic_level:
            print(f"🚦 Traffic event triggered: {traffic_level}")

            location_name = last_location_name
            if internet_ok and (last_lat or last_lng):
                location_name = geocode_location(last_lat, last_lng)
                last_location_name = location_name

            # Tell ESP32 → LoRa
            if esp32 is not None:
                try:
                    cmd = f"CMD|TRAFFIC|level:{traffic_level}|loc:{location_name}\n"
                    esp32.write(cmd.encode())
                except Exception as e:
                    print("Serial write error (TRAFFIC CMD):", e)

            # Firebase + Bluetooth (or buffer)
            if internet_ok:
                log_traffic_event(firebase_url, CAR_ID, REG_NUMBER,
                                  last_lat, last_lng, location_name,
                                  level=traffic_level,
                                  density=density,
                                  crossings=total_crossings)
                send_bt_alert(bt_sock, "TRAFFIC", REG_NUMBER,
                              last_lat, last_lng, location_name,
                              extra={"level": traffic_level, "density": density})
            else:
                offline_events.append({
                    "type": "traffic",
                    "lat": last_lat,
                    "lng": last_lng,
                    "locationName": location_name,
                    "level": traffic_level,
                    "density": density,
                    "crossings": total_crossings,
                })

        # Update last traffic level
        if traffic_level is not None:
            last_traffic_level = traffic_level

        # === Vehicle state update (once per second, if we have GPS) ===
        if (last_lat != 0.0 or last_lng != 0.0) and (now - last_upload_time > 1.0):
            last_upload_time = now
            if internet_ok and last_location_name == "Unknown":
                last_location_name = geocode_location(last_lat, last_lng)
            if internet_ok:
                update_vehicle_state(firebase_url, CAR_ID, REG_NUMBER,
                                     last_lat, last_lng, last_location_name,
                                     traffic_level=traffic_level,
                                     is_accident=accident_detected)

        # FPS overlay
        if args.show_fps:
            dt = time.time() - t0
            fps_live = frames / max(1e-6, dt)
            cv2.putText(frame, f"FPS: {fps_live:.1f}", (10, 150),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        # Output (save video if enabled)
        if writer is not None:
            writer.write(frame)

        # Show window and handle keypress
        if gui:
            if safe_imshow("Road AI (Accident + Traffic)", frame):
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    print("Exiting on Q key...")
                    break
        else:
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("Exiting on Q key (no display)...")
                break

    cap.release()
    if writer is not None:
        writer.release()
        print(f"💾 Saved: {args.save}")
    cv2.destroyAllWindows()
    print("✅ Done.")


if __name__ == "__main__":
    main()
