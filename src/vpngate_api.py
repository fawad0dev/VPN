import csv
from typing import List

import requests
from PyQt6.QtCore import QThread, pyqtSignal

from .models import VPNGateServer

VPNGATE_URLS = [
    "http://www.vpngate.net/api/iphone/",
    "https://www.vpngate.net/api/iphone/",
]


class VPNGateFetcher(QThread):
    servers_fetched = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    progress = pyqtSignal(str)

    def run(self):
        try:
            self.progress.emit("Connecting to VPNGate…")
            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) '
                    'AppleWebKit/605.1.15'
                )
            }

            response = None
            for url in VPNGATE_URLS:
                try:
                    response = requests.get(url, headers=headers, timeout=30)
                    if response.status_code == 200:
                        break
                except requests.RequestException:
                    continue

            if not response or response.status_code != 200:
                self.error_occurred.emit("Failed to connect to VPNGate API")
                return

            self.progress.emit("Parsing server list…")
            servers = self._parse_csv(response.text)
            self.progress.emit(f"Loaded {len(servers)} servers")
            self.servers_fetched.emit(servers)

        except Exception as exc:
            self.error_occurred.emit(f"Error: {exc}")

    def _parse_csv(self, content: str) -> List[VPNGateServer]:
        servers: List[VPNGateServer] = []
        for line in content.splitlines():
            line = line.strip()
            # Skip metadata lines and the header row
            if not line or line.startswith('*') or line.startswith('#'):
                continue
            try:
                for row in csv.reader([line]):
                    if len(row) >= 15 and row[14].strip():
                        server = VPNGateServer.from_csv_row(row)
                        if server.ip and server.ovpn_config_base64:
                            servers.append(server)
            except Exception:
                continue
        return servers
