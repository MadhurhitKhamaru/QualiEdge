#!/usr/bin/env python3
"""
cv_pipeline/camera_stream.py

High-performance non-blocking threaded camera capture engine.
Supports:
1. Standard Industrial USB UVC Cameras (V4L2)
2. Raspberry Pi Camera Module 3 / CSI (libcamera / GStreamer)
3. Simulated steel coil continuous inspection generator for headless edge environments
"""

import time
import threading
from typing import Optional, Tuple
from pathlib import Path

class IndustrialCameraStream:
    """
    Threaded, non-blocking video acquisition stream.
    Prevents OpenCV buffer accumulation to ensure zero-lag real-time inference.
    """
    def __init__(
        self,
        source: int = 0,
        resolution: Tuple[int, int] = (1280, 720),
        target_fps: int = 30,
        use_libcamera: bool = False
    ):
        self.source = source
        self.resolution = resolution
        self.target_fps = target_fps
        self.use_libcamera = use_libcamera

        self.cap = None
        self.frame = None
        self.is_running = False
        self.is_simulation = False
        self.lock = threading.Lock()
        self.thread = None
        self.frame_count = 0
        self.start_time = 0.0

    def start(self):
        """Initialize camera device and start background acquisition thread."""
        try:
            import cv2
            if self.use_libcamera:
                # GStreamer pipeline for Raspberry Pi Camera Module 3
                w, h = self.resolution
                gst_pipeline = (
                    f"libcamerasrc ! video/x-raw, width={w}, height={h}, framerate={self.target_fps}/1 ! "
                    "videoconvert ! video/x-raw, format=BGR ! appsink drop=true"
                )
                self.cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
            else:
                self.cap = cv2.VideoCapture(self.source, cv2.CAP_ANY)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.resolution[0])
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.resolution[1])
                self.cap.set(cv2.CAP_PROP_FPS, self.target_fps)

            if not self.cap.isOpened():
                print(f"[WARN] Camera source {self.source} could not be opened. Falling back to synthetic test stream.")
                self.is_simulation = True
            else:
                ret, frame = self.cap.read()
                if not ret:
                    self.is_simulation = True
                else:
                    self.frame = frame

        except Exception as e:
            print(f"[WARN] Camera initialization encountered exception ({e}). Enabling synthetic stream.")
            self.is_simulation = True

        if self.is_simulation:
            self.frame = self._generate_synthetic_steel_frame()

        self.is_running = True
        self.start_time = time.time()
        self.thread = threading.Thread(target=self._capture_loop, daemon=True)
        self.thread.start()
        print(f"[SUCCESS] Camera stream started (Simulation: {self.is_simulation}, Target: {self.resolution})")
        return self

    def _generate_synthetic_steel_frame(self):
        """Generates realistic synthetic moving steel strip frame when no hardware sensor is connected."""
        try:
            import numpy as np
            import cv2
            w, h = self.resolution
            # Base rolling steel texture
            frame = np.random.normal(loc=135, scale=8, size=(h, w, 3)).astype(np.uint8)
            # Add subtle horizontal rolling grain
            grain = np.tile(np.linspace(125, 145, w, dtype=np.uint8), (h, 1))
            frame[:, :, 0] = cv2.addWeighted(frame[:, :, 0], 0.6, grain, 0.4, 0)
            frame[:, :, 1] = frame[:, :, 0]
            frame[:, :, 2] = frame[:, :, 0]

            # Conveyor side guide boundaries
            cv2.line(frame, (100, 0), (100, h), (40, 40, 40), 4)
            cv2.line(frame, (w - 100, 0), (w - 100, h), (40, 40, 40), 4)

            # Simulated moving surface defect
            t = (self.frame_count % 120) / 120.0
            defect_y = int(100 + t * (h - 200))
            cv2.line(frame, (350, defect_y), (480, defect_y + 15), (220, 220, 220), 3)

            return frame
        except ImportError:
            # Pure Python mock frame representation (height, width, channels)
            class MockFrame:
                def __init__(self, h, w):
                    self.shape = (h, w, 3)
                def copy(self):
                    return self
            return MockFrame(self.resolution[1], self.resolution[0])

    def _capture_loop(self):
        """Dedicated thread continuously reading the latest frame to eliminate buffer lag."""
        while self.is_running:
            if not self.is_simulation and self.cap is not None:
                ret, frame = self.cap.read()
                if ret:
                    with self.lock:
                        self.frame = frame
                        self.frame_count += 1
                else:
                    time.sleep(0.01)
            else:
                synth_frame = self._generate_synthetic_steel_frame()
                with self.lock:
                    self.frame = synth_frame
                    self.frame_count += 1
                time.sleep(1.0 / self.target_fps)

    def read(self):
        """Fetch the most recent frame."""
        with self.lock:
            return self.frame is not None, self.frame.copy() if self.frame is not None else None

    def get_fps(self) -> float:
        """Calculate actual runtime capture frame rate."""
        elapsed = time.time() - self.start_time
        return round(self.frame_count / elapsed, 1) if elapsed > 0 else 0.0

    def stop(self):
        """Stop background thread and release hardware resources."""
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
        if self.cap is not None:
            self.cap.release()
        print("[INFO] Camera stream stopped and hardware device released.")

if __name__ == "__main__":
    stream = IndustrialCameraStream(source=0)
    stream.start()
    time.sleep(0.5)
    ret, frame = stream.read()
    print(f"[TEST] Camera captured frame: {ret}, Frame shape: {frame.shape if frame is not None else 'None'}, FPS: {stream.get_fps()}")
    stream.stop()
