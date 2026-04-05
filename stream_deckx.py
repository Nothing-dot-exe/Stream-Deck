"""
Stream DeckX - Unified Control Center
Single entry point: GUI + embedded Flask server.
Launch this file directly or via Run_Manager.bat.
Pass --headless for silent background server (used by system startup).
"""
import json
import os
import re
import sys
import socket
import subprocess
import threading
import time
import webbrowser

import psutil
from PIL import Image

try:
    import pyautogui
except ImportError:
    pass

from flask import Flask, render_template, request, jsonify
import app_scanner

# ══════════════════════════════════════════════
#  FLASK SERVER
# ══════════════════════════════════════════════

# PyInstaller bundles files into _MEIPASS temp dir
if getattr(sys, 'frozen', False):
    # Running as compiled exe
    BUNDLE_DIR = sys._MEIPASS
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # Running as script
    BUNDLE_DIR = os.path.dirname(os.path.abspath(__file__))
    BASE_DIR = BUNDLE_DIR

os.chdir(BASE_DIR)

flask_app = Flask(
    __name__,
    template_folder=os.path.join(BUNDLE_DIR, "templates"),
    static_folder=os.path.join(BUNDLE_DIR, "static")
)

# Custom route to serve icons from the LOCAL directory (BASE_DIR)
# This is crucial for the EXE: it serves newly synced icons that aren't inside the bundled static folder.
@flask_app.route('/static/icons/<path:filename>')
def custom_icons(filename):
    from flask import send_from_directory
    local_path = os.path.join(BASE_DIR, "static", "icons")
    if os.path.exists(os.path.join(local_path, filename)):
        return send_from_directory(local_path, filename)
    # Fallback to bundled icons in the temp folder (_MEIPASS)
    return send_from_directory(os.path.join(BUNDLE_DIR, "static", "icons"), filename)
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")

connected_ips = set()
MAX_DEVICES = 2

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        ip = s.getsockname()[0]
    except Exception:
        ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def load_config():
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

@flask_app.before_request
def restrict_devices():
    ip = request.remote_addr
    if ip == '127.0.0.1':
        return
    if ip not in connected_ips:
        if len(connected_ips) >= MAX_DEVICES:
            return "Connection limit reached (2 devices only).", 403
        connected_ips.add(ip)

@flask_app.route("/api/status")
def status():
    if request.remote_addr != '127.0.0.1':
        return "Unauthorized", 401
    return jsonify({
        "connected_devices": len(connected_ips),
        "device_ips": list(connected_ips)
    })

@flask_app.route("/")
def index():
    config = load_config()
    ip = get_local_ip()
    return render_template("index.html", buttons=config.get("buttons", []), ip=ip)

@flask_app.route("/execute", methods=["POST"])
def execute():
    data = request.get_json()
    button_id = data.get("id")

    config = load_config()
    clicked_button = next((btn for btn in config.get("buttons", []) if btn["id"] == button_id), None)

    if clicked_button and "command" in clicked_button:
        cmd = clicked_button["command"]
        process_name = clicked_button.get("process_name")

        # Handle MACROS (array of commands)
        if isinstance(cmd, list):
            for sub_cmd in cmd:
                try:
                    subprocess.Popen(sub_cmd, shell=True)
                    time.sleep(0.2)
                except Exception:
                    pass
            return jsonify({"status": "success", "message": "Macro sequence triggered!"})

        # Fallback process name extraction
        if not process_name:
            m = re.search(r'([^\\]+\.exe)', cmd, re.IGNORECASE)
            if m:
                process_name = m.group(1)
            elif "explorer" in cmd.lower():
                process_name = "explorer.exe"
            elif "notepad" in cmd.lower():
                process_name = "notepad.exe"

        # Toggle logic: kill if running, launch if not
        terminated = False
        if process_name:
            mapped_names = {process_name.lower()}
            if "calc" in process_name.lower():
                mapped_names.update(["calculatorapp.exe", "calculator.exe", "calc.exe", "win32calc.exe"])

            if "explorer.exe" in mapped_names:
                mapped_names.remove("explorer.exe")
                try:
                    ps_cmd = 'powershell -command "$Shell = New-Object -ComObject Shell.Application; if ($Shell.Windows().Count -gt 0) { $Shell.Windows() | ForEach-Object { $_.Quit() }; exit 0 } else { exit 1 }"'
                    if os.system(ps_cmd) == 0:
                        terminated = True
                except Exception:
                    pass

            if mapped_names and not terminated:
                for proc in psutil.process_iter(['name']):
                    try:
                        if proc.info['name'] and proc.info['name'].lower() in mapped_names:
                            proc.kill()
                            terminated = True
                    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                        pass

        if terminated:
            display_name = (process_name or cmd).replace('.exe', '')
            return jsonify({"status": "success", "message": f"Closed {display_name}"})

        try:
            subprocess.Popen(cmd, shell=True)
            return jsonify({"status": "success", "message": f"Opened {process_name or cmd}"})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "error", "message": "Command not found"}), 404

