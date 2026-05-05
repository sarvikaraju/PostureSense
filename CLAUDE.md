# PostureSense — IDP Software Prototype

## Project Overview
Real-time posture correction system using webcam + MediaPipe Pose.
Final year engineering project. Hardware integration (vibration motors) is a future phase.

## Stack
- Python 3.10+
- OpenCV (video capture + UI rendering)
- MediaPipe Pose (landmark detection)
- NumPy (angle/distance math)
- pygame / winsound (audio feedback — winsound on Windows, pygame on Linux/Mac)

## How to Run
```
pip install -r requirements.txt
python main.py
```

## Controls
| Key | Action                          |
|-----|---------------------------------|
| C   | Calibrate with current posture  |
| R   | Reset posture score             |
| S   | Save calibration to file        |
| Q   | Quit                            |

## Module Map
| File                | Responsibility                                        |
|---------------------|-------------------------------------------------------|
| main.py             | Entry point, camera loop, key handlers                |
| pose_detector.py    | MediaPipe Pose wrapper — detect_pose()                |
| angle_calculator.py | Neck/shoulder/FHP geometry calculations               |
| posture_analyzer.py | Threshold logic — returns PostureResult namedtuple    |
| calibration.py      | CalibrationSystem — calibrate(), JSON save/load       |
| scoring_system.py   | ScoringSystem — real-time 0–100 score                 |
| feedback.py         | FeedbackSystem — threaded beeps, progressive intensity|
| ui_overlay.py       | Frame drawing — skeleton, panels, score, alerts       |

## Key Landmarks (MediaPipe indices)
| Name           | Index |
|----------------|-------|
| Nose           | 0     |
| Left ear       | 7     |
| Right ear      | 8     |
| Left shoulder  | 11    |
| Right shoulder | 12    |
| Left hip       | 23    |
| Right hip      | 24    |

## Posture Thresholds
| Metric             | Good Threshold     |
|--------------------|--------------------|
| Neck inclination   | < 30 degrees       |
| Shoulder tilt      | < 10 degrees       |
| Forward head pos.  | ± 0.06 (normalized)|

## Hardware Hook (Future Phase)
In `feedback.py` → `FeedbackSystem._play_beep()`, after the audio call, add:
```python
# HARDWARE: trigger vibration motor here
# serial_port.write(b'VIBRATE:<intensity>\n')   # Arduino over USB
# GPIO.output(MOTOR_PIN, GPIO.HIGH); time.sleep(duration_s)  # RPi GPIO
```

## Calibration File
`calibration.json` is auto-created on first calibration and auto-loaded on startup.
Delete it to reset to factory defaults.
