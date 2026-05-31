"""Interactive world-map timezone picker."""
import re
from datetime import datetime, timezone as dt_timezone, timedelta
from typing import Optional

from PyQt6.QtCore import Qt, QPointF, pyqtSignal
from PyQt6.QtGui import (
    QBrush, QColor, QFont, QPainter, QPen, QPolygonF,
)
from PyQt6.QtWidgets import (
    QDialog, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QVBoxLayout, QWidget,
)

from .styles import DARK_THEME

# ── UTC offset list (label, total_minutes) ─────────────────────────────────
def _build_offsets():
    out = []
    for m in range(-720, 841, 30):
        sign = '+' if m >= 0 else '-'
        h, mm = divmod(abs(m), 60)
        out.append((f"UTC{sign}{h:02d}:{mm:02d}", m))
    return out

_UTC_OFFSETS = _build_offsets()          # [(label, minutes), ...]
_OFFSET_LABELS = [l for l, _ in _UTC_OFFSETS]

# ── Cities per offset ───────────────────────────────────────────────────────
_CITIES = {
    "UTC-12:00": "Baker Island",
    "UTC-11:00": "Samoa, Niue",
    "UTC-10:00": "Honolulu, Cook Islands",
    "UTC-09:30": "Marquesas Islands",
    "UTC-09:00": "Anchorage, Alaska",
    "UTC-08:00": "Los Angeles, Vancouver, Tijuana",
    "UTC-07:00": "Denver, Phoenix, Calgary",
    "UTC-06:00": "Chicago, Mexico City, Guatemala",
    "UTC-05:00": "New York, Toronto, Bogotá, Lima",
    "UTC-04:30": "Caracas",
    "UTC-04:00": "Santiago, Halifax, Manaus",
    "UTC-03:30": "St. John's",
    "UTC-03:00": "São Paulo, Buenos Aires, Montevideo",
    "UTC-02:00": "South Georgia",
    "UTC-01:00": "Azores, Cape Verde",
    "UTC+00:00": "London, Dublin, Lisbon, Reykjavik",
    "UTC+01:00": "Paris, Berlin, Rome, Madrid, Lagos",
    "UTC+02:00": "Cairo, Athens, Kyiv, Johannesburg",
    "UTC+03:00": "Moscow, Riyadh, Nairobi, Baghdad",
    "UTC+03:30": "Tehran",
    "UTC+04:00": "Dubai, Baku, Tbilisi, Muscat",
    "UTC+04:30": "Kabul",
    "UTC+05:00": "Karachi, Tashkent, Yekaterinburg",
    "UTC+05:30": "New Delhi, Mumbai, Colombo",
    "UTC+05:45": "Kathmandu",
    "UTC+06:00": "Dhaka, Almaty, Bishkek",
    "UTC+06:30": "Yangon (Rangoon)",
    "UTC+07:00": "Bangkok, Jakarta, Ho Chi Minh City",
    "UTC+08:00": "Beijing, Singapore, Kuala Lumpur, Perth",
    "UTC+08:30": "Pyongyang",
    "UTC+08:45": "Eucla",
    "UTC+09:00": "Tokyo, Seoul, Yakutsk",
    "UTC+09:30": "Adelaide, Darwin",
    "UTC+10:00": "Sydney, Melbourne, Vladivostok",
    "UTC+10:30": "Lord Howe Island",
    "UTC+11:00": "Noumea, Honiara",
    "UTC+12:00": "Auckland, Fiji, Kamchatka",
    "UTC+12:45": "Chatham Islands",
    "UTC+13:00": "Apia, Nuku'alofa",
    "UTC+14:00": "Line Islands (Kiribati)",
}

