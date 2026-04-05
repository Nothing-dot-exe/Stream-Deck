import os
import subprocess
import win32com.client
import win32ui
import win32gui
import win32con
import win32api
import json
import uuid
import pythoncom
from PIL import Image
from win32com.shell import shell, shellcon

CONFIG_FILE = "config.json"
ICONS_DIR = os.path.join("static", "icons")

def ensure_dirs():
    if not os.path.exists(ICONS_DIR):
        os.makedirs(ICONS_DIR)

def extract_icon(path, out_path):
    if not os.path.exists(path):
        return False
    try:
        ico_x = win32api.GetSystemMetrics(win32con.SM_CXICON)
        ico_y = win32api.GetSystemMetrics(win32con.SM_CYICON)

        # Use SHGetFileInfo - accurate for .lnk, .exe, and system paths
        flags = shellcon.SHGFI_ICON | shellcon.SHGFI_LARGEICON
        _, info = shell.SHGetFileInfo(path, 0, flags)
        hIcon = info[0]
        
        if hIcon == 0:
            return False
            
        hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
        hbmp = win32ui.CreateBitmap()
        hbmp.CreateCompatibleBitmap(hdc, ico_x, ico_y)
        hdc = hdc.CreateCompatibleDC()
        hdc.SelectObject(hbmp)
        
        win32gui.DrawIconEx(hdc.GetHandleOutput(), 0, 0, hIcon, ico_x, ico_y, 0, None, 0x0003)
        
        bmpinfo = hbmp.GetInfo()
        bmpstr = hbmp.GetBitmapBits(True)
        img = Image.frombuffer(
            'RGB',
            (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
            bmpstr, 'raw', 'BGRX', 0, 1)
            
        img = img.convert('RGBA')
        datas = img.getdata()
        newData = []
        for item in datas:
            if item[0] == 0 and item[1] == 0 and item[2] == 0:
                newData.append((255, 255, 255, 0))
            else:
                newData.append(item)
        img.putdata(newData)
            
        img.save(out_path, format="PNG")
        
        win32gui.DestroyIcon(hIcon)
        win32gui.DeleteObject(hbmp.GetHandle())
        hdc.DeleteDC()
        return True
    except Exception:
        return False


def scan_shortcut_apps(shell):
    """Scan .lnk shortcuts from Desktop and Start Menu — ALL of them."""
    search_paths = [
        os.path.join(os.environ["USERPROFILE"], "Desktop"),
        os.path.join(os.environ["PUBLIC"], "Desktop"),
        os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
        os.path.join(os.environ.get("PROGRAMDATA", ""), r"Microsoft\Windows\Start Menu\Programs")
    ]
    
    # Only skip truly useless entries (uninstallers, docs, duplicates of python/idle)
    skip_keywords = [
        "uninstall", "module docs", "manuals", "odbc data sources",
        "antigravity", "install additional", "nsight",
        "developer command prompt", "developer powershell"
    ]
    
    found = []
    seen = set()
    browsers = ["chrome.exe", "msedge.exe", "brave.exe", "firefox.exe", "opera.exe"]
    
    for search_path in search_paths:
        if not os.path.exists(search_path):
            continue
        for root, dirs, files in os.walk(search_path):
            for f in files:
                if not f.endswith(".lnk"):
                    continue
                lnk_path = os.path.join(root, f)
                try:
                    shortcut = shell.CreateShortCut(lnk_path)
                    target_path = shortcut.Targetpath
                    arguments = shortcut.Arguments or ""
                    
                    # Remove the strict .exe check - allow any valid shortcut in the Start Menu
                    if not target_path and not f.endswith(".lnk"):
                        continue
                    
                    app_name = os.path.splitext(f)[0]
                    app_name_lower = app_name.lower()
                    
                    # Skip only truly useless entries
                    if any(kw in app_name_lower for kw in skip_keywords):
                        continue
                    
                    exe_name = os.path.basename(target_path).lower()
                    full_cmd = f'"{target_path}" {arguments}'.strip()
                    
                    # Dedup key
                    if exe_name in browsers:
                        unique_key = full_cmd.lower()
                    else:
                        unique_key = exe_name
                    
                    if unique_key in seen:
                        continue
                    seen.add(unique_key)
                    
                    unique_id = str(uuid.uuid4())[:8]
                    icon_filename = f"{unique_id}.png"
                    out_path = os.path.join(ICONS_DIR, icon_filename)
                    
                    # Try extracting icon from shortcut itself (most accurate)
                    # then fallback to target EXE
                    got_icon = extract_icon(lnk_path, out_path)
                    if not got_icon:
                        got_icon = extract_icon(target_path, out_path)

                    app_entry = {
                        "id": unique_id,
                        "title": app_name,
                        "command": full_cmd,
                        "process_name": os.path.basename(target_path)
                    }
                    if got_icon:
                        app_entry["icon_path"] = f"icons/{icon_filename}"
                    else:
                        app_entry["icon"] = "🖥️"
                    found.append(app_entry)
                except Exception:
                    pass
    return found


def extract_uwp_icon(package_family_name, out_path):
    """Extract icon from a UWP/Store app using its package install path."""
    try:
        import glob
        import xml.etree.ElementTree as ET

        # Get the package install location via PowerShell
        pfn = package_family_name.split("!")[0] if "!" in package_family_name else package_family_name
        pkg_name = pfn.split("_")[0]
        
        # Try Get-AppxPackage to find the install location
        ps_cmd = f'powershell -NoProfile -Command "(Get-AppxPackage -Name \'{pkg_name}\' | Select-Object -First 1).InstallLocation"'
        result = subprocess.run(ps_cmd, capture_output=True, text=True, timeout=8, shell=True)
        install_path = result.stdout.strip()
        
        if not install_path or not os.path.exists(install_path):
            return False
        
        # Parse AppxManifest.xml to find the logo
        manifest = os.path.join(install_path, "AppxManifest.xml")
        if not os.path.exists(manifest):
            return False
        
        tree = ET.parse(manifest)
        root = tree.getroot()
        
        # Handle XML namespaces
        ns = {'default': 'http://schemas.microsoft.com/appx/manifest/foundation/windows10',
              'uap': 'http://schemas.microsoft.com/appx/manifest/uap/windows10'}
        
        # Try multiple logo locations in the manifest
        logo_relative = None
        
        # 1. Try VisualElements Square44x44Logo or Square150x150Logo
        for ve in root.iter():
            if 'VisualElements' in ve.tag:
                logo_relative = ve.get('Square44x44Logo') or ve.get('Square150x150Logo') or ve.get('Square30x30Logo')
                if logo_relative:
                    break
        
        # 2. Fallback: try Properties/Logo
        if not logo_relative:
            for prop in root.iter():
                if prop.tag.endswith('}Logo') or prop.tag == 'Logo':
                    logo_relative = prop.text
                    if logo_relative:
                        break
        
        if not logo_relative:
            return False
        
        # The logo path is relative to the install dir
        logo_base = os.path.join(install_path, logo_relative)
        
        # UWP apps store multiple scale versions like Logo.scale-200.png
        # Find the best available version
        logo_dir = os.path.dirname(logo_base)
        logo_stem = os.path.splitext(os.path.basename(logo_base))[0]
        logo_ext = os.path.splitext(logo_base)[1] or ".png"
        
        # Search for scaled variants
        candidates = []
        if os.path.isdir(logo_dir):
            for f in os.listdir(logo_dir):
                f_lower = f.lower()
                stem_lower = logo_stem.lower()
                if f_lower.startswith(stem_lower) and (f_lower.endswith('.png') or f_lower.endswith('.jpg')):
                    candidates.append(os.path.join(logo_dir, f))
        
        # Also check in an Assets subfolder
        assets_dir = os.path.join(install_path, "Assets")
        if os.path.isdir(assets_dir):
            for f in os.listdir(assets_dir):
                f_lower = f.lower()
                stem_lower = logo_stem.lower()
                if f_lower.startswith(stem_lower) and (f_lower.endswith('.png') or f_lower.endswith('.jpg')):
                    candidates.append(os.path.join(assets_dir, f))
        
        # Direct path check
        if os.path.exists(logo_base):
            candidates.append(logo_base)
        
        if not candidates:
            return False
        
        # Pick the largest file (usually highest resolution)
        best = max(candidates, key=lambda f: os.path.getsize(f) if os.path.exists(f) else 0)
        
        if not os.path.exists(best) or os.path.getsize(best) == 0:
            return False
        
        # Copy and resize to consistent icon size
        img = Image.open(best).convert("RGBA")
        img = img.resize((64, 64), Image.LANCZOS)
        img.save(out_path, format="PNG")
        return True
    except Exception:
        return False


def scan_uwp_apps():
    """Scan Microsoft Store / UWP apps using PowerShell Get-StartApps."""
    found = []
    try:
        # Get-StartApps returns ALL apps visible in Start Menu including UWP
        ps_cmd = 'powershell -NoProfile -Command "Get-StartApps | Select-Object Name, AppID | ConvertTo-Json"'
        result = subprocess.run(ps_cmd, capture_output=True, text=True, timeout=15, shell=True)
        if result.returncode != 0:
            return found
        
        apps = json.loads(result.stdout)
        if isinstance(apps, dict):
            apps = [apps]
        
        # UWP apps have AppIDs like "Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"
        # Desktop apps have AppIDs that are file paths
        for app in apps:
            name = app.get("Name", "").strip()
            app_id = app.get("AppID", "").strip()
            
            if not name or not app_id:
                continue
            
            # Skip very generic Windows system entries
            skip_names = [
                "uninstall", "module docs", "manuals", "antigravity"
            ]
            if any(kw in name.lower() for kw in skip_names):
                continue
            
            # If the app_id is a path, just use it as the command.
            # Otherwise, use shell:appsFolder launch command.
            is_uwp = not ("\\" in app_id or "/" in app_id)
            final_cmd = f'"{app_id}"' if not is_uwp else f"explorer shell:appsFolder\\{app_id}"
            
            unique_id = str(uuid.uuid4())[:12]
            icon_filename = f"{unique_id}.png"
            out_path = os.path.join(ICONS_DIR, icon_filename)
            
            app_entry = {
                "id": unique_id,
                "title": name,
                "command": final_cmd,
                "process_name": os.path.basename(app_id) if not is_uwp else "",
                "app_id": app_id
            }
            
            # Try to extract icon for UWP apps
            got_icon = False
            if is_uwp:
                # We intentionally DO NOT call extract_uwp_icon() here because it is too slow (forks PowerShell).
                # The fix_missing_icons() tool will handle UWP icon extraction retroactively.
                pass
            else:
                # Desktop app via Get-StartApps — try extracting from path (this is fast)
                got_icon = extract_icon(app_id, out_path)
            
            if got_icon:
                app_entry["icon_path"] = f"icons/{icon_filename}"
            else:
                # Use a meaningful emoji based on the app name instead of generic box
                app_entry["icon"] = "🖥️"
            
            found.append(app_entry)
    except Exception as e:
        print(f"UWP scan error: {e}")
    
    return found


def fix_missing_icons():
    """Retroactively fix all entries that have 📦 or missing icons by extracting proper icons."""
    import re
    ensure_dirs()
    
    if not os.path.exists(CONFIG_FILE):
        return 0
    
    with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    fixed_count = 0
    for btn in config.get("buttons", []):
        # Skip entries that already have a valid icon_path
        if btn.get("icon_path"):
            icon_full = os.path.join("static", btn["icon_path"])
            if os.path.exists(icon_full) and os.path.getsize(icon_full) > 100:
                continue
        
        # Target: entries with 📦 emoji or 🖥️ or no icon at all
        current_icon = btn.get("icon", "")
        if btn.get("icon_path") and os.path.exists(os.path.join("static", btn["icon_path"])):
            continue  # Already has a working icon file
        
        cmd = btn.get("command", "")
        if isinstance(cmd, list):
            continue  # Skip macros
        
        # Determine app_id — either from field or parsed from shell:appsFolder command
        app_id = btn.get("app_id", "")
        if not app_id and "shell:appsFolder" in cmd:
            # Extract app_id from command like "explorer shell:appsFolder\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App"
            match = re.search(r'shell:appsFolder\\(.+)', cmd)
            if match:
                app_id = match.group(1).strip()
        
        unique_id = btn.get("id", str(uuid.uuid4())[:8])
        icon_filename = f"{unique_id}_fixed.png"
        out_path = os.path.join(ICONS_DIR, icon_filename)
        
        got_icon = False
        
        # Strategy 1: UWP app — extract from package assets
        if app_id and not ("\\" in app_id or "/" in app_id):
            got_icon = extract_uwp_icon(app_id, out_path)
        
        # Strategy 2: Desktop app — extract from .exe path in command
        if not got_icon and cmd:
            # Extract exe path from command string
            match = re.search(r'"([^"]+\.exe)"', cmd, re.IGNORECASE)
            if match:
                exe_path = match.group(1)
                got_icon = extract_icon(exe_path, out_path)
        
        # Strategy 3: Try to find matching .lnk in Start Menu by app title
        if not got_icon:
            title = btn.get("title", "")
            if title:
                search_paths = [
                    os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Start Menu\Programs"),
                    os.path.join(os.environ.get("PROGRAMDATA", ""), r"Microsoft\Windows\Start Menu\Programs")
                ]
                for sp in search_paths:
                    if not os.path.exists(sp):
                        continue
                    for root, dirs, files in os.walk(sp):
                        for f in files:
                            if f.endswith(".lnk") and title.lower() in os.path.splitext(f)[0].lower():
                                lnk_path = os.path.join(root, f)
                                got_icon = extract_icon(lnk_path, out_path)
                                if got_icon:
                                    break
                        if got_icon:
                            break
                    if got_icon:
                        break
        
        if got_icon:
            btn["icon_path"] = f"icons/{icon_filename}"
            if "icon" in btn:
                del btn["icon"]
            fixed_count += 1
    
    if fixed_count > 0:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
    
    return fixed_count


def scan_desktop_apps():
    """Master scan: shortcuts + UWP apps. Returns count of newly added apps."""
    pythoncom.CoInitialize()
    try:
        ensure_dirs()
        shell = win32com.client.Dispatch("WScript.Shell")
        
        # Phase 1: Traditional shortcuts (.lnk files)
        shortcut_apps = scan_shortcut_apps(shell)
        
        # Phase 2: UWP / Microsoft Store apps
        uwp_apps = scan_uwp_apps()
        
        # Combine all discovered apps
        all_found = shortcut_apps + uwp_apps
        
        # Load existing config
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                config = json.load(f)
        else:
            config = {"buttons": []}
        
        # Build existing keys set for dedup
        browsers = ["chrome.exe", "msedge.exe", "brave.exe", "firefox.exe", "opera.exe"]
        existing_keys = set()
        for b in config.get("buttons", []):
            p_name = b.get("process_name", "").lower()
            cmd = b.get("command", "")
            # Skip macros
            if isinstance(cmd, list):
                existing_keys.add(b.get("id", ""))
                continue
            cmd_lower = cmd.lower()
            if p_name in browsers:
                existing_keys.add(cmd_lower)
            elif p_name:
                existing_keys.add(p_name)
            else:
                # UWP apps — use command as key
                existing_keys.add(cmd_lower)
        
        # Add new apps or update existing missing icons
        new_apps_count = 0
        existing_apps = config.get("buttons", [])
        
        for a in all_found:
            p_name = a.get("process_name", "").lower()
            cmd = a.get("command", "").lower()
            a_id = a.get("app_id", "").lower()
            
            # Better key for deduplication: prioritize AppID (if available), then process_name or command
            if a_id:
                key = a_id
            elif p_name in browsers:
                key = cmd
            else:
                key = p_name if p_name else cmd

            # Check if this app is already in the config
            found_existing = False
            for existing in existing_apps:
                e_p_name = existing.get("process_name", "").lower()
                e_cmd = existing.get("command", "")
                if isinstance(e_cmd, list): continue # Skip macros
                e_cmd = e_cmd.lower()
                e_a_id = existing.get("app_id", "").lower()
                
                if e_a_id:
                    e_key = e_a_id
                elif e_p_name in browsers:
                    e_key = e_cmd
                else:
                    e_key = e_p_name if e_p_name else e_cmd

                if key == e_key:
                    found_existing = True
                    # FIX-UP: If it has no icon_path, try to add it from the scan
                    if not existing.get("icon_path") and a.get("icon_path"):
                        existing["icon_path"] = a["icon_path"]
                        if "icon" in existing: del existing["icon"]
                    break

            if not found_existing:
                a["is_hidden"] = True
                existing_apps.append(a)
                new_apps_count += 1
        
        config["buttons"] = existing_apps
        
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, indent=4)
        
        return new_apps_count
    except Exception as e:
        print(f"Error scanning: {e}")
        return 0
    finally:
        pythoncom.CoUninitialize()

if __name__ == "__main__":
    count = scan_desktop_apps()
    print(f"Found {count} new apps")
