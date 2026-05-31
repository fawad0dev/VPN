import ctypes
import os
import sys

# Allow running from the project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMessageBox

from src.config import AppConfig
from src.ui.main_window import MainWindow
from src.vpn_manager import OpenVPNManager


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("VPN Client")
    app.setOrganizationName("VPNClient")

    config = AppConfig()

    # Auto-detect OpenVPN path if not yet configured / found on disk
    if not os.path.exists(config.openvpn_path):
        found = OpenVPNManager.find_openvpn()
        if found:
            config.openvpn_path = found
        # If still not found we'll prompt from inside the main window (see below)
    # Warn if not running as admin (needed on Windows for TAP interface)
    if os.name == "nt":
        try:
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            is_admin = False

        if not is_admin:
            QMessageBox.information(
                None,
                "Administrator Recommended",
                "VPN Client works best when run as Administrator.\n\n"
                "Right-click the application and choose 'Run as administrator' "
                "to avoid OpenVPN permission errors.",
            )

    window = MainWindow(config)
    window.show()

    # If OpenVPN still not found, open Settings immediately so the user can set the path
    if not os.path.exists(config.openvpn_path):
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(
            300,
            lambda: window.open_settings_with_hint(
                "⚠  OpenVPN Community Edition was not found.\n\n"
                "OpenVPN Connect is NOT compatible — it does not include a command-line openvpn.exe.\n\n"
                "Please download and install OpenVPN Community Edition:\n"
                "  https://openvpn.net/community-downloads/\n\n"
                "Then set the path to:\n"
                r"  C:\Program Files\OpenVPN\bin\openvpn.exe"
            ),
        )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
