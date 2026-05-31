import os
import shutil
import subprocess
import tempfile
import threading
import time
from collections import deque
from enum import Enum
from typing import List, Optional

from PyQt6.QtCore import QObject, pyqtSignal


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    ERROR = "error"


# Known OpenVPN log patterns → human-readable reason
_ERROR_PATTERNS: List[tuple] = [
    ("AUTH_FAILED",                         "Authentication failed (wrong credentials)"),
    ("TLS Error",                           "TLS handshake failed (server may be down or wrong port)"),
    ("TLS handshake failed",                "TLS handshake failed"),
    ("Cannot open TUN/TAP dev",             "TUN/TAP device error — run as Administrator and install TAP driver"),
    ("Access is denied",                    "Access denied — run the app as Administrator"),
    ("route addition failed",               "Route addition failed — run as Administrator"),
    ("Cannot allocate TUN/TAP",             "Cannot allocate TUN/TAP interface — run as Administrator"),
    ("WSAECONNREFUSED",                     "Connection refused by server"),
    ("WSAENETUNREACH",                      "Network unreachable — check your internet connection"),
    ("WSAETIMEDOUT",                        "Connection timed out"),
    ("ECONNREFUSED",                        "Connection refused by server"),
    ("Network unreachable",                 "Network unreachable — check your internet connection"),
    ("No route to host",                    "No route to host"),
    ("Connection timed out",                "Connection timed out"),
    ("Inactivity timeout",                  "VPN session timed out due to inactivity"),
    ("getaddrinfo failed",                  "DNS resolution failed — cannot resolve server hostname"),
    ("Name or service not known",           "DNS resolution failed"),
    ("Cannot resolve host",                 "DNS resolution failed"),
    ("RESOLVE: Cannot resolve",             "DNS resolution failed — server hostname not found"),
    ("read UDPv4 [ECONNRESET]",            "Connection reset by server"),
    ("process_ip_header",                   "IP header error"),
    ("Exiting due to fatal error",          "OpenVPN exited with a fatal error"),
    ("SIGTERM",                             "Process was terminated"),
    ("OPTIONS ERROR",                       "Cipher/option mismatch — server requires unsupported cipher"),
    ("failed to negotiate cipher",          "Cipher negotiation failed — server uses unsupported cipher"),
    ("unrecognized option",                 "Unrecognized option — check config file"),
    ("ERROR:",                              None),   # None = use the raw line
]


