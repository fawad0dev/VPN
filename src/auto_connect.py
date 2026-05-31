import socket
import time
from typing import List, Optional

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .models import SavedVPN
from .vpn_manager import ConnectionState, OpenVPNManager


class AutoConnectConfig:
    def __init__(self):
        self.enabled: bool = False
        self.strategy: str = "sequential"   # sequential | best_ping | random
        self.connection_timeout: int = 30   # seconds to wait for connect
        self.retry_delay: int = 5           # seconds between retries
        self.max_retries_per_server: int = 2
        self.health_check_interval: int = 30
        self.health_check_host: str = "8.8.8.8"
        self.health_check_port: int = 53
        self.health_check_timeout: int = 5

    def to_dict(self) -> dict:
        return self.__dict__.copy()

    @classmethod
    def from_dict(cls, data: dict) -> 'AutoConnectConfig':
        cfg = cls()
        for k, v in data.items():
            if hasattr(cfg, k):
                setattr(cfg, k, v)
        return cfg


class AutoConnectManager(QObject):
    switching_server = pyqtSignal(str)   # reason string
    status_update = pyqtSignal(str)

    def __init__(self, vpn_manager: OpenVPNManager, config: AutoConnectConfig):
        super().__init__()
        self.vpn_manager = vpn_manager
        self.config = config

        self._vpn_list: List[SavedVPN] = []
        self._current_index: int = 0
        self._retry_count: int = 0
        self._active: bool = False
        self._connecting: bool = False

        self._health_timer: Optional[QTimer] = None
        self._timeout_timer: Optional[QTimer] = None

        vpn_manager.connected.connect(self._on_connected)
        vpn_manager.error_occurred.connect(self._on_error)
        vpn_manager.disconnected.connect(self._on_disconnected)

    # ------------------------------------------------------------------ public

    def start(self, vpn_list: List[SavedVPN], start_index: int = 0):
        if not vpn_list:
            return
        self._vpn_list = self._order_by_strategy(vpn_list, start_index)
        self._current_index = 0
        self._retry_count = 0
        self._active = True
        self._connect_current()

    def stop(self):
        self._active = False
        self._stop_timers()
        self.vpn_manager.disconnect()

    # --------------------------------------------------------------- internals

    def _order_by_strategy(self, vpn_list: List[SavedVPN], start_index: int) -> List[SavedVPN]:
        import random
        if self.config.strategy == "best_ping":
            return sorted(vpn_list, key=lambda v: v.ping or 9999)
        if self.config.strategy == "random":
            lst = vpn_list[:]
            random.shuffle(lst)
            return lst
        # sequential – start from selected index
        return vpn_list[start_index:] + vpn_list[:start_index]

    def _connect_current(self):
        if not self._active or not self._vpn_list:
            return
        vpn = self._vpn_list[self._current_index % len(self._vpn_list)]
        self.status_update.emit(f"Connecting to {vpn.name} ({vpn.ip})…")
        self._connecting = True

        self.vpn_manager.connect_vpn(vpn)

        self._timeout_timer = QTimer(singleShot=True)
        self._timeout_timer.timeout.connect(self._on_timeout)
        self._timeout_timer.start(self.config.connection_timeout * 1000)

    def _on_timeout(self):
        if self._connecting and self._active:
            self.switching_server.emit("Connection timed out")
            self._try_next()

    def _on_connected(self, _ip: str):
        self._connecting = False
        self._stop_timers()
        self._retry_count = 0
        if self._active:
            self._start_health_timer()

    def _on_error(self, error: str):
        if self._active:
            self.switching_server.emit(f"Error: {error}")
            self._try_next()

    def _on_disconnected(self):
        if self._active and not self._connecting:
            self.switching_server.emit("Disconnected unexpectedly")
            self._try_next()

    def _try_next(self):
        if not self._active:
            return
        self._stop_timers()
        self._retry_count += 1
        if self._retry_count < self.config.max_retries_per_server:
            msg = f"Retrying ({self._retry_count}/{self.config.max_retries_per_server})…"
            self.status_update.emit(msg)
            QTimer.singleShot(self.config.retry_delay * 1000, self._connect_current)
        else:
            self._retry_count = 0
            self._current_index = (self._current_index + 1) % len(self._vpn_list)
            self.status_update.emit("Switching to next server…")
            QTimer.singleShot(self.config.retry_delay * 1000, self._connect_current)

    def _start_health_timer(self):
        self._health_timer = QTimer()
        self._health_timer.timeout.connect(self._check_health)
        self._health_timer.start(self.config.health_check_interval * 1000)

    def _check_health(self):
        if not self._active or not self.vpn_manager.is_connected():
            return
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.config.health_check_timeout)
            result = sock.connect_ex(
                (self.config.health_check_host, self.config.health_check_port)
            )
            sock.close()
            if result != 0:
                raise OSError("health check failed")
        except Exception:
            self.switching_server.emit("Health check failed")
            self._stop_timers()
            self._try_next()

    def _stop_timers(self):
        for timer in (self._health_timer, self._timeout_timer):
            if timer:
                timer.stop()
        self._health_timer = None
        self._timeout_timer = None
