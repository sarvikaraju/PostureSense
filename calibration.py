"""
calibration.py — Personalised posture baseline

Stores the user's "correct posture" reference so that future frames can be
compared against it rather than relying solely on hard-coded angle limits.

Calibration data is persisted to a JSON file so it survives application
restarts. The file is auto-loaded in main.py on startup.
"""

import json
import os

from angle_calculator import (
    calculate_neck_inclination,
    calculate_shoulder_tilt,
    calculate_forward_head_offset,
)


class CalibrationSystem:
    def __init__(self):
        # None when the system has not been calibrated yet
        self._baseline = None

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    def calibrate(self, landmarks):
        """
        Record the user's current posture as the personal 'good posture' baseline.

        landmarks: dict from PoseDetector.detect_pose()
        Call this when the user is sitting correctly and presses [C].
        Returns True on success, False if landmarks is None/invalid.
        """
        if not landmarks or 'nose' not in landmarks:
            return False

        # Extract (x, y) for the landmarks we need
        nose           = (landmarks['nose'][0],           landmarks['nose'][1])
        left_shoulder  = (landmarks['left_shoulder'][0],  landmarks['left_shoulder'][1])
        right_shoulder = (landmarks['right_shoulder'][0], landmarks['right_shoulder'][1])
        left_ear       = (landmarks['left_ear'][0],       landmarks['left_ear'][1])
        right_ear      = (landmarks['right_ear'][0],      landmarks['right_ear'][1])

        shoulder_mid = (
            (left_shoulder[0] + right_shoulder[0]) / 2.0,
            (left_shoulder[1] + right_shoulder[1]) / 2.0,
        )
        ear_mid = (
            (left_ear[0] + right_ear[0]) / 2.0,
            (left_ear[1] + right_ear[1]) / 2.0,
        )

        # Store computed metrics AND raw midpoints (useful for debugging)
        self._baseline = {
            'neck_angle':    calculate_neck_inclination(nose, shoulder_mid),
            'shoulder_tilt': calculate_shoulder_tilt(left_shoulder, right_shoulder),
            'fhp_offset':    calculate_forward_head_offset(ear_mid, shoulder_mid),
            # Raw positions let us compute additional metrics later if needed
            'nose':          list(nose),
            'shoulder_mid':  list(shoulder_mid),
            'ear_mid':       list(ear_mid),
        }
        return True

    def is_calibrated(self):
        """Return True if a baseline has been recorded."""
        return self._baseline is not None

    def get_baseline(self):
        """
        Return the baseline dict, or None if not calibrated.
        posture_analyzer.analyze_posture() accepts None safely.
        """
        return self._baseline

    def reset(self):
        """Clear the stored baseline (does not delete the JSON file)."""
        self._baseline = None

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    # Required keys that any valid baseline JSON must contain
    _REQUIRED_KEYS = ('neck_angle', 'shoulder_tilt', 'fhp_offset')

    def save(self, path='calibration.json'):
        """
        Write current calibration data to a JSON file.
        Returns True on success, False if no calibration exists or write fails.
        """
        if not self._baseline:
            return False
        try:
            with open(path, 'w') as f:
                json.dump(self._baseline, f, indent=2)
            return True
        except (OSError, TypeError):
            # Disk full / permission denied / non-serialisable data
            return False

    def load(self, path='calibration.json'):
        """
        Load calibration data from a JSON file.
        Returns True only if the file exists, parses to a dict, and contains
        all required keys with numeric values. Garbage files are rejected.
        """
        if not os.path.exists(path):
            return False
        try:
            with open(path, 'r') as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError, ValueError):
            # File missing, locked, or malformed JSON
            return False

        # Reject any payload that isn't a dict (e.g. '[]', '"foo"', 'null')
        if not isinstance(data, dict):
            return False

        # Ensure all required numeric metrics are present and finite
        for key in self._REQUIRED_KEYS:
            if key not in data or not isinstance(data[key], (int, float)):
                return False

        # Convert list positions back to tuples for internal consistency
        for key in ('nose', 'shoulder_mid', 'ear_mid'):
            if key in data and isinstance(data[key], list):
                data[key] = tuple(data[key])

        self._baseline = data
        return True
