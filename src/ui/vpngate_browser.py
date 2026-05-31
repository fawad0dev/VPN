import uuid
from datetime import datetime
from typing import List, Optional

from PyQt6.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDoubleSpinBox, QFrame,
    QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox,
    QProgressBar, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from ..models import SavedVPN, VPNGateServer
from ..vpngate_api import VPNGateFetcher
from .styles import DARK_THEME

# (display name, attribute on VPNGateServer)
COLUMNS = [
    ("Flag",        "flag"),
    ("Country",     "country_long"),
    ("IP",          "ip"),
    ("Score",       "score"),
    ("Ping (ms)",   "ping"),
    ("Speed (Mbps)","speed_mbps"),
    ("Sessions",    "num_vpn_sessions"),
    ("Uptime (h)",  "uptime_hours"),
    ("Users",       "total_users"),
    ("Traffic (GB)","total_traffic_gb"),
    ("Logs",        "log_type"),
    ("Operator",    "operator"),
    ("Hostname",    "hostname"),
]

COL_WIDTHS = [36, 140, 120, 80, 80, 110, 80, 90, 80, 100, 70, 160, 160]


class VPNGateBrowser(QDialog):
    servers_added = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Browse VPNGate Servers")
        self.setMinimumSize(1200, 680)
        self.resize(1400, 780)
        self.setStyleSheet(DARK_THEME)

        self._all: List[VPNGateServer] = []
        self._shown: List[VPNGateServer] = []
        self._sort_col = 3          # Score by default
        self._sort_asc = False
        self._fetcher: Optional[VPNGateFetcher] = None

        self._build_ui()
        self._fetch()

    # ══════════════════════════════════════════════════════════════════════
    #  UI
    # ══════════════════════════════════════════════════════════════════════

    def _build_ui(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        # ── Header row
        hr = QHBoxLayout()
        title = QLabel("🌐  VPNGate Server Browser")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: #e94560;")
        hr.addWidget(title)
        hr.addStretch()
        self._count_lbl = QLabel("—")
        self._count_lbl.setStyleSheet("color: #666;")
        hr.addWidget(self._count_lbl)
        lay.addLayout(hr)

        # ── Progress
        self._pbar = QProgressBar()
        self._pbar.setRange(0, 0)
        self._pbar.setFixedHeight(4)
        self._pbar.setVisible(False)
        lay.addWidget(self._pbar)

        self._plbl = QLabel("")
        self._plbl.setStyleSheet("color: #555; font-size: 11px;")
        lay.addWidget(self._plbl)

        # ── Filter bar
        lay.addWidget(self._build_filter_bar())

        # ── Table
        self._table = QTableWidget()
        self._setup_table()
        lay.addWidget(self._table, 1)

        # ── Bottom toolbar
        bt = QHBoxLayout()
        self._sel_lbl = QLabel("0 selected")
        self._sel_lbl.setStyleSheet("color: #666;")
        bt.addWidget(self._sel_lbl)
        bt.addStretch()

        ref_btn = QPushButton("🔄 Refresh")
        ref_btn.clicked.connect(self._fetch)
        bt.addWidget(ref_btn)

        sa_btn = QPushButton("Select All")
        sa_btn.clicked.connect(self._table.selectAll)
        bt.addWidget(sa_btn)

        cs_btn = QPushButton("Clear Selection")
        cs_btn.clicked.connect(self._table.clearSelection)
        bt.addWidget(cs_btn)

        self._add_btn = QPushButton("➕  Add Selected to My VPNs")
        self._add_btn.setObjectName("primaryBtn")
        self._add_btn.setEnabled(False)
        self._add_btn.clicked.connect(self._add_selected)
        bt.addWidget(self._add_btn)

        lay.addLayout(bt)

    def _build_filter_bar(self) -> QWidget:
        bar = QWidget()
        bar.setStyleSheet(
            "background:#0e0e28; border:1px solid #2a2a4a; border-radius:6px; padding:4px;"
        )
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(8, 6, 8, 6)
        lay.setSpacing(8)

        def add_label(text):
            l = QLabel(text)
            l.setStyleSheet("color:#888; font-size:12px;")
            lay.addWidget(l)

        add_label("Country:")
        self._f_country = QLineEdit()
        self._f_country.setPlaceholderText("Filter…")
        self._f_country.setFixedWidth(130)
        self._f_country.textChanged.connect(self._apply_filters)
        lay.addWidget(self._f_country)

        add_label("Max Ping:")
        self._f_ping = QSpinBox()
        self._f_ping.setRange(0, 9999)
        self._f_ping.setValue(9999)
        self._f_ping.setSuffix(" ms")
        self._f_ping.setFixedWidth(90)
        self._f_ping.valueChanged.connect(self._apply_filters)
        lay.addWidget(self._f_ping)

        add_label("Min Speed:")
        self._f_speed = QDoubleSpinBox()
        self._f_speed.setRange(0, 10000)
        self._f_speed.setValue(0)
        self._f_speed.setSuffix(" Mbps")
        self._f_speed.setFixedWidth(110)
        self._f_speed.valueChanged.connect(self._apply_filters)
        lay.addWidget(self._f_speed)

        add_label("Min Score:")
        self._f_score = QSpinBox()
        self._f_score.setRange(0, 100_000_000)
        self._f_score.setValue(0)
        self._f_score.setSingleStep(10000)
        self._f_score.setFixedWidth(100)
        self._f_score.valueChanged.connect(self._apply_filters)
        lay.addWidget(self._f_score)

        add_label("Logs:")
        self._f_logs = QComboBox()
        self._f_logs.addItems(["All", "No Logging (2)", "1 Week (1)"])
        self._f_logs.setFixedWidth(130)
        self._f_logs.currentIndexChanged.connect(self._apply_filters)
        lay.addWidget(self._f_logs)

        add_label("Operator:")
        self._f_operator = QLineEdit()
        self._f_operator.setPlaceholderText("Search…")
        self._f_operator.setFixedWidth(130)
        self._f_operator.textChanged.connect(self._apply_filters)
        lay.addWidget(self._f_operator)

        lay.addStretch()

        reset = QPushButton("Reset")
        reset.setFixedWidth(60)
        reset.setStyleSheet("padding: 4px 8px;")
        reset.clicked.connect(self._reset_filters)
        lay.addWidget(reset)

        return bar

    def _setup_table(self):
        self._table.setColumnCount(len(COLUMNS))
        self._table.setHorizontalHeaderLabels([c[0] for c in COLUMNS])
        self._table.setAlternatingRowColors(True)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._table.verticalHeader().setVisible(False)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        hdr = self._table.horizontalHeader()
        hdr.setSortIndicatorShown(True)
        hdr.sectionClicked.connect(self._on_header_clicked)
        hdr.setSortIndicator(self._sort_col, Qt.SortOrder.DescendingOrder)

        for i, w in enumerate(COL_WIDTHS):
            self._table.setColumnWidth(i, w)

        self._table.itemSelectionChanged.connect(self._on_selection_changed)

    # ══════════════════════════════════════════════════════════════════════
    #  Fetch & parse
    # ══════════════════════════════════════════════════════════════════════

    def _fetch(self):
        if self._fetcher and self._fetcher.isRunning():
            return
        self._pbar.setVisible(True)
        self._plbl.setText("Fetching from VPNGate…")
        self._count_lbl.setText("Loading…")
        self._fetcher = VPNGateFetcher()
        self._fetcher.servers_fetched.connect(self._on_fetched)
        self._fetcher.error_occurred.connect(self._on_fetch_error)
        self._fetcher.progress.connect(self._plbl.setText)
        self._fetcher.start()

    @pyqtSlot(list)
    def _on_fetched(self, servers: List[VPNGateServer]):
        self._all = servers
        self._pbar.setVisible(False)
        self._plbl.setText(f"Loaded {len(servers)} servers from VPNGate")
        self._apply_filters()

    @pyqtSlot(str)
    def _on_fetch_error(self, err: str):
        self._pbar.setVisible(False)
        self._plbl.setText(f"Error: {err}")
        QMessageBox.warning(self, "Fetch Error", err)

    # ══════════════════════════════════════════════════════════════════════
    #  Filter / sort / populate
    # ══════════════════════════════════════════════════════════════════════

    def _apply_filters(self):
        country = self._f_country.text().strip().lower()
        max_ping = self._f_ping.value()
        min_speed = self._f_speed.value()
        min_score = self._f_score.value()
        log_idx = self._f_logs.currentIndex()   # 0=All, 1=No Logging, 2=1Week
        operator = self._f_operator.text().strip().lower()

        result = []
        for s in self._all:
            if country and country not in s.country_long.lower():
                continue
            if s.ping > max_ping and s.ping > 0:
                continue
            if s.speed_mbps < min_speed:
                continue
            if s.score < min_score:
                continue
            if log_idx == 1 and s.log_type != "2":
                continue
            if log_idx == 2 and s.log_type != "1":
                continue
            if operator and operator not in s.operator.lower():
                continue
            result.append(s)

        self._shown = result
        self._sort_inplace()
        self._populate()
        self._count_lbl.setText(
            f"{len(result):,} / {len(self._all):,} servers"
        )

    def _on_header_clicked(self, col: int):
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = col not in (3, 5)  # Score/Speed default descending

        order = Qt.SortOrder.AscendingOrder if self._sort_asc else Qt.SortOrder.DescendingOrder
        self._table.horizontalHeader().setSortIndicator(col, order)
        self._sort_inplace()
        self._populate()

    def _sort_inplace(self):
        if not self._shown:
            return
        attr = COLUMNS[self._sort_col][1]
        try:
            self._shown.sort(
                key=lambda s: getattr(s, attr) or 0,
                reverse=not self._sort_asc,
            )
        except TypeError:
            self._shown.sort(
                key=lambda s: str(getattr(s, attr, "")),
                reverse=not self._sort_asc,
            )

    def _populate(self):
        self._table.setUpdatesEnabled(False)
        self._table.setRowCount(0)
        self._table.setRowCount(len(self._shown))

        for row, s in enumerate(self._shown):
            vals = [
                s.flag,
                s.country_long,
                s.ip,
                str(s.score),
                str(s.ping),
                f"{s.speed_mbps:.2f}",
                str(s.num_vpn_sessions),
                f"{s.uptime_hours:.1f}",
                str(s.total_users),
                f"{s.total_traffic_gb:.2f}",
                s.log_type,
                s.operator[:45],
                s.hostname,
            ]
            for col, val in enumerate(vals):
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

                # Colour-code ping & speed
                if col == 4 and s.ping:
                    item.setForeground(QColor(
                        "#27ae60" if s.ping < 50 else
                        "#f39c12" if s.ping < 150 else "#e74c3c"
                    ))
                elif col == 5:
                    item.setForeground(QColor(
                        "#27ae60" if s.speed_mbps >= 50 else
                        "#f39c12" if s.speed_mbps >= 10 else "#e74c3c"
                    ))

                self._table.setItem(row, col, item)

        self._table.setUpdatesEnabled(True)

    # ══════════════════════════════════════════════════════════════════════
    #  Selection & add
    # ══════════════════════════════════════════════════════════════════════

    def _on_selection_changed(self):
        n = len(self._table.selectionModel().selectedRows())
        self._sel_lbl.setText(f"{n:,} selected")
        self._add_btn.setEnabled(n > 0)

    def _reset_filters(self):
        self._f_country.clear()
        self._f_ping.setValue(9999)
        self._f_speed.setValue(0)
        self._f_score.setValue(0)
        self._f_logs.setCurrentIndex(0)
        self._f_operator.clear()

    def _add_selected(self):
        rows = sorted({i.row() for i in self._table.selectionModel().selectedRows()})
        vpns: List[SavedVPN] = []
        for row in rows:
            if row >= len(self._shown):
                continue
            s = self._shown[row]
            try:
                cfg = s.get_ovpn_config()
            except Exception as exc:
                self._plbl.setText(f"Skipped {s.ip}: {exc}")
                continue
            vpns.append(SavedVPN(
                id=str(uuid.uuid4()),
                name=f"{s.flag} {s.country_long} — {s.ip}",
                ip=s.ip,
                country=s.country_long,
                ovpn_config=cfg,
                added_at=datetime.now().isoformat(),
                source="vpngate",
                hostname=s.hostname,
                ping=s.ping,
                speed=s.speed,
            ))

        if vpns:
            self.servers_added.emit(vpns)
            QMessageBox.information(
                self, "Added",
                f"Added {len(vpns)} server(s) to your VPN list."
            )
            self.accept()
