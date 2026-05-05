"""
scoring_system.py — Real-time posture score (0–100)

Score dynamics:
  • Starts at 100.
  • Drops 1.5 points per second of bad posture.
  • Gains 0.5 points per second of good posture (capped at 100).
  • Loses an extra 5 points the moment posture transitions from good → bad
    (this is the "bad event" penalty — it registers one bad_event count too).
  • Floor is 0.

This design rewards sustained good posture and penalises repeated lapses
more than a single long bad stretch.
"""


class ScoringSystem:
    def __init__(self):
        self.reset()

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def reset(self):
        """Reset all counters and return score to 100."""
        self._score               = 100.0

        # Cumulative session time (seconds)
        self.good_seconds         = 0.0
        self.bad_seconds          = 0.0

        # Number of times posture switched from good → bad
        self.bad_events           = 0

        # Continuous-bad streak — both representations exposed for callers
        self.consecutive_bad_frames  = 0     # frames since last good frame
        self.consecutive_bad_seconds = 0.0   # real seconds since last good frame

        # Track the previous frame's posture state to detect transitions
        self._prev_was_bad        = False

    # ------------------------------------------------------------------
    # Per-frame update
    # ------------------------------------------------------------------

    def update(self, is_good, delta_time):
        """
        Update score and all counters for one camera frame.

        is_good    : bool  — True if current frame's posture is acceptable
        delta_time : float — seconds elapsed since the previous frame
        """
        if is_good:
            self.good_seconds            += delta_time
            self.consecutive_bad_frames   = 0
            self.consecutive_bad_seconds  = 0.0
            # Slowly recover score; cap at 100
            self._score = min(100.0, self._score + 0.5 * delta_time)
            self._prev_was_bad = False
        else:
            self.bad_seconds             += delta_time
            self.consecutive_bad_frames  += 1
            self.consecutive_bad_seconds += delta_time

            # Extra one-time penalty on the first bad frame of a new bad streak
            if not self._prev_was_bad:
                self._score = max(0.0, self._score - 5.0)
                self.bad_events += 1

            # Continuous drain while bad posture persists
            self._score = max(0.0, self._score - 1.5 * delta_time)
            self._prev_was_bad = True

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_score(self):
        """Return the current posture score as an integer in [0, 100]."""
        return int(round(self._score))

    def get_stats(self):
        """
        Return a dict of all tracked statistics.
        Keys:
          score, good_time, bad_time, bad_events,
          consecutive_bad_frames, consecutive_bad_seconds
        """
        return {
            'score':                   self.get_score(),
            'good_time':               self.good_seconds,
            'bad_time':                self.bad_seconds,
            'bad_events':              self.bad_events,
            'consecutive_bad_frames':  self.consecutive_bad_frames,
            'consecutive_bad_seconds': self.consecutive_bad_seconds,
        }
