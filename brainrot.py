#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

URLS = [
    "https://www.tiktok.com/",
    "https://www.instagram.com/reels/",
    "https://www.youtube.com/shorts",
]

HOOK_TOKEN = "brainrot.py"
CREATE_NEW_PROCESS_GROUP = 0x00000200
DETACHED_PROCESS = 0x00000008
CREATE_NO_WINDOW = 0x08000000


def log(message: str) -> None:
    line = f"[brainrot] {message}\n"
    sys.stderr.write(line)
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass


def cache_dir() -> Path:
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "brainrot"
    xdg = os.environ.get("XDG_CACHE_HOME")
    return Path(xdg) / "brainrot" if xdg else Path.home() / ".cache" / "brainrot"


def log_path() -> Path:
    return cache_dir() / "brainrot.log"


def state_path() -> Path:
    return cache_dir() / "windows.json"


def drain_stdin() -> None:
    try:
        sys.stdin.read()
    except OSError:
        pass


def emit_hook_json() -> None:
    sys.stdout.write("{}\n")
    sys.stdout.flush()


def quoted(path: Path | str) -> str:
    text = str(path)
    if os.name == "nt":
        return f'"{text}"'
    if any(ch.isspace() for ch in text):
        return json.dumps(text)
    return text


def url_hosts() -> list[str]:
    hosts = []
    for url in URLS:
        host = url.split("/")[2].lower().removeprefix("www.")
        hosts.append(host)
    return hosts


def find_browser() -> str | None:
    names = [
        "brave",
        "brave-browser",
        "google-chrome-stable",
        "google-chrome",
        "chromium",
        "chromium-browser",
        "microsoft-edge-stable",
        "microsoft-edge",
        "msedge",
        "vivaldi",
        "opera",
    ]
    for name in names:
        found = shutil.which(name)
        if found:
            return found

    if os.name == "nt":
        local = os.environ.get("LOCALAPPDATA", "")
        pf = os.environ.get("PROGRAMFILES", r"C:\Program Files")
        pf86 = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")
        win_paths = [
            Path(local) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
            Path(pf) / "BraveSoftware" / "Brave-Browser" / "Application" / "brave.exe",
            Path(local) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(pf) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(pf86) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(pf) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(pf86) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        ]
        for path in win_paths:
            if path.exists():
                return str(path)
        return None

    for path in (
        "/usr/bin/brave",
        "/usr/bin/brave-browser",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/opt/google/chrome/chrome",
    ):
        if Path(path).exists():
            return path
    return None


def popen_detached(argv: list[str]) -> subprocess.Popen:
    kwargs: dict = {
        "stdout": subprocess.DEVNULL,
        "stderr": subprocess.DEVNULL,
        "stdin": subprocess.DEVNULL,
    }
    if os.name == "nt":
        kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
        kwargs["close_fds"] = True
    else:
        kwargs["start_new_session"] = True
        kwargs["close_fds"] = True
    return subprocess.Popen(argv, **kwargs)


def save_window_ids(ids: list[str]) -> None:
    cache_dir().mkdir(parents=True, exist_ok=True)
    state_path().write_text(json.dumps({"ids": ids}, indent=2) + "\n", encoding="utf-8")


def load_window_ids() -> list[str]:
    path = state_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    ids = data.get("ids") if isinstance(data, dict) else None
    if not isinstance(ids, list):
        return []
    return [str(i) for i in ids]


def clear_window_ids() -> None:
    try:
        state_path().unlink(missing_ok=True)
    except OSError:
        pass


def get_work_area() -> tuple[int, int, int, int]:
    if os.name == "nt":
        area = _work_area_windows()
        if area:
            return area
        return (0, 0, 1920, 1080)
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        area = _work_area_hyprland()
        if area:
            return area
    if os.environ.get("SWAYSOCK"):
        area = _work_area_sway()
        if area:
            return area
    area = _work_area_xrandr()
    if area:
        return area
    return (0, 0, 1920, 1080)


