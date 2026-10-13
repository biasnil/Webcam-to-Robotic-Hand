"""
Hand Gesture Recognition - GUI with webcam selection & auto-detect
====================================================================
Adds a Tkinter GUI on top of the MediaPipe hand-gesture pipeline:
- Dropdown to pick which webcam feeds the detector
- Background scanning that picks up newly plugged-in cameras automatically
  (and drops cameras that get unplugged)
- Live video + gesture overlay rendered inside the window (no cv2.imshow)

SETUP (one-time):
1. pip install mediapipe opencv-python pillow
2. Download the hand landmark model file and put it in the same folder,
   named exactly hand_landmarker.task:
   https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task

Run: python hand_gesture_gui.py
Close the window to quit.
"""

import threading
import time
import tkinter as tk
from tkinter import ttk
from collections import deque

import cv2
from PIL import Image, ImageTk
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import HandLandmarker, HandLandmarkerOptions, RunningMode

from Arduino_Link import ArduinoLink

# ---- Settings ----
GESTURE_WINDOW_SIZE = 15
CONFIDENCE_THRESHOLD = 0.80
DEBOUNCE_COOLDOWN_MS = 500
OK_TOUCH_RATIO_THRESHOLD = 0.35
MODEL_PATH = "hand_landmarker.task"
MAX_CAMERA_INDEX = 5           # how many device indices to probe
CAMERA_SCAN_INTERVAL_SEC = 5   # how often to look for new/removed cameras
FRAME_INTERVAL_MS = 15         # how often to pull + process a frame (~fast as camera allows)

# Landmark indices (MediaPipe's standard 21-point hand model)
WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (0, 9), (9, 10), (10, 11), (11, 12),
    (0, 13), (13, 14), (14, 15), (15, 16),
    (0, 17), (17, 18), (18, 19), (19, 20),
    (5, 9), (9, 13), (13, 17),
]


def dist(a, b):
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def get_finger_states(landmarks):
    lm = landmarks
    index_up = lm[INDEX_TIP].y < lm[INDEX_PIP].y
    middle_up = lm[MIDDLE_TIP].y < lm[MIDDLE_PIP].y
    ring_up = lm[RING_TIP].y < lm[RING_PIP].y
    pinky_up = lm[PINKY_TIP].y < lm[PINKY_PIP].y

    thumb_tip_dist = dist(lm[THUMB_TIP], lm[PINKY_MCP])
    thumb_ip_dist = dist(lm[THUMB_IP], lm[PINKY_MCP])
    thumb_up = thumb_tip_dist > thumb_ip_dist * 1.1

    return {
        "thumb": thumb_up,
        "index": index_up,
        "middle": middle_up,
        "ring": ring_up,
        "pinky": pinky_up,
    }


def detect_ok_sign(landmarks, finger_states):
    lm = landmarks
    palm_size = dist(lm[WRIST], lm[MIDDLE_MCP])
    if palm_size == 0:
        return False
    thumb_index_ratio = dist(lm[THUMB_TIP], lm[INDEX_TIP]) / palm_size
    touching = thumb_index_ratio < OK_TOUCH_RATIO_THRESHOLD
    return touching and finger_states["middle"] and finger_states["ring"] and finger_states["pinky"]


def classify_gesture(finger_states, landmarks):
    if detect_ok_sign(landmarks, finger_states):
        return "OK"

    up = [name for name, is_up in finger_states.items() if is_up]
    count = len(up)

    if count == 0:
        return "FIST"
    if count == 5:
        return "OPEN_HAND"
    if count == 1:
        if finger_states["index"]:
            return "POINT"
        if finger_states["thumb"]:
            return "THUMBS_UP"
        return "ONE_FINGER_" + up[0].upper()
    if count == 2:
        if finger_states["index"] and finger_states["middle"] and not finger_states["thumb"]:
            return "PEACE"
        return "TWO_FINGERS"
    if count == 3:
        if (finger_states["thumb"] and finger_states["index"] and finger_states["pinky"]
                and not finger_states["middle"] and not finger_states["ring"]):
            return "ROCK_N_ROLL"
        return "THREE"
    if count == 4:
        return "FOUR"
    return "UNKNOWN"