@flask_app.route("/api/toggle_visibility", methods=["POST"])
def toggle_visibility():
    data = request.get_json()
    button_id = data.get("id")
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
            for btn in config.get("buttons", []):
                if btn["id"] == button_id:
                    btn["is_hidden"] = not btn.get("is_hidden", False)
                    break
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4)
            return jsonify({"status": "success", "message": "Visibility toggled!"})
        return jsonify({"status": "error", "message": "Config not found"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@flask_app.route("/api/pc_metrics", methods=["GET"])
def pc_metrics():
    return jsonify({
        "cpu": psutil.cpu_percent(interval=None),
        "ram": psutil.virtual_memory().percent
    })

@flask_app.route("/api/media", methods=["POST"])
def media_controls():
    data = request.get_json()
    action = data.get("action")
    keymap = {
        "playpause": "playpause", "prev": "prevtrack", "next": "nexttrack",
        "mute": "volumemute", "voldown": "volumedown", "volup": "volumeup"
    }
    if action in keymap and 'pyautogui' in globals():
        try:
            pyautogui.press(keymap[action])
            return jsonify({"status": "success"})
        except Exception:
            pass
    return jsonify({"status": "error"}), 500

@flask_app.route("/api/sync", methods=["POST"])
def sync_apps():
    try:
        count = app_scanner.scan_desktop_apps()
        return jsonify({"status": "success", "message": f"Synced {count} apps!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


def run_server():
    """Start Flask in a background thread."""
    import logging
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    flask_app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False)


# ══════════════════════════════════════════════
#  DESKTOP GUI (customtkinter)
# ══════════════════════════════════════════════

def launch_gui():
    import customtkinter as ctk
    import qrcode
    import urllib.request

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    class StreamDeckManager(ctk.CTk):
        def __init__(self):
            super().__init__()
            self.title("Stream DeckX Pro - Control Center")
            self.geometry("700x530")
            self.resizable(False, False)
            self.protocol("WM_DELETE_WINDOW", self.on_close)
            
            # Use the Pro logo for the window icon (check bundled and local)
            icon_path = os.path.join(BUNDLE_DIR, "icon.ico")
            if not os.path.exists(icon_path):
                icon_path = os.path.join(BASE_DIR, "icon.ico")
            
            if os.path.exists(icon_path):
                self.after(200, lambda: self.iconbitmap(icon_path))

            self.ip = get_local_ip()
            self.port = 5000
            self.url = f"http://{self.ip}:{self.port}"
            self.server_thread = None

            self.startup_dir = os.path.join(os.getenv('APPDATA'), r'Microsoft\Windows\Start Menu\Programs\Startup')
            self.startup_file = os.path.join(self.startup_dir, 'stream_deck_runner.vbs')

            # ── Layout ──
            self.grid_columnconfigure(0, weight=1)
            self.grid_columnconfigure(1, weight=1)
            self.grid_rowconfigure(0, weight=1)

            # Left Panel (QR Code)
            self.left_frame = ctk.CTkFrame(self, fg_color="#1E1E1E", corner_radius=15)
            self.left_frame.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

            ctk.CTkLabel(self.left_frame, text="Scan to Connect", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(20, 10))

            qr = qrcode.QRCode(box_size=10, border=4)
            qr.add_data(self.url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            qr_path = os.path.join(BASE_DIR, "temp_qr.png")
            img.save(qr_path)
            self.qr_image = ctk.CTkImage(light_image=Image.open(qr_path), dark_image=Image.open(qr_path), size=(220, 220))

            qr_bg = ctk.CTkFrame(self.left_frame, fg_color="white", corner_radius=10)
            qr_bg.pack(pady=10, padx=20)
            ctk.CTkLabel(qr_bg, text="", image=self.qr_image).pack(padx=10, pady=10)

            # Right Panel
            self.right_frame = ctk.CTkFrame(self, fg_color="transparent")
            self.right_frame.grid(row=0, column=1, padx=20, pady=20, sticky="nsew")

            ctk.CTkLabel(self.right_frame, text="Control Center", font=ctk.CTkFont(size=24, weight="bold")).pack(anchor="w", pady=(10, 15))

            # Metrics Card
            metrics = ctk.CTkFrame(self.right_frame, fg_color="#2A2A2A", corner_radius=10)
            metrics.pack(fill="x", pady=10)

            self.servers_label = ctk.CTkLabel(metrics, text="● Server: Starting...", font=ctk.CTkFont(size=14, weight="bold"), text_color="#FFB74D")
            self.servers_label.pack(anchor="w", padx=20, pady=(15, 5))

            self.devices_label = ctk.CTkLabel(metrics, text="🔌 Connected Devices: 0 / 2", font=ctk.CTkFont(size=14))
            self.devices_label.pack(anchor="w", padx=20, pady=(5, 10))

            # Startup Switch
            is_startup_active = os.path.exists(self.startup_file)
            self.startup_var = ctk.BooleanVar(value=True)
            ctk.CTkSwitch(metrics, text="Run on System Boot (Recommended: Keep ON)", variable=self.startup_var, command=self.toggle_startup, progress_color="#4CAF50").pack(anchor="w", padx=20, pady=(10, 15))
            if not is_startup_active:
                self.toggle_startup()

            # URL Box
            url_box = ctk.CTkFrame(self.right_frame, fg_color="#1E1E1E", corner_radius=8)
            url_box.pack(fill="x", pady=10)
            ctk.CTkLabel(url_box, text=self.url, font=ctk.CTkFont(size=14, family="Consolas")).pack(side="left", padx=15, pady=10)
            self.copy_btn = ctk.CTkButton(url_box, text="Copy", width=60, height=28, fg_color="#4CAF50", hover_color="#388E3C", command=self.copy_url)
            self.copy_btn.pack(side="right", padx=10, pady=10)

            # Server Controls
            btn_frame = ctk.CTkFrame(self.right_frame, fg_color="transparent")
            btn_frame.pack(fill="x", pady=10)

            self.restart_btn = ctk.CTkButton(btn_frame, text="RESTART SERVER", height=40, font=ctk.CTkFont(size=14, weight="bold"), fg_color="#1E88E5", hover_color="#1565C0", command=self.restart_server)
            self.restart_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

            self.kill_btn = ctk.CTkButton(btn_frame, text="STOP SERVER", height=40, font=ctk.CTkFont(size=14, weight="bold"), fg_color="#ef5350", hover_color="#c62828", command=self.stop_server)
            self.kill_btn.pack(side="right", expand=True, fill="x", padx=(5, 0))

            # GitHub
            ctk.CTkButton(self.right_frame, text="GitHub: @Nothing-dot-exe", fg_color="transparent", text_color="#64B5F6", hover_color="#2b2b2b", command=lambda: webbrowser.open("https://github.com/Nothing-dot-exe")).pack(side="bottom", anchor="w", pady=(10, 0))

            # Auto-start the server
            self.start_embedded_server()

            # Start polling thread
            threading.Thread(target=self.background_polling, daemon=True).start()

        def start_embedded_server(self):
            """Launch the Flask server as a separate background process."""
            # Check if server is already running
            try:
                import urllib.request
                req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/status")
                urllib.request.urlopen(req, timeout=1)
                # Server already running, skip
                self.servers_label.configure(text="● Server: Running", text_color="#4CAF50")
                return
            except Exception:
                pass
            # Wait for 1 second instead of returning immediately so we can reliably check (optional, but the below logic is better)
            
            # Spawn as independent process that survives GUI close
            if getattr(sys, 'frozen', False):
                cmd_list = [sys.executable, '--headless']
            else:
                cmd_list = [os.path.join(BASE_DIR, 'venv', 'Scripts', 'pythonw.exe'), os.path.abspath(__file__), '--headless']

            subprocess.Popen(
                cmd_list,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
                cwd=BASE_DIR
            )
            self.servers_label.configure(text="● Server: Starting...", text_color="#FFB74D")

        def stop_server(self):
            """Kill any running server processes (threads die with the app)."""
            current_pid = os.getpid()
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = proc.info.get('cmdline') or []
                    if proc.info['pid'] != current_pid and 'python' in proc.info.get('name', '').lower():
                        if any('stream_deckx' in cmd or 'app.py' in cmd for cmd in cmdline):
                            proc.kill()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            self.servers_label.configure(text="● Server: Stopped", text_color="#ef5350")
            self.devices_label.configure(text="🔌 Connected Devices: 0 / 2")

        def restart_server(self):
            self.stop_server()
            self.servers_label.configure(text="● Server: Restarting...", text_color="#FFB74D")
            self.after(500, self.start_embedded_server)

        def toggle_startup(self):
            enabled = self.startup_var.get()
            if enabled:
                if getattr(sys, 'frozen', False):
                    run_cmd = f'"""{sys.executable}"" --headless"'
                else:
                    run_cmd = '"venv\\Scripts\\pythonw.exe stream_deckx.py --headless"'
                    
                vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "{BASE_DIR}"
WshShell.Run {run_cmd}, 0, False'''
                with open(self.startup_file, 'w', encoding='utf-8') as f:
                    f.write(vbs_content)
            else:
                if os.path.exists(self.startup_file):
                    os.remove(self.startup_file)

        def copy_url(self):
            self.clipboard_clear()
            self.clipboard_append(self.url)
            self.copy_btn.configure(text="Copied!")
            self.after(2000, lambda: self.copy_btn.configure(text="Copy"))

        def on_close(self):
            self.destroy()

        def background_polling(self):
            while True:
                device_count = 0
                is_running = False
                try:
                    req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/status")
                    with urllib.request.urlopen(req, timeout=0.8) as response:
                        if response.status == 200:
                            data = json.loads(response.read().decode())
                            device_count = data.get("connected_devices", 0)
                            is_running = True
                except Exception:
                    pass

                self.after(0, self.update_ui, device_count, is_running)
                time.sleep(2)

        def update_ui(self, d_count, is_running):
            color = "#4CAF50" if is_running else "#ef5350"
            status_text = "Running" if is_running else "Stopped"
            self.servers_label.configure(text=f"● Server: {status_text}", text_color=color)
            self.devices_label.configure(text=f"🔌 Connected Devices: {d_count} / 2")

    gui = StreamDeckManager()
    gui.mainloop()


# ══════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════
if __name__ == "__main__":
    if "--headless" in sys.argv:
        # Silent mode: just run the server (used by system startup)
        ip = get_local_ip()
        print(f"Stream DeckX server running at http://{ip}:5000")
        run_server()
    else:
        # GUI mode: server starts automatically inside the GUI
        launch_gui()
