"""
angle_calculator.py — Geometric helpers for posture metric computation

All inputs use MediaPipe normalized coordinates: x, y in [0.0, 1.0].
Functions expect plain (x, y) tuples (drop z and visibility before calling).
"""

import math
import numpy as np


def calculate_angle(a, b, c):
    """
    Calculate the interior angle at point b, formed by segments b→a and b→c.
    Uses the dot-product formula: cos θ = (ba·bc) / (|ba| |bc|).

    a, b, c: (x, y) tuples
    Returns angle in degrees [0, 180].
    """
    a = np.array(a, dtype=float)
    b = np.array(b, dtype=float)
    c = np.array(c, dtype=float)

    ba = a - b
    bc = c - b

    # Clamp to [-1, 1] to guard against floating-point rounding past ±1
    cosine = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-8)
    cosine = np.clip(cosine, -1.0, 1.0)

    return float(np.degrees(np.arccos(cosine)))


def calculate_neck_inclination(nose, shoulder_mid):
    """
    Angle between the vertical axis and the line from shoulder midpoint to nose.

    A perfectly upright neck gives ≈ 0°.
    Leaning the head forward or tilting it increases this angle.

    nose, shoulder_mid: (x, y) tuples (normalized coords)
    Returns angle in degrees.
    """
    dx = abs(nose[0] - shoulder_mid[0])   # horizontal separation
    dy = abs(nose[1] - shoulder_mid[1])   # vertical separation

    # atan2(horizontal, vertical) gives the angle away from vertical
    return math.degrees(math.atan2(dx, dy + 1e-8))


def calculate_shoulder_tilt(left_shoulder, right_shoulder):
    """
    Angle the shoulder line makes with the horizontal.

    0° = perfectly level shoulders.
    Increases when one shoulder is raised or the torso is tilted sideways.

    left_shoulder, right_shoulder: (x, y) tuples (normalized coords)
    Returns angle in degrees.
    """
    dx = abs(right_shoulder[0] - left_shoulder[0])  # horizontal span
    dy = abs(right_shoulder[1] - left_shoulder[1])  # vertical difference

    # atan2(vertical_diff, horizontal_span) gives the tilt from horizontal
    return math.degrees(math.atan2(dy, dx + 1e-8))


def calculate_forward_head_offset(ear_mid, shoulder_mid):
    """
    Signed horizontal offset of the ear midpoint relative to the shoulder midpoint.

    Positive  → ears are in front of (forward of) shoulders.
    Negative  → ears are behind shoulders (rare during normal sitting).
    ≈ 0       → ears directly above shoulders (ideal alignment).

    ear_mid, shoulder_mid: (x, y) tuples (normalized coords)
    Returns a signed float in normalized-coordinate units.

    Note: Because the frame is mirrored (selfie view) in main.py, left/right
    are already natural from the user's perspective. The sign still indicates
    direction but the analysis uses absolute deviation from the calibrated baseline.
    """
    return ear_mid[0] - shoulder_mid[0]
