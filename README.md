# 微信小程序自动化 Agent - Demo

> 🤖 使用大模型的多模态视觉能力，自动操作微信桌面客户端中的小程序。

## 项目结构

```
wechat-miniprogram-agent/
├── agent/
│   ├── core.py          # Agent 主循环（截图→分析→操作）
│   └── vision.py        # 多模态 LLM 视觉分析模块
├── automation/
│   ├── wechat_controller.py  # 微信窗口控制与截图
│   └── gui_actions.py        # GUI 操作执行器
├── config/
│   └── settings.py      # 配置管理
├── tests/
│   └── verify_tech_blockers.py  # 技术卡点验证脚本
├── .env.example         # 环境变量示例
├── requirements.txt     # Python 依赖
├── main.py             # CLI 入口
└── README.md
```

## 快速开始

### 环境要求

- Python 3.9+
- macOS 10.15+ 或 Windows 10+
- 微信桌面客户端（Mac 版 / Windows 版）

**macOS 额外要求：** 需要在「系统设置 → 隐私与安全性」中授权以下权限：
- **辅助功能**（Accessibility）：允许终端/Python 控制鼠标键盘
- **屏幕录制**（Screen Recording）：允许截图

### 1. 安装依赖

```bash
cd wechat-miniprogram-agent
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 文件，填入你的 LLM API Key
```

### 3. 验证技术卡点

```bash
# 运行所有验证
python tests/verify_tech_blockers.py --all

# 单独验证微信窗口检测
python tests/verify_tech_blockers.py --test wechat_window

# 单独验证截图功能
python tests/verify_tech_blockers.py --test screenshot

# 单独验证 LLM 视觉理解
python tests/verify_tech_blockers.py --test llm_vision
```

### 4. 运行 Agent

```bash
# 打开指定小程序
python main.py "打开微信中的 美团 小程序"

# 打开小程序并登录
python main.py "搜索并打开 京东购物 小程序，然后完成登录"

# 使用 --task 参数
python main.py --task "在微信中打开 滴滴出行 小程序"
```

## 工作原理

```
┌──────────────────────────────────────────────────────┐
│                    Agent Loop                          │
│                                                        │
│  ┌─────────┐    ┌──────────┐    ┌─────────────────┐  │
│  │ 截图     │───▶│ LLM 分析  │───▶│ 执行 GUI 操作   │  │
│  │ pyautogui│    │ GPT-4o   │    │ click/type/...  │  │
│  └─────────┘    └──────────┘    └─────────────────┘  │
│       ▲                                    │          │
│       └────────────────────────────────────┘          │
│                   循环直到完成                          │
└──────────────────────────────────────────────────────┘
```

## 支持的 LLM

本项目使用 OpenAI 兼容接口，支持：
- GPT-4o (推荐)
- Gemini Vision
- DeepSeek-V3
- 通义千问 VL
- 任何支持 OpenAI API 格式的多模态模型

## 技术要点

- **视觉驱动**: 不依赖微信内部 API，纯截图 + 多模态模型识别
- **坐标定位**: LLM 分析截图后返回精确的点击坐标
- **上下文记忆**: 保留最近 5 步操作历史，帮助模型理解当前进展
- **安全机制**: pyautogui FailSafe（鼠标移到左上角紧急停止）
