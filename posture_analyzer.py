"""
posture_analyzer.py — Posture classification logic

Converts raw landmark positions into a PostureResult that captures:
  - whether posture is acceptable
  - individual metric values (neck angle, shoulder tilt, FHP)
  - a list of plain-English issues for display
  - an overall severity level

Thresholds are tuned for a seated desk-work scenario. Adjust them in
THRESHOLDS if the user's natural posture triggers false positives.
"""

from collections import namedtuple

from angle_calculator import (
    calculate_neck_inclination,
    calculate_shoulder_tilt,
    calculate_forward_head_offset,
)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
THRESHOLDS = {
    # Neck inclination above this → forward head / neck strain
    'neck_inclination_max': 30,    # degrees

    # Shoulder line tilt above this → slouching or asymmetric posture
    'shoulder_tilt_max': 10,       # degrees

    # How far the ear midpoint can deviate from the calibrated baseline
    # before flagging forward head posture (only used when calibrated)
    'fhp_offset_tolerance': 0.06,  # normalized coordinate units
}

# Minimum MediaPipe visibility score for a landmark to be trusted
# Below this, the landmark is likely hidden/occluded and should not be used
LANDMARK_VISIBILITY_MIN = 0.5

# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------
PostureResult = namedtuple('PostureResult', [
    'is_good',        # bool  — True if all checks pass
    'neck_angle',     # float — neck inclination in degrees
    'shoulder_tilt',  # float — shoulder tilt in degrees
    'fhp_offset',     # float — forward-head offset (normalized, signed)
    'issues',         # list[str] — human-readable problem descriptions
    'severity',       # str  — 'good' | 'warning' | 'bad'
])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _xy(landmark):
    """Extract (x, y) from a landmark tuple (x, y, z, visibility)."""
    return (landmark[0], landmark[1])


def _mid(p1, p2):
    """Return the midpoint of two (x, y) points."""
    return ((p1[0] + p2[0]) / 2.0, (p1[1] + p2[1]) / 2.0)


# ---------------------------------------------------------------------------
# Main analysis function
# ---------------------------------------------------------------------------
def analyze_posture(landmarks, calibration_data=None):
    """
    Analyse posture for a single frame.

    Parameters
    ----------
    landmarks : dict
        Output of PoseDetector.detect_pose() — keys are landmark names,
        values are (x, y, z, visibility) tuples.
    calibration_data : dict or None
        Baseline values from CalibrationSystem.get_baseline().
        When None, only absolute thresholds (neck + shoulder) are checked.

    Returns
    -------
    PostureResult namedtuple
    """
    # --- Extract (x, y) for each landmark we need ---
    nose            = _xy(landmarks['nose'])
    left_shoulder   = _xy(landmarks['left_shoulder'])
    right_shoulder  = _xy(landmarks['right_shoulder'])
    left_ear        = _xy(landmarks['left_ear'])
    right_ear       = _xy(landmarks['right_ear'])

    # Visibility scores let us reject occluded/hidden landmarks (typically
    # ears get hidden by hair or when the user faces straight at the camera)
    left_ear_vis    = landmarks['left_ear'][3]
    right_ear_vis   = landmarks['right_ear'][3]

    shoulder_mid = _mid(left_shoulder, right_shoulder)

    # Choose the most reliable ear reference for FHP:
    #   • Both ears visible  → use their midpoint (best)
    #   • Only one visible   → use that one alone
    #   • Neither visible    → fall back to the nose so we still have a value
    left_ok  = left_ear_vis  >= LANDMARK_VISIBILITY_MIN
    right_ok = right_ear_vis >= LANDMARK_VISIBILITY_MIN

    if left_ok and right_ok:
        ear_mid = _mid(left_ear, right_ear)
        fhp_reliable = True
    elif left_ok:
        ear_mid = left_ear
        fhp_reliable = True
    elif right_ok:
        ear_mid = right_ear
        fhp_reliable = True
    else:
        ear_mid = nose
        fhp_reliable = False   # FHP value reported but won't drive issue flag

    # --- Compute posture metrics ---
    neck_angle    = calculate_neck_inclination(nose, shoulder_mid)
    shoulder_tilt = calculate_shoulder_tilt(left_shoulder, right_shoulder)
    fhp_offset    = calculate_forward_head_offset(ear_mid, shoulder_mid)

    issues = []

    # Check 1: neck inclination (catches forward-head and neck-drop)
    if neck_angle > THRESHOLDS['neck_inclination_max']:
        issues.append(f"Forward head posture (neck {neck_angle:.0f}°)")

    # Check 2: shoulder symmetry / torso tilt
    if shoulder_tilt > THRESHOLDS['shoulder_tilt_max']:
        issues.append(f"Uneven shoulders ({shoulder_tilt:.0f}° tilt)")

    # Check 3: calibration-relative forward-head
    # Only run when calibrated AND ears were visible enough to trust the FHP value
    if calibration_data and fhp_reliable:
        baseline_fhp = calibration_data.get('fhp_offset', 0.0)
        fhp_deviation = abs(fhp_offset - baseline_fhp)
        if fhp_deviation > THRESHOLDS['fhp_offset_tolerance']:
            # Avoid duplicate if neck check already flagged forward head
            already_flagged = any('Forward head' in i for i in issues)
            if not already_flagged:
                issues.append(f"Head shifted forward ({fhp_deviation:.3f} units)")

    # --- Determine severity ---
    if len(issues) == 0:
        severity = 'good'
    elif len(issues) == 1:
        severity = 'warning'
    else:
        severity = 'bad'

    return PostureResult(
        is_good       = (severity == 'good'),
        neck_angle    = neck_angle,
        shoulder_tilt = shoulder_tilt,
        fhp_offset    = fhp_offset,
        issues        = issues,
        severity      = severity,
    )
