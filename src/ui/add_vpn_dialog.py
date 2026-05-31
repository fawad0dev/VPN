"""
Add VPN dialog — lets the user manually add a VPN of any supported protocol.
"""
import json
import os
import uuid
from datetime import datetime
from typing import Optional

from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QSpinBox,
    QStackedWidget, QTextEdit, QVBoxLayout, QWidget,
)
from PyQt6.QtCore import Qt

from ..models import SavedVPN
from ..vpn_protocols.shadowsocks import SS_METHODS
from ..vpn_protocols.windows_vpn import TUNNEL_TYPES
from .styles import DARK_THEME


_PROTOCOLS = [
    ("openvpn",     "OpenVPN  (.ovpn)"),
    ("wireguard",   "WireGuard  (.conf)"),
    ("windows",     "Windows Built-in  (IKEv2 / L2TP / SSTP / PPTP)"),
    ("shadowsocks", "Shadowsocks  (ss-local)"),
    ("v2ray",       "V2Ray  (JSON config)"),
    ("xray",        "Xray  (JSON config)"),
]
_PROTO_KEYS = [p[0] for p in _PROTOCOLS]


class AddVPNDialog(QDialog):
    """Returns a filled SavedVPN via `result_vpn` after exec() == Accepted."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add VPN")
        self.setMinimumWidth(560)
        self.setStyleSheet(DARK_THEME)
        self.result_vpn: Optional[SavedVPN] = None
        self._build_ui()

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        lay = QVBoxLayout(self)

        # Protocol selector
        top = QFormLayout()
        self._proto_combo = QComboBox()
        self._proto_combo.addItems([p[1] for p in _PROTOCOLS])
        self._proto_combo.currentIndexChanged.connect(self._on_proto_changed)
        top.addRow("Protocol:", self._proto_combo)
        lay.addLayout(top)

        # Common fields
        common_grp = QGroupBox("Connection Info")
        cf = QFormLayout(common_grp)
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("My VPN")
        cf.addRow("Name:", self._name_edit)
        self._country_edit = QLineEdit()
        self._country_edit.setPlaceholderText("e.g. United States")
        cf.addRow("Country:", self._country_edit)
        lay.addWidget(common_grp)

        # Protocol-specific stacked pages
        self._stack = QStackedWidget()
        self._stack.addWidget(self._page_openvpn())
        self._stack.addWidget(self._page_wireguard())
        self._stack.addWidget(self._page_windows())
        self._stack.addWidget(self._page_shadowsocks())
        self._stack.addWidget(self._page_v2ray("V2Ray"))    # v2ray
        self._stack.addWidget(self._page_v2ray("Xray"))     # xray
        lay.addWidget(self._stack)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._on_accept)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    # ── Per-protocol pages ────────────────────────────────────────────────

    def _page_openvpn(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        grp = QGroupBox("OpenVPN Configuration")
        vl = QVBoxLayout(grp)

        row = QHBoxLayout()
        self._ovpn_import_btn = QPushButton("📂  Import .ovpn File…")
        self._ovpn_import_btn.clicked.connect(self._import_ovpn)
        row.addWidget(self._ovpn_import_btn)
        row.addStretch()
        vl.addLayout(row)

        vl.addWidget(QLabel("Or paste config:"))
        self._ovpn_text = QTextEdit()
        self._ovpn_text.setPlaceholderText("Paste OpenVPN config here…")
        self._ovpn_text.setMinimumHeight(140)
        vl.addWidget(self._ovpn_text)

        ip_row = QFormLayout()
        self._ovpn_ip = QLineEdit()
        self._ovpn_ip.setPlaceholderText("Extracted automatically from config")
        ip_row.addRow("Server IP (optional):", self._ovpn_ip)
        vl.addLayout(ip_row)

        lay.addWidget(grp)
        return w

    def _page_wireguard(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        grp = QGroupBox("WireGuard Configuration")
        vl = QVBoxLayout(grp)

        row = QHBoxLayout()
        self._wg_import_btn = QPushButton("📂  Import .conf File…")
        self._wg_import_btn.clicked.connect(self._import_wg)
        row.addWidget(self._wg_import_btn)
        row.addStretch()
        vl.addLayout(row)

        vl.addWidget(QLabel("Or paste config:"))
        self._wg_text = QTextEdit()
        self._wg_text.setPlaceholderText("[Interface]\nPrivateKey = ...\n\n[Peer]\nPublicKey = ...")
        self._wg_text.setMinimumHeight(140)
        vl.addWidget(self._wg_text)

        ip_row = QFormLayout()
        self._wg_ip = QLineEdit()
        self._wg_ip.setPlaceholderText("Endpoint IP (optional — extracted from config)")
        ip_row.addRow("Server IP (optional):", self._wg_ip)
        vl.addLayout(ip_row)

        note = QLabel("⚠  WireGuard requires Administrator privileges.")
        note.setStyleSheet("color: #f39c12; font-size: 11px;")
        vl.addWidget(note)
        lay.addWidget(grp)
        return w

    def _page_windows(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        grp = QGroupBox("Windows VPN Settings")
        form = QFormLayout(grp)

        self._win_server = QLineEdit()
        self._win_server.setPlaceholderText("vpn.example.com or 1.2.3.4")
        form.addRow("Server:", self._win_server)

        self._win_type = QComboBox()
        self._win_type.addItems(TUNNEL_TYPES)
        form.addRow("Tunnel Type:", self._win_type)

        self._win_user = QLineEdit()
        self._win_user.setPlaceholderText("(leave blank if not required)")
        form.addRow("Username:", self._win_user)

        self._win_pass = QLineEdit()
        self._win_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password:", self._win_pass)

        self._win_psk = QLineEdit()
        self._win_psk.setPlaceholderText("Pre-shared key for L2TP (if required)")
        form.addRow("L2TP PSK:", self._win_psk)

        lay.addWidget(grp)
        return w

    def _page_shadowsocks(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        grp = QGroupBox("Shadowsocks Settings")
        form = QFormLayout(grp)

        self._ss_server = QLineEdit()
        self._ss_server.setPlaceholderText("ss.example.com or 1.2.3.4")
        form.addRow("Server:", self._ss_server)

        self._ss_port = QSpinBox()
        self._ss_port.setRange(1, 65535)
        self._ss_port.setValue(8388)
        form.addRow("Server Port:", self._ss_port)

        self._ss_pass = QLineEdit()
        self._ss_pass.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow("Password:", self._ss_pass)

        self._ss_method = QComboBox()
        self._ss_method.addItems(SS_METHODS)
        form.addRow("Cipher Method:", self._ss_method)

        self._ss_local = QSpinBox()
        self._ss_local.setRange(1, 65535)
        self._ss_local.setValue(1080)
        form.addRow("Local SOCKS5 Port:", self._ss_local)

        note = QLabel(
            "After connecting, point your app/browser proxy to:\n"
            "  SOCKS5  127.0.0.1 : <local port>"
        )
        note.setStyleSheet("color: #888; font-size: 11px;")
        form.addRow(note)

        lay.addWidget(grp)
        return w

    def _page_v2ray(self, label: str) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        grp = QGroupBox(f"{label} JSON Configuration")
        vl = QVBoxLayout(grp)

        row = QHBoxLayout()
        import_btn = QPushButton(f"📂  Import {label} JSON File…")
        import_btn.clicked.connect(lambda: self._import_json(label))
        row.addWidget(import_btn)
        row.addStretch()
        vl.addLayout(row)

        vl.addWidget(QLabel("Or paste JSON config:"))
        if label == "V2Ray":
            self._v2ray_text = QTextEdit()
            self._v2ray_text.setPlaceholderText('{\n  "inbounds": [...],\n  "outbounds": [...]\n}')
            self._v2ray_text.setMinimumHeight(160)
            vl.addWidget(self._v2ray_text)
        else:
            self._xray_text = QTextEdit()
            self._xray_text.setPlaceholderText('{\n  "inbounds": [...],\n  "outbounds": [...]\n}')
            self._xray_text.setMinimumHeight(160)
            vl.addWidget(self._xray_text)

        ip_row = QFormLayout()
        if label == "V2Ray":
            self._v2ray_ip = QLineEdit()
            self._v2ray_ip.setPlaceholderText("Remote server IP (optional)")
            ip_row.addRow("Server IP (optional):", self._v2ray_ip)
        else:
            self._xray_ip = QLineEdit()
            self._xray_ip.setPlaceholderText("Remote server IP (optional)")
            ip_row.addRow("Server IP (optional):", self._xray_ip)
        vl.addLayout(ip_row)

        lay.addWidget(grp)
        return w

    # ── slots ─────────────────────────────────────────────────────────────

    def _on_proto_changed(self, idx: int):
        self._stack.setCurrentIndex(idx)

    def _import_ovpn(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import OpenVPN Config", "", "OpenVPN (*.ovpn *.conf);;All Files (*)"
        )
        if path:
            with open(path, 'r', errors='replace') as fh:
                self._ovpn_text.setPlainText(fh.read())
            if not self._name_edit.text():
                self._name_edit.setText(os.path.splitext(os.path.basename(path))[0])
            # Extract server IP from remote directive
            ip = _extract_remote_ip(self._ovpn_text.toPlainText())
            if ip and not self._ovpn_ip.text():
                self._ovpn_ip.setText(ip)

    def _import_wg(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import WireGuard Config", "", "WireGuard (*.conf);;All Files (*)"
        )
        if path:
            with open(path, 'r', errors='replace') as fh:
                self._wg_text.setPlainText(fh.read())
            if not self._name_edit.text():
                self._name_edit.setText(os.path.splitext(os.path.basename(path))[0])
            ip = _extract_wg_endpoint(self._wg_text.toPlainText())
            if ip and not self._wg_ip.text():
                self._wg_ip.setText(ip)

    def _import_json(self, label: str):
        path, _ = QFileDialog.getOpenFileName(
            self, f"Import {label} JSON Config", "", "JSON (*.json);;All Files (*)"
        )
        if path:
            with open(path, 'r', errors='replace') as fh:
                text = fh.read()
            if label == "V2Ray":
                self._v2ray_text.setPlainText(text)
            else:
                self._xray_text.setPlainText(text)
            if not self._name_edit.text():
                self._name_edit.setText(os.path.splitext(os.path.basename(path))[0])

    def _on_accept(self):
        proto_idx = self._proto_combo.currentIndex()
        protocol = _PROTO_KEYS[proto_idx]
        name = self._name_edit.text().strip() or f"{_PROTOCOLS[proto_idx][1].split('(')[0].strip()} VPN"
        country = self._country_edit.text().strip() or "Unknown"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        config_data = ""
        ip = ""
        credentials: dict = {}

        if protocol == "openvpn":
            config_data = self._ovpn_text.toPlainText().strip()
            if not config_data:
                _warn(self, "Please provide an OpenVPN config.")
                return
            ip = self._ovpn_ip.text().strip() or _extract_remote_ip(config_data) or "0.0.0.0"

        elif protocol == "wireguard":
            config_data = self._wg_text.toPlainText().strip()
            if not config_data:
                _warn(self, "Please provide a WireGuard config.")
                return
            ip = self._wg_ip.text().strip() or _extract_wg_endpoint(config_data) or "0.0.0.0"

        elif protocol == "windows":
            server = self._win_server.text().strip()
            if not server:
                _warn(self, "Please provide a server address.")
                return
            ip = server
            credentials = {
                "server": server,
                "tunnel_type": self._win_type.currentText(),
                "username": self._win_user.text().strip(),
                "password": self._win_pass.text(),
                "psk": self._win_psk.text().strip(),
            }

        elif protocol == "shadowsocks":
            server = self._ss_server.text().strip()
            if not server:
                _warn(self, "Please provide a Shadowsocks server address.")
                return
            ip = server
            credentials = {
                "server": server,
                "server_port": self._ss_port.value(),
                "password": self._ss_pass.text(),
                "method": self._ss_method.currentText(),
                "local_port": self._ss_local.value(),
            }

        elif protocol == "v2ray":
            config_data = self._v2ray_text.toPlainText().strip()
            if not config_data:
                _warn(self, "Please provide a V2Ray JSON config.")
                return
            ip = self._v2ray_ip.text().strip() or _extract_v2ray_ip(config_data)

        elif protocol == "xray":
            config_data = self._xray_text.toPlainText().strip()
            if not config_data:
                _warn(self, "Please provide an Xray JSON config.")
                return
            ip = self._xray_ip.text().strip() or _extract_v2ray_ip(config_data)

        self.result_vpn = SavedVPN(
            id=str(uuid.uuid4()),
            name=name,
            ip=ip,
            country=country,
            ovpn_config=config_data,
            added_at=now,
            source="manual",
            protocol=protocol,
            credentials=credentials,
        )
        self.accept()


# ── helpers ───────────────────────────────────────────────────────────────

def _warn(parent, msg: str):
    from PyQt6.QtWidgets import QMessageBox
    QMessageBox.warning(parent, "Missing Info", msg)


def _extract_remote_ip(config: str) -> str:
    """Extract the first 'remote' IP/hostname from an OpenVPN config."""
    import re
    m = re.search(r'^\s*remote\s+(\S+)', config, re.MULTILINE)
    return m.group(1) if m else ""


def _extract_wg_endpoint(config: str) -> str:
    """Extract Endpoint IP from a WireGuard config."""
    import re
    m = re.search(r'Endpoint\s*=\s*(\S+?):\d+', config, re.IGNORECASE)
    return m.group(1) if m else ""


def _extract_v2ray_ip(config_json: str) -> str:
    """Try to extract server address from V2Ray/Xray JSON config."""
    try:
        data = json.loads(config_json)
        for ob in data.get("outbounds", []):
            settings = ob.get("settings", {})
            for server in settings.get("servers", []) or settings.get("vnext", []):
                addr = server.get("address", "")
                if addr:
                    return addr
    except Exception:
        pass
    return ""
