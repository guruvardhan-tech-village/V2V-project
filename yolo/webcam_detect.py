#!/usr/bin/env python3
import argparse, os, time
from collections import deque
from typing import List, Tuple

import cv2
import numpy as np
from ultralytics import YOLO


VIDEO_EXTS = {".mp4", ".avi", ".mov", ".mkv", ".m4v", ".webm"}

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
    if inter <= 0:
        return 0.0
    area_a = max(0, ax2 - ax1) * max(0, ay2 - ay1)
    area_b = max(0, bx2 - bx1) * max(0, by2 - by1)
    return inter / max(area_a + area_b - inter, 1e-6)


class AccidentSmoother:
    """
    Simple temporal smoother:
      - considers 'accident' if any accident-class box appears for >= rise_frames
      - clears when no accident boxes for >= fall_frames
      - optional IoU match to keep a persistent 'hot' region (best_box)
    """
    def __init__(self, rise_frames=3, fall_frames=6, iou_match=0.3):
        self.rise_frames = rise_frames
        self.fall_frames = fall_frames
        self.iou_match = iou_match

        self.acc_count = 0
        self.noacc_count = 0
        self.state_on = False
        self.best_box = None        # (x1,y1,x2,y2)
        self.best_conf = 0.0
        self.last_seen_time = 0.0

    def update(self, acc_boxes: List[Tuple[int,int,int,int]], acc_confs: List[float]):
        now = time.time()

        if acc_boxes:
            # pick the highest-confidence accident box as the current focus
            max_idx = int(np.argmax(acc_confs))
            cur_box = acc_boxes[max_idx]
            cur_conf = float(acc_confs[max_idx])

            # maintain a persistent "best_box" using IoU match
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


def parse_args():
    ap = argparse.ArgumentParser("Real-time Accident BOX Detector (YOLO)")
    ap.add_argument(
        "--weights", type=str,
        default=r"C:\Users\Somashekar A\Desktop\Major Pro\yolo\accident\v1\weights\best.pt",
        help="Path to your trained YOLO detection weights (.pt)"
    )
    ap.add_argument("--source", type=str, default="0", help="0=webcam or path to video")
    ap.add_argument("--imgsz", type=int, default=640, help="inference size")
    ap.add_argument("--conf", type=float, default=0.35, help="confidence threshold")
    ap.add_argument("--iou", type=float, default=0.5, help="NMS IoU threshold")
    ap.add_argument("--device", type=str, default=None, help="CUDA device id like 0, or cpu")
    ap.add_argument("--rise-frames", type=int, default=3, help="frames needed to light up ACCIDENT")
    ap.add_argument("--fall-frames", type=int, default=6, help="frames needed to clear ACCIDENT")
    ap.add_argument("--show-fps", action="store_true", help="overlay live FPS")
    ap.add_argument("--display", action="store_true", help="show window")
    ap.add_argument("--save", type=str, default="", help="optional output mp4 path")
    ap.add_argument("--fps_out", type=int, default=25, help="save FPS")
    return ap.parse_args()


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


def main():
    args = parse_args()

    # Load model
    model = YOLO(args.weights)

    # Build accident-class id set from names
    # Your data.yaml shows: ['Accident','Accident-fire-smoke','Bike','CAR','Truck']
    names = model.names if hasattr(model, "names") else {}
    accident_ids = set()
    for i, n in names.items():
        s = str(n).lower()
        if ("accident" in s) or ("collision" in s) or ("fire" in s) or ("smoke" in s):
            accident_ids.add(int(i))
    # Fallback if none matched (shouldn't happen with your YAML)
    if not accident_ids and 0 in names:
        accident_ids.add(0)

    # Video I/O
    cap, is_cam = open_capture(args.source)
    if not cap or not cap.isOpened():
        print("❌ Could not open source"); return
    if is_cam:
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    W = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1280)
    H = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 720)
    in_fps = cap.get(cv2.CAP_PROP_FPS) or 30.0

    writer = None
    if args.save:
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(args.save, fourcc, args.fps_out or in_fps, (W, H))
        if not writer.isOpened():
            print("⚠️ Failed to open writer; disabling save.")
            writer = None

    smoother = AccidentSmoother(rise_frames=args.rise_frames, fall_frames=args.fall_frames)
    gui = args.display
    print("✅ Running. Press 'q' to quit.")
    t0, frames = time.time(), 0

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        frames += 1

        # Inference (single image)
        res = model.predict(
            frame,
            imgsz=args.imgsz,
            conf=args.conf,
            iou=args.iou,
            device=args.device if args.device is not None else None,
            verbose=False
        )

        accident_boxes = []
        accident_confs = []

        if res and len(res):
            r = res[0]
            if r.boxes is not None and len(r.boxes) > 0:
                xyxy = r.boxes.xyxy.cpu().numpy()
                cls = r.boxes.cls.cpu().numpy().astype(int)
                conf = r.boxes.conf.cpu().numpy()

                for (x1, y1, x2, y2), c, p in zip(xyxy, cls, conf):
                    x1i, y1i, x2i, y2i = map(int, (x1, y1, x2, y2))
                    label = names.get(int(c), str(c))
                    is_acc = (int(c) in accident_ids)

                    if is_acc:
                        accident_boxes.append((x1i, y1i, x2i, y2i))
                        accident_confs.append(float(p))
                        color = (0, 0, 255)  # RED for accident
                    else:
                        color = (0, 200, 0)  # GREEN for non-accident classes

                    cv2.rectangle(frame, (x1i, y1i), (x2i, y2i), color, 2)
                    cv2.putText(
                        frame,
                        f"{label} {p:.2f}",
                        (x1i, max(0, y1i - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        color,
                        2
                    )

        # Temporal smoothing + big banner
        state_on, best_box, best_conf = smoother.update(accident_boxes, accident_confs)
        if state_on and best_box is not None:
            bx1, by1, bx2, by2 = best_box
            cv2.rectangle(frame, (bx1, by1), (bx2, by2), (0, 0, 255), 3)  # emphasize red
            cv2.putText(
                frame,
                f"ACCIDENT DETECTED ({best_conf:.2f})",
                (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.2,
                (0, 0, 255),
                3
            )
        else:
            cv2.putText(
                frame,
                "NO ACCIDENT",
                (10, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                1.2,
                (0, 200, 0),
                3
            )

        if args.show_fps:
            dt = time.time() - t0
            fps_live = frames / max(1e-6, dt)
            cv2.putText(frame, f"FPS: {fps_live:.1f}", (10, 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)

        if writer is not None:
            writer.write(frame)
        if gui:
            if not safe_imshow("Accident Detector (YOLO)", frame):
                gui = False
            else:
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

    cap.release()
    if writer is not None:
        writer.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
