"""
Shadowsocks protocol manager.
Runs ss-local (shadowsocks-libev) as a SOCKS5 proxy.
vpn.credentials keys:
  - server       : remote server address
  - server_port  : remote port (int)
  - password     : password
  - method       : cipher method (e.g. aes-256-gcm, chacha20-ietf-poly1305)
  - local_port   : local SOCKS5 port (default 1080)
"""
import json
import os
import subprocess
import tempfile
import threading
import time
from typing import Optional

from ..models import SavedVPN
from .base import BaseVPNManager, ConnectionState

# Common Shadowsocks cipher methods
SS_METHODS = [
    "aes-256-gcm",
    "aes-128-gcm",
    "chacha20-ietf-poly1305",
    "aes-256-cfb",
    "aes-128-cfb",
    "rc4-md5",
    "none",
]


class ShadowsocksProtocol(BaseVPNManager):
    """
    Shadowsocks local SOCKS5 proxy via ss-local.exe.
    After connecting, the system proxy should be pointed to 127.0.0.1:<local_port>.
    """

    def __init__(self, sslocal_path: str = "ss-local"):
        super().__init__()
        self.sslocal_path = sslocal_path
        self._process: Optional[subprocess.Popen] = None
        self._config_file: Optional[str] = None
        self._stop_flag = False
        self._thread: Optional[threading.Thread] = None

    # ── public ────────────────────────────────────────────────────────────

    def connect_vpn(self, vpn: SavedVPN) -> None:
        if self._state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            self.disconnect()
            time.sleep(1)

        creds = vpn.credentials
        self._current_server_ip = creds.get('server', vpn.ip)
        self._stop_flag = False
        self._set_state(ConnectionState.CONNECTING)

        self._thread = threading.Thread(
            target=self._connect_worker,
            args=(vpn,),
            daemon=True,
        )
        self._thread.start()

    def disconnect(self):
        self._stop_flag = True
        self._set_state(ConnectionState.DISCONNECTING)
        self._kill_process()

    # ── workers ───────────────────────────────────────────────────────────

    def _connect_worker(self, vpn: SavedVPN):
        creds = vpn.credentials
        server      = creds.get('server', vpn.ip)
        server_port = int(creds.get('server_port', 8388))
        password    = creds.get('password', '')
        method      = creds.get('method', 'aes-256-gcm')
        local_port  = int(creds.get('local_port', 1080))

        if not self._exe_exists():
            self._set_state(ConnectionState.ERROR)
            self.error_occurred.emit(
                f"ss-local not found: '{self.sslocal_path}'\n\n"
                "Download shadowsocks-libev (Windows build) and set the path in "
                "Settings → Protocols."
            )
            return

        # Write JSON config
        config = {
            "server": server,
            "server_port": server_port,
            "local_address": "127.0.0.1",
            "local_port": local_port,
            "password": password,
            "method": method,
            "timeout": 60,
        }
        try:
            fd, self._config_file = tempfile.mkstemp(suffix='.json', prefix='ss_')
            with os.fdopen(fd, 'w') as fh:
                json.dump(config, fh)

            self.log_message.emit(
                f"[Shadowsocks] Connecting {server}:{server_port} → "
                f"SOCKS5 127.0.0.1:{local_port}  method={method}"
            )

            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            self._process = subprocess.Popen(
                [self.sslocal_path, '-c', self._config_file],
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
                self.log_message.emit(f"[Shadowsocks] {line}")

                # Detect successful listen
                if not connected_emitted and (
                    'listening at' in line.lower()
                    or 'tcp server listening' in line.lower()
                    or 'udp server listening' in line.lower()
                    or f':{local_port}' in line
                ):
                    connected_emitted = True
                    self._set_state(ConnectionState.CONNECTED)
                    self.connected.emit(self._current_server_ip)
                    self.log_message.emit(
                        f"[Shadowsocks] ✔ SOCKS5 proxy running on 127.0.0.1:{local_port}"
                    )
                    self.log_message.emit(
                        f"[Shadowsocks] Point your app or system proxy to SOCKS5 127.0.0.1:{local_port}"
                    )

                if 'error' in line.lower() and not connected_emitted:
                    self._process.terminate()
                    self._set_state(ConnectionState.ERROR)
                    self.error_occurred.emit(f"Shadowsocks error: {line}")
                    return

            self._process.wait()

        except Exception as exc:
            self._set_state(ConnectionState.ERROR)
            self.error_occurred.emit(str(exc))
            return
        finally:
            self._cleanup_config()

        if self._stop_flag:
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
        if os.path.isfile(self.sslocal_path):
            return True
        import shutil
        return shutil.which(self.sslocal_path) is not None

    def _cleanup_config(self):
        if self._config_file and os.path.exists(self._config_file):
            try:
                os.remove(self._config_file)
            except OSError:
                pass
            self._config_file = None
