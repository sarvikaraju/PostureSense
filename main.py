'''PostureSense — Real-Time Posture Correction System
Final Year Engineering Project (IDP)

Author: PostureSense Team
Description:
    Captures webcam video, detects upper-body landmarks via MediaPipe Pose,
    analyses neck inclination, shoulder alignment, and forward head posture,
    maintains a real-time posture score, and provides escalating audio alerts
    when bad posture is sustained.

Controls:
  [C] — Calibrate with your current (correct) posture
  [R] — Reset session score and time counters
  [S] — Manually save calibration to calibration.json
  [Q] / [Esc] — Quit

Module architecture:
  pose_detector.py   → MediaPipe Pose wrapper
  angle_calculator.py → Geometric angle computations
  posture_analyzer.py → Threshold-based classification
  calibration.py      → Personal baseline (save/load JSON)
  scoring_system.py   → 0–100 real-time score
  feedback.py         → Threaded audio alerts (hardware hook inside)
  ui_overlay.py       → All on-screen drawing

Hardware hook (future):
  See feedback.py → FeedbackSystem._beep_thread_fn() for the marked
  insertion point to add vibration motor commands.'''

import cv2
import time
import serial

arduino = serial.Serial('COM7', 9600)
time.sleep(2)

last_state = ""

from pose_detector    import PoseDetector
from posture_analyzer import analyze_posture
from calibration      import CalibrationSystem
from scoring_system   import ScoringSystem
from feedback         import FeedbackSystem
from ui_overlay       import draw_ui, draw_calibration_prompt, draw_no_pose

# Path to the JSON file that persists calibration between sessions
CALIBRATION_FILE = 'calibration.json'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_banner():
    print("=" * 55)
    print("  PostureSense — Real-Time Posture Correction System")
    print("=" * 55)
    print("  Controls:")
    print("    [C]   Calibrate with current posture")
    print("    [R]   Reset score / counters")
    print("    [S]   Save calibration")
    print("    [Q]   Quit")
    print("=" * 55)


