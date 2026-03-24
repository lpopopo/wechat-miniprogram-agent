# 微信小程序自动化 Agent

> 使用大模型的多模态视觉能力，自动操作微信桌面客户端中的小程序。支持 macOS 和 Windows。

## 项目结构

```
wechat-miniprogram-agent/
├── agent/
│   ├── core.py               # Agent 主循环（规划→截图→分析→操作）
│   └── vision.py             # 多模态 LLM 视觉分析 + 任务规划模块
├── automation/
│   ├── wechat_controller.py  # 微信窗口控制与截图（跨平台）
│   └── gui_actions.py        # GUI 操作执行器
├── config/
│   └── settings.py           # 配置管理（跨平台路径）
├── tests/
│   └── verify_tech_blockers.py  # 技术卡点验证脚本
├── .env.example              # 环境变量示例
├── requirements.txt          # Python 依赖
├── main.py                   # CLI 入口
└── README.md
```

## 快速开始

### 环境要求

- Python 3.9+
- macOS 10.15+ 或 Windows 10+
- 微信桌面客户端（Mac 版 / Windows 版）

**macOS 额外要求：** 首次运行需在「系统设置 → 隐私与安全性」中授权：
- **辅助功能**（Accessibility）：允许终端 / Python 控制鼠标键盘
- **屏幕录制**（Screen Recording）：允许截图

### 1. 创建虚拟环境并安装依赖

```bash
cd wechat-miniprogram-agent
python3 -m venv venv

# macOS / Linux
source venv/bin/activate

# Windows
venv\Scripts\activate

pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env，填入 LLM_API_KEY 等配置
```

关键配置项：

```env
# LLM 接口（支持任何 OpenAI 兼容接口）
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1   # 注意：结尾到 /v1，不要带 /chat/completions
LLM_MODEL=gpt-4o

# 微信路径（macOS 默认 "WeChat"，Windows 需填完整 exe 路径）
# WECHAT_EXE_PATH=WeChat
```

### 3. 运行 Agent

```bash
# 打开指定小程序
python3 main.py "打开微信中的 美团 小程序"

# 打开小程序 + 登录 + 执行操作
python3 main.py "搜索并打开 新城小新家 小程序，登录账号 138xxxx，城市选天津，搜索项目万青云启"

# 使用 --task 参数
python3 main.py --task "在微信中打开 滴滴出行 小程序"
```

## 工作原理

```
┌─────────────────────────────────────────────────────────────┐
│                        Agent 运行流程                         │
│                                                               │
│  启动                                                         │
│   │                                                           │
│   ▼                                                           │
│  【规划阶段】LLM 将任务拆解为有序子任务列表                      │
│   │                                                           │
│   ▼                                                           │
│  ┌─────────┐    ┌─────────────────────┐    ┌──────────────┐  │
│  │  截图    │───▶│  LLM 分析           │───▶│  执行操作    │  │
│  │ 优先截   │    │  · 查看任务列表状态  │    │  click       │  │
│  │ 小程序   │    │  · 分析当前截图      │    │  type        │  │
│  │ 浮窗    │    │  · 决定下一步操作    │    │  hotkey      │  │
│  └─────────┘    │  · 更新子任务状态    │    │  multi_action│  │
│       ▲         └─────────────────────┘    └──────────────┘  │
│       └──────────────────────────────────────────┘           │
│                      循环直到全部子任务完成                     │
└─────────────────────────────────────────────────────────────┘
```

## 核心特性

### 任务规划（Task Planning）
启动时 LLM 先将自然语言任务拆解为有序子任务列表，每步执行后实时更新完成状态，确保 LLM 始终知道"做了什么、正在做什么、还剩什么"，避免重复操作。

```
▶ 规划子任务 …
[1] 在微信中搜索并打开"新城小新家"小程序
[2] 确认登录状态
[3] 切换城市为天津
[4] 搜索项目"万青云启"并进入详情
```

### 跨平台支持

| 功能 | macOS | Windows |
|------|-------|---------|
| 窗口查找 | Quartz `CGWindowListCopyWindowInfo` | Win32 `EnumWindows` |
| 启动微信 | `open -a WeChat` | `subprocess.Popen` |
| 置前窗口 | AppleScript `osascript` | `SetForegroundWindow` |
| 截图 | `screencapture -x -R` | `PIL.ImageGrab` |
| 中文输入 | `pbcopy` + `command+v` | `win32clipboard` + `ctrl+v` |

### 多屏幕 & Retina 支持
- 自动过滤菜单栏等小窗口，优先抓取小程序浮窗
- 截图自动缩放至逻辑分辨率，坐标与 pyautogui 逻辑点 1:1 对应
- 支持副屏坐标（含负坐标）

### 智能操作规则
- **搜索优先**：查找项目/内容时强制使用搜索功能，禁止滚动列表
- **搜索 icon 定位**：点击搜索框右侧放大镜图标，比点击文字区域更准确
- **协议自动处理**：登录前自动识别并完成用户协议 / 隐私政策勾选确认
- **批量操作**：支持 `multi_action` 一步发出多个指令（如同时勾选多个协议）
- **死循环检测**：检测到重复点击同一坐标时，自动偏移坐标重试

### 支持的动作类型

| 动作 | 说明 | 示例 |
|------|------|------|
| `click` | 点击 | `{"type": "click", "x": 100, "y": 200}` |
| `double_click` | 双击 | `{"type": "double_click", "x": 100, "y": 200}` |
| `right_click` | 右击 | `{"type": "right_click", "x": 100, "y": 200}` |
| `type` | 输入文字 | `{"type": "type", "text": "hello", "x": 100, "y": 200}` |
| `hotkey` | 快捷键 | `{"type": "hotkey", "keys": ["enter"]}` |
| `scroll` | 滚动 | `{"type": "scroll", "clicks": -3}` |
| `wait` | 等待 | `{"type": "wait", "seconds": 2}` |
| `multi_action` | 批量操作 | `{"type": "multi_action", "actions": [...]}` |
| `done` | 任务完成 | `{"type": "done", "summary": "完成描述"}` |

## 支持的 LLM

使用 OpenAI 兼容接口，支持任何多模态模型：

- GPT-4o（推荐）
- Gemini Vision
- DeepSeek-V3
- 通义千问 VL
- 其他支持 OpenAI API 格式的视觉模型

## 安全机制

- **pyautogui FailSafe**：鼠标移到屏幕左上角立即停止
- **最大步数限制**：默认 30 步，防止无限循环（可通过 `MAX_STEPS` 配置）
- **虚拟环境隔离**：建议在 venv 中运行，避免污染系统 Python
