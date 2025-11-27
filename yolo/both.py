#!/usr/bin/env python3
import argparse, os, time
from collections import defaultdict
from typing import List, Tuple

import cv2
import numpy as np
from ultralytics import YOLO

VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".m4v", ".webm"}
VEHICLE_NAMES = {"car", "bus", "truck", "motorcycle", "bicycle"}
VEHICLE_CLASS_IDS = [1, 2, 3, 5, 7]  # COCO: bicycle=1, car=2, motorcycle=3, bus=5, truck=7

def is_video(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in VIDEO_EXTS

def safe_imshow(title, frame):
    try:
        cv2.imshow(title, frame); return True
    except cv2.error:
        return False

def iou_xyxy(a, b) -> float:
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    iw, ih = max(0, ix2 - ix1), max(0, iy2 - iy1)
    inter = iw * ih
    if inter <= 0: return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    return inter / max(area_a + area_b - inter, 1e-6)

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

    def update(self, acc_boxes: List[Tuple[int,int,int,int]], acc_confs: List[float]):
        now = time.time()
        if acc_boxes:
            max_idx = int(np.argmax(acc_confs))
            cur_box = acc_boxes[max_idx]
            cur_conf = float(acc_confs[max_idx])
            if self.best_box is None or iou_xyxy(self.best_box, cur_box) < self.iou_match or cur_conf > self.best_conf:
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

def parse_args():
    ap = argparse.ArgumentParser("Road AI: Accident Detection + Traffic Analysis (YOLO)")
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
    return ap.parse_args()

def main():
    args = parse_args()
    if not args.enable_accident and not args.enable_traffic:
        print("⚠️ Nothing to do. Use --enable-accident and/or --enable-traffic.")
        return

    # Open source
    cap, is_cam = open_capture(args.source)
    if not cap or not cap.isOpened():
        print("❌ Could not open source"); return
    if is_cam:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
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
        accident_model = YOLO(args.accident_weights)
        accident_names = accident_model.names if hasattr(accident_model, "names") else {}
        # Build accident class id set from names
        for i, n in accident_names.items():
            s = str(n).lower()
            if ("accident" in s) or ("collision" in s) or ("fire" in s) or ("smoke" in s):
                accident_ids.add(int(i))
        if not accident_ids and 0 in accident_names:
            accident_ids.add(0)
        smoother = AccidentSmoother(rise_frames=args.rise_frames, fall_frames=args.fall_frames)

    traffic_model = None
    lx1 = ly1 = lx2 = ly2 = 0
    rx1 = ry1 = rx2 = ry2 = 0
    count_y = 0
    roi_box = (0,0,0,0)
    total_crossings = 0
    prev_cy = {}  # id -> previous centroid y
    last_count_frame = defaultdict(int)
    cooldown = 5  # frames

    if args.enable_traffic:
        traffic_model = YOLO(args.traffic_model)
        lx1, ly1, lx2, ly2 = norm_to_abs(args.line, W, H)
        rx1, ry1, rx2, ry2 = norm_to_abs(args.roi, W, H)
        count_y = ly1
        roi_box = (rx1, ry1, rx2, ry2)

    print("✅ Running. Press 'q' to quit.")
    gui = args.display
    t0, frames = time.time(), 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames += 1

        # We will draw everything on 'frame'
        # Make a copy for each pipeline if you ever want separate outputs.

        # === Accident detection ===
        if args.enable_accident:
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
            if state_on and best_box is not None:
                bx1, by1, bx2, by2 = best_box
                cv2.rectangle(frame, (bx1, by1), (bx2, by2), (0, 0, 255), 3)
                cv2.putText(frame, f"ACCIDENT DETECTED ({best_conf:.2f})",
                            (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 255), 3)
            else:
                cv2.putText(frame, "NO ACCIDENT",
                            (10, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 200, 0), 3)

        # === Traffic analysis (tracking + density + crossing) ===
        if args.enable_traffic:
            # Draw ROI + count line first (so boxes are on top)
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
                    level = "LOW"; color = (0, 255, 0)
                elif density <= 8:
                    level = "MEDIUM"; color = (0, 255, 255)
                else:
                    level = "HIGH / TRAFFIC JAM"; color = (0, 0, 255)

                cv2.putText(frame, f"Traffic: {level} (Vehicles in ROI: {density})",
                            (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)
            else:
                cv2.putText(frame, f"Vehicles crossed: {total_crossings}",
                            (10, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
                cv2.putText(frame, f"Vehicles in ROI: 0",
                            (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)

        # FPS overlay (overall)
        if args.show_fps:
            dt = time.time() - t0
            fps_live = frames / max(1e-6, dt)
            cv2.putText(frame, f"FPS: {fps_live:.1f}", (10, 150),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        # Output
        if writer is not None:
            writer.write(frame)

        if args.display:
            if not safe_imshow("Road AI (Accident + Traffic)", frame):
                pass
            else:
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    cap.release()
    if writer is not None:
        writer.release()
        print(f"💾 Saved: {args.save}")
    cv2.destroyAllWindows()
    print("✅ Done.")

if __name__ == "__main__":
    main()
