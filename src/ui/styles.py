DARK_THEME = """
/* ── Base ─────────────────────────────────────────────────────────────── */
QMainWindow, QDialog {
    background-color: #12121e;
    color: #e0e0e0;
}
QWidget {
    background-color: #12121e;
    color: #e0e0e0;
    font-family: 'Segoe UI', Arial, sans-serif;
    font-size: 13px;
}

/* ── Buttons ──────────────────────────────────────────────────────────── */
QPushButton {
    background-color: #1e1e3a;
    color: #e0e0e0;
    border: 1px solid #2d2d5a;
    border-radius: 6px;
    padding: 7px 15px;
    font-weight: 500;
}
QPushButton:hover  { background-color: #2d2d5a; border-color: #e94560; }
QPushButton:pressed { background-color: #e94560; color: #fff; }
QPushButton:disabled { color: #555; border-color: #222; }

QPushButton#primaryBtn {
    background-color: #e94560;
    color: #fff;
    border: none;
    font-weight: bold;
    font-size: 14px;
    padding: 10px 20px;
    border-radius: 8px;
}
QPushButton#primaryBtn:hover   { background-color: #c7304a; }
QPushButton#primaryBtn:pressed { background-color: #a52040; }

/* ── Tables ───────────────────────────────────────────────────────────── */
QTableWidget {
    background-color: #1a1a2e;
    alternate-background-color: #16163a;
    gridline-color: #2a2a4a;
    border: 1px solid #2a2a4a;
    border-radius: 4px;
    selection-background-color: #3a1a3a;
    selection-color: #fff;
    outline: none;
}
QTableWidget::item { padding: 4px 8px; }
QTableWidget::item:selected { background-color: #e94560; color: #fff; }

QHeaderView::section {
    background-color: #0e0e28;
    color: #ccc;
    padding: 7px 8px;
    border: none;
    border-right: 1px solid #2a2a4a;
    border-bottom: 1px solid #2a2a4a;
    font-weight: bold;
    font-size: 12px;
}
QHeaderView::section:hover { background-color: #e94560; color: #fff; }
QHeaderView::section:pressed { background-color: #c7304a; }

/* ── Inputs ───────────────────────────────────────────────────────────── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QTextEdit {
    background-color: #1e1e3a;
    color: #e0e0e0;
    border: 1px solid #2d2d5a;
    border-radius: 4px;
    padding: 6px;
}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus,
QComboBox:focus, QTextEdit:focus { border-color: #e94560; }

QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background-color: #1e1e3a;
    color: #e0e0e0;
    selection-background-color: #e94560;
}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {
    background-color: #2d2d5a;
    border: none;
}

/* ── Tabs ─────────────────────────────────────────────────────────────── */
QTabWidget::pane { border: 1px solid #2a2a4a; background-color: #1a1a2e; border-radius: 4px; }
QTabBar::tab {
    background-color: #12121e;
    color: #aaa;
    padding: 8px 18px;
    border: 1px solid #2a2a4a;
    border-bottom: none;
    border-radius: 4px 4px 0 0;
    margin-right: 2px;
}
QTabBar::tab:selected { background-color: #1a1a2e; color: #e94560; font-weight: bold; }
QTabBar::tab:hover    { color: #e0e0e0; }

/* ── ScrollBars ───────────────────────────────────────────────────────── */
QScrollBar:vertical   { background: #1a1a2e; width: 8px; margin: 0; }
QScrollBar:horizontal { background: #1a1a2e; height: 8px; margin: 0; }
QScrollBar::handle:vertical, QScrollBar::handle:horizontal {
    background: #2d2d5a; border-radius: 4px; min-height: 20px; min-width: 20px;
}
QScrollBar::handle:vertical:hover, QScrollBar::handle:horizontal:hover {
    background: #e94560;
}
QScrollBar::add-line, QScrollBar::sub-line { height: 0; width: 0; }

/* ── GroupBox ─────────────────────────────────────────────────────────── */
QGroupBox {
    border: 1px solid #2d2d5a;
    border-radius: 6px;
    margin-top: 14px;
    padding: 8px 6px;
    color: #bbb;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: #e94560;
}

/* ── CheckBox ─────────────────────────────────────────────────────────── */
QCheckBox { color: #e0e0e0; spacing: 8px; }
QCheckBox::indicator {
    width: 17px; height: 17px;
    border: 1px solid #2d2d5a;
    border-radius: 3px;
    background: #1e1e3a;
}
QCheckBox::indicator:checked  { background: #e94560; border-color: #e94560; }
QCheckBox::indicator:hover    { border-color: #e94560; }

/* ── ProgressBar ──────────────────────────────────────────────────────── */
QProgressBar {
    border: 1px solid #2d2d5a; border-radius: 3px;
    background: #1e1e3a; text-align: center; color: #fff; height: 6px;
}
QProgressBar::chunk { background: #e94560; border-radius: 2px; }

/* ── Splitter ─────────────────────────────────────────────────────────── */
QSplitter::handle { background: #2a2a4a; }
QSplitter::handle:horizontal { width: 1px; }
QSplitter::handle:vertical   { height: 1px; }

/* ── Status bar ───────────────────────────────────────────────────────── */
QStatusBar { background: #0e0e28; color: #666; font-size: 11px; }
QStatusBar::item { border: none; }

/* ── ToolTip ──────────────────────────────────────────────────────────── */
QToolTip {
    background: #1e1e3a; color: #e0e0e0;
    border: 1px solid #2d2d5a; padding: 4px 6px;
}

/* ── Left panel ───────────────────────────────────────────────────────── */
#leftPanel { background-color: #0e0e28; }

/* ── Log ──────────────────────────────────────────────────────────────── */
QTextEdit#logView {
    background: #080814;
    color: #55cc77;
    font-family: Consolas, 'Courier New', monospace;
    font-size: 11px;
    border: 1px solid #1a1a2e;
    border-radius: 4px;
}

/* ── Dialogs ──────────────────────────────────────────────────────────── */
QDialogButtonBox QPushButton {
    min-width: 80px;
    padding: 7px 15px;
}
"""
