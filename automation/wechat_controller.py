"""
Screenshot and Window Management Utilities.
Provides functions for capturing screenshots and managing WeChat window.

Cross-platform implementation:
  - macOS: uses AppKit (pyobjc) for window enumeration and Quartz for screenshots
  - Windows: uses Win32 API via ctypes
"""

import os
import subprocess
import sys
import time
from datetime import datetime
from typing import List, Optional, Tuple

from PIL import Image

# Pillow 10+ uses Image.Resampling.LANCZOS; older versions expose Image.LANCZOS directly
_LANCZOS = getattr(Image, "Resampling", Image).LANCZOS

from config.settings import (
    WECHAT_WINDOW_TITLE,
    WECHAT_EXE_PATH,
    SCREENSHOT_DIR,
    SAVE_SCREENSHOTS,
)

IS_MAC = sys.platform == "darwin"
IS_WIN = sys.platform == "win32"

# ------------------------------------------------------------------ #
# Windows-only imports
# ------------------------------------------------------------------ #
if IS_WIN:
    import ctypes
    import ctypes.wintypes as wintypes
    from PIL import ImageGrab

    user32 = ctypes.windll.user32
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass

    SW_RESTORE = 9


class WindowInfo:
    """Lightweight wrapper for a discovered window."""

    def __init__(self, hwnd, title: str, rect: Tuple[int, int, int, int]):
        self.hwnd = hwnd
        self.title = title
        self.left, self.top, self.right, self.bottom = rect

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def __repr__(self):
        return (
            f"WindowInfo(title={self.title!r}, "
            f"rect=({self.left},{self.top},{self.width}x{self.height}))"
        )


# ------------------------------------------------------------------ #
# macOS window helpers
# ------------------------------------------------------------------ #

def _mac_find_windows_by_title(keyword: str) -> List[WindowInfo]:
    """Find visible windows containing *keyword* in the title on macOS.

    Filters out tiny windows (e.g. menu bar items) and returns results
    sorted by area descending so the main window is first.
    """
    try:
        from Quartz import CGWindowListCopyWindowInfo, kCGWindowListOptionOnScreenOnly, kCGNullWindowID
        window_list = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
        results = []
        for win in window_list:
            name = win.get("kCGWindowName", "") or ""
            owner = win.get("kCGWindowOwnerName", "") or ""
            if keyword in name or keyword in owner:
                bounds = win.get("kCGWindowBounds", {})
                left = int(bounds.get("X", 0))
                top = int(bounds.get("Y", 0))
                w = int(bounds.get("Width", 0))
                h = int(bounds.get("Height", 0))
                # Ignore tiny windows (menu bar icons, tooltips, etc.)
                if w < 200 or h < 200:
                    continue
                results.append(WindowInfo(
                    hwnd=win.get("kCGWindowNumber", 0),
                    title=name or owner,
                    rect=(left, top, left + w, top + h),
                ))
        # Sort by area descending – the main window is almost always the largest
        results.sort(key=lambda wi: wi.width * wi.height, reverse=True)
        if results:
            print(f"[INFO] All matched windows: {results}")
        return results
    except Exception as e:
        print(f"[WARN] Quartz window enumeration failed: {e}")
        return []


def _mac_launch_wechat(app_path: str) -> bool:
    """Launch WeChat on macOS using 'open'."""
    try:
        subprocess.Popen(["open", "-a", app_path])
        return True
    except Exception as e:
        print(f"[ERROR] Failed to launch WeChat: {e}")
        return False


def _mac_focus_wechat(app_name: str = "WeChat") -> bool:
    """Bring WeChat to the foreground on macOS via AppleScript."""
    try:
        script = f'tell application "{app_name}" to activate'
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)
        time.sleep(0.3)
        return True
    except Exception as e:
        print(f"[WARN] Could not focus WeChat: {e}")
        return False


