"""
ui_overlay.py — Frame drawing module

All rendering happens on a copy of the OpenCV BGR frame.
Uses semi-transparent overlays (addWeighted) for panels so the webcam image
remains visible beneath the UI elements.

Color scheme (BGR):
  Green  — good posture
  Yellow — single warning issue
  Red    — bad posture / critical alerts
  White  — neutral text
  Orange — issue description text
"""

import cv2
import time

# ---------------------------------------------------------------------------
# Colour constants (BGR for OpenCV)
# ---------------------------------------------------------------------------
GREEN     = (0, 210, 0)
RED       = (0, 0, 220)
YELLOW    = (0, 210, 220)
WHITE     = (255, 255, 255)
ORANGE    = (30, 150, 255)
DARK_BG   = (20, 20, 20)
GREY      = (140, 140, 140)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _lm_px(landmark, frame_shape):
    """Convert a normalised (x, y) landmark to pixel coordinates."""
    h, w = frame_shape[:2]
    return (int(landmark[0] * w), int(landmark[1] * h))


def _semi_rect(frame, x1, y1, x2, y2, color=DARK_BG, alpha=0.65):
    """Draw a filled rectangle with transparency over the frame."""
    overlay = frame.copy()
    cv2.rectangle(overlay, (x1, y1), (x2, y2), color, -1)
    cv2.addWeighted(overlay, alpha, frame, 1 - alpha, 0, frame)


def _text(frame, msg, x, y, scale=0.5, color=WHITE, thickness=1, font=cv2.FONT_HERSHEY_SIMPLEX):
    cv2.putText(frame, msg, (x, y), font, scale, color, thickness, cv2.LINE_AA)


# ---------------------------------------------------------------------------
# Individual drawing components
# ---------------------------------------------------------------------------

def draw_skeleton(frame, landmarks, is_good):
    """
    Draw a coloured posture skeleton over the MediaPipe default grey one.
    Green lines for good posture, red for bad — gives instant visual feedback.
    """
    color     = GREEN if is_good else RED
    thickness = 2

    # Map all landmark names to pixel coordinates at once
    px = {name: _lm_px(lm, frame.shape) for name, lm in landmarks.items()}

    # Skeleton connections relevant to upper-body posture
    connections = [
        ('left_shoulder',  'right_shoulder'),   # shoulder bar
        ('left_shoulder',  'left_hip'),          # left side of torso
        ('right_shoulder', 'right_hip'),         # right side of torso
        ('left_hip',       'right_hip'),         # hip bar
        ('left_shoulder',  'nose'),              # left neck line
        ('right_shoulder', 'nose'),              # right neck line
        ('nose',           'left_ear'),          # left head side
        ('nose',           'right_ear'),         # right head side
    ]

    for start, end in connections:
        cv2.line(frame, px[start], px[end], color, thickness, cv2.LINE_AA)

    # Draw landmark dots with a white outline for contrast
    for pt in px.values():
        cv2.circle(frame, pt, 5, color, -1)
        cv2.circle(frame, pt, 5, WHITE, 1)


def draw_status_panel(frame, stats, calibrated, fps):
    """
    Top-left panel: app title, FPS, calibration status, session time, controls hint.
    """
    panel_w, panel_h = 270, 140
    _semi_rect(frame, 5, 5, 5 + panel_w, 5 + panel_h)

    x, y = 12, 26

    _text(frame, "PostureSense v1.0", x, y, scale=0.55, color=GREEN, thickness=1)

    cal_text  = "CALIBRATED" if calibrated else "Not calibrated — press [C]"
    cal_color = GREEN if calibrated else YELLOW
    _text(frame, cal_text, x, y + 22, scale=0.42, color=cal_color)

    _text(frame, f"FPS: {fps:.0f}", x, y + 42, scale=0.42, color=WHITE)

    # Session time counters
    g_m, g_s = divmod(int(stats['good_time']), 60)
    b_m, b_s = divmod(int(stats['bad_time']),  60)
    _text(frame, f"Good: {g_m:02d}:{g_s:02d}   Bad: {b_m:02d}:{b_s:02d}",
          x, y + 62, scale=0.42, color=WHITE)

    _text(frame, f"Bad posture events: {stats['bad_events']}",
          x, y + 82, scale=0.42, color=WHITE)

    _text(frame, "C: Calibrate   R: Reset   Q: Quit",
          x, y + 106, scale=0.38, color=GREY)


