# -*- coding: utf-8 -*-
import subprocess

from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QPushButton,
    QSpinBox, QTabWidget, QCheckBox, QVBoxLayout, QWidget,
)

from ..config import AppConfig
from .styles import DARK_THEME
from .timezone_map import TimezoneMapDialog

# Generate UTC offsets from -12:00 to +14:00 in 30-minute steps
def _build_offsets():
    result = []
    for total_min in range(-720, 841, 30):
        sign = '+' if total_min >= 0 else '-'
        h, m = divmod(abs(total_min), 60)
        result.append(f"UTC{sign}{h:02d}:{m:02d}")
    return result

_UTC_OFFSETS = _build_offsets()

import platform

# UTC offset → Windows timezone ID (for tzutil)
_OFFSET_TO_WIN_TZ: dict = {
    "UTC-12:00": "Dateline Standard Time",
    "UTC-11:00": "UTC-11",
    "UTC-10:00": "Hawaiian Standard Time",
    "UTC-09:30": "Marquesas Standard Time",
    "UTC-09:00": "Alaskan Standard Time",
    "UTC-08:00": "Pacific Standard Time",
    "UTC-07:00": "Mountain Standard Time",
    "UTC-06:00": "Central Standard Time",
    "UTC-05:00": "Eastern Standard Time",
    "UTC-04:00": "Atlantic Standard Time",
    "UTC-03:30": "Newfoundland Standard Time",
    "UTC-03:00": "E. South America Standard Time",
    "UTC-02:00": "UTC-02",
    "UTC-01:00": "Azores Standard Time",
    "UTC+00:00": "UTC",
    "UTC+01:00": "W. Europe Standard Time",
    "UTC+02:00": "Egypt Standard Time",
    "UTC+03:00": "Arab Standard Time",
    "UTC+03:30": "Iran Standard Time",
    "UTC+04:00": "Arabian Standard Time",
    "UTC+04:30": "Afghanistan Standard Time",
    "UTC+05:00": "West Asia Standard Time",
    "UTC+05:30": "India Standard Time",
    "UTC+05:45": "Nepal Standard Time",
    "UTC+06:00": "Central Asia Standard Time",
    "UTC+06:30": "Myanmar Standard Time",
    "UTC+07:00": "SE Asia Standard Time",
    "UTC+08:00": "China Standard Time",
    "UTC+08:45": "Aus Central W. Standard Time",
    "UTC+09:00": "Tokyo Standard Time",
    "UTC+09:30": "AUS Central Standard Time",
    "UTC+10:00": "AUS Eastern Standard Time",
    "UTC+10:30": "Lord Howe Standard Time",
    "UTC+11:00": "Central Pacific Standard Time",
    "UTC+12:00": "New Zealand Standard Time",
    "UTC+12:45": "Chatham Islands Standard Time",
    "UTC+13:00": "Tonga Standard Time",
    "UTC+14:00": "Line Islands Standard Time",
}

# UTC offset → IANA timezone ID (for Linux/macOS timedatectl / systemsetup)
_OFFSET_TO_IANA_TZ: dict = {
    "UTC-12:00": "Etc/GMT+12",
    "UTC-11:00": "Pacific/Midway",
    "UTC-10:00": "Pacific/Honolulu",
    "UTC-09:30": "Pacific/Marquesas",
    "UTC-09:00": "America/Anchorage",
    "UTC-08:00": "America/Los_Angeles",
    "UTC-07:00": "America/Denver",
    "UTC-06:00": "America/Chicago",
    "UTC-05:00": "America/New_York",
    "UTC-04:00": "America/Halifax",
    "UTC-03:30": "America/St_Johns",
    "UTC-03:00": "America/Sao_Paulo",
    "UTC-02:00": "Etc/GMT+2",
    "UTC-01:00": "Atlantic/Azores",
    "UTC+00:00": "UTC",
    "UTC+01:00": "Europe/Paris",
    "UTC+02:00": "Africa/Cairo",
    "UTC+03:00": "Asia/Riyadh",
    "UTC+03:30": "Asia/Tehran",
    "UTC+04:00": "Asia/Dubai",
    "UTC+04:30": "Asia/Kabul",
    "UTC+05:00": "Asia/Karachi",
    "UTC+05:30": "Asia/Kolkata",
    "UTC+05:45": "Asia/Kathmandu",
    "UTC+06:00": "Asia/Almaty",
    "UTC+06:30": "Asia/Rangoon",
    "UTC+07:00": "Asia/Bangkok",
    "UTC+08:00": "Asia/Shanghai",
    "UTC+08:45": "Australia/Eucla",
    "UTC+09:00": "Asia/Tokyo",
    "UTC+09:30": "Australia/Darwin",
    "UTC+10:00": "Australia/Sydney",
    "UTC+10:30": "Australia/Lord_Howe",
    "UTC+11:00": "Pacific/Noumea",
    "UTC+12:00": "Pacific/Auckland",
    "UTC+12:45": "Pacific/Chatham",
    "UTC+13:00": "Pacific/Tongatapu",
    "UTC+14:00": "Pacific/Kiritimati",
}


