"""
技术卡点验证脚本 - Tech Blocker Verification Tests

独立运行每个技术卡点的验证，快速判断哪些环节可行、哪些存在障碍。

Usage:
    python tests/verify_tech_blockers.py --all
    python tests/verify_tech_blockers.py --test wechat_window
    python tests/verify_tech_blockers.py --test screenshot
    python tests/verify_tech_blockers.py --test llm_vision
    python tests/verify_tech_blockers.py --test gui_action
"""

import argparse
import os
import sys
import time
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.panel import Panel

console = Console()


def test_wechat_window():
    """
    卡点 1：验证能否找到并控制微信窗口
    """
    console.rule("[bold cyan]TEST 1: 微信窗口检测[/bold cyan]")

    from automation.wechat_controller import WeChatController

    controller = WeChatController()

    # 1a. 检测微信是否在运行
    found = controller.find_wechat_window()
    if found:
        console.print("[green]✔ 找到微信窗口[/green]")
    else:
        console.print("[red]✘ 未找到微信窗口[/red]")
        console.print("[yellow]请确保微信已打开并登录[/yellow]")
        return False

    # 1b. 获取窗口尺寸
    rect = controller.get_window_rect()
    if rect:
        console.print(f"[green]✔ 窗口位置: left={rect[0]}, top={rect[1]}, width={rect[2]}, height={rect[3]}[/green]")
    else:
        console.print("[red]✘ 无法获取窗口尺寸[/red]")
        return False

    # 1c. 聚焦窗口
    focused = controller.focus_wechat()
    if focused:
        console.print("[green]✔ 成功聚焦微信窗口[/green]")
    else:
        console.print("[yellow]⚠ 无法聚焦窗口（可能影响后续操作）[/yellow]")

    return True


def test_screenshot():
    """
    卡点 2：验证截图功能
    """
    console.rule("[bold cyan]TEST 2: 截图功能[/bold cyan]")

    from automation.wechat_controller import WeChatController

    controller = WeChatController()

    if not controller.find_wechat_window():
        console.print("[red]✘ 未找到微信窗口，跳过截图测试[/red]")
        return False

    # 2a. 全屏截图
    full_screenshot = controller.take_screenshot()
    console.print(f"[green]✔ 全屏截图成功: {full_screenshot.size}[/green]")

    # 2b. 微信窗口截图
    wechat_screenshot = controller.take_wechat_screenshot()
    if wechat_screenshot:
        console.print(f"[green]✔ 微信窗口截图成功: {wechat_screenshot.size}[/green]")

        # Save for inspection
        wechat_screenshot.save("screenshots/test_wechat_window.png")
        console.print("[dim]截图已保存: screenshots/test_wechat_window.png[/dim]")
    else:
        console.print("[red]✘ 微信窗口截图失败[/red]")
        return False

    return True


def test_llm_vision():
    """
    卡点 3：验证多模态 LLM 能否理解微信界面
    """
    console.rule("[bold cyan]TEST 3: LLM 视觉理解[/bold cyan]")

    from config.settings import LLM_API_KEY

    if not LLM_API_KEY or LLM_API_KEY == "your-api-key-here":
        console.print("[red]✘ 未配置 LLM_API_KEY，请在 .env 文件中设置[/red]")
        return False

    from automation.wechat_controller import WeChatController
    from agent.vision import VisionAnalyzer

    controller = WeChatController()
    vision = VisionAnalyzer()

    # Take screenshot
    if not controller.find_wechat_window():
        console.print("[yellow]⚠ 未找到微信窗口，使用全屏截图测试[/yellow]")
        screenshot = controller.take_screenshot()
    else:
        screenshot = controller.take_wechat_screenshot()

    # Test LLM analysis
    console.print("[yellow]🧠 正在发送截图到 LLM 分析 …[/yellow]")
    start_time = time.time()

    result = vision.analyze(
        screenshot=screenshot,
        task="描述当前界面内容，识别所有可见的按钮和文字",
    )

    elapsed = time.time() - start_time
    console.print(f"[dim]LLM 响应时间: {elapsed:.1f}s[/dim]")

    if result.get("observation") and result["observation"] != "Failed to parse response":
        console.print(f"[green]✔ LLM 分析成功[/green]")
        console.print(f"  观察: {result.get('observation', 'N/A')}")
        console.print(f"  思考: {result.get('thinking', 'N/A')}")
        console.print(f"  操作: {json.dumps(result.get('action', {}), ensure_ascii=False)}")
        return True
    else:
        console.print("[red]✘ LLM 分析失败[/red]")
        console.print(f"  详情: {result}")
        return False