def _work_area_hyprland() -> tuple[int, int, int, int] | None:
    try:
        result = subprocess.run(
            [_hyprctl_bin(), "monitors", "-j"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        monitors = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        return None
    if not monitors:
        return None
    mon = next((m for m in monitors if m.get("focused")), monitors[0])
    scale = float(mon.get("scale") or 1) or 1.0
    transform = int(mon.get("transform") or 0)
    width = int(mon["width"])
    height = int(mon["height"])
    if transform in (1, 3, 5, 7):
        width, height = height, width
    logical_w = int(round(width / scale))
    logical_h = int(round(height / scale))
    reserved = mon.get("reserved") or [0, 0, 0, 0]
    left, top, right, bottom = (int(v) for v in reserved[:4])
    x = int(mon.get("x") or 0) + left
    y = int(mon.get("y") or 0) + top
    w = max(200, logical_w - left - right)
    h = max(200, logical_h - top - bottom)
    return (x, y, w, h)


def _work_area_sway() -> tuple[int, int, int, int] | None:
    try:
        result = subprocess.run(
            ["swaymsg", "-t", "get_outputs"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        outputs = json.loads(result.stdout)
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        return None
    focused = next((o for o in outputs if o.get("focused") and o.get("active")), None)
    if not focused:
        focused = next((o for o in outputs if o.get("active")), None)
    if not focused:
        return None
    rect = focused.get("rect") or {}
    return (
        int(rect.get("x") or 0),
        int(rect.get("y") or 0),
        int(rect.get("width") or 1920),
        int(rect.get("height") or 1080),
    )


def _work_area_xrandr() -> tuple[int, int, int, int] | None:
    xrandr = shutil.which("xrandr")
    if not xrandr:
        return None
    try:
        result = subprocess.run([xrandr], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.TimeoutExpired):
        return None
    primary = None
    first = None
    for line in result.stdout.splitlines():
        if " connected" not in line:
            continue
        for part in line.split():
            if "x" in part and "+" in part and part[0].isdigit():
                geom, *pos = part.split("+")
                wh = geom.split("x")
                if len(wh) == 2 and len(pos) >= 2:
                    box = (int(pos[0]), int(pos[1]), int(wh[0]), int(wh[1]))
                    if first is None:
                        first = box
                    if "primary" in line:
                        primary = box
                    break
    return primary or first


def _work_area_windows() -> tuple[int, int, int, int] | None:
    import ctypes
    from ctypes import wintypes

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", wintypes.LONG),
            ("top", wintypes.LONG),
            ("right", wintypes.LONG),
            ("bottom", wintypes.LONG),
        ]

    class MONITORINFO(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", wintypes.DWORD),
        ]

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    monitor = user32.MonitorFromWindow(hwnd, 2)
    info = MONITORINFO()
    info.cbSize = ctypes.sizeof(MONITORINFO)
    if not user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
        return None
    work = info.rcWork
    return (
        int(work.left),
        int(work.top),
        int(work.right - work.left),
        int(work.bottom - work.top),
    )


def columns_for(area: tuple[int, int, int, int], count: int) -> list[tuple[int, int, int, int]]:
    x, y, width, height = area
    cols = []
    used = 0
    for i in range(count):
        remaining = count - i
        col_w = (width - used) // remaining
        cols.append((x + used, y, col_w, height))
        used += col_w
    return cols


def _hyprctl_bin() -> str:
    return shutil.which("hyprctl") or "/usr/bin/hyprctl"


def hyprland_is_lua() -> bool:
    cached = getattr(hyprland_is_lua, "_cached", None)
    if cached is not None:
        return cached
    try:
        result = subprocess.run(
            [_hyprctl_bin(), "dispatch", "no_op"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        hyprland_is_lua._cached = False  # type: ignore[attr-defined]
        return False
    out = (result.stdout or "") + (result.stderr or "")
    uses_lua = "expected a dispatcher" in out
    hyprland_is_lua._cached = uses_lua  # type: ignore[attr-defined]
    return uses_lua


def _hypr_dispatch(expr: str) -> None:
    subprocess.run(
        [_hyprctl_bin(), "dispatch", expr],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        timeout=5,
    )


def _hypr_clients() -> list[dict]:
    try:
        result = subprocess.run(
            [_hyprctl_bin(), "clients", "-j"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        data = json.loads(result.stdout)
        return data if isinstance(data, list) else []
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError, ValueError):
        return []


def _hypr_close_address(addr: str) -> None:
    if hyprland_is_lua():
        _hypr_dispatch(f'hl.dsp.window.close({{ window = "address:{addr}" }})')
    else:
        _hypr_dispatch(f"closewindow address:{addr}")


def _matches_brainrot_app(client: dict) -> bool:
    cls = str(client.get("class") or "").lower()
    initial = str(client.get("initialClass") or "").lower()
    blob = f"{cls} {initial}"
    if "brainrot" in blob or "cursor-brainrot" in blob:
        return True
    for host in url_hosts():
        if f"{host}__" in blob:
            return True
    return False


def _window_sort_key(client: dict) -> tuple[int, int]:
    blob = f"{client.get('class') or ''} {client.get('title') or ''}".lower()
    for index, host in enumerate(url_hosts()):
        if host in blob or host.split(".")[0] in blob:
            return (0, index)
    return (1, 99)


def find_brainrot_windows_hypr() -> list[dict]:
    tracked = set(load_window_ids())
    wins = []
    for client in _hypr_clients():
        if not client.get("mapped") or client.get("hidden"):
            continue
        addr = str(client.get("address") or "")
        if addr in tracked or _matches_brainrot_app(client):
            wins.append(client)
    wins.sort(key=_window_sort_key)
    seen: set[str] = set()
    ordered: list[dict] = []
    for client in wins:
        addr = str(client.get("address") or "")
        if not addr or addr in seen:
            continue
        seen.add(addr)
        ordered.append(client)
        if len(ordered) >= len(URLS):
            break
    return ordered


def launch_windows(browser: str, area: tuple[int, int, int, int]) -> None:
    cols = columns_for(area, len(URLS))
    for index, (url, (x, y, w, h)) in enumerate(zip(URLS, cols)):
        argv = [
            browser,
            f"--app={url}",
            f"--window-position={x},{y}",
            f"--window-size={max(w, 480)},{h}",
        ]
        popen_detached(argv)
        time.sleep(0.55 if index == 0 else 0.35)


def tile_hyprland(area: tuple[int, int, int, int], wins: list[dict]) -> None:
    if not wins:
        return
    cols = columns_for(area, len(wins))
    for client, (x, y, w, h) in zip(wins, cols):
        addr = client.get("address")
        if not addr:
            continue
        win = f"address:{addr}"
        if hyprland_is_lua():
            if not client.get("floating"):
                _hypr_dispatch(
                    f'hl.dsp.window.float({{ action = "enable", window = "{win}" }})'
                )
            _hypr_dispatch(
                f'hl.dsp.window.move({{ x = {int(x)}, y = {int(y)}, relative = false, window = "{win}" }})'
            )
            _hypr_dispatch(
                f'hl.dsp.window.resize({{ x = {int(w)}, y = {int(h)}, relative = false, window = "{win}" }})'
            )
        else:
            if not client.get("floating"):
                _hypr_dispatch(f"setfloating address:{addr}")
            _hypr_dispatch(f"movewindowpixel exact {x} {y},address:{addr}")
            _hypr_dispatch(f"resizewindowpixel exact {w} {h},address:{addr}")


def tile_windows_os(area: tuple[int, int, int, int], hwnds: list[int]) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    cols = columns_for(area, len(hwnds))
    HWND_TOP = 0
    SWP_SHOWWINDOW = 0x0040
    for hwnd, (x, y, w, h) in zip(hwnds, cols):
        user32.SetWindowPos(hwnd, HWND_TOP, x, y, w, h, SWP_SHOWWINDOW)


def find_brainrot_hwnds() -> list[int]:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    tracked = {int(x) for x in load_window_ids() if str(x).isdigit()}
    hosts = url_hosts()
    hwnds: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_proc(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        if user32.GetWindow(hwnd, 4):
            return True
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value.lower()
        hid = int(hwnd)
        if hid in tracked or any(host.split(".")[0] in title for host in hosts):
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            if (rect.right - rect.left) >= 200 and (rect.bottom - rect.top) >= 200:
                hwnds.append(hid)
        return True

    user32.EnumWindows(enum_proc, 0)
    if tracked:
        ordered = [h for h in hwnds if h in tracked]
        extras = [h for h in hwnds if h not in tracked]
        return (ordered + extras)[: len(URLS)]
    return hwnds[: len(URLS)]


def close_hwnds(hwnds: list[int]) -> None:
    import ctypes

    user32 = ctypes.windll.user32
    WM_CLOSE = 0x0010
    for hwnd in hwnds:
        user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)


def wait_and_tile(area: tuple[int, int, int, int]) -> None:
    wanted = len(URLS)
    deadline = time.time() + 12

    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        wins: list[dict] = []
        while time.time() < deadline:
            wins = find_brainrot_windows_hypr()
            if wins:
                tile_hyprland(area, wins)
            if len(wins) >= wanted:
                save_window_ids([str(w.get("address")) for w in wins if w.get("address")])
                tile_hyprland(area, wins)
                return
            time.sleep(0.35)
        if wins:
            save_window_ids([str(w.get("address")) for w in wins if w.get("address")])
            tile_hyprland(area, wins)
        return

    if os.name == "nt":
        hwnds: list[int] = []
        while time.time() < deadline:
            hwnds = find_brainrot_hwnds()
            if hwnds:
                tile_windows_os(area, hwnds)
            if len(hwnds) >= wanted:
                save_window_ids([str(h) for h in hwnds])
                return
            time.sleep(0.35)
        if hwnds:
            save_window_ids([str(h) for h in hwnds])
        return

    time.sleep(2.0)


def close_brainrot_windows() -> None:
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        wins = find_brainrot_windows_hypr()
        known = {str(w.get("address")) for w in wins if w.get("address")}
        for addr in load_window_ids():
            if addr not in known:
                _hypr_close_address(addr)
        for client in wins:
            addr = client.get("address")
            if addr:
                log(f"closing {client.get('class')} {client.get('title')}")
                _hypr_close_address(str(addr))
        clear_window_ids()
        return

    if os.name == "nt":
        hwnds = find_brainrot_hwnds()
        close_hwnds(hwnds)
        clear_window_ids()
        return

    ids = load_window_ids()
    wmctrl = shutil.which("wmctrl")
    if wmctrl and ids:
        for wid in ids:
            subprocess.run(
                [wmctrl, "-i", "-c", wid],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
    clear_window_ids()


def do_open() -> None:
    browser = find_browser()
    if not browser:
        log("no Chromium-based browser found (Chrome, Brave, Edge, Chromium)")
        return
    log(f"browser={browser} (using your normal profile / logins)")
    close_brainrot_windows()
    time.sleep(0.35)
    area = get_work_area()
    log(f"work area={area}")
    launch_windows(browser, area)
    wait_and_tile(area)


def do_close() -> None:
    close_brainrot_windows()


def spawn_detached_self(action: str) -> None:
    argv = [sys.executable, str(Path(__file__).resolve()), action]
    popen_detached(argv)


def user_hooks_path() -> Path:
    return Path.home() / ".cursor" / "hooks.json"


def hook_command(action: str) -> str:
    return f"{quoted(sys.executable)} {quoted(Path(__file__).resolve())} {action}"


def is_our_hook(entry: object) -> bool:
    if not isinstance(entry, dict):
        return False
    command = str(entry.get("command") or "").replace("\\", "/")
    return HOOK_TOKEN in command


def load_hooks_file(path: Path) -> dict:
    if not path.exists():
        return {"version": 1, "hooks": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        log(f"could not parse {path}; starting a fresh hooks file")
        return {"version": 1, "hooks": {}}
    if not isinstance(data, dict):
        return {"version": 1, "hooks": {}}
    data.setdefault("version", 1)
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        data["hooks"] = {}
    return data


def do_install() -> None:
    path = user_hooks_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = load_hooks_file(path)
    hooks = data["hooks"]
    open_entry = {"command": hook_command("open"), "timeout": 20}
    close_entry = {"command": hook_command("close"), "timeout": 20}

    def merge(event: str, entry: dict) -> None:
        current = hooks.get(event) or []
        if not isinstance(current, list):
            current = []
        current = [item for item in current if not is_our_hook(item)]
        current.append(entry)
        hooks[event] = current

    merge("beforeSubmitPrompt", open_entry)
    merge("stop", close_entry)
    merge("sessionEnd", close_entry)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Installed Cursor hooks → {path}")
    print(f"  open : {open_entry['command']}")
    print(f"  close: {close_entry['command']}")
    print("Cursor reloads hooks on save; if nothing happens, restart Cursor.")


def do_uninstall() -> None:
    path = user_hooks_path()
    if not path.exists():
        print("No ~/.cursor/hooks.json found.")
        return
    data = load_hooks_file(path)
    hooks = data["hooks"]
    changed = False
    for event, entries in list(hooks.items()):
        if not isinstance(entries, list):
            continue
        kept = [item for item in entries if not is_our_hook(item)]
        if len(kept) != len(entries):
            changed = True
        if kept:
            hooks[event] = kept
        else:
            hooks.pop(event, None)
            changed = True
    if not changed:
        print("No brainrot hooks were installed.")
        return
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Removed brainrot hooks from {path}")


def usage() -> None:
    print(
        "Usage: brainrot.py [open|close|install|uninstall]\n"
        "  open       Open tiled windows in your normal browser profile\n"
        "  close      Close only those windows (browser stays open)\n"
        "  install    Register Cursor user hooks\n"
        "  uninstall  Remove those hooks"
    )


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else "open"
    drain_stdin()

    if action == "open":
        spawn_detached_self("open-now")
        emit_hook_json()
        return 0
    if action == "open-now":
        try:
            do_open()
        except Exception as exc:  # noqa: BLE001
            log(f"open failed: {exc}")
        return 0
    if action == "close":
        try:
            do_close()
        except Exception as exc:  # noqa: BLE001
            log(f"close failed: {exc}")
        emit_hook_json()
        return 0
    if action == "install":
        do_install()
        return 0
    if action == "uninstall":
        do_uninstall()
        return 0

    usage()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