def _set_system_timezone(tz_id: str) -> tuple[bool, str]:
    """Change the system timezone. tz_id must be the correct ID for the current OS."""
    _sys = platform.system()
    try:
        if _sys == "Windows":
            kwargs = {"creationflags": subprocess.CREATE_NO_WINDOW}
            cmd = ["tzutil", "/s", tz_id]
        elif _sys == "Linux":
            kwargs = {}
            cmd = ["timedatectl", "set-timezone", tz_id]
        elif _sys == "Darwin":
            kwargs = {}
            cmd = ["systemsetup", "-settimezone", tz_id]
        else:
            return False, f"Unsupported platform: {_sys}"

        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10, **kwargs
        )
        if result.returncode == 0:
            return True, f"System timezone set to: {tz_id}"
        err = (result.stdout + result.stderr).strip() or f"Exit code {result.returncode}"
        return False, err
    except FileNotFoundError as exc:
        return False, f"Command not found: {exc.filename}"
    except Exception as exc:
        return False, str(exc)


def _get_tz_id_for_offset(offset: str) -> tuple[str | None, str]:
    """Return (tz_id, label) appropriate for the current OS, or (None, reason)."""
    _sys = platform.system()
    if _sys == "Windows":
        tz = _OFFSET_TO_WIN_TZ.get(offset)
        return tz, (tz or f"No Windows timezone ID for {offset}")
    elif _sys in ("Linux", "Darwin"):
        tz = _OFFSET_TO_IANA_TZ.get(offset)
        return tz, (tz or f"No IANA timezone ID for {offset}")
    return None, f"Unsupported platform: {_sys}"



class SettingsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None, hint: str = ""):
        super().__init__(parent)
        self.config = config
        self._hint = hint
        self.setWindowTitle("Settings")
        self.setMinimumWidth(520)
        self.setStyleSheet(DARK_THEME)
        self._build_ui()
        self._load()

    def _build_ui(self):
        lay = QVBoxLayout(self)

        tabs = QTabWidget()
        tabs.addTab(self._general_tab(), "General")
        tabs.addTab(self._protocols_tab(), "Protocols")
        tabs.addTab(self._autoconnect_tab(), "Auto-Connect")
        lay.addWidget(tabs)

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.accepted.connect(self._save)
        btns.rejected.connect(self.reject)
        lay.addWidget(btns)

    # ── General tab ────────────────────────────────────────────────────────

    def _general_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)

        # Show hint banner if provided (e.g. "OpenVPN not found")
        if self._hint:
            banner = QLabel(self._hint)
            banner.setStyleSheet(
                "background:#2a1010; color:#e74c3c; border:1px solid #e74c3c;"
                "border-radius:6px; padding:10px; font-size:12px;"
            )
            banner.setWordWrap(True)
            lay.addWidget(banner)

        grp = QGroupBox("OpenVPN Executable Path")
        form = QFormLayout(grp)

        row = QHBoxLayout()
        self._openvpn_path = QLineEdit()
        self._openvpn_path.setPlaceholderText("e.g. C:\\Program Files\\OpenVPN\\bin\\openvpn.exe")
        row.addWidget(self._openvpn_path)
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_openvpn)
        row.addWidget(browse)
        form.addRow("Path:", row)

        hint = QLabel(
            "⚠  Requires OpenVPN Community Edition — NOT OpenVPN Connect.\n\n"
            "OpenVPN Connect (the GUI app) does not include a command-line openvpn.exe.\n"
            "Download Community Edition from:\n"
            "  https://openvpn.net/community-downloads/\n\n"
            "After installing, the path will be:\n"
            r"  C:\Program Files\OpenVPN\bin\openvpn.exe"
        )
        hint.setStyleSheet("color: #f39c12; font-size: 11px;")
        hint.setWordWrap(True)
        form.addRow(hint)

        lay.addWidget(grp)

        # ── Timezone ──────────────────────────────────────────────────────
        tzgrp = QGroupBox("Timezone")
        tzform = QFormLayout(tzgrp)

        tz_row = QHBoxLayout()
        self._tz_combo = QComboBox()
        self._tz_combo.addItems(_UTC_OFFSETS)
        self._tz_combo.setMaxVisibleItems(14)
        tz_row.addWidget(self._tz_combo, 1)
        map_btn = QPushButton("🗺  Pick on Map…")
        map_btn.clicked.connect(self._pick_on_map)
        tz_row.addWidget(map_btn)
        tzform.addRow("UTC Offset:", tz_row)

        apply_row = QHBoxLayout()
        self._apply_tz_btn = QPushButton("🕐  Apply to System Clock")
        self._apply_tz_btn.setStyleSheet(
            "background:#1a3a1a; border:1px solid #27ae60; color:#27ae60;"
            "border-radius:5px; padding:5px 12px; font-weight:600;"
        )
        self._apply_tz_btn.setToolTip(
            "Changes the OS system timezone.\n"
            "Windows: requires Administrator (UAC prompt offered).\n"
            "Linux/macOS: requires sudo."
        )
        self._apply_tz_btn.clicked.connect(self._apply_system_timezone)
        apply_row.addWidget(self._apply_tz_btn)
        apply_row.addStretch()
        tzform.addRow(apply_row)

        tz_hint = QLabel(
            "① Pick an offset above  \u2192  ② Click 'Apply to System Clock' to update the OS timezone."
        )
        tz_hint.setStyleSheet("color: #888; font-size: 11px;")
        tzform.addRow(tz_hint)

        lay.addWidget(tzgrp)
        lay.addStretch()
        return tab

    # ── Protocols tab ──────────────────────────────────────────────────────

    def _protocols_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)

        def _exe_row(label: str, placeholder: str):
            grp = QGroupBox(label)
            form = QFormLayout(grp)
            row = QHBoxLayout()
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            row.addWidget(edit)
            btn = QPushButton("Browse…")
            btn.clicked.connect(lambda: self._browse_exe(edit))
            row.addWidget(btn)
            form.addRow("Path:", row)
            return grp, edit

        wg_grp, self._wg_path = _exe_row(
            "WireGuard",
            r"wireguard  or  C:\Program Files\WireGuard\wireguard.exe"
        )
        wg_note = QLabel("Requires Administrator privileges.\nDownload: https://www.wireguard.com/install/")
        wg_note.setStyleSheet("color:#888; font-size:11px;")
        wg_grp.layout().addRow(wg_note)
        lay.addWidget(wg_grp)

        ss_grp, self._ss_path = _exe_row(
            "Shadowsocks (ss-local)",
            r"ss-local  or  C:\tools\shadowsocks\ss-local.exe"
        )
        ss_note = QLabel("Download shadowsocks-libev Windows build.")
        ss_note.setStyleSheet("color:#888; font-size:11px;")
        ss_grp.layout().addRow(ss_note)
        lay.addWidget(ss_grp)

        v2ray_grp, self._v2ray_path = _exe_row(
            "V2Ray",
            r"v2ray  or  C:\tools\v2ray\v2ray.exe"
        )
        v2ray_note = QLabel("Download: https://github.com/v2fly/v2ray-core/releases")
        v2ray_note.setStyleSheet("color:#888; font-size:11px;")
        v2ray_grp.layout().addRow(v2ray_note)
        lay.addWidget(v2ray_grp)

        xray_grp, self._xray_path = _exe_row(
            "Xray",
            r"xray  or  C:\tools\xray\xray.exe"
        )
        xray_note = QLabel("Download: https://github.com/XTLS/Xray-core/releases")
        xray_note.setStyleSheet("color:#888; font-size:11px;")
        xray_grp.layout().addRow(xray_note)
        lay.addWidget(xray_grp)

        lay.addStretch()
        return tab

    # ── Auto-connect tab ───────────────────────────────────────────────────

    def _autoconnect_tab(self) -> QWidget:
        tab = QWidget()
        lay = QVBoxLayout(tab)

        self._ac_enable = QCheckBox("Enable Auto-Connect / Failover")
        self._ac_enable.setStyleSheet("font-weight: bold; font-size: 13px;")
        lay.addWidget(self._ac_enable)

        # Strategy
        sg = QGroupBox("Failover Strategy")
        sf = QFormLayout(sg)
        self._strategy = QComboBox()
        self._strategy.addItems([
            "sequential  (go through list in order)",
            "best_ping   (sort by lowest ping first)",
            "random      (random server order)",
        ])
        sf.addRow("Strategy:", self._strategy)
        lay.addWidget(sg)

        # Connection settings
        cg = QGroupBox("Connection Settings")
        cf = QFormLayout(cg)

        self._timeout = QSpinBox()
        self._timeout.setRange(5, 300)
        self._timeout.setSuffix("  seconds")
        cf.addRow("Connection timeout:", self._timeout)

        self._retry_delay = QSpinBox()
        self._retry_delay.setRange(1, 120)
        self._retry_delay.setSuffix("  seconds")
        cf.addRow("Retry delay:", self._retry_delay)

        self._max_retries = QSpinBox()
        self._max_retries.setRange(0, 20)
        cf.addRow("Max retries per server:", self._max_retries)
        lay.addWidget(cg)

        # Health check
        hg = QGroupBox("Health Check (keeps checking after connect)")
        hf = QFormLayout(hg)

        self._health_interval = QSpinBox()
        self._health_interval.setRange(5, 600)
        self._health_interval.setSuffix("  seconds")
        hf.addRow("Check interval:", self._health_interval)

        self._health_host = QLineEdit()
        hf.addRow("Check host:", self._health_host)

        self._health_port = QSpinBox()
        self._health_port.setRange(1, 65535)
        hf.addRow("Check port:", self._health_port)

        self._health_timeout = QSpinBox()
        self._health_timeout.setRange(1, 60)
        self._health_timeout.setSuffix("  seconds")
        hf.addRow("Check timeout:", self._health_timeout)

        lay.addWidget(hg)
        lay.addStretch()
        return tab

    # ── Load / save ────────────────────────────────────────────────────────

    _STRATEGY_MAP = ["sequential", "best_ping", "random"]

    def _load(self):
        self._openvpn_path.setText(self.config.openvpn_path)

        tz = self.config.timezone
        idx = self._tz_combo.findText(tz)
        self._tz_combo.setCurrentIndex(idx if idx >= 0 else self._tz_combo.findText("UTC+00:00"))

        self._wg_path.setText(self.config.wireguard_path)
        self._ss_path.setText(self.config.sslocal_path)
        self._v2ray_path.setText(self.config.v2ray_path)
        self._xray_path.setText(self.config.xray_path)

        ac = self.config.auto_connect
        self._ac_enable.setChecked(ac.enabled)
        idx = self._STRATEGY_MAP.index(ac.strategy) if ac.strategy in self._STRATEGY_MAP else 0
        self._strategy.setCurrentIndex(idx)
        self._timeout.setValue(ac.connection_timeout)
        self._retry_delay.setValue(ac.retry_delay)
        self._max_retries.setValue(ac.max_retries_per_server)
        self._health_interval.setValue(ac.health_check_interval)
        self._health_host.setText(ac.health_check_host)
        self._health_port.setValue(ac.health_check_port)
        self._health_timeout.setValue(ac.health_check_timeout)

    def _save(self):
        self.config.openvpn_path = self._openvpn_path.text().strip() or "openvpn"
        self.config.timezone = self._tz_combo.currentText()

        self.config.wireguard_path = self._wg_path.text().strip() or "wireguard"
        self.config.sslocal_path   = self._ss_path.text().strip() or "ss-local"
        self.config.v2ray_path     = self._v2ray_path.text().strip() or "v2ray"
        self.config.xray_path      = self._xray_path.text().strip() or "xray"

        ac = self.config.auto_connect
        ac.enabled = self._ac_enable.isChecked()
        ac.strategy = self._STRATEGY_MAP[self._strategy.currentIndex()]
        ac.connection_timeout = self._timeout.value()
        ac.retry_delay = self._retry_delay.value()
        ac.max_retries_per_server = self._max_retries.value()
        ac.health_check_interval = self._health_interval.value()
        ac.health_check_host = self._health_host.text().strip() or "8.8.8.8"
        ac.health_check_port = self._health_port.value()
        ac.health_check_timeout = self._health_timeout.value()

        self.config.save()
        self.accept()

    def _apply_system_timezone(self):
        offset = self._tz_combo.currentText()
        tz_id, label = _get_tz_id_for_offset(offset)

        if not tz_id:
            QMessageBox.warning(
                self, "No Mapping",
                f"No timezone mapping found for {offset}.\n\n{label}"
            )
            return

        ok, msg = _set_system_timezone(tz_id)
        _sys = platform.system()
        if ok:
            QMessageBox.information(
                self, "System Timezone Updated",
                f"\u2714 {msg}\n\nUTC Offset: {offset}\nTimezone ID: {tz_id}"
            )
        else:
            extra = ""
            offer_elevate = False
            if _sys == "Windows":
                extra = "\n\nWould you like to retry with Administrator privileges (UAC prompt)?"
                offer_elevate = True
            elif _sys == "Linux":
                extra = "\n\nOn Linux, run the app with sudo, or run:\n  sudo timedatectl set-timezone " + tz_id
            elif _sys == "Darwin":
                extra = "\n\nOn macOS, run the app with sudo, or run:\n  sudo systemsetup -settimezone " + tz_id

            buttons = (
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                if offer_elevate else QMessageBox.StandardButton.Ok
            )
            title = "Administrator Required" if offer_elevate else "Failed to Set Timezone"
            ret = QMessageBox.warning(self, title,
                f"Could not change system timezone:\n\n{msg}{extra}", buttons)

            if offer_elevate and ret == QMessageBox.StandardButton.Yes:
                self._apply_elevated(tz_id, offset)

    def _apply_elevated(self, tz_id: str, offset: str):
        """Re-run timezone change elevated via UAC (Windows only)."""
        try:
            result = subprocess.run(
                [
                    'powershell', '-NoProfile', '-NonInteractive', '-Command',
                    f"Start-Process powershell -Verb RunAs -Wait -ArgumentList "
                    f"'-NoProfile -Command \"Set-TimeZone -Id \\\'{tz_id}\\\'\"'"
                ],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
                timeout=30,
            )
            verify = subprocess.run(
                ['powershell', '-NoProfile', '-Command', '(Get-TimeZone).Id'],
                capture_output=True, text=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            current = verify.stdout.strip()
            if tz_id.lower() in current.lower():
                QMessageBox.information(
                    self, "Success",
                    f"\u2714 System timezone set to: {tz_id}\nUTC Offset: {offset}"
                )
            else:
                QMessageBox.information(
                    self, "Done",
                    "Elevation prompt shown. If you accepted, the timezone was updated.\n"
                    f"Expected: {tz_id}\nCurrent reported: {current}"
                )
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))

    def _browse_openvpn(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select OpenVPN Executable", "",
            "Executables (*.exe);;All Files (*)"
        )
        if path:
            self._openvpn_path.setText(path)

    def _browse_exe(self, target_edit):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Executable", "",
            "Executables (*.exe);;All Files (*)"
        )
        if path:
            target_edit.setText(path)

    def _pick_on_map(self):
        dlg = TimezoneMapDialog(self._tz_combo.currentText(), self)
        if dlg.exec():
            tz = dlg.selected_timezone
            idx = self._tz_combo.findText(tz)
            if idx >= 0:
                self._tz_combo.setCurrentIndex(idx)
