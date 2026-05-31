"""
V2Ray / Xray protocol manager.
Runs v2ray.exe (or xray.exe) with a JSON config file.
The JSON config is stored in vpn.ovpn_config.
"""
import os
import subprocess
import tempfile
import threading
import time
from typing import Optional

from ..models import SavedVPN
from .base import BaseVPNManager, ConnectionState


class V2RayProtocol(BaseVPNManager):
    """
    V2Ray / Xray proxy via v2ray.exe run -c config.json
    Config format: V2Ray / Xray JSON (stored in vpn.ovpn_config).
    """

    def __init__(self, v2ray_path: str = "v2ray", label: str = "V2Ray"):
        super().__init__()
        self.v2ray_path = v2ray_path
        self.label = label   # "V2Ray" or "Xray"
        self._process: Optional[subprocess.Popen] = None
        self._config_file: Optional[str] = None
        self._stop_flag = False
        self._thread: Optional[threading.Thread] = None

    # ── public ────────────────────────────────────────────────────────────

    def connect_vpn(self, vpn: SavedVPN) -> None:
        if self._state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            self.disconnect()
            time.sleep(1)

        self._current_server_ip = vpn.ip
        self._stop_flag = False
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
        self._kill_process()

    # ── workers ───────────────────────────────────────────────────────────

    def _connect_worker(self, config_json: str):
        if not self._exe_exists():
            self._set_state(ConnectionState.ERROR)
            self.error_occurred.emit(
                f"{self.label} executable not found: '{self.v2ray_path}'\n\n"
                f"Download {self.label} from https://github.com/v2fly/v2ray-core/releases\n"
                "Then set the path in Settings → Protocols."
            )
            return

        try:
            fd, self._config_file = tempfile.mkstemp(suffix='.json', prefix='v2ray_')
            with os.fdopen(fd, 'w') as fh:
                fh.write(config_json)

            self.log_message.emit(f"[{self.label}] Starting with config {self._config_file}")

            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            self._process = subprocess.Popen(
                [self.v2ray_path, 'run', '-c', self._config_file],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=flags,
            )

            connected_emitted = False
            for line in iter(self._process.stdout.readline, ''):
                if self._stop_flag:
                    break
                line = line.strip()
                if not line:
                    continue
                self.log_message.emit(f"[{self.label}] {line}")

                # V2Ray logs "listening on ..." or "started" messages
                if not connected_emitted and any(kw in line.lower() for kw in (
                    'listening', 'started', 'inbound', 'proxy server start'
                )):
                    connected_emitted = True
                    self._set_state(ConnectionState.CONNECTED)
                    self.connected.emit(self._current_server_ip)
                    self.log_message.emit(f"[{self.label}] ✔ Proxy running")

                if not connected_emitted and 'failed' in line.lower():
                    self._process.terminate()
                    self._set_state(ConnectionState.ERROR)
                    self.error_occurred.emit(f"{self.label} startup failed: {line}")
                    return

            self._process.wait()

        except Exception as exc:
            self._set_state(ConnectionState.ERROR)
            self.error_occurred.emit(str(exc))
            return
        finally:
            self._cleanup_config()

        if self._state != ConnectionState.DISCONNECTING:
            self._set_state(ConnectionState.DISCONNECTED)
            self.disconnected.emit()
        else:
            self._set_state(ConnectionState.DISCONNECTED)
            self.disconnected.emit()

    # ── helpers ───────────────────────────────────────────────────────────

    def _kill_process(self):
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

    def _exe_exists(self) -> bool:
        if os.path.isfile(self.v2ray_path):
            return True
        import shutil
        return shutil.which(self.v2ray_path) is not None

    def _cleanup_config(self):
        if self._config_file and os.path.exists(self._config_file):
            try:
                os.remove(self._config_file)
            except OSError:
                pass
            self._config_file = None
