"""
WireGuard protocol manager.
Uses wireguard.exe /installtunnel and /uninstalltunnel (Windows).
Requires Administrator privileges.
"""
import os
import re
import subprocess
import tempfile
import threading
import time
from typing import Optional

from ..models import SavedVPN
from .base import BaseVPNManager, ConnectionState


def _safe_tunnel_name(name: str) -> str:
    """WireGuard tunnel names must be short alphanumeric identifiers."""
    clean = re.sub(r'[^\w]', '_', name)[:32].strip('_') or "wg_tunnel"
    return clean


class WireGuardProtocol(BaseVPNManager):
    """
    WireGuard connection via wireguard.exe CLI.
    Config format: standard WireGuard .conf (INI) file stored in vpn.ovpn_config.
    """

    def __init__(self, wireguard_path: str = "wireguard"):
        super().__init__()
        self.wireguard_path = wireguard_path
        self._tunnel_name: str = ""
        self._config_file: Optional[str] = None
        self._stop_flag = False
        self._thread: Optional[threading.Thread] = None

    # ── public ────────────────────────────────────────────────────────────

    def connect_vpn(self, vpn: SavedVPN) -> None:
        if self._state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            self.disconnect()
            time.sleep(2)

        self._stop_flag = False
        self._current_server_ip = vpn.ip
        self._tunnel_name = _safe_tunnel_name(vpn.name)
        self._set_state(ConnectionState.CONNECTING)

        self._thread = threading.Thread(
            target=self._connect_worker,
            args=(vpn.ovpn_config,),
            daemon=True,
        )
        self._thread.start()

    def disconnect(self):
        self._stop_flag = True
        self._set_state(ConnectionState.DISCONNECTING)
        self._thread = threading.Thread(target=self._disconnect_worker, daemon=True)
        self._thread.start()

    # ── workers ───────────────────────────────────────────────────────────

    def _connect_worker(self, wg_config: str):
        # Write config to a named temp file (WireGuard uses the filename as tunnel name)
        tmp_dir = tempfile.gettempdir()
        self._config_file = os.path.join(tmp_dir, f"{self._tunnel_name}.conf")
        try:
            with open(self._config_file, 'w') as fh:
                fh.write(wg_config)

            self.log_message.emit(f"[WireGuard] Installing tunnel '{self._tunnel_name}'…")
            self.log_message.emit(f"[WireGuard] Config: {self._config_file}")

            # Check executable exists
            if not self._exe_exists():
                self._set_state(ConnectionState.ERROR)
                self.error_occurred.emit(
                    f"WireGuard executable not found: '{self.wireguard_path}'\n\n"
                    "Download from https://www.wireguard.com/install/\n"
                    "Then set the path in Settings → Protocols."
                )
                return

            # Install the tunnel service
            result = self._run_cmd([self.wireguard_path, '/installtunnel', self._config_file])
            if result.returncode != 0:
                err = (result.stdout + result.stderr).strip()
                if not err:
                    err = f"wireguard.exe /installtunnel exited with code {result.returncode}"
                self.log_message.emit(f"[WireGuard] Error: {err}")
                self._set_state(ConnectionState.ERROR)
                self.error_occurred.emit(
                    f"WireGuard tunnel install failed.\n\n{err}\n\n"
                    "Note: WireGuard requires Administrator privileges."
                )
                return

            self.log_message.emit("[WireGuard] Tunnel service installed, waiting for connection…")

            # Poll for the service to reach RUNNING state
            service_name = f"WireGuardTunnel${self._tunnel_name}"
            deadline = time.time() + 30   # 30-second timeout
            while time.time() < deadline:
                if self._stop_flag:
                    self._do_uninstall()
                    self._set_state(ConnectionState.DISCONNECTED)
                    self.disconnected.emit()
                    return

                status = self._get_service_state(service_name)
                self.log_message.emit(f"[WireGuard] Service state: {status}")

                if status == "RUNNING":
                    self._set_state(ConnectionState.CONNECTED)
                    self.connected.emit(self._current_server_ip)
                    # Monitor for unexpected disconnect
                    self._monitor_connection(service_name)
                    return
                elif status in ("STOPPED", "FAILED"):
                    self._do_uninstall()
                    self._set_state(ConnectionState.ERROR)
                    self.error_occurred.emit(
                        f"WireGuard tunnel service stopped unexpectedly (state: {status}).\n"
                        "Check the WireGuard config and that you are running as Administrator."
                    )
                    return

                time.sleep(1)

            # Timed out
            self._do_uninstall()
            self._set_state(ConnectionState.ERROR)
            self.error_occurred.emit(
                "WireGuard connection timed out waiting for tunnel service to start.\n"
                "Check the WireGuard config and Administrator privileges."
            )

        except Exception as exc:
            self._set_state(ConnectionState.ERROR)
            self.error_occurred.emit(str(exc))
        finally:
            self._cleanup_config()

    def _monitor_connection(self, service_name: str):
        """Keep polling until the service stops or we're asked to disconnect."""
        while not self._stop_flag:
            time.sleep(5)
            status = self._get_service_state(service_name)
            if status not in ("RUNNING", "START_PENDING"):
                self.log_message.emit(f"[WireGuard] Service stopped: {status}")
                self._do_uninstall()
                self._set_state(ConnectionState.DISCONNECTED)
                self.disconnected.emit()
                return

        # Stop was requested
        self._do_uninstall()
        self._set_state(ConnectionState.DISCONNECTED)
        self.disconnected.emit()

    def _disconnect_worker(self):
        self._do_uninstall()
        self._set_state(ConnectionState.DISCONNECTED)
        self.disconnected.emit()

    # ── helpers ───────────────────────────────────────────────────────────

    def _do_uninstall(self):
        if self._tunnel_name:
            self.log_message.emit(f"[WireGuard] Uninstalling tunnel '{self._tunnel_name}'…")
            self._run_cmd([self.wireguard_path, '/uninstalltunnel', self._tunnel_name])

    def _get_service_state(self, service_name: str) -> str:
        try:
            r = subprocess.run(
                ['sc', 'query', service_name],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            out = r.stdout
            m = re.search(r'STATE\s*:\s*\d+\s+(\w+)', out)
            return m.group(1) if m else "UNKNOWN"
        except Exception:
            return "UNKNOWN"

    def _run_cmd(self, cmd) -> subprocess.CompletedProcess:
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        return subprocess.run(
            cmd,
            capture_output=True, text=True,
            creationflags=flags
        )

    def _exe_exists(self) -> bool:
        if os.path.isfile(self.wireguard_path):
            return True
        import shutil
        return shutil.which(self.wireguard_path) is not None

    def _cleanup_config(self):
        if self._config_file and os.path.exists(self._config_file):
            try:
                os.remove(self._config_file)
            except OSError:
                pass
            self._config_file = None