def _mac_screenshot(region: Optional[Tuple[int, int, int, int]] = None) -> Image.Image:
    """Take a screenshot on macOS using screencapture CLI.

    Handles multi-monitor setups correctly:
    - Quartz returns logical-point coordinates (same unit as screencapture -R).
    - On Retina/HiDPI screens the captured image will be 2x the logical size,
      but that is fine — the LLM receives the actual pixel image and we pass
      the real pixel dimensions so coordinates stay consistent.
    """
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        tmp_path = f.name

    try:
        if region:
            left, top, w, h = region
            # screencapture -R accepts logical points: x,y,width,height
            subprocess.run(
                ["screencapture", "-x", "-R", f"{left},{top},{w},{h}", tmp_path],
                check=True,
                capture_output=True,
            )
        else:
            # Full screen across all monitors
            subprocess.run(
                ["screencapture", "-x", tmp_path],
                check=True,
                capture_output=True,
            )

        img = Image.open(tmp_path).copy()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    return img


# ------------------------------------------------------------------ #
# Windows window helpers
# ------------------------------------------------------------------ #

def _win_enum_windows_by_title(keyword: str) -> List[WindowInfo]:
    results: List[WindowInfo] = []

    @ctypes.WINFUNCTYPE(
        ctypes.c_bool,
        ctypes.POINTER(ctypes.c_int),
        ctypes.POINTER(ctypes.c_int),
    )
    def _callback(hwnd, _lParam):
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                title = buf.value
                if keyword in title:
                    rect = wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    hwnd_int = ctypes.cast(hwnd, ctypes.c_void_p).value
                    results.append(
                        WindowInfo(
                            hwnd_int,
                            title,
                            (rect.left, rect.top, rect.right, rect.bottom),
                        )
                    )
        return True

    user32.EnumWindows(_callback, 0)
    return results


# ------------------------------------------------------------------ #
# Controller
# ------------------------------------------------------------------ #