# ── Simplified continent polygons [(lon, lat)] ─────────────────────────────
_CONTINENTS = [
    # North America
    [(-168,72),(-140,60),(-130,55),(-125,48),(-120,37),(-118,32),(-105,20),
     (-90,15),(-83,10),(-77,8),(-75,10),(-65,18),(-60,46),(-55,47),(-53,47),
     (-60,52),(-65,60),(-80,72),(-95,74),(-110,74),(-130,68),(-150,62),(-168,72)],
    # Greenland
    [(-44,83),(-20,84),(-18,76),(-22,72),(-32,70),(-44,70),(-50,65),
     (-52,70),(-48,80),(-44,83)],
    # South America
    [(-80,10),(-77,8),(-68,0),(-60,-5),(-50,-28),(-52,-33),(-58,-38),
     (-65,-55),(-67,-56),(-73,-50),(-75,-40),(-72,-30),(-70,-18),(-76,0),(-80,10)],
    # Europe
    [(-10,36),(-9,38),(-6,37),(-8,43),(-2,44),(3,44),(7,47),(15,47),
     (20,46),(24,56),(28,59),(24,64),(20,70),(15,72),(10,72),(5,62),
     (2,51),(-2,51),(-5,48),(-8,44),(-10,44),(-10,36)],
    # Scandinavia extension
    [(5,57),(5,62),(10,63),(15,70),(25,71),(30,70),(28,65),(20,60),(15,57),(5,57)],
    # Africa
    [(-18,15),(-14,10),(-5,4),(10,-5),(36,-35),(38,-26),(40,-12),
     (42,12),(45,12),(35,22),(32,32),(25,37),(12,38),(-5,35),(-15,28),(-18,15)],
    # Asia (mainland)
    [(28,72),(60,74),(100,73),(120,60),(132,50),(136,34),(120,25),
     (108,10),(103,1),(98,5),(92,22),(80,32),(68,24),(57,22),(48,12),
     (42,12),(38,36),(37,37),(26,42),(24,56),(28,60),(28,72)],
    # Indian subcontinent
    [(68,24),(80,32),(90,22),(95,20),(80,8),(70,8),(65,22),(68,24)],
    # Indochina / SE Asia peninsula
    [(98,20),(100,20),(102,22),(108,22),(108,10),(103,1),(100,4),(98,5),(98,20)],
    # Australia
    [(114,-22),(120,-20),(130,-12),(136,-12),(148,-20),(152,-24),
     (152,-32),(148,-38),(140,-38),(130,-32),(116,-34),(113,-26),(114,-22)],
    # New Zealand (rough combined)
    [(172,-34),(174,-36),(178,-37),(178,-40),(176,-42),(172,-44),
     (168,-46),(167,-46),(170,-44),(174,-43),(178,-38),(172,-34)],
    # Japan
    [(130,31),(131,34),(135,34),(136,37),(140,36),(141,40),(143,42),
     (140,44),(134,44),(130,32),(130,31)],
    # UK / Ireland
    [(-6,51),(-5,55),(-3,58),(0,58),(2,55),(2,52),(0,51),(-2,51),(-5,50),(-6,51)],
    # Iceland
    [(-24,64),(-14,64),(-13,66),(-18,66),(-24,65),(-24,64)],
    # Madagascar
    [(44,-26),(50,-16),(50,-12),(44,-12),(43,-20),(44,-26)],
    # Borneo (simplified)
    [(108,7),(117,7),(118,4),(117,0),(115,-4),(108,-4),(108,3),(108,7)],
    # Philippines (rough)
    [(118,18),(122,18),(126,8),(124,6),(122,8),(118,12),(118,18)],
    # Sri Lanka
    [(80,10),(82,10),(82,6),(80,6),(80,10)],
]


def _parse_minutes(label: str) -> Optional[int]:
    m = re.match(r'UTC([+-])(\d{2}):(\d{2})', label)
    if not m:
        return None
    sign = 1 if m.group(1) == '+' else -1
    return sign * (int(m.group(2)) * 60 + int(m.group(3)))


def _label_for_lon(lon: float) -> str:
    """Map a longitude to the nearest UTC offset label (30-min granularity)."""
    minutes = round(lon / 7.5) * 30
    minutes = max(-720, min(840, minutes))
    sign = '+' if minutes >= 0 else '-'
    h, mm = divmod(abs(minutes), 60)
    return f"UTC{sign}{h:02d}:{mm:02d}"


