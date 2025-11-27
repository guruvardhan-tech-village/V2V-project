import argparse
import os
import time
from collections import defaultdict

import cv2
import numpy as np
from ultralytics import YOLO

# COCO vehicle class names
VEHICLE_NAMES = {"car", "bus", "truck", "motorcycle", "bicycle"}
# COCO vehicle class IDs (for classes= filter): bicycle=1, car=2, motorcycle=3, bus=5, truck=7
VEHICLE_CLASS_IDS = [1, 2, 3, 5, 7]


def parse_args():
    ap = argparse.ArgumentParser("Traffic count & density with YOLOv8 + BoT-SORT")
    ap.add_argument("--source", default="0", help="0/webcam or path to video")
    ap.add_argument("--model", default="yolov8s.pt", help="YOLOv8 model or path to .pt")
    ap.add_argument("--imgsz", type=int, default=640)
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--iou", type=float, default=0.5)
    ap.add_argument("--tracker", default="botsort.yaml")
    ap.add_argument("--line", type=str, default="0.15,0.80,0.85,0.80",
                    help="count line x1,y1,x2,y2 (normalized 0..1)")
    ap.add_argument("--roi", type=str, default="0.25,0.35,0.75,0.95",
                    help="density ROI x1,y1,x2,y2 (normalized 0..1)")
    ap.add_argument("--display", action="store_true", help="show GUI window if available")
    ap.add_argument("--save", type=str, default="", help="optional output mp4 path")
    ap.add_argument("--fps_out", type=int, default=20, help="output video FPS if --save used")
    return ap.parse_args()


def norm_to_abs(rect_str, W, H):
    x1, y1, x2, y2 = [float(v) for v in rect_str.split(",")]
    return int(x1 * W), int(y1 * H), int(x2 * W), int(y2 * H)


def intersect(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    return (ix2 > ix1) and (iy2 > iy1)


def main():
    args = parse_args()
    src = int(args.source) if args.source.isdigit() else os.path.expanduser(args.source)

    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        print("❌ Cannot open source"); return

    # If width/height unavailable, use sane defaults
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)

    lx1, ly1, lx2, ly2 = norm_to_abs(args.line, W, H)
    rx1, ry1, rx2, ry2 = norm_to_abs(args.roi, W, H)
    count_y = ly1  # horizontal line (ly1 == ly2)
    roi_box = (rx1, ry1, rx2, ry2)

    # Load YOLO
    model = YOLO(args.model)

    # Tracking and counting state
    total_crossings = 0
    prev_cy = {}  # id -> previous centroid y
    last_count_frame = defaultdict(int)  # id -> frame index of last count (cooldown)
    cooldown = 5  # frames to ignore repeated toggles for same ID

    # Video writer (optional)
    writer = None
    if args.save:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(args.save, fourcc, args.fps_out, (W, H))
        if not writer.isOpened():
            print("⚠️ Failed to open writer; disabling save.")
            writer = None

    # FPS
    t0, frames = time.time(), 0
    gui_ok = bool(args.display)

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames += 1

        # Inference + tracking; filter to vehicles to speed up
        results = model.track(
            frame,
            imgsz=args.imgsz,
            conf=args.conf,
            iou=args.iou,
            tracker=args.tracker,
            persist=True,
            classes=VEHICLE_CLASS_IDS,  # filter to vehicles
            verbose=False
        )

        # Draw ROI + line
        cv2.rectangle(frame, (rx1, ry1), (rx2, ry2), (255, 255, 0), 2)
        cv2.line(frame, (lx1, ly1), (lx2, ly2), (0, 255, 255), 2)

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
                    # (Extra guard — classes filter already applied)
                    continue

                x1i, y1i, x2i, y2i = map(int, (x1, y1, x2, y2))
                # draw box
                cv2.rectangle(frame, (x1i, y1i), (x2i, y2i), (0, 255, 0), 2)
                cv2.putText(frame, f"{label}#{tid}", (x1i, max(0, y1i - 6)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

                # density: box ∩ ROI
                if intersect((x1i, y1i, x2i, y2i), roi_box):
                    density += 1

                # line-crossing via previous vs current centroid
                cx, cy = int((x1 + x2) / 2), int((y1 + y2) / 2)
                pcy = prev_cy.get(tid, None)
                prev_cy[tid] = cy

                if pcy is None:
                    continue

                # Check if crossed between last frame and now
                crossed = (pcy < count_y <= cy) or (pcy > count_y >= cy)
                if crossed:
                    # simple cooldown to avoid bounce double-counts
                    if frames - last_count_frame[tid] >= cooldown:
                        total_crossings += 1
                        last_count_frame[tid] = frames

            # HUD
            fps = frames / (time.time() - t0 + 1e-6)
            cv2.putText(frame, f"Vehicles crossed: {total_crossings}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
            # Determine congestion level
            if density <= 3:
                level = "LOW"
                color = (0, 255, 0)      # Green
            elif density <= 8:
                level = "MEDIUM"
                color = (0, 255, 255)    # Yellow
            else:
                level = "HIGH / TRAFFIC JAM"
                color = (0, 0, 255)      # Red

            # Draw text on screen
            cv2.putText(frame, f"Traffic: {level}  (Vehicles: {density})", 
                        (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.9, color, 2)

            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        else:
            # still draw HUD so output video stays informative
            fps = frames / (time.time() - t0 + 1e-6)
            cv2.putText(frame, f"Vehicles crossed: {total_crossings}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
            cv2.putText(frame, f"Vehicles in ROI: 0", (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 0), 2)
            cv2.putText(frame, f"FPS: {fps:.1f}", (10, 90),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

        # Display if requested; fall back to file output if GUI not available
        if gui_ok:
            try:
                cv2.imshow("Traffic count & density", frame)
            except cv2.error:
                gui_ok = False  # stop trying GUI
        if not gui_ok and writer is not None:
            writer.write(frame)

        # only meaningful when GUI is on
        if gui_ok and (cv2.waitKey(1) & 0xFF == ord('q')):
            break

    cap.release()
    if writer is not None:
        writer.release()
        print(f"💾 Saved: {args.save}")
    cv2.destroyAllWindows()
    print(f"✅ Done. Total crossings: {total_crossings}")
    if not args.display and not args.save:
        print("ℹ️ Tip: use --display to see a window or --save out.mp4 to write a video.")


if __name__ == "__main__":
    main()