class WeChatController:
    """Controls the WeChat desktop application window (cross-platform)."""

    def __init__(self):
        self.window: Optional[WindowInfo] = None
        self._all_windows: List[WindowInfo] = []
        # Retina scale detected from last screenshot (pixel / logical point)
        self.last_scale: float = 1.0
        self._ensure_screenshot_dir()

    def _ensure_screenshot_dir(self):
        if SAVE_SCREENSHOTS:
            os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    # ---------------------------------------------------------------- #
    # Window Management
    # ---------------------------------------------------------------- #
    def find_wechat_window(self) -> bool:
        """Try to find all running WeChat-related windows."""
        if IS_MAC:
            windows = _mac_find_windows_by_title(WECHAT_WINDOW_TITLE)
        else:
            windows = _win_enum_windows_by_title(WECHAT_WINDOW_TITLE)

        if windows:
            self._all_windows = windows
            self.window = windows[0]  # largest window = main WeChat
            print(f"[INFO] Found WeChat window: {self.window}")
            return True
        print("[INFO] WeChat window not found.")
        return False

    def get_active_window(self) -> Optional["WindowInfo"]:
        """Return the best window to interact with.

        When a mini program is open (a smaller floating window), prefer it
        over the main WeChat window so the LLM sees only the relevant UI.
        Main WeChat window is typically ≥1000px wide; mini programs are narrower.
        """
        if not self._all_windows:
            return self.window

        MAIN_WIN_MIN_WIDTH = 800  # anything wider is the main WeChat frame
        mini_windows = [w for w in self._all_windows if w.width < MAIN_WIN_MIN_WIDTH]
        if mini_windows:
            # Pick the largest among mini program windows
            return max(mini_windows, key=lambda w: w.width * w.height)
        return self.window

    def launch_wechat(self) -> bool:
        """Launch WeChat if not already running."""
        if self.find_wechat_window():
            print("[INFO] WeChat is already running.")
            return True

        if IS_MAC:
            app_path = WECHAT_EXE_PATH  # On Mac this is the .app bundle name/path
            print(f"[INFO] Launching WeChat: {app_path} …")
            if not _mac_launch_wechat(app_path):
                return False
        else:
            if not os.path.exists(WECHAT_EXE_PATH):
                print(f"[ERROR] WeChat not found at: {WECHAT_EXE_PATH}")
                return False
            print(f"[INFO] Launching WeChat from {WECHAT_EXE_PATH} …")
            import subprocess as sp
            sp.Popen(WECHAT_EXE_PATH)

        time.sleep(5)
        return self.find_wechat_window()

    def focus_wechat(self) -> bool:
        """Bring the WeChat window to the foreground."""
        if IS_MAC:
            return _mac_focus_wechat("WeChat")

        if self.window is None:
            return False
        try:
            hwnd = self.window.hwnd
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.3)
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            self.window.left = rect.left
            self.window.top = rect.top
            self.window.right = rect.right
            self.window.bottom = rect.bottom
            return True
        except Exception as e:
            print(f"[WARN] Could not focus WeChat window: {e}")
            return False

    def get_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """Return (left, top, width, height) of the active window in logical points."""
        win = self.get_active_window()
        if win is None:
            return None
        return (win.left, win.top, win.width, win.height)

    # ---------------------------------------------------------------- #
    # Screenshot
    # ---------------------------------------------------------------- #
    def take_screenshot(
        self, region: Optional[Tuple[int, int, int, int]] = None
    ) -> Image.Image:
        """Capture a screenshot. region = (left, top, width, height)."""
        if IS_MAC:
            screenshot = _mac_screenshot(region)
        else:
            from PIL import ImageGrab
            if region:
                left, top, w, h = region
                screenshot = ImageGrab.grab(bbox=(left, top, left + w, top + h))
            else:
                screenshot = ImageGrab.grab()

        if SAVE_SCREENSHOTS:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = os.path.join(SCREENSHOT_DIR, f"screenshot_{ts}.png")
            screenshot.save(path)
            print(f"[INFO] Screenshot saved: {path}")

        return screenshot

    def take_wechat_screenshot(self) -> Optional[Image.Image]:
        """Capture a screenshot of the active WeChat/miniprogram window.

        Refreshes window list each call (handles window moves / new mini programs).
        Detects the Retina scale factor and stores it in self.last_scale so that
        core.py can convert LLM pixel coordinates back to logical screen points.
        """
        # Refresh every tick so we pick up newly opened mini program windows
        self.find_wechat_window()

        target = self.get_active_window()
        if target is None:
            print("[WARN] Falling back to full-screen screenshot")
            return self.take_screenshot()

        print(f"[INFO] Capturing '{target.title}': "
              f"left={target.left} top={target.top} w={target.width} h={target.height}")

        region = (target.left, target.top, target.width, target.height)

        if IS_MAC:
            screenshot = _mac_screenshot(region)
        else:
            from PIL import ImageGrab
            screenshot = ImageGrab.grab(
                bbox=(target.left, target.top, target.right, target.bottom)
            )

        # Detect Retina scale then resize to logical resolution.
        # LLM coordinate hints in the system prompt are in logical-point space,
        # so we always send a logical-resolution image and use scale=1.0.
        if target.width > 0:
            raw_scale = screenshot.width / target.width
        else:
            raw_scale = 1.0

        if raw_scale > 1.0:
            logical_size = (target.width, target.height)
            screenshot = screenshot.resize(logical_size, _LANCZOS)
            print(f"[INFO] Retina {raw_scale:.0f}x → resized to logical {logical_size}")

        self.last_scale = 1.0  # coords are now in logical space, no further scaling needed
        print(f"[INFO] Screenshot size sent to LLM: {screenshot.size}")

        if SAVE_SCREENSHOTS:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = os.path.join(SCREENSHOT_DIR, f"wechat_{ts}.png")
            screenshot.save(path)
            print(f"[INFO] WeChat screenshot saved: {path}")

        return screenshot
