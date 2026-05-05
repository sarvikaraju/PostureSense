"""
pose_detector.py — MediaPipe Pose wrapper

Responsibilities:
  - Open a MediaPipe Pose instance with tuned confidence thresholds
  - Convert frames between BGR (OpenCV) and RGB (MediaPipe)
  - Return annotated frame + a clean dict of the 7 landmarks we use
"""

import cv2
import mediapipe as mp


class PoseDetector:
    def __init__(self):
        # MediaPipe Pose solution handles single-person detection
        self._mp_pose = mp.solutions.pose

        # min_detection_confidence: how confident MP must be to start tracking
        # min_tracking_confidence: how confident MP must be to keep tracking
        self._pose = self._mp_pose.Pose(
            min_detection_confidence=0.7,
            min_tracking_confidence=0.7,
        )

    def detect_pose(self, frame):
        """
        Run MediaPipe Pose on one BGR frame from OpenCV.

        Returns:
            (frame, landmarks_dict) — landmarks_dict is None if no pose
            was detected. The frame is returned unchanged; ui_overlay handles
            all visual annotation.

        landmarks_dict keys:
            'nose', 'left_ear', 'right_ear',
            'left_shoulder', 'right_shoulder',
            'left_hip', 'right_hip'
        Each value is a tuple: (x, y, z, visibility)
        x, y are normalized 0.0–1.0; z is depth (relative); visibility 0–1.
        """
        # MediaPipe requires RGB. We do NOT need to convert back to BGR
        # because the original 'frame' parameter is already BGR and is
        # untouched by MediaPipe — this saves ~1–2 ms per frame.
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False   # tells MP it can avoid copying
        results = self._pose.process(rgb)

        if not results.pose_landmarks:
            return frame, None

        # Extract the 7 landmarks we need by their fixed MediaPipe indices
        lm = results.pose_landmarks.landmark

        def _lm(idx):
            return (lm[idx].x, lm[idx].y, lm[idx].z, lm[idx].visibility)

        landmarks = {
            'nose':            _lm(0),
            'left_ear':        _lm(7),
            'right_ear':       _lm(8),
            'left_shoulder':   _lm(11),
            'right_shoulder':  _lm(12),
            'left_hip':        _lm(23),
            'right_hip':       _lm(24),
        }

        return frame, landmarks

    def close(self):
        """Release MediaPipe Pose resources."""
        self._pose.close()
