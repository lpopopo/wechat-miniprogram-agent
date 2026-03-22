import sys
import os
import time
import win32clipboard
import win32con
import pyautogui

# Add current dir to path
sys.path.append(os.getcwd())

from automation.gui_actions import GUIActionExecutor

def test_typing():
    executor = GUIActionExecutor()
    print("Testing typing '美团' in 3 seconds. Please focus on an input box.")
    time.sleep(3)
    
    # Try typing Chinese
    action = {"type": "type", "text": "美团"}
    result = executor.execute(action)
    print(f"Result: {result}")

if __name__ == "__main__":
    test_typing()