def _print_summary(stats):
    """Print a session summary to the console when the user quits."""
    g_m, g_s = divmod(int(stats['good_time']), 60)
    b_m, b_s = divmod(int(stats['bad_time']),  60)
    print("\n--- Session Summary ---")
    print(f"  Final score       : {stats['score']} / 100")
    print(f"  Good posture time : {g_m:02d}:{g_s:02d}")
    print(f"  Bad posture time  : {b_m:02d}:{b_s:02d}")
    print(f"  Bad posture events: {stats['bad_events']}")
    print("-" * 23)


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    _print_banner()

    # --- Open webcam ---
    # Index 0 = default system camera; change to 1 for an external USB webcam
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("ERROR: Cannot open webcam. Check that a camera is connected and not "
              "in use by another application.")
        return

    # Request 1280×720 for a larger overlay canvas (falls back to native if unsupported)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    # --- Initialise all modules ---
    detector    = PoseDetector()
    calibration = CalibrationSystem()
    scorer      = ScoringSystem()
    feedback    = FeedbackSystem()

    # Auto-load any saved calibration from a previous session
    if calibration.load(CALIBRATION_FILE):
        print(f"Calibration loaded from '{CALIBRATION_FILE}'.")
    else:
        print("No saved calibration found. Press [C] once you are seated correctly.")

    # Track wall-clock time for delta-time calculations
    prev_time = time.time()

    # Keep a reference to the last detected landmarks so the calibration key
    # can act even if the user presses [C] slightly after a detection frame
    last_landmarks = None

    # Camera-loss tolerance: bail out cleanly if too many frames fail in a row
    consecutive_failures = 0
    MAX_CONSECUTIVE_FAILURES = 30

    print("PostureSense is running. Press [Q] to quit.\n")

    while True:
        # --- Capture frame ---
        ret, frame = cap.read()
        if not ret:
            consecutive_failures += 1
            # Still poll for keys so the user can quit during an outage
            key = cv2.waitKey(50) & 0xFF
            if key in (ord('q'), 27):
                print("Quit requested.")
                break
            if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                print("ERROR: Lost camera feed — too many consecutive failures. Exiting.")
                break
            continue

        # Camera came back (or has been working) — reset the failure counter
        consecutive_failures = 0

        # Mirror horizontally so the view is intuitive (selfie-style)
        frame = cv2.flip(frame, 1)

        # --- Delta time (seconds since last frame) ---
        now       = time.time()
        delta     = now - prev_time
        delta     = min(delta, 0.10)   # cap at 100 ms to avoid score jumps after lag
        prev_time = now
        fps       = 1.0 / delta if delta > 0 else 30.0

        # --- Pose detection ---
        # Returns annotated frame and a landmarks dict (or None if no person found)
        frame, landmarks = detector.detect_pose(frame)

        if landmarks:
            last_landmarks = landmarks   # cache for the calibration key handler

            # --- Posture analysis ---
            # Compares current angles against thresholds and (if calibrated)
            # against the personal baseline stored in calibration_data
            result = analyze_posture(landmarks, calibration.get_baseline())

            # --- Score and feedback ---
            # Both updated using real seconds (not frame counts) so behaviour
            # is consistent across slower / faster hardware
            scorer.update(result.is_good, delta)
            stats = scorer.get_stats()
            feedback.update(stats['consecutive_bad_seconds'])

            # --- Bluetooth Motor Control ---

            bad_time = stats['consecutive_bad_seconds']

            # GOOD POSTURE
            if result.is_good:
                if last_state != "GOOD":
                    arduino.write(b'G')
                    print("GOOD POSTURE")
                    last_state = "GOOD"

            # SLIGHT BAD POSTURE
            elif bad_time >= 3 and bad_time < 8:
                if last_state != "WARNING":
                    arduino.write(b'W')
                    print("WARNING BUZZ")
                    last_state = "WARNING"

            # SEVERE BAD POSTURE
            elif bad_time >= 8:
                if last_state != "BAD":
                    arduino.write(b'B')
                    print("CONTINUOUS BUZZ")
                    last_state = "BAD"

            # --- Draw all UI elements onto the frame ---
            draw_ui(
                frame                  = frame,
                landmarks              = landmarks,
                result                 = result,
                score                  = scorer.get_score(),
                stats                  = stats,
                calibrated             = calibration.is_calibrated(),
                fps                    = fps,
                consecutive_bad_seconds = stats['consecutive_bad_seconds'],)

        else:
            # --- No pose detected ---
            draw_no_pose(frame)
            if not calibration.is_calibrated():
                draw_calibration_prompt(frame)

        # --- Display ---
        cv2.imshow('PostureSense — Real-Time Posture Correction', frame)

        # --- Keyboard input (1 ms poll — keeps frame rate high) ---
        key = cv2.waitKey(1) & 0xFF

        if key in (ord('q'), 27):          # [Q] or [Esc] — quit
            print("Quit requested.")
            break

        elif key == ord('c'):              # [C] — calibrate
            if last_landmarks and calibration.calibrate(last_landmarks):
                if calibration.save(CALIBRATION_FILE):
                    print("Calibrated! Your current posture is now the baseline.")
                else:
                    print("Calibrated, but could not write calibration.json (check permissions).")
            else:
                print("Cannot calibrate: no pose detected. Ensure your upper body is visible.")

        elif key == ord('r'):              # [R] — reset score
            scorer.reset()
            print("Score and session counters reset.")

        elif key == ord('s'):              # [S] — save calibration
            if calibration.save(CALIBRATION_FILE):
                print(f"Calibration saved to '{CALIBRATION_FILE}'.")
            else:
                print("Nothing to save — press [C] first to calibrate.")

    # --- Cleanup ---
    cap.release()
    cv2.destroyAllWindows()
    detector.close()

    _print_summary(scorer.get_stats())


if __name__ == '__main__':
    main()
