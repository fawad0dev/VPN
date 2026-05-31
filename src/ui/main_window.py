import uuid
from datetime import datetime, timezone as dt_timezone, timedelta
from typing import Optional
import re as _re

from PyQt6.QtCore import Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QAction, QColor, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFrame, QGroupBox, QHBoxLayout, QLabel,
    QMainWindow, QMenu, QMessageBox, QSplitter, QStatusBar, QTableWidget,
    QTableWidgetItem, QTextEdit, QVBoxLayout, QWidget, QPushButton,
    QHeaderView,
)

from ..auto_connect import AutoConnectManager
from ..config import AppConfig
from ..models import SavedVPN
from ..network_stats import NetworkStatsMonitor, fmt_bytes, fmt_rate
from ..vpn_dispatcher import VPNDispatcher
from ..vpn_protocols.base import ConnectionState
from .add_vpn_dialog import AddVPNDialog
from .settings_dialog import SettingsDialog
from .styles import DARK_THEME
from .vpngate_browser import VPNGateBrowser

_VPN_COLS   = ["", "Protocol", "Name", "IP", "Country", "Ping", "Speed", "Source", "Added"]
_VPN_WIDTHS = [24,  80,         0,      120,  130,        65,     90,      80,        95]   # 0 = stretch

_PROTO_ICON = {
    "openvpn":     "🔒",
    "wireguard":   "🔐",
    "windows":     "🪟",
    "shadowsocks": "🌑",
    "v2ray":       "⚡",
    "xray":        "✖",
}


