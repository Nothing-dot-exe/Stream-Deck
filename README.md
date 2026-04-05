<div align="center">

# 🎮 Stream DeckX Pro

### Transform Your Smartphone Into a Professional PC Command Center

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows-0078D6?style=for-the-badge&logo=windows&logoColor=white)](https://www.microsoft.com/windows)

**Stream DeckX Pro** is a premium, open-source alternative to the Elgato Stream Deck — built entirely in Python. It turns any smartphone into a fully-featured wireless macro pad, media controller, and app launcher with a beautiful native interface. No extra hardware required.

<br>

[Features](#-features) • [Installation](#-installation) • [Usage](#-usage) • [Architecture](#-architecture) • [Contributing](#-contributing)

</div>

---

## ⚡ Features

### 🖥️ Native Desktop Control Center
A stunning **dark-mode GUI** built with CustomTkinter, featuring a dual-panel dashboard with:
- **Live QR Code** — Scan from your phone to connect instantly. No typing IP addresses.
- **Real-time metrics** — Server status, connected device count, and connection URLs.
- **One-click controls** — Start, stop, and restart the server from a single interface.
- **System boot integration** — Toggle to auto-launch on Windows startup.

### 📱 Mobile Web Interface
A responsive PWA (Progressive Web App) optimized for every screen size and orientation:
- **App Grid** — Tap to launch or kill any desktop application from your phone.
- **Toggle Logic** — Intelligent process management. Tap once to open, tap again to close.
- **Edit Mode** — Full PC app scanner. Discovers every installed application. Toggle visibility per-app.
- **Auto-Fullscreen** — Hides the browser address bar for a true native app experience.
- **Landscape + Portrait** — Fully responsive grid layout adapts to any device or orientation.

### 🎵 Global Media Dock
A sticky bottom bar with hardware-level media controls:
- ⏮ Previous Track
- ⏯ Play / Pause
- ⏭ Next Track
- 🔉🔇🔊 Volume Down / Mute / Volume Up

Works with **Spotify, YouTube, VLC, Windows Media Player**, and any app that responds to media keys.

### 🚀 Multi-Action Macros
Create powerful one-tap automation sequences:
```json
{
    "id": "gaming_mode",
    "title": "Gaming Mode",
    "command": [
        "taskkill /f /im chrome.exe",
        "start steam://open/main"
    ],
    "color": "#e91e63"
}
```
Each command in the array executes sequentially. Kill apps, launch software, and chain actions — all from a single button.

### 🔊 Premium Sound & Haptics
- **Synthesized audio feedback** via Web Audio API — satisfying click, success, and error tones.
- **Haptic vibration patterns** — Physical confirmation on every tap.

### 🔐 Access Control
- **2-device hard limit** — Only two phones can connect simultaneously. Additional connections are rejected with `403 Forbidden`.
- **Local-only admin API** — Server status endpoints are locked to `127.0.0.1`.

---

## 📦 Installation

### Prerequisites
- **Windows 10/11**
- **Python 3.10+** with pip
- A smartphone on the **same Wi-Fi network**

### Quick Setup

```bash
# 1. Clone the repository
git clone https://github.com/Nothing-dot-exe/stream-deckx.git
cd stream-deckx

# 2. Create a virtual environment
python -m venv venv
venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Launch Stream DeckX
python stream_deckx.py
```

The GUI will open automatically. The server starts in the background. Scan the QR code with your phone.

### Alternative: Silent Server Mode

```bash
# Run without GUI (headless mode — used for system startup)
pythonw stream_deckx.py --headless
```

### One-Click Launch
Double-click **`Run_Manager.bat`** to launch the full GUI + server instantly.

---

## 🚀 Usage

### Connecting Your Phone
1. Launch `Run_Manager.bat` or run `python stream_deckx.py`
2. The Control Center GUI opens with a **QR code**
3. **Scan the QR code** with your phone camera
4. Your phone opens the Stream DeckX web interface
5. Tap any app icon to launch/close it on your PC

### Adding Apps
1. Tap **"Edit"** on your phone
2. Stream DeckX automatically **scans your entire PC** for installed applications
3. All discovered apps appear (greyed out = hidden from main view)
4. **Tap any app** to toggle its visibility on your dashboard
5. Tap **"Done"** to save

### Creating Custom Macros
Edit `config.json` and add a button with an array of commands:
```json
{
    "id": "work_mode",
    "title": "Work Mode",
    "command": [
        "start outlook",
        "start slack",
        "start code"
    ],
    "color": "#2196F3",
    "is_hidden": false
}
```

### System Startup
Toggle **"Run on System Boot"** in the GUI. The server will silently start every time Windows boots — your phone is always ready to connect.

---

## 🏗️ Architecture

```
stream-deckx/
├── stream_deckx.py      # 🏆 Unified entry point (GUI + Flask server)
├── app_scanner.py       # Desktop shortcut discovery engine
├── config.json          # Button configuration database
├── requirements.txt     # Python dependencies
├── Run_Manager.bat      # One-click launcher
├── runner.vbs           # Silent background launcher (for startup)
├── templates/
│   └── index.html       # Mobile PWA interface
└── static/
    ├── style.css         # Responsive dark-mode stylesheet
    ├── manifest.json     # PWA manifest (fullscreen)
    ├── sw.js             # Service Worker (offline caching)
    ├── logo.png          # App icon
    └── icons/            # Auto-extracted app icons
```

### How It Works

```
┌─────────────────────┐     HTTP/JSON     ┌──────────────────┐
│   📱 Your Phone     │ ◄──────────────► │  🖥️ Flask Server  │
│   (PWA Interface)   │    Wi-Fi LAN     │  (stream_deckx)  │
└─────────────────────┘                  └────────┬─────────┘
                                                  │
                                    subprocess / psutil / pyautogui
                                                  │
                                         ┌────────▼─────────┐
                                         │  💻 Windows OS    │
                                         │  Apps, Media,     │
                                         │  Processes        │
                                         └──────────────────┘
```

### Technology Stack

| Component | Technology |
|---|---|
| **Server** | Flask 3.0 (Python) |
| **Desktop GUI** | CustomTkinter |
| **Mobile UI** | Vanilla HTML/CSS/JS (PWA) |
| **Process Management** | psutil + subprocess |
| **Media Control** | PyAutoGUI (virtual keystroke injection) |
| **Icon Extraction** | pywin32 (COM + Win32 API) |
| **QR Generation** | qrcode + Pillow |

---

## 🛡️ Security Notes

- The server binds to `0.0.0.0` on your **local Wi-Fi only**. It is not exposed to the internet.
- The `/api/status` endpoint is restricted to `127.0.0.1` (localhost only).
- A maximum of **2 devices** can connect simultaneously.
- For public networks, consider adding authentication middleware.

---

## 🤝 Contributing

Contributions are welcome! If you'd like to add features, fix bugs, or improve documentation:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📜 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

---

<div align="center">

**Built with ❤️ by [@Nothing-dot-exe](https://github.com/Nothing-dot-exe)**

⭐ Star this repo if you found it useful!

</div>
