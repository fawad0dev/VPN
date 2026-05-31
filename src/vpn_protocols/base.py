"""
Shared base class and ConnectionState enum for all VPN protocol managers.
"""
from enum import Enum
from typing import TYPE_CHECKING

from PyQt6.QtCore import QObject, pyqtSignal

if TYPE_CHECKING:
    from ..models import SavedVPN


class ConnectionState(Enum):
    DISCONNECTED  = "disconnected"
    CONNECTING    = "connecting"
    CONNECTED     = "connected"
    DISCONNECTING = "disconnecting"
    ERROR         = "error"


class BaseVPNManager(QObject):
    """Abstract base — all protocol managers must implement connect_vpn / disconnect."""

    state_changed  = pyqtSignal(str)
    log_message    = pyqtSignal(str)
    connected      = pyqtSignal(str)   # emits server IP
    disconnected   = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._state = ConnectionState.DISCONNECTED
        self._current_server_ip: str = ""

    # ── public interface ───────────────────────────────────────────────────

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def current_server_ip(self) -> str:
        return self._current_server_ip

    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED

    def connect_vpn(self, vpn: "SavedVPN") -> None:
        raise NotImplementedError

    def disconnect(self) -> None:
        raise NotImplementedError

    # ── helpers ───────────────────────────────────────────────────────────

    def _set_state(self, state: ConnectionState):
        self._state = state
        self.state_changed.emit(state.value)
