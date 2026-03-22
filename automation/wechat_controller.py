"""
Screenshot and Window Management Utilities.
Provides functions for capturing screenshots and managing WeChat window.

Uses Win32 API directly for reliable, fast window management instead of
pywinauto (which can hang when connecting to WeChat via UIA backend).
"""

import os
import ctypes
import ctypes.wintypes as wintypes
import subprocess
import time
from datetime import datetime
from typing import List, Optional, Tuple

from PIL import Image, ImageGrab

from config.settings import (
    WECHAT_WINDOW_TITLE,
    WECHAT_EXE_PATH,
    SCREENSHOT_DIR,
    SAVE_SCREENSHOTS,
)

# Win32 API references
user32 = ctypes.windll.user32

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2) # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass

SW_RESTORE = 9


class WindowInfo:
    """Lightweight wrapper for a discovered window."""

    def __init__(self, hwnd: int, title: str, rect: Tuple[int, int, int, int]):
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


def _enum_windows_by_title(keyword: str) -> List[WindowInfo]:
    """Enumerate all visible windows whose title contains *keyword*."""
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
                    # Convert POINTER(c_int) → Python int
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


class WeChatController:
    """Controls the WeChat desktop application window via Win32 API."""

    def __init__(self):
        self.window: Optional[WindowInfo] = None
        self._ensure_screenshot_dir()

    def _ensure_screenshot_dir(self):
        if SAVE_SCREENSHOTS:
            os.makedirs(SCREENSHOT_DIR, exist_ok=True)

    # ------------------------------------------------------------------ #
    # Window Management
    # ------------------------------------------------------------------ #
    def find_wechat_window(self) -> bool:
        """Try to find an already-running WeChat window."""
        windows = _enum_windows_by_title(WECHAT_WINDOW_TITLE)
        if windows:
            self.window = windows[0]
            print(f"[INFO] Found WeChat window: {self.window}")
            return True
        print("[INFO] WeChat window not found.")
        return False

    def launch_wechat(self) -> bool:
        """Launch WeChat executable if it is not already running."""
        if self.find_wechat_window():
            print("[INFO] WeChat is already running.")
            return True

        if not os.path.exists(WECHAT_EXE_PATH):
            print(f"[ERROR] WeChat not found at: {WECHAT_EXE_PATH}")
            return False

        print(f"[INFO] Launching WeChat from {WECHAT_EXE_PATH} …")
        subprocess.Popen(WECHAT_EXE_PATH)
        time.sleep(5)  # wait for WeChat to start

        return self.find_wechat_window()

    def focus_wechat(self) -> bool:
        """Bring the WeChat window to the foreground."""
        if self.window is None:
            return False
        try:
            hwnd = self.window.hwnd
            # Restore if minimised
            if user32.IsIconic(hwnd):
                user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.3)
            # Refresh rect after restore
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
        """Return the (left, top, width, height) of the WeChat window."""
        if self.window is None:
            return None
        return (
            self.window.left,
            self.window.top,
            self.window.width,
            self.window.height,
        )

    # ------------------------------------------------------------------ #
    # Screenshot
    # ------------------------------------------------------------------ #
    def take_screenshot(
        self, region: Optional[Tuple[int, int, int, int]] = None
    ) -> Image.Image:
        """
        Capture a screenshot.

        Parameters
        ----------
        region : tuple, optional
            (left, top, width, height). If *None*, captures the whole screen.
        """
        if region:
            left, top, w, h = region
            bbox = (left, top, left + w, top + h)
            screenshot = ImageGrab.grab(bbox=bbox)
        else:
            screenshot = ImageGrab.grab()

        if SAVE_SCREENSHOTS:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = os.path.join(SCREENSHOT_DIR, f"screenshot_{ts}.png")
            screenshot.save(path)
            print(f"[INFO] Screenshot saved: {path}")

        return screenshot

    def take_wechat_screenshot(self) -> Optional[Image.Image]:
        """Capture a screenshot of only the WeChat window area."""
        # Do not force focus_wechat() here on every tick, because if a MiniProgram 
        # is opened, forcing the main window to focus will hide the MiniProgram!
        
        if self.window is None:
            print("[WARN] Falling back to full-screen screenshot")
            return self.take_screenshot()

        bbox = (
            self.window.left,
            self.window.top,
            self.window.right,
            self.window.bottom,
        )
        screenshot = ImageGrab.grab(bbox=bbox)

        if SAVE_SCREENSHOTS:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            path = os.path.join(SCREENSHOT_DIR, f"wechat_{ts}.png")
            screenshot.save(path)
            print(f"[INFO] WeChat screenshot saved: {path}")

        return screenshot
