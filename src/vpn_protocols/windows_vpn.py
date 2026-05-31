"""
Windows Built-in VPN protocol manager.
Supports IKEv2, L2TP/IPsec, SSTP, and PPTP using PowerShell + rasdial.
Credentials stored in vpn.credentials: {username, password, psk (for L2TP)}
"""
import os
import re
import subprocess
import threading
import time
from typing import Optional

from ..models import SavedVPN
from .base import BaseVPNManager, ConnectionState

# Tunnel type strings accepted by Add-VpnConnection
TUNNEL_TYPES = ["Automatic", "IKEv2", "L2tp", "Sstp", "Pptp"]


class WindowsVPNProtocol(BaseVPNManager):
    """
    Windows built-in VPN via PowerShell Add-VpnConnection + rasdial.
    vpn.credentials keys:
      - server       : server hostname/IP
      - tunnel_type  : IKEv2 | L2tp | Sstp | Pptp | Automatic
      - username     : (optional)
      - password     : (optional)
      - psk          : pre-shared key for L2TP (optional)
    """

    def __init__(self):
        super().__init__()
        self._conn_name: str = ""
        self._stop_flag = False
        self._thread: Optional[threading.Thread] = None

    # ── public ────────────────────────────────────────────────────────────

    def connect_vpn(self, vpn: SavedVPN) -> None:
        if self._state in (ConnectionState.CONNECTED, ConnectionState.CONNECTING):
            self.disconnect()
            time.sleep(2)

        self._stop_flag = False
        self._current_server_ip = vpn.credentials.get('server', vpn.ip)
        self._conn_name = f"VPNClient_{re.sub(r'[^\\w]', '_', vpn.name)[:24]}"
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
        self._thread = threading.Thread(target=self._disconnect_worker, daemon=True)
        self._thread.start()

    # ── workers ───────────────────────────────────────────────────────────

    def _connect_worker(self, vpn: SavedVPN):
        creds   = vpn.credentials
        server  = creds.get('server', vpn.ip)
        ttype   = creds.get('tunnel_type', 'Automatic')
        user    = creds.get('username', '')
        passwd  = creds.get('password', '')
        psk     = creds.get('psk', '')

        try:
            # Step 1: Register the VPN connection (idempotent)
            self.log_message.emit(f"[Windows VPN] Registering '{self._conn_name}' ({ttype}) → {server}")

            # Build PS command
            ps_add = (
                f"Add-VpnConnection -Name '{self._conn_name}' "
                f"-ServerAddress '{server}' "
                f"-TunnelType {ttype} "
                f"-RememberCredential $false "
                f"-Force"
            )
            if ttype == "L2tp" and psk:
                ps_add += (
                    f"; Set-VpnConnectionIPsecConfiguration "
                    f"-ConnectionName '{self._conn_name}' "
                    f"-AuthenticationTransformConstants GCMAES256 "
                    f"-CipherTransformConstants GCMAES256 "
                    f"-DHGroup Group14 "
                    f"-IntegrityCheckMethod SHA256 "
                    f"-PfsGroup None "
                    f"-Force"
                )

            rc, out, err = self._ps(ps_add)
            if rc != 0:
                combined = (out + err).strip()
                # Ignore "already exists" error
                if 'AlreadyExists' not in combined and 'already' not in combined.lower():
                    self.log_message.emit(f"[Windows VPN] Warning: {combined}")

            if self._stop_flag:
                self._do_disconnect()
                return

            # Step 2: Dial
            self.log_message.emit(f"[Windows VPN] Dialing…")
            rasdial_cmd = ['rasdial', self._conn_name]
            if user:
                rasdial_cmd += [user, passwd]

            flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            result = subprocess.run(
                rasdial_cmd,
                capture_output=True, text=True,
                creationflags=flags,
                timeout=60,
            )

            out_combined = (result.stdout + result.stderr).strip()
            self.log_message.emit(f"[Windows VPN] rasdial: {out_combined}")

            if result.returncode == 0:
                self._set_state(ConnectionState.CONNECTED)
                self.connected.emit(self._current_server_ip)
                # Monitor until disconnected
                self._monitor_connection()
            else:
                err_msg = self._interpret_rasdial_error(result.returncode, out_combined)
                self._set_state(ConnectionState.ERROR)
                self.error_occurred.emit(err_msg)

        except subprocess.TimeoutExpired:
            self._set_state(ConnectionState.ERROR)
            self.error_occurred.emit("Windows VPN connection timed out (60 s).")
        except Exception as exc:
            self._set_state(ConnectionState.ERROR)
            self.error_occurred.emit(str(exc))

    def _monitor_connection(self):
        """Poll rasdial to detect unexpected disconnect."""
        while not self._stop_flag:
            time.sleep(10)
            try:
                r = subprocess.run(
                    ['rasdial'],
                    capture_output=True, text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=5,
                )
                if self._conn_name not in r.stdout:
                    if not self._stop_flag:
                        self.log_message.emit("[Windows VPN] Connection dropped.")
                        self._set_state(ConnectionState.DISCONNECTED)
                        self.disconnected.emit()
                        return
            except Exception:
                pass

        self._do_disconnect()
        self._set_state(ConnectionState.DISCONNECTED)
        self.disconnected.emit()

    def _disconnect_worker(self):
        self._do_disconnect()
        self._set_state(ConnectionState.DISCONNECTED)
        self.disconnected.emit()

    def _do_disconnect(self):
        if self._conn_name:
            self.log_message.emit(f"[Windows VPN] Disconnecting '{self._conn_name}'…")
            subprocess.run(
                ['rasdial', self._conn_name, '/disconnect'],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            # Optionally remove the connection entry
            self._ps(f"Remove-VpnConnection -Name '{self._conn_name}' -Force")

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _ps(command: str):
        flags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        r = subprocess.run(
            ['powershell', '-NoProfile', '-NonInteractive', '-Command', command],
            capture_output=True, text=True,
            creationflags=flags,
            timeout=30,
        )
        return r.returncode, r.stdout, r.stderr

    @staticmethod
    def _interpret_rasdial_error(code: int, msg: str) -> str:
        known = {
            691: "Authentication failed — wrong username or password.",
            720: "No PPP control protocols configured.",
            721: "Remote PPP peer did not respond.",
            732: "PPP negotiation is not converging.",
            734: "PPP link control protocol terminated.",
            742: "Remote server does not support encryption.",
            800: "VPN connection failed — cannot connect to server.",
            809: "VPN connection failed — server unreachable or port blocked.",
            812: "Connection refused: policy on the server prevents this connection.",
        }
        reason = known.get(code, "")
        base = f"rasdial failed (code {code})"
        if reason:
            return f"{base}: {reason}"
        if msg:
            return f"{base}\n\n{msg}"
        return base
