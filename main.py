# -*- coding: utf-8 -*-
"""
WeChat Mini Program Automation Agent – Entry Point.

Usage:
    python main.py "打开微信中的 美团 小程序，完成登录"
    python main.py --task "搜索并打开 京东购物 小程序"
"""

import argparse
import sys

from agent.core import WeChatMiniProgramAgent


def main():
    parser = argparse.ArgumentParser(
        description="LLM-driven WeChat Mini Program automation agent"
    )
    parser.add_argument(
        "task",
        nargs="?",
        default=None,
        help="Natural language task description",
    )
    parser.add_argument(
        "--task", "-t",
        dest="task_flag",
        default=None,
        help="Alternative way to specify the task",
    )

    args = parser.parse_args()
    task = args.task or args.task_flag

    if not task:
        print("请提供任务描述，例如:")
        print('  python main.py "打开微信中的 美团 小程序"')
        print('  python main.py --task "搜索并打开 京东购物 小程序"')
        sys.exit(1)

    print(f"[DEBUG] Initializing agent with task: {task}")
    agent = WeChatMiniProgramAgent(task=task)
    print("[DEBUG] Running agent...")
    result = agent.run()
    print(f"[DEBUG] Finished run with success={result.get('success')}")
    agent.print_summary(result)


if __name__ == "__main__":
    main()
