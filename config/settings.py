"""Configuration settings for the WeChat Mini Program Agent."""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# LLM Configuration
# ============================================================
# 支持 OpenAI 兼容接口 (GPT-4o, Gemini, DeepSeek 等)
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

# ============================================================
# Agent Configuration
# ============================================================
MAX_STEPS = int(os.getenv("MAX_STEPS", "30"))
SCREENSHOT_INTERVAL = float(os.getenv("SCREENSHOT_INTERVAL", "1.0"))  # seconds
ACTION_DELAY = float(os.getenv("ACTION_DELAY", "0.5"))  # seconds between actions

# ============================================================
# WeChat Configuration
# ============================================================
WECHAT_WINDOW_TITLE = os.getenv("WECHAT_WINDOW_TITLE", "微信")
WECHAT_EXE_PATH = os.getenv(
    "WECHAT_EXE_PATH",
    r"C:\Program Files (x86)\Tencent\WeChat\WeChat.exe"
)

# Target mini program name
TARGET_MINIPROGRAM = os.getenv("TARGET_MINIPROGRAM", "")

# ============================================================
# Screenshot Configuration
# ============================================================
SCREENSHOT_DIR = os.getenv("SCREENSHOT_DIR", "screenshots")
SAVE_SCREENSHOTS = os.getenv("SAVE_SCREENSHOTS", "true").lower() == "true"