class OpenVPNManager(QObject):
    state_changed = pyqtSignal(str)
    log_message = pyqtSignal(str)
    connected = pyqtSignal(str)
    disconnected = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, openvpn_path: str = "openvpn"):
        super().__init__()
        self.openvpn_path = openvpn_path
        self._process: Optional[subprocess.Popen] = None
        self._config_file: Optional[str] = None
        self._state = ConnectionState.DISCONNECTED
        self._current_server_ip = ""
        self._stop_flag = False
        self._thread: Optional[threading.Thread] = None

    @property
    def state(self) -> ConnectionState:
        return self._state

    @property
    def current_server_ip(self) -> str:
        return self._current_server_ip

    def is_connected(self) -> bool:
        return self._state == ConnectionState.CONNECTED

    def _set_state(self, state: ConnectionState):
        self._state = state
        self.state_changed.emit(state.value)

    def connect_vpn(self, vpn) -> None:
        """Protocol-agnostic entry point (used by dispatcher interface)."""
        self.connect(vpn.ovpn_config, vpn.ip)

    def connect(self, ovpn_config: str, server_ip: str = ""):
        if self._state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            self._kill_process()
            time.sleep(1)

        self._current_server_ip = server_ip
        self._stop_flag = False
        self._set_state(ConnectionState.CONNECTING)

        self._thread = threading.Thread(
            target=self._connect_worker,
            args=(ovpn_config,),
            daemon=True,
        )
        self._thread.start()

    def _connect_worker(self, ovpn_config: str):
        connected_once = False
        detected_reason: Optional[str] = None
        # Rolling buffer of last 8 non-empty lines for fallback error context
        last_lines: deque = deque(maxlen=8)

        try:
            self._config_file = tempfile.mktemp(suffix='.ovpn', prefix='vpnclient_')
            with open(self._config_file, 'w') as fh:
                fh.write(ovpn_config)

            cmd = [
                self.openvpn_path,
                '--config', self._config_file,
                '--verb', '4',
                '--connect-retry', '1',
                '--connect-retry-max', '1',
                # Accept legacy ciphers used by many VPNGate servers
                '--data-ciphers', 'AES-256-GCM:AES-128-GCM:AES-256-CBC:AES-128-CBC:CHACHA20-POLY1305',
                '--data-ciphers-fallback', 'AES-128-CBC',
            ]

            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                creationflags=flags,
            )

            for line in iter(self._process.stdout.readline, ''):
                if self._stop_flag:
                    break
                line = line.strip()
                if not line:
                    continue

                self.log_message.emit(line)
                last_lines.append(line)

                if 'Initialization Sequence Completed' in line:
                    connected_once = True
                    detected_reason = None
                    self._set_state(ConnectionState.CONNECTED)
                    self.connected.emit(self._current_server_ip)
                    continue

                # Check all error patterns; first match wins
                if not connected_once and detected_reason is None:
                    for pattern, reason in _ERROR_PATTERNS:
                        if pattern in line:
                            detected_reason = reason if reason else f"OpenVPN error: {line}"
                            break

                if 'AUTH_FAILED' in line:
                    break
                if 'Exiting due to fatal error' in line:
                    break

            rc = self._process.wait()

        except FileNotFoundError:
            exe = self.openvpn_path
            is_connect = 'OpenVPN Connect' in exe or 'OpenVPNConnect' in exe
            if is_connect:
                msg = (
                    f"Cannot use '{exe}'\n\n"
                    "OpenVPN Connect is a GUI app — it does NOT include a command-line "
                    "openvpn.exe.\n\n"
                    "Please install OpenVPN Community Edition:\n"
                    "  https://openvpn.net/community-downloads/\n\n"
                    "Then set the path to:\n"
                    r"  C:\Program Files\OpenVPN\bin\openvpn.exe"
                )
            else:
                msg = (
                    f"OpenVPN executable not found: '{exe}'\n\n"
                    "Install OpenVPN Community Edition and set the path in Settings.\n"
                    "  https://openvpn.net/community-downloads/"
                )
            self._set_state(ConnectionState.ERROR)
            self.error_occurred.emit(msg)
            return

        except Exception as exc:
            self._set_state(ConnectionState.ERROR)
            self.error_occurred.emit(str(exc))
            return
        finally:
            self._cleanup_config()

        if self._state == ConnectionState.DISCONNECTING:
            self._set_state(ConnectionState.DISCONNECTED)
            self.disconnected.emit()
            return

        if connected_once:
            self._set_state(ConnectionState.DISCONNECTED)
            self.disconnected.emit()
        else:
            # Build a meaningful error from what we detected + last log lines
            if detected_reason:
                final_error = detected_reason
            else:
                # No known pattern matched — show last lines as context
                context = "\n  ".join(last_lines) if last_lines else "No output from OpenVPN"
                exit_hint = f" (exit code {rc})" if rc else ""
                final_error = (
                    f"Could not establish connection{exit_hint}.\n\n"
                    f"Last OpenVPN output:\n  {context}"
                )

            self._set_state(ConnectionState.ERROR)
            self.error_occurred.emit(final_error)

    def disconnect(self):
        self._set_state(ConnectionState.DISCONNECTING)
        self._stop_flag = True
        self._kill_process()

    def _kill_process(self):
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()

    def _cleanup_config(self):
        if self._config_file and os.path.exists(self._config_file):
            try:
                os.remove(self._config_file)
            except OSError:
                pass
            self._config_file = None

    @staticmethod
    def find_openvpn() -> Optional[str]:
        common = [
            # OpenVPN Community Edition (the one with CLI openvpn.exe)
            r"C:\Program Files\OpenVPN\bin\openvpn.exe",
            r"C:\Program Files (x86)\OpenVPN\bin\openvpn.exe",
        ]
        for path in common:
            if os.path.exists(path):
                return path
        # PATH fallback
        found = shutil.which('openvpn')
        if found:
            return found
        # NOTE: OpenVPN Connect does NOT ship a usable openvpn.exe CLI.
        # Intentionally not returning OpenVPN Connect paths.
        return None