class MainWindow(QMainWindow):
    def __init__(self, config: AppConfig):
        super().__init__()
        self.config = config
        self.vpn_manager = VPNDispatcher(config)
        self.auto_manager = AutoConnectManager(self.vpn_manager, config.auto_connect)
        self._current_vpn: Optional[SavedVPN] = None
        self._connect_start: Optional[datetime] = None
        self._stats_monitor = NetworkStatsMonitor(interval_ms=1000)

        self.setWindowTitle("🛡 VPN Client")
        self.setMinimumSize(960, 640)
        self.resize(1100, 720)
        self.setStyleSheet(DARK_THEME)

        self._build_ui()
        self._wire_signals()
        self._refresh_table()

        # Clock ticker
        self._ticker = QTimer()
        self._ticker.timeout.connect(self._tick_clock)
        self._ticker.start(1000)

    # ══════════════════════════════════════════════════════════════════════
    #  UI construction
    # ══════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        outer = QHBoxLayout(root)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Left sidebar
        sidebar = self._make_sidebar()
        sidebar.setObjectName("leftPanel")
        sidebar.setFixedWidth(270)
        outer.addWidget(sidebar)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet("color: #2a2a4a;")
        outer.addWidget(sep)

        # Main content
        content = self._make_content()
        outer.addWidget(content, 1)

        # Status bar
        sb = QStatusBar()
        sb.setObjectName("statusBar")
        self.setStatusBar(sb)
        self._sb = sb
        self._sb.showMessage("Ready")

    # ── Sidebar ────────────────────────────────────────────────────────────

    def _make_sidebar(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(10)

        # App title
        title = QLabel("🛡  VPN Client")
        title.setStyleSheet(
            "font-size: 20px; font-weight: 700; color: #e94560; padding: 6px 0;"
        )
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(title)

        # Connection group
        grp = QGroupBox("Connection")
        gl = QVBoxLayout(grp)

        self._status_lbl = QLabel("● Disconnected")
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_lbl.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #e94560;"
        )
        gl.addWidget(self._status_lbl)

        self._server_lbl = QLabel("—")
        self._server_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._server_lbl.setWordWrap(True)
        self._server_lbl.setStyleSheet("color: #666; font-size: 11px;")
        gl.addWidget(self._server_lbl)

        lay.addWidget(grp)

        # Connect button
        self._conn_btn = QPushButton("CONNECT")
        self._conn_btn.setObjectName("primaryBtn")
        self._conn_btn.setFixedHeight(50)
        self._conn_btn.clicked.connect(self._toggle_connection)
        lay.addWidget(self._conn_btn)

        # Timer label (connection duration)
        self._clock_lbl = QLabel("")
        self._clock_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._clock_lbl.setStyleSheet("color: #27ae60; font-size: 12px;")
        lay.addWidget(self._clock_lbl)

        # World clock label (timezone)
        self._tz_clock_lbl = QLabel("")
        self._tz_clock_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._tz_clock_lbl.setStyleSheet("color: #888; font-size: 11px;")
        lay.addWidget(self._tz_clock_lbl)

        # ── Network Stats panel ────────────────────────────────────────────
        stats_grp = QGroupBox("Network Stats")
        stats_grp.setStyleSheet(
            "QGroupBox { font-size:12px; font-weight:600; color:#aaa; }"
        )
        sg = QVBoxLayout(stats_grp)
        sg.setSpacing(3)
        sg.setContentsMargins(8, 8, 8, 8)

        def _stat_row(icon: str, label: str, color: str = "#ccc") -> QLabel:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            lbl_left = QLabel(f"{icon}  {label}")
            lbl_left.setStyleSheet(f"color:#888; font-size:11px;")
            val = QLabel("—")
            val.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            val.setStyleSheet(f"color:{color}; font-size:11px; font-weight:600;")
            row.addWidget(lbl_left, 1)
            row.addWidget(val, 0)
            sg.addLayout(row)
            return val

        self._stat_down_rate  = _stat_row("↓", "Download",      "#27ae60")
        self._stat_up_rate    = _stat_row("↑", "Upload",         "#3498db")
        sg.addWidget(self.__make_divider())
        self._stat_total_down = _stat_row("📥", "Total In",      "#27ae60")
        self._stat_total_up   = _stat_row("📤", "Total Out",     "#3498db")
        sg.addWidget(self.__make_divider())
        self._stat_pkts_down  = _stat_row("📦", "Packets In",    "#aaa")
        self._stat_pkts_up    = _stat_row("📦", "Packets Out",   "#aaa")
        sg.addWidget(self.__make_divider())
        self._stat_protocol   = _stat_row("🔒", "Protocol",      "#e0e0e0")
        self._stat_country    = _stat_row("🌐", "Country",       "#e0e0e0")
        self._stat_ping       = _stat_row("📶", "Ping",          "#f39c12")

        lay.addWidget(stats_grp)
        self._stats_grp = stats_grp

        # Auto-connect group
        ag = QGroupBox("Auto-Connect / Failover")
        al = QVBoxLayout(ag)

        self._auto_cb = QCheckBox("Enable Auto-Connect")
        self._auto_cb.setChecked(self.config.auto_connect.enabled)
        self._auto_cb.toggled.connect(self._toggle_auto_connect)
        al.addWidget(self._auto_cb)

        self._auto_lbl = QLabel("Disabled")
        self._auto_lbl.setStyleSheet("color: #555; font-size: 11px;")
        self._auto_lbl.setWordWrap(True)
        al.addWidget(self._auto_lbl)

        lay.addWidget(ag)
        lay.addStretch()

        # Settings
        settings_btn = QPushButton("⚙  Settings")
        settings_btn.setStyleSheet(
            "padding: 8px; font-size: 13px; font-weight: 600;"
            "background:#1e1e3a; border:1px solid #e94560; border-radius:6px; color:#e94560;"
        )
        settings_btn.clicked.connect(self._open_settings)
        lay.addWidget(settings_btn)

        return panel

    @staticmethod
    def __make_divider() -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #2a2a4a; margin: 2px 0;")
        return line

    # ── Content area ───────────────────────────────────────────────────────

    def _make_content(self) -> QWidget:
        panel = QWidget()
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(14, 12, 14, 0)
        lay.setSpacing(8)

        # Toolbar row
        tb = QHBoxLayout()
        lbl = QLabel("My VPN Servers")
        lbl.setStyleSheet("font-size: 16px; font-weight: 700; color: #e0e0e0;")
        tb.addWidget(lbl)
        tb.addStretch()

        # Add VPN button
        add_btn = QPushButton("➕  Add VPN")
        add_btn.setObjectName("primaryBtn")
        add_btn.clicked.connect(self._add_vpn)
        tb.addWidget(add_btn)

        browse_btn = QPushButton("🌐  Browse VPNGate")
        browse_btn.setObjectName("primaryBtn")
        browse_btn.clicked.connect(self._open_browser)
        tb.addWidget(browse_btn)

        remove_btn = QPushButton("🗑  Remove")
        remove_btn.clicked.connect(self._remove_selected)
        tb.addWidget(remove_btn)

        lay.addLayout(tb)

        # Splitter (table + log)
        splitter = QSplitter(Qt.Orientation.Vertical)

        self._table = QTableWidget()
        self._setup_table()
        splitter.addWidget(self._table)

        # Log pane
        log_wrap = QWidget()
        lw = QVBoxLayout(log_wrap)
        lw.setContentsMargins(0, 4, 0, 0)

        lh = QHBoxLayout()
        lh.addWidget(QLabel("Connection Log"))
        clear_btn = QPushButton("Clear")
        clear_btn.setFixedWidth(54)
        clear_btn.setStyleSheet("padding: 2px 6px; font-size: 11px;")
        clear_btn.clicked.connect(lambda: self._log.clear())
        lh.addWidget(clear_btn)
        lw.addLayout(lh)

        self._log = QTextEdit()
        self._log.setObjectName("logView")
        self._log.setReadOnly(True)
        self._log.setMaximumHeight(140)
        lw.addWidget(self._log)
        splitter.addWidget(log_wrap)

        splitter.setSizes([480, 140])
        lay.addWidget(splitter)

        return panel

    # ── VPN table ──────────────────────────────────────────────────────────

    def _setup_table(self):
        self._table.setColumnCount(len(_VPN_COLS))
        self._table.setHorizontalHeaderLabels(_VPN_COLS)
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setVisible(False)
        self._table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._table.customContextMenuRequested.connect(self._ctx_menu)
        self._table.doubleClicked.connect(lambda _: self._connect_selected())

        hdr = self._table.horizontalHeader()
        for i, w in enumerate(_VPN_WIDTHS):
            if w == 0:
                hdr.setSectionResizeMode(i, QHeaderView.ResizeMode.Stretch)
            else:
                self._table.setColumnWidth(i, w)

    def _refresh_table(self):
        self._table.setRowCount(0)
        for vpn in self.config.vpns:
            self._append_row(vpn)

    def _append_row(self, vpn: SavedVPN):
        row = self._table.rowCount()
        self._table.insertRow(row)

        is_active = (
            self._current_vpn
            and self._current_vpn.id == vpn.id
            and self.vpn_manager.is_connected()
        )
        dot = QTableWidgetItem("●")
        dot.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        dot.setForeground(QColor("#27ae60" if is_active else "#333"))
        self._table.setItem(row, 0, dot)

        proto = vpn.protocol or "openvpn"
        icon = _PROTO_ICON.get(proto, "🔒")
        proto_item = QTableWidgetItem(f"{icon} {proto}")
        proto_item.setData(Qt.ItemDataRole.UserRole, vpn.id)
        self._table.setItem(row, 1, proto_item)

        cells = [
            vpn.name,
            vpn.ip,
            vpn.country,
            f"{vpn.ping} ms" if vpn.ping else "—",
            f"{vpn.speed / 1_000_000:.1f} M" if vpn.speed else "—",
            vpn.source,
            vpn.added_at[:10],
        ]
        for col, text in enumerate(cells, 2):
            item = QTableWidgetItem(str(text))
            item.setData(Qt.ItemDataRole.UserRole, vpn.id)
            self._table.setItem(row, col, item)

    # ══════════════════════════════════════════════════════════════════════
    #  Signal wiring
    # ══════════════════════════════════════════════════════════════════════

    def _wire_signals(self):
        m = self.vpn_manager
        m.state_changed.connect(self._on_state)
        m.log_message.connect(self._append_log)
        m.connected.connect(self._on_connected)
        m.disconnected.connect(self._on_disconnected)
        m.error_occurred.connect(self._on_error)

        self.auto_manager.switching_server.connect(
            lambda r: self._append_log(f"[AUTO] {r}")
        )
        self.auto_manager.status_update.connect(self._on_auto_status)

        self._stats_monitor.stats_updated.connect(self._on_stats_update)

    # ══════════════════════════════════════════════════════════════════════
    #  Slots
    # ══════════════════════════════════════════════════════════════════════

    @pyqtSlot(str)
    def _on_state(self, state: str):
        if state == ConnectionState.CONNECTED.value:
            self._status_lbl.setText("● Connected")
            self._status_lbl.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: #27ae60;"
            )
            self._set_btn_style("■  DISCONNECT", "#27ae60")
            self._conn_btn.setEnabled(True)
            self._connect_start = datetime.now()
            if self._current_vpn:
                self._server_lbl.setText(
                    f"{self._current_vpn.name}\n{self._current_vpn.ip}"
                )

        elif state == ConnectionState.CONNECTING.value:
            self._status_lbl.setText("● Connecting…")
            self._status_lbl.setStyleSheet(
                "font-size: 14px; font-weight: bold; color: #f39c12;"
            )
            self._set_btn_style("■  STOP", "#c0392b")
            self._conn_btn.setEnabled(True)

        elif state in (ConnectionState.DISCONNECTED.value, ConnectionState.ERROR.value):
            color = "#e94560"
            label = "● Error" if state == ConnectionState.ERROR.value else "● Disconnected"
            self._status_lbl.setText(label)
            self._status_lbl.setStyleSheet(
                f"font-size: 14px; font-weight: bold; color: {color};"
            )
            self._set_btn_style("CONNECT", "#e94560")
            self._conn_btn.setEnabled(True)
            self._server_lbl.setText("—")
            self._connect_start = None
            self._clock_lbl.setText("")

        self._refresh_table()

    def _set_btn_style(self, text: str, color: str):
        self._conn_btn.setText(text)
        self._conn_btn.setStyleSheet(
            f"background-color:{color};color:#fff;border:none;"
            "font-size:14px;font-weight:bold;padding:10px 20px;border-radius:8px;"
        )

    @pyqtSlot(str)
    def _append_log(self, msg: str):
        self._log.append(msg)
        sb = self._log.verticalScrollBar()
        sb.setValue(sb.maximum())

    @pyqtSlot(str)
    def _on_connected(self, ip: str):
        self._sb.showMessage(f"✔ Connected — {ip}")
        self._stats_monitor.start()
        # Populate static server info immediately
        if self._current_vpn:
            proto = self._current_vpn.protocol or "openvpn"
            icon = _PROTO_ICON.get(proto, "🔒")
            self._stat_protocol.setText(f"{icon} {proto}")
            self._stat_country.setText(self._current_vpn.country or "—")
            ping = self._current_vpn.ping
            self._stat_ping.setText(f"{ping} ms" if ping else "—")

    @pyqtSlot()
    def _on_disconnected(self):
        self._sb.showMessage("Disconnected")
        self._stats_monitor.stop()
        self._reset_stats_labels()

    @pyqtSlot(dict)
    def _on_stats_update(self, s: dict):
        self._stat_down_rate.setText(fmt_rate(s["down_rate"]))
        self._stat_up_rate.setText(fmt_rate(s["up_rate"]))
        self._stat_total_down.setText(fmt_bytes(s["total_down"]))
        self._stat_total_up.setText(fmt_bytes(s["total_up"]))
        self._stat_pkts_down.setText(f"{s['packets_down']:,}")
        self._stat_pkts_up.setText(f"{s['packets_up']:,}")

    def _reset_stats_labels(self):
        for lbl in (
            self._stat_down_rate, self._stat_up_rate,
            self._stat_total_down, self._stat_total_up,
            self._stat_pkts_down, self._stat_pkts_up,
            self._stat_protocol, self._stat_country, self._stat_ping,
        ):
            lbl.setText("—")

    @pyqtSlot(str)
    def _on_error(self, err: str):
        self._sb.showMessage(f"✖ {err.splitlines()[0]}")   # first line in status bar
        self._append_log(f"ERROR: {err}")

    @pyqtSlot(str)
    def _on_auto_status(self, msg: str):
        self._auto_lbl.setText(msg)
        self._sb.showMessage(msg)

    def _tick_clock(self):
        # Connection duration timer
        if self._connect_start:
            secs = int((datetime.now() - self._connect_start).total_seconds())
            h, r = divmod(secs, 3600)
            m, s = divmod(r, 60)
            self._clock_lbl.setText(f"⏱ {h:02d}:{m:02d}:{s:02d}")

        # Timezone world clock — parse "UTC+05:30" / "UTC-03:00"
        try:
            tz_str = self.config.timezone
            match = _re.match(r'UTC([+-])(\d{2}):(\d{2})', tz_str)
            if match:
                sign = 1 if match.group(1) == '+' else -1
                delta = timedelta(
                    hours=sign * int(match.group(2)),
                    minutes=sign * int(match.group(3))
                )
                tz = dt_timezone(delta)
            else:
                tz = dt_timezone.utc
            now = datetime.now(tz)
            self._tz_clock_lbl.setText(
                f"🕐 {now.strftime('%H:%M:%S')}  ({tz_str})"
            )
        except Exception:
            self._tz_clock_lbl.setText("")

    # ══════════════════════════════════════════════════════════════════════
    #  Actions
    # ══════════════════════════════════════════════════════════════════════

    def _toggle_connection(self):
        if self.vpn_manager.state in (
            ConnectionState.CONNECTED, ConnectionState.CONNECTING
        ):
            if self.config.auto_connect.enabled:
                self.auto_manager.stop()
            else:
                self.vpn_manager.disconnect()
        else:
            vpn = self._get_selected_vpn()
            if not vpn:
                QMessageBox.information(
                    self, "No Server Selected",
                    "Select a VPN server in the list or add VPNs from Browse VPNGate."
                )
                return
            self._current_vpn = vpn
            self._server_lbl.setText(f"{vpn.name}\n{vpn.ip}")
            if self.config.auto_connect.enabled and len(self.config.vpns) > 1:
                idx = next(
                    (i for i, v in enumerate(self.config.vpns) if v.id == vpn.id), 0
                )
                self.auto_manager.start(self.config.vpns, idx)
            else:
                self.vpn_manager.connect_vpn(vpn)

    def _connect_selected(self):
        vpn = self._get_selected_vpn()
        if vpn:
            self._current_vpn = vpn
            self._server_lbl.setText(f"{vpn.name}\n{vpn.ip}")
            self.vpn_manager.connect_vpn(vpn)

    def _get_selected_vpn(self) -> Optional[SavedVPN]:
        rows = self._table.selectionModel().selectedRows()
        if rows:
            item = self._table.item(rows[0].row(), 2)   # Name column
            if item:
                return self.config.get_vpn(item.data(Qt.ItemDataRole.UserRole))
        return self.config.vpns[0] if self.config.vpns else None

    def _toggle_auto_connect(self, enabled: bool):
        self.config.auto_connect.enabled = enabled
        self.config.save()
        self._auto_lbl.setText("Enabled" if enabled else "Disabled")

    def _add_vpn(self):
        dlg = AddVPNDialog(self)
        if dlg.exec() and dlg.result_vpn:
            if self.config.add_vpn(dlg.result_vpn):
                self._refresh_table()
                self._sb.showMessage(f"Added: {dlg.result_vpn.name}")
            else:
                QMessageBox.information(
                    self, "Already Exists",
                    f"A VPN with IP {dlg.result_vpn.ip} is already in your list."
                )

    def _open_browser(self):
        dlg = VPNGateBrowser(self)
        dlg.servers_added.connect(self._on_servers_added)
        dlg.exec()

    @pyqtSlot(list)
    def _on_servers_added(self, vpns: list):
        added = sum(1 for v in vpns if self.config.add_vpn(v))
        self._refresh_table()
        self._sb.showMessage(f"Added {added} server(s)")

    def _remove_selected(self):
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        if QMessageBox.question(
            self, "Remove", f"Remove {len(rows)} selected VPN(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) != QMessageBox.StandardButton.Yes:
            return
        for row_idx in rows:
            item = self._table.item(row_idx.row(), 2)   # Name column
            if item:
                self.config.remove_vpn(item.data(Qt.ItemDataRole.UserRole))
        self._refresh_table()

    def _ctx_menu(self, pos):
        menu = QMenu(self)
        menu.addAction("Connect", self._connect_selected)
        menu.addAction("Remove", self._remove_selected)
        menu.exec(self._table.viewport().mapToGlobal(pos))

    def open_settings_with_hint(self, hint: str = ""):
        dlg = SettingsDialog(self.config, self, hint=hint)
        if dlg.exec():
            self.vpn_manager.refresh_paths()   # reload exe paths in dispatcher
            self.auto_manager.config = self.config.auto_connect
            self._auto_cb.setChecked(self.config.auto_connect.enabled)
            self._tick_clock()  # immediately refresh tz clock

    def _open_settings(self):
        self.open_settings_with_hint()

    # ══════════════════════════════════════════════════════════════════════
    #  Close
    # ══════════════════════════════════════════════════════════════════════

    def closeEvent(self, event):
        if self.vpn_manager.is_connected():
            if QMessageBox.question(
                self, "Quit",
                "You are connected to a VPN. Disconnect and quit?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) == QMessageBox.StandardButton.No:
                event.ignore()
                return
            self.vpn_manager.disconnect()
        self.config.save()
        event.accept()
