import base64
from dataclasses import dataclass, field
from typing import Optional


def country_flag(code: str) -> str:
    """Convert ISO country code to flag emoji."""
    if not code or len(code) != 2:
        return "🌐"
    try:
        return chr(0x1F1E0 + ord(code[0].upper()) - ord('A')) + \
               chr(0x1F1E0 + ord(code[1].upper()) - ord('A'))
    except Exception:
        return "🌐"


@dataclass
class VPNGateServer:
    hostname: str
    ip: str
    score: int
    ping: int
    speed: int          # bps
    country_long: str
    country_short: str
    num_vpn_sessions: int
    uptime: int         # seconds
    total_users: int
    total_traffic: int  # bytes
    log_type: str
    operator: str
    message: str
    ovpn_config_base64: str

    @property
    def speed_mbps(self) -> float:
        return self.speed / 1_000_000

    @property
    def uptime_hours(self) -> float:
        return self.uptime / 3600

    @property
    def total_traffic_gb(self) -> float:
        return self.total_traffic / 1_073_741_824

    @property
    def flag(self) -> str:
        return country_flag(self.country_short)

    def get_ovpn_config(self) -> str:
        return base64.b64decode(self.ovpn_config_base64).decode('utf-8', errors='replace')

    @classmethod
    def from_csv_row(cls, row: list) -> 'VPNGateServer':
        def safe_int(val, default=0):
            try:
                return int(str(val).strip())
            except (ValueError, TypeError):
                return default

        return cls(
            hostname=row[0].strip() if len(row) > 0 else '',
            ip=row[1].strip() if len(row) > 1 else '',
            score=safe_int(row[2] if len(row) > 2 else 0),
            ping=safe_int(row[3] if len(row) > 3 else 0),
            speed=safe_int(row[4] if len(row) > 4 else 0),
            country_long=row[5].strip() if len(row) > 5 else '',
            country_short=row[6].strip() if len(row) > 6 else '',
            num_vpn_sessions=safe_int(row[7] if len(row) > 7 else 0),
            uptime=safe_int(row[8] if len(row) > 8 else 0),
            total_users=safe_int(row[9] if len(row) > 9 else 0),
            total_traffic=safe_int(row[10] if len(row) > 10 else 0),
            log_type=row[11].strip() if len(row) > 11 else '',
            operator=row[12].strip() if len(row) > 12 else '',
            message=row[13].strip() if len(row) > 13 else '',
            ovpn_config_base64=row[14].strip() if len(row) > 14 else '',
        )


@dataclass
class SavedVPN:
    id: str
    name: str
    ip: str
    country: str
    ovpn_config: str        # generic config payload (ovpn text / wg conf / json / etc.)
    added_at: str
    source: str = "vpngate"
    hostname: str = ""
    ping: int = 0
    speed: int = 0
    protocol: str = "openvpn"          # openvpn | wireguard | windows | shadowsocks | v2ray | xray
    credentials: dict = field(default_factory=dict)   # username, password, extra params

    def to_dict(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'ip': self.ip,
            'country': self.country,
            'ovpn_config': self.ovpn_config,
            'added_at': self.added_at,
            'source': self.source,
            'hostname': self.hostname,
            'ping': self.ping,
            'speed': self.speed,
            'protocol': self.protocol,
            'credentials': self.credentials,
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'SavedVPN':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
