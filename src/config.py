import json
import os
from typing import List, Optional

from .auto_connect import AutoConnectConfig
from .models import SavedVPN

APP_DIR = os.path.join(
    os.environ.get('APPDATA', os.path.expanduser('~')),
    'VPNClient'
)


class AppConfig:
    def __init__(self):
        os.makedirs(APP_DIR, exist_ok=True)
        self._config_file = os.path.join(APP_DIR, 'config.json')
        self._vpns_file = os.path.join(APP_DIR, 'vpns.json')

        self._data: dict = {}
        self._vpns: List[SavedVPN] = []
        self.auto_connect = AutoConnectConfig()

        self._load()

    # ------------------------------------------------------------------ load/save

    def _load(self):
        if os.path.exists(self._config_file):
            try:
                with open(self._config_file, 'r', encoding='utf-8') as fh:
                    self._data = json.load(fh)
            except Exception:
                self._data = {}

        if os.path.exists(self._vpns_file):
            try:
                with open(self._vpns_file, 'r', encoding='utf-8') as fh:
                    self._vpns = [SavedVPN.from_dict(v) for v in json.load(fh)]
            except Exception:
                self._vpns = []

        if 'auto_connect' in self._data:
            self.auto_connect = AutoConnectConfig.from_dict(self._data['auto_connect'])

    def save(self):
        self._data['auto_connect'] = self.auto_connect.to_dict()
        with open(self._config_file, 'w', encoding='utf-8') as fh:
            json.dump(self._data, fh, indent=2)
        with open(self._vpns_file, 'w', encoding='utf-8') as fh:
            json.dump([v.to_dict() for v in self._vpns], fh, indent=2)

    # ------------------------------------------------------------------ generic kv

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self.save()

    # ------------------------------------------------------------------ openvpn path

    @property
    def openvpn_path(self) -> str:
        return self._data.get('openvpn_path', 'openvpn')

    @openvpn_path.setter
    def openvpn_path(self, value: str):
        self._data['openvpn_path'] = value
        self.save()

    # ------------------------------------------------------------------ extra protocol paths

    @property
    def wireguard_path(self) -> str:
        return self._data.get('wireguard_path', 'wireguard')

    @wireguard_path.setter
    def wireguard_path(self, value: str):
        self._data['wireguard_path'] = value
        self.save()

    @property
    def sslocal_path(self) -> str:
        return self._data.get('sslocal_path', 'ss-local')

    @sslocal_path.setter
    def sslocal_path(self, value: str):
        self._data['sslocal_path'] = value
        self.save()

    @property
    def v2ray_path(self) -> str:
        return self._data.get('v2ray_path', 'v2ray')

    @v2ray_path.setter
    def v2ray_path(self, value: str):
        self._data['v2ray_path'] = value
        self.save()

    @property
    def xray_path(self) -> str:
        return self._data.get('xray_path', 'xray')

    @xray_path.setter
    def xray_path(self, value: str):
        self._data['xray_path'] = value
        self.save()

    # ------------------------------------------------------------------ timezone

    @property
    def timezone(self) -> str:
        return self._data.get('timezone', 'UTC+00:00')

    @timezone.setter
    def timezone(self, value: str):
        self._data['timezone'] = value
        self.save()

    # ------------------------------------------------------------------ vpn list

    @property
    def vpns(self) -> List[SavedVPN]:
        return self._vpns

    def add_vpn(self, vpn: SavedVPN) -> bool:
        if any(v.ip == vpn.ip for v in self._vpns):
            return False
        self._vpns.append(vpn)
        self.save()
        return True

    def remove_vpn(self, vpn_id: str):
        self._vpns = [v for v in self._vpns if v.id != vpn_id]
        self.save()

    def get_vpn(self, vpn_id: str) -> Optional[SavedVPN]:
        return next((v for v in self._vpns if v.id == vpn_id), None)