class GestureStabilizer:
    def __init__(self, window_size=GESTURE_WINDOW_SIZE, confidence_threshold=CONFIDENCE_THRESHOLD,
                 cooldown_ms=DEBOUNCE_COOLDOWN_MS):
        self.window = deque(maxlen=window_size)
        self.confidence_threshold = confidence_threshold
        self.cooldown_ms = cooldown_ms
        self.last_triggered_gesture = None
        self.last_trigger_time_ms = 0

    def update(self, raw_gesture):
        self.window.append(raw_gesture)
        counts = {}
        for g in self.window:
            counts[g] = counts.get(g, 0) + 1
        majority_gesture, majority_count = max(counts.items(), key=lambda kv: kv[1])
        confidence = majority_count / len(self.window)
        stable_gesture = majority_gesture if confidence >= self.confidence_threshold else None

        now_ms = time.time() * 1000
        is_new_event = False
        if stable_gesture is not None and stable_gesture != self.last_triggered_gesture:
            if now_ms - self.last_trigger_time_ms >= self.cooldown_ms:
                is_new_event = True
                self.last_triggered_gesture = stable_gesture
                self.last_trigger_time_ms = now_ms

        return stable_gesture, confidence, is_new_event


def draw_landmarks(frame, landmarks, w, h):
    for start_idx, end_idx in HAND_CONNECTIONS:
        p1 = landmarks[start_idx]
        p2 = landmarks[end_idx]
        cv2.line(frame, (int(p1.x * w), int(p1.y * h)), (int(p2.x * w), int(p2.y * h)), (0, 255, 0), 2)
    for point in landmarks:
        cv2.circle(frame, (int(point.x * w), int(point.y * h)), 4, (0, 0, 255), -1)


class CameraScanner(threading.Thread):
    """
    Background thread that periodically probes camera indices 0..max_index-1
    and records which ones are currently openable. Runs off the GUI thread
    since opening/closing a VideoCapture is slow (especially on Windows).
    """

    def __init__(self, max_index=MAX_CAMERA_INDEX, interval_sec=CAMERA_SCAN_INTERVAL_SEC, skip_index_getter=None):
        super().__init__(daemon=True)
        self.max_index = max_index
        self.interval_sec = interval_sec
        self._skip_index_getter = skip_index_getter
        self._available = []
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    def run(self):
        while not self._stop_event.is_set():
            found = []
            active_index = self._skip_index_getter() if self._skip_index_getter else None
            for index in range(self.max_index):
                if index == active_index:
                    # Already known-open by the app itself - skip re-probing to
                    # avoid fighting over the same device handle.
                    found.append(index)
                    continue
                cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
                if cap.isOpened():
                    found.append(index)
                cap.release()
            with self._lock:
                self._available = found
            self._stop_event.wait(self.interval_sec)

    def get_available(self):
        with self._lock:
            return list(self._available)

    def stop(self):
        self._stop_event.set()


class GestureApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Hand Gesture Recognition")

        top_frame = ttk.Frame(root)
        top_frame.pack(side=tk.TOP, fill=tk.X, padx=8, pady=8)

        ttk.Label(top_frame, text="Webcam:").pack(side=tk.LEFT, padx=(0, 6))
        self.camera_var = tk.StringVar()
        self.camera_combo = ttk.Combobox(top_frame, textvariable=self.camera_var, state="readonly", width=20)
        self.camera_combo.pack(side=tk.LEFT)
        self.camera_combo.bind("<<ComboboxSelected>>", self.on_camera_selected)

        self.status_label = ttk.Label(top_frame, text="Scanning for cameras...")
        self.status_label.pack(side=tk.LEFT, padx=12)

        self.video_label = ttk.Label(root)
        self.video_label.pack(side=tk.TOP, padx=8, pady=(0, 8))

        self.gesture_label = ttk.Label(root, text="Stable: --  |  Confidence: 0%", font=("Segoe UI", 14))
        self.gesture_label.pack(side=tk.TOP, pady=(0, 8))

        self.cap = None
        self.current_index = None
        self.known_cameras = []
        self.stabilizer = GestureStabilizer()

        base_options = BaseOptions(model_asset_path=MODEL_PATH)
        options = HandLandmarkerOptions(
            base_options=base_options,
            running_mode=RunningMode.VIDEO,
            num_hands=1,
            min_hand_detection_confidence=0.5,
            min_hand_presence_confidence=0.5,
            min_tracking_confidence=0.5,
        )
        self.landmarker = HandLandmarker.create_from_options(options)
        self.start_time = time.time()

        self.arduino = ArduinoLink()
        self.arduino.connect()  # non-blocking-ish; safe no-op if not plugged in yet

        self.scanner = CameraScanner(skip_index_getter=lambda: self.current_index)
        self.scanner.start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        self.refresh_camera_list()
        self.update_frame()

    def refresh_camera_list(self):
        available = self.scanner.get_available()
        if available != self.known_cameras:
            self.known_cameras = available
            self.camera_combo["values"] = [f"Camera {i}" for i in available]

            if available:
                self.status_label.config(text=f"{len(available)} camera(s) found")
            else:
                self.status_label.config(text="No cameras found")

            if self.current_index is None and available:
                self.camera_combo.current(0)
                self.switch_camera(available[0])
            elif self.current_index is not None and self.current_index not in available:
                self.status_label.config(text="Active camera disconnected")
                self.release_camera()

        self.root.after(1000, self.refresh_camera_list)

    def on_camera_selected(self, event=None):
        selection = self.camera_combo.current()
        if 0 <= selection < len(self.known_cameras):
            self.switch_camera(self.known_cameras[selection])

    def switch_camera(self, index):
        self.release_camera()
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if cap.isOpened():
            self.cap = cap
            self.current_index = index
            self.stabilizer = GestureStabilizer()  # fresh confidence window on camera switch
            self.status_label.config(text=f"Using Camera {index}")
        else:
            cap.release()
            self.status_label.config(text=f"Could not open Camera {index}")

    def release_camera(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.current_index = None

    def update_frame(self):
        if self.cap is not None:
            ret, frame = self.cap.read()
            if ret:
                frame = cv2.flip(frame, 1)
                h, w, _ = frame.shape
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
                timestamp_ms = int((time.time() - self.start_time) * 1000)
                result = self.landmarker.detect_for_video(mp_image, timestamp_ms)

                raw_gesture = "NONE"
                if result.hand_landmarks:
                    landmarks = result.hand_landmarks[0]
                    draw_landmarks(frame, landmarks, w, h)
                    finger_states = get_finger_states(landmarks)
                    raw_gesture = classify_gesture(finger_states, landmarks)
                    cv2.putText(frame, f"Raw: {raw_gesture}", (20, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                else:
                    cv2.putText(frame, "NO HAND DETECTED", (20, 30),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

                stable_gesture, confidence, is_new_event = self.stabilizer.update(raw_gesture)
                if is_new_event:
                    print(f"[EVENT] Confirmed gesture change -> {stable_gesture} "
                          f"(confidence {int(confidence * 100)}%)")
                    sent = self.arduino.send_gesture(stable_gesture)
                    if not sent:
                        print("[Arduino] Not connected - gesture not sent")

                label_text = stable_gesture if stable_gesture else f"building... ({int(confidence * 100)}%)"
                self.gesture_label.config(text=f"Stable: {label_text}  |  Confidence: {int(confidence * 100)}%")

                img_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                imgtk = ImageTk.PhotoImage(image=Image.fromarray(img_rgb))
                self.video_label.imgtk = imgtk  # keep a reference - otherwise Tkinter garbage-collects it
                self.video_label.configure(image=imgtk)
            else:
                self.status_label.config(text="Camera read failed - reconnecting...")
                self.release_camera()

        self.root.after(FRAME_INTERVAL_MS, self.update_frame)

    def on_close(self):
        self.scanner.stop()
        self.release_camera()
        self.landmarker.close()
        self.arduino.close()
        self.root.destroy()


def main():
    root = tk.Tk()
    GestureApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()