def draw_score(frame, score):
    """
    Top-right: posture score box with a colour-coded fill bar.
      >= 70 → green  (good)
      40–69 → yellow (average)
      < 40  → red    (poor)
    """
    h, w = frame.shape[:2]

    if score >= 70:
        color = GREEN
    elif score >= 40:
        color = YELLOW
    else:
        color = RED

    box_w, box_h = 145, 88
    x1 = w - box_w - 10
    y1 = 8

    _semi_rect(frame, x1, y1, x1 + box_w, y1 + box_h)

    # Label — centred above the score number
    label = "SCORE"
    (lw, _), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.52, 1)
    _text(frame, label, x1 + (box_w - lw) // 2, y1 + 22, scale=0.52, color=WHITE)

    # Large score number — measured and centred dynamically so 0, 99, and 100
    # all sit in the middle of the box regardless of digit count
    score_str = str(score)
    (sw, sh), _ = cv2.getTextSize(score_str, cv2.FONT_HERSHEY_DUPLEX, 1.7, 2)
    sx = x1 + (box_w - sw) // 2
    sy = y1 + 28 + sh
    _text(frame, score_str, sx, sy,
          scale=1.7, color=color, thickness=2, font=cv2.FONT_HERSHEY_DUPLEX)

    # Progress bar at the bottom of the box
    bar_x1 = x1 + 8
    bar_x2 = x1 + box_w - 8
    bar_y  = y1 + box_h - 8
    bar_filled = int((score / 100.0) * (bar_x2 - bar_x1))
    cv2.rectangle(frame, (bar_x1, bar_y - 7), (bar_x2, bar_y), DARK_BG, -1)
    if bar_filled > 0:
        cv2.rectangle(frame, (bar_x1, bar_y - 7), (bar_x1 + bar_filled, bar_y), color, -1)


def draw_posture_status(frame, result):
    """
    Bottom-left: large status label (GOOD / WARNING / BAD POSTURE)
    followed by a line showing current metric values and any detected issues.
    """
    h = frame.shape[0]

    # Choose label and colour by severity
    if result.severity == 'good':
        label, color = "GOOD POSTURE",    GREEN
    elif result.severity == 'warning':
        label, color = "POSTURE WARNING", YELLOW
    else:
        label, color = "BAD POSTURE",     RED

    y_base = h - 85

    _text(frame, label, 15, y_base, scale=0.9, color=color,
          thickness=2, font=cv2.FONT_HERSHEY_DUPLEX)

    # Metric readout
    metrics = (f"Neck: {result.neck_angle:.1f}deg  "
               f"Shoulder: {result.shoulder_tilt:.1f}deg  "
               f"FHP: {result.fhp_offset:+.3f}")
    _text(frame, metrics, 15, y_base + 26, scale=0.40, color=WHITE)

    # List each detected issue
    for i, issue in enumerate(result.issues):
        _text(frame, f"  ! {issue}", 15, y_base + 48 + i * 20,
              scale=0.42, color=ORANGE)


def draw_alerts(frame, result, consecutive_bad_seconds):
    """
    Top-centre: blinking warning banner when posture is bad.
    The message and colour intensify the longer bad posture continues.
    Thresholds are real-time seconds, matching the audio feedback levels.
    """
    if result.is_good:
        return

    h, w = frame.shape[:2]

    # Blink slowly during the warning phase; stay solid once critical
    if consecutive_bad_seconds < 3.0:
        blink_on = (int(time.time() * 2) % 2 == 0)
        if not blink_on:
            return

    # Message and background colour by duration of bad posture
    if consecutive_bad_seconds >= 6.0:
        msg      = "!! CRITICAL POSTURE ALERT — PLEASE CORRECT NOW !!"
        bg_color = (0, 0, 160)
    elif consecutive_bad_seconds >= 3.0:
        msg      = "! Neck strain warning — adjust your posture !"
        bg_color = (0, 60, 180)
    else:
        msg      = "Sit up straight!"
        bg_color = (20, 100, 200)

    (tw, th), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.60, 2)
    tx = max(10, (w - tw) // 2)

    cv2.rectangle(frame, (tx - 10, 8), (tx + tw + 10, 40), bg_color, -1)
    _text(frame, msg, tx, 32, scale=0.60, color=WHITE, thickness=2)


def draw_calibration_prompt(frame):
    """
    Centred prompt shown until the user performs their first calibration.
    """
    h, w = frame.shape[:2]

    lines = [
        ("Sit in your correct posture, then press [C] to calibrate", 0.52, YELLOW, 1),
        ("Calibration personalises detection to your body",           0.42, WHITE,  1),
    ]

    # Measure the widest line to size the background box
    widths = [cv2.getTextSize(l[0], cv2.FONT_HERSHEY_SIMPLEX, l[1], l[3])[0][0]
              for l in lines]
    max_w = max(widths)

    cx  = (w - max_w) // 2
    cy  = h // 2 - 20
    pad = 14

    _semi_rect(frame, cx - pad, cy - 28, cx + max_w + pad, cy + 46)

    _text(frame, lines[0][0], cx, cy,       scale=lines[0][1], color=lines[0][2])
    _text(frame, lines[1][0], cx, cy + 26,  scale=lines[1][1], color=lines[1][2])


def draw_no_pose(frame):
    """Shown when MediaPipe cannot detect any person in the frame."""
    h, w = frame.shape[:2]
    msg = "No pose detected — ensure your upper body is fully visible"
    (tw, _), _ = cv2.getTextSize(msg, cv2.FONT_HERSHEY_SIMPLEX, 0.50, 1)
    tx = (w - tw) // 2
    _semi_rect(frame, tx - 10, h - 38, tx + tw + 10, h - 10)
    _text(frame, msg, tx, h - 18, scale=0.50, color=YELLOW)


# ---------------------------------------------------------------------------
# Master compositor
# ---------------------------------------------------------------------------

def draw_ui(frame, landmarks, result, score, stats, calibrated, fps,
            consecutive_bad_seconds):
    """
    Compose all overlay elements onto the frame in the correct Z-order.
    Call once per frame from main.py after posture analysis is complete.

    Returns the annotated frame (in-place modification + return for clarity).
    """
    # 1. Custom coloured posture skeleton
    draw_skeleton(frame, landmarks, result.is_good)

    # 2. Top-left: info panel
    draw_status_panel(frame, stats, calibrated, fps)

    # 3. Top-right: score gauge
    draw_score(frame, score)

    # 4. Top-centre: blinking alert banner (only when bad posture)
    draw_alerts(frame, result, consecutive_bad_seconds)

    # 5. Bottom-left: posture status label + metric values
    draw_posture_status(frame, result)

    # 6. Centre: calibration prompt (only when not yet calibrated)
    if not calibrated:
        draw_calibration_prompt(frame)

    return frame
