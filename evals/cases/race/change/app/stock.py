import threading


class Stock:
    """Units left for one product. reserve() is called from many worker threads at once."""

    def __init__(self, units):
        self.units = units
        self._lock = threading.Lock()

    def reserve(self, n):
        """Take n units; False when fewer than n are left. Stock must never go negative."""
        if self.units >= n:
            self.units -= n
            return True
        return False
