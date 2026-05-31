# -*- coding: utf-8 -*-
"""
Real-time network statistics monitor.
Tracks upload/download rates and session totals using psutil.
"""
import time
from dataclasses import dataclass, field
from typing import Optional

import psutil
from PyQt6.QtCore import QObject, QTimer, pyqtSignal


@dataclass
class _Snapshot:
    bytes_sent:    int
    bytes_recv:    int
    packets_sent:  int
    packets_recv:  int
    timestamp:     float = field(default_factory=time.monotonic)


def _take() -> _Snapshot:
    c = psutil.net_io_counters()
    return _Snapshot(c.bytes_sent, c.bytes_recv, c.packets_sent, c.packets_recv)


def fmt_bytes(n: float) -> str:
    """Format raw byte count to human-readable string (B / KB / MB / GB)."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


def fmt_rate(n: float) -> str:
    """Format bytes-per-second as e.g. '12.4 KB/s'."""
    return fmt_bytes(n) + "/s"


class NetworkStatsMonitor(QObject):
    """
    Polls psutil every `interval_ms` while running.

    Emits `stats_updated` with a dict:
        up_rate      – upload speed   (bytes/s)
        down_rate    – download speed (bytes/s)
        total_up     – total uploaded   since start (bytes)
        total_down   – total downloaded since start (bytes)
        packets_up   – total packets sent     since start
        packets_down – total packets received since start
        elapsed      – seconds since start
    """

    stats_updated = pyqtSignal(dict)

    def __init__(self, interval_ms: int = 1000, parent=None):
        super().__init__(parent)
        self._interval = interval_ms
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._poll)
        self._baseline: Optional[_Snapshot] = None
        self._prev:     Optional[_Snapshot] = None
        self._start_ts: float = 0.0

    # ── public ────────────────────────────────────────────────────────────

    def start(self):
        snap = _take()
        self._baseline = snap
        self._prev = snap
        self._start_ts = time.monotonic()
        self._timer.start(self._interval)

    def stop(self):
        self._timer.stop()
        self._baseline = None
        self._prev = None

    @property
    def is_running(self) -> bool:
        return self._timer.isActive()

    # ── internal ──────────────────────────────────────────────────────────

    def _poll(self):
        if self._prev is None or self._baseline is None:
            return

        now = _take()
        dt = now.timestamp - self._prev.timestamp
        if dt <= 0:
            return

        up_rate   = max(0, now.bytes_sent - self._prev.bytes_sent) / dt
        down_rate = max(0, now.bytes_recv - self._prev.bytes_recv) / dt

        total_up   = max(0, now.bytes_sent   - self._baseline.bytes_sent)
        total_down = max(0, now.bytes_recv   - self._baseline.bytes_recv)
        pkts_up    = max(0, now.packets_sent  - self._baseline.packets_sent)
        pkts_down  = max(0, now.packets_recv  - self._baseline.packets_recv)

        self._prev = now

        self.stats_updated.emit({
            "up_rate":      up_rate,
            "down_rate":    down_rate,
            "total_up":     total_up,
            "total_down":   total_down,
            "packets_up":   pkts_up,
            "packets_down": pkts_down,
            "elapsed":      now.timestamp - self._start_ts,
        })
