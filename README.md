<div align="center">
  <img src="Resources/main.png" alt="VPN Client Logo" width="300">
</div>

# VPN Client

A full-featured desktop VPN client built with **Python + PyQt6**, inspired by [amnezia-vpn](https://github.com/amnezia-vpn/amnezia-client).  
Supports multiple VPN protocols, full VPNGate server browsing, automatic failover, and cross-platform timezone management.

---

## Features

### 🌐 VPNGate Browser
Fetches all public servers from [VPNGate](https://www.vpngate.net) with:
- Sort by any column (country, ping, speed, score, traffic, uptime, …)
- Filter by country, max ping, min speed, min score, log policy, operator
- Color-coded ping and speed values
- Multi-select with `Ctrl+Click` / `Shift+Click`
- One-click **"Add Selected to My VPNs"**

### 📋 My VPN List
- Saved servers persisted between sessions
- Protocol badge (emoji) per server: OpenVPN, WireGuard, IKEv2/L2TP, Shadowsocks, V2Ray, Xray
- Double-click any row to connect
- Remove selected servers

### 🔌 Multi-Protocol Support

| Protocol | How it connects | Notes |
|---|---|---|
| **OpenVPN** | `openvpn.exe --config` | Community Edition required (not OpenVPN Connect) |
| **WireGuard** | `wireguard.exe /installtunnel` | Requires Administrator |
| **Windows VPN** (IKEv2/L2TP/SSTP) | PowerShell `Add-VpnConnection` + `rasdial` | Windows built-in |
| **Shadowsocks** | `ss-local.exe -c config.json` | Local SOCKS5 proxy on configured port |
| **V2Ray** | `v2ray.exe run -config` | Watches stdout for "listening" |
| **Xray** | `xray.exe run -config` | Same engine as V2Ray |

### ⚡ Auto-Connect / Failover
- Automatically switches to the next server when a connection fails, drops, or times out
- **Strategies:** `sequential`, `best_ping`, `random`
- Configurable: connection timeout, retry delay, retries per server
- Periodic **health-check** (TCP socket probe, default 8.8.8.8:53)
- **Stop/Disconnect** button always visible during connecting or auto-connect

### 🕐 Timezone (System Clock)
- Pick UTC offset via dropdown or interactive world map
- **Apply to System Clock** — actually changes the OS timezone:
  - **Windows:** `tzutil /s "..."` with UAC elevation fallback
  - **Linux:** `timedatectl set-timezone <IANA>`
  - **macOS:** `systemsetup -settimezone <IANA>`
- Sidebar live clock reflects selected offset

### ⚙️ Settings
- **General** — OpenVPN path, system timezone
- **Protocols** — Exe paths for WireGuard, ss-local, V2Ray, Xray
- **Auto-Connect** — All failover and health-check options

---

## Requirements

| Component | Version | Notes |
|---|---|---|
| Python | 3.10+ | [python.org](https://www.python.org/downloads/) |
| PyQt6 | 6.4+ | Installed automatically via `requirements.txt` |
| OpenVPN Community | 2.x / 3.x | [openvpn.net](https://openvpn.net/community-downloads/) — **not** OpenVPN Connect |
| WireGuard *(optional)* | any | [wireguard.com](https://www.wireguard.com/install/) |
| shadowsocks-libev *(optional)* | any | `ss-local.exe` |
| V2Ray / Xray *(optional)* | any | [v2fly.org](https://github.com/v2fly/v2ray-core/releases) |
| **Administrator** | — | Required on Windows for TAP/TUN and WireGuard tunnel |

---

## Setup

Dependencies are installed automatically by the run scripts. To install manually:

```bash
pip install -r requirements.txt
```

---

## Running

### Windows
```bat
run(win).bat
```
> Right-click → **Run as administrator** to avoid OpenVPN/WireGuard permission errors.

### Linux / macOS
```bash
chmod +x "run(linux-mac).sh"
./"run(linux-mac).sh"
```

### Any platform (PowerShell Core 7+)
```powershell
pwsh "run(all-powershell).ps1"
```

All run scripts automatically:
- Check for Python 3.10+
- Create a `.venv` virtual environment if it doesn't exist
- Install / update `requirements.txt` dependencies
- Launch the application

---

## Project Structure

```
VPN/
├── main.py                        # Entry point — admin check, auto-detect OpenVPN
├── requirements.txt               # PyQt6, requests
├── run(win).bat                   # Windows launcher
├── run(linux-mac).sh              # Linux / macOS launcher
├── run(all-powershell).ps1        # Cross-platform PowerShell launcher
└── src/
    ├── models.py                  # VPNGateServer, SavedVPN dataclasses
    ├── vpngate_api.py             # Async VPNGate fetcher (QThread)
    ├── vpn_manager.py             # Legacy OpenVPN wrapper (backward compat)
    ├── vpn_dispatcher.py          # Routes connect() to correct protocol manager
    ├── auto_connect.py            # Auto-connect / failover engine
    ├── config.py                  # JSON settings persistence
    ├── vpn_protocols/
    │   ├── base.py                # BaseVPNManager + ConnectionState enum
    │   ├── openvpn.py             # OpenVPN protocol
    │   ├── wireguard.py           # WireGuard protocol
    │   ├── windows_vpn.py         # Windows IKEv2 / L2TP / SSTP
    │   ├── shadowsocks.py         # Shadowsocks (ss-local)
    │   └── v2ray.py               # V2Ray and Xray
    └── ui/
        ├── main_window.py         # Main application window
        ├── vpngate_browser.py     # VPNGate server browser dialog
        ├── add_vpn_dialog.py      # Add VPN dialog (per-protocol forms)
        ├── settings_dialog.py     # Settings dialog (3 tabs)
        ├── timezone_map.py        # Interactive world map timezone picker
        └── styles.py              # Dark theme QSS stylesheet
```

---

## Settings & Data Files

Saved to `%APPDATA%\VPNClient\` (Windows) or `~/.config/VPNClient/` (Linux/macOS):

| File | Contents |
|---|---|
| `config.json` | OpenVPN/WireGuard/V2Ray paths, timezone, auto-connect options |
| `vpns.json` | Your saved VPN server list (protocol + credentials per server) |

---

## Auto-Connect Options

| Setting | Default | Description |
|---|---|---|
| Strategy | `sequential` | Order to try servers: `sequential`, `best_ping`, `random` |
| Connection timeout | 30 s | Give up connecting after this long |
| Retry delay | 5 s | Wait before retrying / switching server |
| Max retries per server | 2 | Before moving to the next server |
| Health check interval | 30 s | How often to probe if the VPN is alive |
| Health check host | `8.8.8.8` | TCP destination for the health probe |
| Health check port | `53` | TCP port for the health probe |
| Health check timeout | 5 s | Socket connect timeout for health probe |
