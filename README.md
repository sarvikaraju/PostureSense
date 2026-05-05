# PostureSense — Real-Time Posture Correction System

A final year engineering project that uses a standard webcam and MediaPipe Pose to detect, classify, and correct posture in real time — simulating the software module of a smart wearable device.

---

## Demo

The system overlays a colour-coded skeleton on the live webcam feed, displays a real-time posture score, and plays progressive audio alerts when bad posture is detected.

| Good Posture | Bad Posture |
|---|---|
| Green skeleton + "GOOD POSTURE" | Red skeleton + "BAD POSTURE" + beep escalation |

---

## Features

- **Real-time pose detection** — MediaPipe Pose detects 33 body landmarks at ~30 FPS
- **Posture analysis** — calculates neck inclination, shoulder tilt, and forward head position
- **Personalised calibration** — press `C` to lock in *your* correct sitting posture as the baseline; persists across sessions via `calibration.json`
- **Posture classification** — Good / Warning / Bad with per-issue breakdown on screen
- **Real-time score (0–100)** — recovers slowly on good posture, penalises bad posture events
- **Progressive audio feedback** — beep intensity escalates at 1 s, 3 s, and 6 s of continuous bad posture (simulates wearable vibration motor)
- **Skeleton overlay** — green when good, red when bad; panels show FPS, score, calibration status, and issue list

---

## Module Architecture

```
PostureSense/
├── main.py               # Entry point — camera loop, key handlers
├── pose_detector.py      # MediaPipe Pose wrapper → detect_pose()
├── angle_calculator.py   # Neck / shoulder / FHP geometry
├── posture_analyzer.py   # Threshold logic → PostureResult namedtuple
├── calibration.py        # CalibrationSystem — calibrate(), JSON save/load
├── scoring_system.py     # ScoringSystem — real-time 0–100 score
├── feedback.py           # FeedbackSystem — threaded audio, 3 intensity levels
├── ui_overlay.py         # OpenCV drawing — skeleton, panels, alerts
└── requirements.txt
```

---

## Key Landmarks (MediaPipe Pose indices)

| Landmark | Index |
|---|---|
| Nose | 0 |
| Left / Right ear | 7 / 8 |
| Left / Right shoulder | 11 / 12 |
| Left / Right hip | 23 / 24 |

---

## Posture Thresholds

| Metric | Good Threshold |
|---|---|
| Neck inclination | < 30° from vertical |
| Shoulder tilt | < 10° from horizontal |
| Forward head position | ≤ 0.06 normalised units from calibration baseline |

---

## Installation

**Requirements:** Python 3.10+, a webcam

```bash
git clone https://github.com/arya-shetty/PostureSense.git
cd PostureSense
pip install -r requirements.txt
python main.py
```

> **Note:** `mediapipe==0.10.14` and `opencv-python==4.10.0.84` are pinned in `requirements.txt`
> because MediaPipe 0.10.21+ removed the legacy `mp.solutions` API, and OpenCV 4.11+ requires NumPy ≥ 2
> which conflicts with that MediaPipe version.

---

## Controls

| Key | Action |
|---|---|
| `C` | Calibrate — records your current posture as the baseline |
| `R` | Reset score and session counters |
| `S` | Save calibration to `calibration.json` |
| `Q` | Quit and show session summary |

---

## How It Works

### 1. Pose Detection
Each webcam frame is converted to RGB and passed to `mediapipe.solutions.pose.Pose`. The 33 detected landmarks are extracted as normalised (x, y, z, visibility) tuples.

### 2. Angle Calculation
Three metrics are computed from the landmarks:

- **Neck inclination** — `atan2(|Δx|, |Δy|)` between nose and shoulder midpoint; measures forward head tilt
- **Shoulder tilt** — `atan2(|Δy|, |Δx|)` between left and right shoulders; measures asymmetric slouching
- **Forward head position (FHP)** — horizontal offset of the ear midpoint relative to the shoulder midpoint (only computed when ear landmarks have visibility ≥ 0.5)

### 3. Calibration
Pressing `C` records the current values of all three metrics as the personal baseline, stored in `calibration.json`. Future frames compare against this baseline using an FHP tolerance of ±0.06 normalised units.

### 4. Scoring
- Start: **100**
- Each second of bad posture: **−1.5**
- Bad posture event (good→bad transition): **−5**
- Each second of good posture: **+0.5** (capped at 100)

### 5. Feedback
| Duration of bad posture | Audio alert |
|---|---|
| ≥ 1 second | Soft beep (600 Hz, 150 ms) |
| ≥ 3 seconds | Double beep (900 Hz, 200 ms × 2) |
| ≥ 6 seconds | Triple beep (1200 Hz, 300 ms × 3) |

A 2-second cooldown prevents spam. On Windows, `winsound.Beep` is used. On Linux/macOS, `pygame.mixer` generates a sine-wave tone.

---

## Hardware Integration (Future Phase)

The vibration motor hook is already marked in `feedback.py → FeedbackSystem._play_beep()`:

```python
# HARDWARE: trigger vibration motor here
# serial_port.write(b'VIBRATE:<intensity>\n')   # Arduino over USB
# GPIO.output(MOTOR_PIN, GPIO.HIGH)              # Raspberry Pi GPIO
```

When the hardware phase is implemented, add the serial/GPIO call at that point — no other code changes needed.

---

## Tech Stack

| Library | Version | Purpose |
|---|---|---|
| opencv-python | 4.10.0.84 | Video capture + UI rendering |
| mediapipe | 0.10.14 | Pose landmark detection |
| numpy | 1.26.x | Angle and distance math |
| pygame | 2.6.x | Cross-platform audio (Linux/macOS) |

---

## Project Structure Notes

- `calibration.json` — auto-created on first calibration; delete to reset to factory defaults
- All landmark coordinates stay in MediaPipe's normalised 0.0–1.0 space for resolution-independent thresholds
- Audio runs on daemon threads so the 30 FPS camera loop is never blocked

---

*Final Year Engineering Project — PostureSense: A Smart Wearable Device for Real-Time Posture Correction*
