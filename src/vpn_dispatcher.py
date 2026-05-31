"""
VPNDispatcher — routes connect/disconnect to the correct protocol manager.
Presents the same signal interface as OpenVPNProtocol so MainWindow and
AutoConnectManager need no special-casing per protocol.
"""
from typing import Optional

from PyQt6.QtCore import QObject, pyqtSignal

from .config import AppConfig
from .models import SavedVPN
from .vpn_protocols.base import BaseVPNManager, ConnectionState
from .vpn_protocols.openvpn import OpenVPNProtocol
from .vpn_protocols.wireguard import WireGuardProtocol
from .vpn_protocols.windows_vpn import WindowsVPNProtocol
from .vpn_protocols.shadowsocks import ShadowsocksProtocol
from .vpn_protocols.v2ray import V2RayProtocol


class VPNDispatcher(QObject):
    """
    Single entry point for all VPN protocols.
    Signals are identical to BaseVPNManager so the rest of the UI/auto-connect
    code doesn't need to know which protocol is active.
    """

    state_changed  = pyqtSignal(str)
    log_message    = pyqtSignal(str)
    connected      = pyqtSignal(str)
    disconnected   = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, config: AppConfig):
        super().__init__()
        self._config = config
        self._managers: dict[str, BaseVPNManager] = {}
        self._active: Optional[BaseVPNManager] = None

    # ── public ────────────────────────────────────────────────────────────

    @property
    def state(self) -> ConnectionState:
        if self._active:
            return self._active.state
        return ConnectionState.DISCONNECTED

    @property
    def current_server_ip(self) -> str:
        return self._active.current_server_ip if self._active else ""

    def is_connected(self) -> bool:
        return self.state == ConnectionState.CONNECTED

    def connect_vpn(self, vpn: SavedVPN) -> None:
        manager = self._get_manager(vpn.protocol)
        if self._active and self._active is not manager:
            # disconnect the previously active protocol first
            try:
                self._active.disconnect()
            except Exception:
                pass
            self._detach(self._active)

        if self._active is not manager:
            self._attach(manager)
        self._active = manager
        manager.connect_vpn(vpn)

    def disconnect(self) -> None:
        if self._active:
            self._active.disconnect()

    def refresh_paths(self) -> None:
        """Call after saving Settings so new exe paths take effect."""
        self._managers.clear()
        self._active = None

    # ── manager factory ───────────────────────────────────────────────────

    def _get_manager(self, protocol: str) -> BaseVPNManager:
        if protocol not in self._managers:
            self._managers[protocol] = self._create_manager(protocol)
        return self._managers[protocol]

    def _create_manager(self, protocol: str) -> BaseVPNManager:
        c = self._config
        if protocol == "openvpn":
            return OpenVPNProtocol(c.openvpn_path)
        if protocol == "wireguard":
            return WireGuardProtocol(c.wireguard_path)
        if protocol == "windows":
            return WindowsVPNProtocol()
        if protocol == "shadowsocks":
            return ShadowsocksProtocol(c.sslocal_path)
        if protocol == "v2ray":
            return V2RayProtocol(c.v2ray_path, "V2Ray")
        if protocol == "xray":
            return V2RayProtocol(c.xray_path, "Xray")
        # fallback
        return OpenVPNProtocol(c.openvpn_path)

    # ── signal relay ──────────────────────────────────────────────────────

    def _attach(self, manager: BaseVPNManager) -> None:
        manager.state_changed.connect(self.state_changed)
        manager.log_message.connect(self.log_message)
        manager.connected.connect(self.connected)
        manager.disconnected.connect(self.disconnected)
        manager.error_occurred.connect(self.error_occurred)

    def _detach(self, manager: BaseVPNManager) -> None:
        try:
            manager.state_changed.disconnect(self.state_changed)
            manager.log_message.disconnect(self.log_message)
            manager.connected.disconnect(self.connected)
            manager.disconnected.disconnect(self.disconnected)
            manager.error_occurred.disconnect(self.error_occurred)
        except RuntimeError:
            pass