def _lon_center(label: str) -> float:
    mins = _parse_minutes(label)
    return (mins / 60.0) * 15.0 if mins is not None else 0.0


def _current_time_str(label: str) -> str:
    mins = _parse_minutes(label)
    if mins is None:
        return ""
    tz = dt_timezone(timedelta(minutes=mins))
    return datetime.now(tz).strftime('%H:%M')


# ── Map canvas ──────────────────────────────────────────────────────────────

class _WorldMapCanvas(QWidget):
    timezone_hovered = pyqtSignal(str)
    timezone_clicked = pyqtSignal(str)

    _BAND_COLORS = [QColor(40, 60, 105, 50), QColor(55, 75, 120, 50)]
    _LAND_FILL   = QColor(200, 196, 170, 230)
    _LAND_BORDER = QColor(160, 156, 135, 200)
    _OCEAN       = QColor(28, 55, 90)
    _EQUATOR     = QColor(90, 130, 160, 90)
    _GRID        = QColor(70, 95, 140, 50)
    _SELECTED    = QColor(39, 174, 96, 110)
    _HOVERED     = QColor(243, 156, 18, 100)
    _SEL_BORDER  = QColor("#27ae60")
    _HOV_BORDER  = QColor("#f39c12")

    def __init__(self, current_tz: str, parent=None):
        super().__init__(parent)
        self.selected = current_tz
        self._hovered: Optional[str] = None
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMinimumSize(720, 340)

    # coordinate helpers
    def _lx(self, lon: float) -> float:
        return (lon + 180.0) / 360.0 * self.width()

    def _ly(self, lat: float) -> float:
        return (90.0 - lat) / 180.0 * self.height()

    def _xl(self, x: float) -> float:
        return x / self.width() * 360.0 - 180.0

    def _band_rect(self, label: str):
        cx = _lon_center(label)
        x1 = self._lx(cx - 7.5)
        x2 = self._lx(cx + 7.5)
        return int(x1), int(x2 - x1) + 1

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        w, h = self.width(), self.height()

        # Ocean
        p.fillRect(0, 0, w, h, self._OCEAN)

        # Timezone bands
        for i, (label, _mins) in enumerate(_UTC_OFFSETS):
            bx, bw = self._band_rect(label)
            if label == self.selected:
                color = self._SELECTED
            elif label == self._hovered:
                color = self._HOVERED
            else:
                color = self._BAND_COLORS[i % 2]
            p.fillRect(bx, 0, bw, h, color)

        # Grid lines
        pen = QPen(self._GRID, 1)
        p.setPen(pen)
        for label, _mins in _UTC_OFFSETS:
            cx = _lon_center(label)
            p.drawLine(int(self._lx(cx - 7.5)), 0, int(self._lx(cx - 7.5)), h)

        # Equator
        p.setPen(QPen(self._EQUATOR, 1))
        ey = int(self._ly(0))
        p.drawLine(0, ey, w, ey)

        # Continents
        p.setPen(QPen(self._LAND_BORDER, 1))
        p.setBrush(QBrush(self._LAND_FILL))
        for shape in _CONTINENTS:
            poly = QPolygonF([QPointF(self._lx(lon), self._ly(lat)) for lon, lat in shape])
            p.drawPolygon(poly)

        # Highlight border for selected / hovered
        for label, border_color in [(self.selected, self._SEL_BORDER),
                                     (self._hovered, self._HOV_BORDER)]:
            if not label:
                continue
            bx, bw = self._band_rect(label)
            p.setPen(QPen(border_color, 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(bx, 1, bw, h - 2)

        # UTC labels along bottom
        p.setPen(QPen(QColor(180, 200, 220, 130), 1))
        font = QFont()
        font.setPixelSize(8)
        p.setFont(font)
        for label, mins in _UTC_OFFSETS:
            if mins % 60 == 0:   # only whole hours
                cx = int(self._lx(_lon_center(label)))
                text = f"{int(mins/60):+d}"
                p.drawText(cx - 10, h - 2, text)

        p.end()

    def mouseMoveEvent(self, ev):
        lon = self._xl(ev.position().x())
        tz = _label_for_lon(lon)
        if tz != self._hovered:
            self._hovered = tz
            self.timezone_hovered.emit(tz)
            self.update()

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            lon = self._xl(ev.position().x())
            tz = _label_for_lon(lon)
            self._hovered = tz   # keep hover in sync so no flicker
            self.selected = tz
            self.timezone_clicked.emit(tz)
            self.update()

    def leaveEvent(self, _):
        self._hovered = None
        # Restore info bar to the currently selected timezone
        self.timezone_hovered.emit(self.selected)
        self.update()

    def set_selected(self, tz: str):
        self.selected = tz
        self.timezone_hovered.emit(tz)
        self.update()


# ── Public dialog ───────────────────────────────────────────────────────────

class TimezoneMapDialog(QDialog):
    timezone_selected = pyqtSignal(str)

    def __init__(self, current_tz: str = "UTC+00:00", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Timezone")
        self.setMinimumSize(820, 520)
        self.setStyleSheet(DARK_THEME)
        self._selected = current_tz
        self._build_ui(current_tz)

    def _build_ui(self, current_tz: str):
        lay = QVBoxLayout(self)
        lay.setSpacing(8)
        lay.setContentsMargins(12, 12, 12, 12)

        # Search
        row = QHBoxLayout()
        row.addWidget(QLabel("🔍"))
        self._search = QLineEdit()
        self._search.setPlaceholderText(
            "Search city or offset — e.g.  'Karachi',  '+05:30',  'New York'"
        )
        self._search.textChanged.connect(self._on_search)
        row.addWidget(self._search)
        lay.addLayout(row)

        # Map
        self._map = _WorldMapCanvas(current_tz, self)
        self._map.timezone_hovered.connect(self._on_hover)
        self._map.timezone_clicked.connect(self._on_click)
        lay.addWidget(self._map, 1)

        # Info bar
        self._info = QLabel()
        self._info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._info.setMinimumHeight(54)
        self._info.setStyleSheet(
            "background:#1a1a35; border:1px solid #2a2a4a;"
            "border-radius:6px; padding:8px; font-size:13px; color:#e0e0e0;"
        )
        self._info.setWordWrap(True)
        lay.addWidget(self._info)
        self._show_info(current_tz, is_selected=True)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        ok = QPushButton("✔  Use This Timezone")
        ok.setObjectName("primaryBtn")
        ok.clicked.connect(self._accept)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        btn_row.addWidget(ok)
        btn_row.addWidget(cancel)
        lay.addLayout(btn_row)

    def _show_info(self, tz: str, is_selected: bool = False):
        cities = _CITIES.get(tz, "—")
        t = _current_time_str(tz)
        badge = "  ✔ <span style='color:#27ae60;font-size:11px;'>SELECTED</span>" if is_selected else ""
        self._info.setText(
            f"<b style='font-size:16px;color:#f0f0f0;'>{tz}</b>{badge}"
            f"  &nbsp; 🕐 <b style='font-size:15px;color:#27ae60;'>{t}</b>"
            f"<br><span style='color:#999;font-size:11px;'>{cities}</span>"
        )

    def _on_hover(self, tz: str):
        # Show hover info; if this is also the selected tz, show badge
        self._show_info(tz, is_selected=(tz == self._selected))

    def _on_click(self, tz: str):
        self._selected = tz
        self._show_info(tz, is_selected=True)

    def _on_search(self, text: str):
        q = text.strip().lower()
        if not q:
            return
        for label, _ in _UTC_OFFSETS:
            cities = _CITIES.get(label, "")
            if q in label.lower() or q in cities.lower():
                self._selected = label
                self._map.set_selected(label)
                self._show_info(label, is_selected=True)
                break

    def _accept(self):
        self.timezone_selected.emit(self._selected)
        self.accept()

    @property
    def selected_timezone(self) -> str:
        return self._selected
