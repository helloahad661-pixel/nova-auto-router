"""Rolling health tracker: success rate per provider over a recent window."""
import time


class Health:
    def __init__(self, window=20):
        self.window = window
        self._events = {}  # provider -> [True/False, ...]

    def report(self, provider, ok):
        ev = self._events.setdefault(provider, [])
        ev.append(bool(ok))
        del ev[:-self.window]

    def score(self, provider):
        ev = self._events.get(provider, [])
        if not ev:
            return 1.0  # unknown providers start trusted
        return sum(ev) / len(ev)