def test_gui_action():
    """
    卡点 4：验证 GUI 操作能否正确执行
    """
    console.rule("[bold cyan]TEST 4: GUI 操作执行[/bold cyan]")

    from automation.gui_actions import GUIActionExecutor

    executor = GUIActionExecutor()

    # 4a. 移动鼠标（安全操作）
    import pyautogui
    screen_w, screen_h = pyautogui.size()
    center_x, center_y = screen_w // 2, screen_h // 2

    result = executor.execute({"type": "move", "x": center_x, "y": center_y})
    if result["success"]:
        console.print(f"[green]✔ 鼠标移动成功: {result['message']}[/green]")
    else:
        console.print(f"[red]✘ 鼠标移动失败: {result['message']}[/red]")
        return False

    # 4b. 等待操作
    result = executor.execute({"type": "wait", "seconds": 0.5})
    console.print(f"[green]✔ 等待操作成功: {result['message']}[/green]")

    # 4c. 滚动操作
    result = executor.execute({"type": "scroll", "clicks": -1})
    if result["success"]:
        console.print(f"[green]✔ 滚动操作成功: {result['message']}[/green]")
    else:
        console.print(f"[red]✘ 滚动操作失败: {result['message']}[/red]")

    # 4d. 输入操作（模拟输入中文）
    result = executor.execute({"type": "type", "text": "测试输入"})
    if result["success"]:
        console.print(f"[green]✔ 输入操作成功: {result['message']}[/green]")
    else:
        console.print(f"[red]✘ 输入操作失败: {result['message']}[/red]")

    console.print("[yellow]⚠ 请确保有一个可以接收输入的焦点位置[/yellow]")
    return True


def test_full_flow_dry_run():
    """
    卡点 5：验证完整流程（干跑模式，不执行真实操作）
    """
    console.rule("[bold cyan]TEST 5: 完整流程干跑[/bold cyan]")

    from config.settings import LLM_API_KEY

    # Check all prerequisites
    checks = {
        "pyautogui": False,
        "pywinauto": False,
        "openai": False,
        "PIL": False,
        "LLM_API_KEY": bool(LLM_API_KEY and LLM_API_KEY != "your-api-key-here"),
    }

    try:
        import pyautogui
        checks["pyautogui"] = True
    except ImportError:
        pass

    try:
        import pywinauto
        checks["pywinauto"] = True
    except ImportError:
        pass

    try:
        import openai
        checks["openai"] = True
    except ImportError:
        pass

    try:
        from PIL import Image
        checks["PIL"] = True
    except ImportError:
        pass

    all_ok = True
    for name, ok in checks.items():
        if ok:
            console.print(f"  [green]✔ {name}[/green]")
        else:
            console.print(f"  [red]✘ {name}[/red]")
            all_ok = False

    if all_ok:
        console.print("\n[green]✔ 所有前置条件满足，可以运行完整 Agent[/green]")
    else:
        console.print("\n[yellow]⚠ 部分依赖缺失，请先安装:[/yellow]")
        console.print("  pip install -r requirements.txt")

    return all_ok


def main():
    parser = argparse.ArgumentParser(description="技术卡点验证脚本")
    parser.add_argument(
        "--test",
        choices=["wechat_window", "screenshot", "llm_vision", "gui_action", "full_flow"],
        default=None,
        help="Run a specific test",
    )
    parser.add_argument("--all", action="store_true", help="Run all tests")

    args = parser.parse_args()

    test_map = {
        "wechat_window": test_wechat_window,
        "screenshot": test_screenshot,
        "llm_vision": test_llm_vision,
        "gui_action": test_gui_action,
        "full_flow": test_full_flow_dry_run,
    }

    console.print(Panel(
        "[bold]微信小程序自动化 - 技术卡点验证[/bold]",
        border_style="cyan",
    ))

    if args.all or args.test is None:
        results = {}
        for name, func in test_map.items():
            try:
                results[name] = func()
            except Exception as e:
                console.print(f"[red]✘ {name} 异常: {e}[/red]")
                results[name] = False
            console.print()

        # Summary
        console.rule("[bold]验证总结[/bold]")
        for name, ok in results.items():
            status = "[green]✔ 通过[/green]" if ok else "[red]✘ 未通过[/red]"
            console.print(f"  {name}: {status}")
    else:
        func = test_map[args.test]
        try:
            func()
        except Exception as e:
            console.print(f"[red]✘ 异常: {e}[/red]")


if __name__ == "__main__":
    main()
