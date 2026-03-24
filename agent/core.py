"""
Agent Core – Main control loop.
Orchestrates the screenshot → LLM analysis → action execution cycle.
"""

import time
from typing import Any, Dict, List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from agent.vision import VisionAnalyzer
from automation.wechat_controller import WeChatController
from automation.gui_actions import GUIActionExecutor
from config.settings import MAX_STEPS, SCREENSHOT_INTERVAL

console = Console()


class WeChatMiniProgramAgent:
    """
    LLM-driven agent that automates WeChat Mini Program operations.

    The agent follows a simple perceive-think-act loop:
    1. Take a screenshot of the WeChat window
    2. Send it to a multimodal LLM for analysis
    3. Execute the returned GUI action
    4. Repeat until the task is done or max steps exceeded
    """

    def __init__(self, task: str):
        """
        Parameters
        ----------
        task : str
            Natural language description of the task, e.g.
            "打开微信，搜索并打开 '美团' 小程序，然后完成登录"
        """
        self.task = task
        self.controller = WeChatController()
        self.vision = VisionAnalyzer()
        self.executor = GUIActionExecutor()
        self.history: List[Dict[str, Any]] = []
        self.task_plan: List[Dict[str, Any]] = []
        self.max_steps = MAX_STEPS

    def run(self) -> Dict[str, Any]:
        """Execute the agent loop and return the final result."""
        print(f"[DEBUG] Entering WeChatMiniProgramAgent.run() for task: {self.task}")
        console.print(Panel(
            f"[bold cyan]任务:[/bold cyan] {self.task}\n"
            f"[dim]最大步数: {self.max_steps}[/dim]",
            title="🤖 WeChat MiniProgram Agent",
            border_style="cyan",
        ))

        # Step 0: Ensure WeChat is running
        print("[DEBUG] Step 0: Checking WeChat...")
        console.print("\n[bold yellow]▶ Step 0:[/bold yellow] 启动微信 …")
        if not self.controller.launch_wechat():
            print("[DEBUG] Failed to launch/find WeChat")
            console.print("[bold red]✘ 无法启动或找到微信窗口，请确保微信已安装。[/bold red]")
            return {"success": False, "reason": "wechat_not_found", "steps": []}

        print("[DEBUG] WeChat found/launched, focusing...")
        self.controller.focus_wechat()
        console.print("[green]✔ 微信窗口已就绪[/green]\n")

        # Step 0.5: Plan tasks
        console.print("[bold yellow]▶ 规划子任务 …[/bold yellow]")
        self.task_plan = self.vision.plan_tasks(self.task)
        plan_table = Table(show_header=False, box=None, padding=(0, 1))
        for t in self.task_plan:
            plan_table.add_row(f"[dim][{t['id']}][/dim]", t["description"])
        console.print(plan_table)
        console.print()

        # Main loop
        for step in range(1, self.max_steps + 1):
            console.rule(f"[bold]Step {step}/{self.max_steps}[/bold]")

            # 1. Screenshot
            time.sleep(SCREENSHOT_INTERVAL)
            screenshot = self.controller.take_wechat_screenshot()
            if screenshot is None:
                console.print("[red]✘ 截图失败[/red]")
                continue

            console.print(f"[dim]截图尺寸: {screenshot.size}[/dim]")

            # 2. Analyze with LLM
            console.print("[yellow]🧠 正在分析截图 …[/yellow]")
            analysis = self.vision.analyze(
                screenshot=screenshot,
                task=self.task,
                history=self.history,
                task_plan=self.task_plan,
            )

            observation = analysis.get("observation", "N/A")
            thinking = analysis.get("thinking", "N/A")
            action = analysis.get("action", {"type": "wait", "seconds": 1})
            completed_ids = analysis.get("completed_task_ids", [])

            # Update task plan status
            if completed_ids and self.task_plan:
                for t in self.task_plan:
                    if t["id"] in completed_ids:
                        t["status"] = "done"

            # Display task list
            if self.task_plan:
                tl = Table(show_header=False, box=None, padding=(0, 1))
                for t in self.task_plan:
                    icon = "[green]✅[/green]" if t["status"] == "done" else "[dim]⏳[/dim]"
                    tl.add_row(icon, f"[{t['id']}]", t["description"])
                console.print(tl)

            # Display analysis
            table = Table(show_header=False, box=None, padding=(0, 1))
            table.add_row("[cyan]👁 观察:[/cyan]", observation)
            table.add_row("[magenta]💭 思考:[/magenta]", thinking)
            table.add_row("[green]🎯 操作:[/green]", str(action))
            console.print(table)

            # 3. Execute action
            # Translate window-relative pixel coordinates to absolute logical screen points.
            # LLM returns pixel coords based on the screenshot image.
            # On Retina displays the screenshot is 2x the logical size, so we must:
            #   1. Divide by scale (e.g. 2.0 for Retina) → logical coords within window
            #   2. Add the window's logical origin on screen → absolute screen coords
            rect = self.controller.get_window_rect()

            def _apply_offset(a: dict) -> dict:
                """Add window offset to any action that contains x/y coordinates."""
                a = a.copy()
                if rect and "x" in a and "y" in a:
                    a["x"] = int(a["x"]) + rect[0]
                    a["y"] = int(a["y"]) + rect[1]
                # Recursively handle multi_action sub-actions
                if a.get("type") == "multi_action" and "actions" in a:
                    a["actions"] = [_apply_offset(sub) for sub in a["actions"]]
                return a

            execute_action = _apply_offset(action)
            if rect and "x" in action and "y" in action:
                console.print(
                    f"[dim]坐标: ({action['x']},{action['y']}) "
                    f"+ 窗口偏移({rect[0]},{rect[1]}) "
                    f"→ 屏幕({execute_action['x']},{execute_action['y']})[/dim]"
                )

            console.print(f"[yellow]⚡ 执行: {execute_action}[/yellow]")
            result = self.executor.execute(execute_action)

            if result["success"]:
                console.print(f"[green]✔ {result['message']}[/green]")
            else:
                console.print(f"[red]✘ {result['message']}[/red]")

            # 4. Record history
            self.history.append({
                "step": step,
                "observation": observation,
                "thinking": thinking,
                "action": action,
                "result": result,
            })

            # 5. Check if done
            if action.get("type") == "done":
                console.print(Panel(
                    f"[bold green]✅ 任务完成![/bold green]\n{result['message']}",
                    border_style="green",
                ))
                return {
                    "success": True,
                    "steps": self.history,
                    "total_steps": step,
                }

        # Max steps exceeded
        console.print(Panel(
            "[bold red]⚠ 达到最大步数限制，任务未完成[/bold red]",
            border_style="red",
        ))
        return {
            "success": False,
            "reason": "max_steps_exceeded",
            "steps": self.history,
            "total_steps": self.max_steps,
        }

    def print_summary(self, result: Dict[str, Any]):
        """Print a summary of the agent run."""
        console.print("\n")
        console.rule("[bold]运行总结[/bold]")

        if self.task_plan:
            pt = Table(title="任务列表完成情况")
            pt.add_column("状态", justify="center")
            pt.add_column("ID", justify="center", style="dim")
            pt.add_column("子任务")
            for t in self.task_plan:
                icon = "✅" if t["status"] == "done" else "❌"
                pt.add_row(icon, str(t["id"]), t["description"])
            console.print(pt)

        table = Table(title="操作历史")
        table.add_column("步骤", justify="center", style="cyan")
        table.add_column("操作", style="green")
        table.add_column("结果", style="white")

        for h in result.get("steps", []):
            table.add_row(
                str(h["step"]),
                str(h["action"].get("type", "?")),
                h["result"].get("message", "?"),
            )

        console.print(table)
        status = "✅ 成功" if result["success"] else "❌ 失败"
        console.print(f"\n最终状态: [bold]{status}[/bold]")
        console.print(f"总步数: {result.get('total_steps', '?')}")
