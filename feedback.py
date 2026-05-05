"""
feedback.py — Progressive audio alert system (simulates wearable vibration)

Three intensity levels triggered by how long bad posture has persisted:
  Level 1 (>= 1 s bad):  soft single beep    — "heads up"
  Level 2 (>= 3 s bad):  medium double beep  — "please correct"
  Level 3 (>= 6 s bad):  loud triple beep    — "critical alert"

Thresholds are in real seconds (not frames) so timing is consistent across
hardware running at different FPS.

All beeps run on a daemon thread so the camera loop never blocks.
A 2-second cooldown prevents beep spam.

Audio backend:
  Windows → winsound.Beep()   (built-in, no extra install)
  Linux / Mac → pygame.mixer  (generates a sine-wave tone)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HARDWARE HOOK — Vibration Motor Integration (Future Phase)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Inside _beep_thread_fn(), after the audio section, add one of:

  # Option A: Arduino over USB serial
  # import serial
  # port = serial.Serial('COM3', 9600)
  # port.write(f'VIBRATE:{intensity}\n'.encode())

  # Option B: Raspberry Pi GPIO
  # import RPi.GPIO as GPIO
  # GPIO.output(MOTOR_PIN, GPIO.HIGH)
  # time.sleep(duration_ms / 1000)
  # GPIO.output(MOTOR_PIN, GPIO.LOW)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import time
import threading
import platform

_IS_WINDOWS = platform.system() == 'Windows'

# Module-level flags — defined unconditionally so any reference is safe
_AUDIO_AVAILABLE  = False
_PYGAME_AVAILABLE = False

# Attempt to import the appropriate audio backend
if _IS_WINDOWS:
    import winsound
    _AUDIO_AVAILABLE = True
else:
    try:
        import pygame
        try:
            # mixer.init can raise pygame.error on headless / no-audio systems
            pygame.mixer.init(frequency=44100, size=-16, channels=1, buffer=512)
            _AUDIO_AVAILABLE  = True
            _PYGAME_AVAILABLE = True
        except Exception:
            # Audio device unavailable — fall back to ASCII bell
            pass
    except ImportError:
        # pygame not installed — fall back to ASCII bell
        pass


class FeedbackSystem:
    # Time-based thresholds (seconds of continuous bad posture)
    # Independent of FPS, so behaviour is consistent on any hardware.
    LEVEL_1_SECONDS = 1.0   # low beep
    LEVEL_2_SECONDS = 3.0   # medium beep
    LEVEL_3_SECONDS = 6.0   # high beep

    # Minimum seconds between any two beep triggers
    BEEP_COOLDOWN = 2.0

    def __init__(self):
        self._last_beep_time = 0.0
        self._beeping        = False   # True while a beep thread is active

    # ------------------------------------------------------------------
    # Public interface — called once per frame from main.py
    # ------------------------------------------------------------------

    def update(self, consecutive_bad_seconds):
        """
        Decide whether to trigger audio feedback based on how long bad posture
        has persisted (in real seconds). No-ops if posture is currently good.
        """
        if consecutive_bad_seconds <= 0:
            return

        now = time.time()
        # Enforce cooldown and prevent overlapping threads
        if now - self._last_beep_time < self.BEEP_COOLDOWN:
            return
        if self._beeping:
            return

        # Select intensity by longest threshold exceeded
        if consecutive_bad_seconds >= self.LEVEL_3_SECONDS:
            self._play_beep('high')
        elif consecutive_bad_seconds >= self.LEVEL_2_SECONDS:
            self._play_beep('medium')
        elif consecutive_bad_seconds >= self.LEVEL_1_SECONDS:
            self._play_beep('low')

    # ------------------------------------------------------------------
    # Internal — audio triggering
    # ------------------------------------------------------------------

    # Beep parameters: intensity → (frequency_hz, duration_ms, num_repeats)
    _BEEP_PARAMS = {
        'low':    (600,  150, 1),
        'medium': (900,  200, 2),
        'high':   (1200, 300, 3),
    }

    def _play_beep(self, intensity):
        """Launch a daemon thread to play the beep (non-blocking)."""
        freq, duration_ms, repeats = self._BEEP_PARAMS[intensity]
        self._last_beep_time = time.time()
        self._beeping = True

        t = threading.Thread(
            target=self._beep_thread_fn,
            args=(freq, duration_ms, repeats),
            daemon=True,  # thread dies automatically when main exits
        )
        t.start()

    def _beep_thread_fn(self, freq, duration_ms, repeats):
        """
        Runs on a daemon thread.
        Plays the requested tone (repeats) times, then clears the busy flag.
        """
        try:
            for _ in range(repeats):
                if _IS_WINDOWS:
                    # Windows built-in — synchronous, no extra library
                    winsound.Beep(freq, duration_ms)
                elif _AUDIO_AVAILABLE and _PYGAME_AVAILABLE:
                    self._pygame_beep(freq, duration_ms)
                else:
                    # Last resort: ASCII bell character
                    print('\a', end='', flush=True)
                    time.sleep(duration_ms / 1000.0)

                # ── HARDWARE HOOK ──────────────────────────────────────
                # Add serial / GPIO vibration call here (future phase).
                # See module docstring for code templates.
                # ──────────────────────────────────────────────────────

                time.sleep(0.05)   # brief silence between repeats
        finally:
            self._beeping = False

    @staticmethod
    def _pygame_beep(freq, duration_ms):
        """Generate and play a pure sine-wave tone via pygame (Linux/Mac)."""
        import numpy as np
        sample_rate = 44100
        n_samples   = int(sample_rate * duration_ms / 1000)
        t    = np.linspace(0, duration_ms / 1000.0, n_samples, endpoint=False)
        wave = (np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
        sound = pygame.sndarray.make_sound(wave)
        sound.play()
        pygame.time.wait(duration_ms)
