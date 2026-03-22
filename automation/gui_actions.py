"""
GUI Action Executor.
Translates high-level action dicts from the LLM into pyautogui calls.
"""

import time
from typing import Any, Dict

import pyautogui

from config.settings import ACTION_DELAY

# Safety: pyautogui will raise FailSafeException when the mouse
# moves into the upper-left corner of the screen.
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.25  # small default pause between pyautogui calls


class GUIActionExecutor:
    """Execute GUI actions returned by the LLM Agent."""

    # Supported action types
    SUPPORTED_ACTIONS = {
        "click",
        "double_click",
        "right_click",
        "type",
        "hotkey",
        "scroll",
        "move",
        "wait",
        "done",
    }

    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single action and return a result dict.

        Parameters
        ----------
        action : dict
            Must contain ``"type"`` and type-specific parameters.
            Examples::

                {"type": "click", "x": 450, "y": 320}
                {"type": "type", "text": "hello world"}
                {"type": "hotkey", "keys": ["ctrl", "a"]}
                {"type": "scroll", "clicks": -3}
                {"type": "wait", "seconds": 2}
                {"type": "done", "summary": "Task completed"}

        Returns
        -------
        dict  with keys ``"success"`` (bool) and ``"message"`` (str).
        """
        action_type = action.get("type", "").lower()

        if action_type not in self.SUPPORTED_ACTIONS:
            return {
                "success": False,
                "message": f"Unsupported action type: {action_type}",
            }

        handler = getattr(self, f"_do_{action_type}", None)
        if handler is None:
            return {"success": False, "message": f"No handler for: {action_type}"}

        try:
            result = handler(action)
            time.sleep(ACTION_DELAY)
            return result
        except Exception as e:
            return {"success": False, "message": f"Action failed: {e}"}

    # ------------------------------------------------------------------ #
    # Action Handlers
    # ------------------------------------------------------------------ #
    def _do_click(self, action: Dict) -> Dict:
        x, y = int(action["x"]), int(action["y"])
        # Move the mouse smoothly to the coordinate so the UI registers hover state
        pyautogui.moveTo(x, y, duration=0.2)
        time.sleep(0.1)
        pyautogui.click()
        return {"success": True, "message": f"Clicked at ({x}, {y})"}

    def _do_double_click(self, action: Dict) -> Dict:
        x, y = int(action["x"]), int(action["y"])
        pyautogui.doubleClick(x, y)
        return {"success": True, "message": f"Double-clicked at ({x}, {y})"}

    def _do_right_click(self, action: Dict) -> Dict:
        x, y = int(action["x"]), int(action["y"])
        pyautogui.rightClick(x, y)
        return {"success": True, "message": f"Right-clicked at ({x}, {y})"}

    def _do_type(self, action: Dict) -> Dict:
        text = str(action.get("text", ""))
        # If coordinates are provided, click first
        if "x" in action and "y" in action:
            x, y = int(action["x"]), int(action["y"])
            # Move the mouse smoothly to the coordinate so the UI registers hover state
            pyautogui.moveTo(x, y, duration=0.2)
            time.sleep(0.1)
            # Click once to avoid triggering window maximize/restore on title bar
            pyautogui.click()
            time.sleep(0.5)  # give it more time for the focus animation

        # Handle 'enter' presses derived from newlines
        has_newline = '\n' in text
        clean_text = text.replace('\n', '')

        if clean_text:
            if clean_text.isascii():
                pyautogui.typewrite(clean_text, interval=0.05)
            else:
                # For Chinese characters, use clipboard to Paste (reliable in most apps)
                try:
                    import win32clipboard
                    import win32con
                    
                    win32clipboard.OpenClipboard()
                    win32clipboard.EmptyClipboard()
                    # Use Unicode format for non-ASCII
                    win32clipboard.SetClipboardText(clean_text, win32con.CF_UNICODETEXT)
                    win32clipboard.CloseClipboard()
                    
                    # Perform Paste action
                    pyautogui.hotkey("ctrl", "v")
                    time.sleep(0.2)
                except Exception as e:
                    # Fallback to write if clipboard fails
                    pyautogui.write(clean_text)
                    return {"success": True, "message": f"Typed (fallback): {text!r} - error: {e}"}

        if has_newline:
            # Press enter for each newline found
            for _ in range(text.count('\n')):
                pyautogui.press('enter')
                time.sleep(0.2)

        return {"success": True, "message": f"Typed: {text!r}"}

    def _do_hotkey(self, action: Dict) -> Dict:
        keys = action.get("keys", [])
        if isinstance(keys, str):
            keys = keys.split("+")
        pyautogui.hotkey(*keys)
        return {"success": True, "message": f"Hotkey: {'+'.join(keys)}"}

    def _do_scroll(self, action: Dict) -> Dict:
        clicks = int(action.get("clicks", -3))
        x = action.get("x")
        y = action.get("y")
        if x is not None and y is not None:
            pyautogui.scroll(clicks, int(x), int(y))
        else:
            pyautogui.scroll(clicks)
        return {"success": True, "message": f"Scrolled {clicks} clicks"}

    def _do_move(self, action: Dict) -> Dict:
        x, y = int(action["x"]), int(action["y"])
        pyautogui.moveTo(x, y, duration=0.3)
        return {"success": True, "message": f"Moved to ({x}, {y})"}

    def _do_wait(self, action: Dict) -> Dict:
        seconds = float(action.get("seconds", 1))
        time.sleep(seconds)
        return {"success": True, "message": f"Waited {seconds}s"}

    def _do_done(self, action: Dict) -> Dict:
        summary = action.get("summary", "Task completed")
        return {"success": True, "message": f"Done – {summary}"}
