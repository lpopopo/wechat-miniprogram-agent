"""
Vision Module – Multimodal LLM Integration.
Sends screenshots to a vision-capable LLM and parses structured responses.
"""

import base64
import json
import io
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI
from PIL import Image

from config.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL


SYSTEM_PROMPT = """你是一个专业的 GUI 自动化助手。你的任务是根据用户描述的目标，分析当前屏幕截图，然后决定下一步要执行的操作。

## 你需要完成的工作流程
1. 查看【任务列表】，确认当前正在执行哪个子任务、哪些已完成
2. 分析当前截图，描述你看到的界面内容
3. 对照任务列表，判断是否有子任务刚刚完成
4. 决定下一步要执行的操作，并声明哪些子任务 ID 已完成

## 你可以执行的操作
返回一个 JSON 对象，包含以下字段：

### 操作类型 (type):
- **click**: 点击指定坐标 → {"type": "click", "x": 100, "y": 200}
- **double_click**: 双击 → {"type": "double_click", "x": 100, "y": 200}
- **right_click**: 右击 → {"type": "right_click", "x": 100, "y": 200}
- **type**: 输入文字 → {"type": "type", "text": "hello", "x": 100, "y": 200}
  - x, y 是可选的，如果提供了会先点击该位置再输入
- **wait**: 等待 → {"type": "wait", "seconds": 2}
- **done**: 任务完成 → {"type": "done", "summary": "完成描述"}
- **multi_action**: 一步执行多个连续操作（适合批量勾选、组合操作）→
  ```json
  {"type": "multi_action", "actions": [
      {"type": "click", "x": 20, "y": 300},
      {"type": "click", "x": 20, "y": 360},
      {"type": "click", "x": 207, "y": 680}
  ]}
  ```

## 坐标说明与视觉限制（非常重要！）
- 当前截图可能是**小程序浮窗的局部截图**（而非全屏）。你给出的坐标是相对于该截图左上角的位置，系统会自动加上窗口在屏幕上的偏移，无需你手动换算。
- 截图已缩放至逻辑分辨率，坐标与屏幕逻辑点 1:1 对应，请根据截图尺寸估算坐标，尽量点击元素中心。

## ⚠️ 微信与小程序核心防错机制（避免死循环）
1. **全新搜索时与左侧边栏下拉建议**：
   -发起全新搜索时，点击左上角的搜索框（大概坐标 x: 140到180, y: 45）。
   - **注意！在左侧边栏（如拉出的下拉列表）点击时，必须把 X 坐标设在 140 到 220 之间！**（如果 X 设在 80~100 附近，会点到最左侧的黑色导航栏边缘导致无效）。
   - 若出现左侧下拉搜索结果，请优先点击带有“小程序”标识且高度匹配的选项。
2. **处理屏幕中央搜索悬浮弹窗**：
   - 屏幕**正中央**弹出详细搜索结果时，说明搜索成功。
   - **绝对禁止此时再去点击左侧背景或搜索框！** 也绝对不要点击弹窗顶部的分类标签。
   - 必须在**屏幕中央的弹窗内部**点击搜索结果。**请仔细阅读结果列表，优先点击与目标名称匹配度最高、并且具有“小程序”标识或字样的选项**；如果无法明确区分，再选择最匹配的第一项。
3. **【强制要求】查找项目必须使用搜索，严禁滚动列表**：
   - 需要查找任何项目、楼盘、内容时，**必须使用搜索功能**，通过输入关键词定位目标。
   - **严禁**通过上下滚动列表来寻找目标项目，无论列表多短。
   - 如果当前页面没有搜索框，先导航到有搜索功能的页面再操作。
4. **搜索操作：优先点击搜索 icon**：
   - 触发搜索时，**优先点击搜索框右侧的放大镜图标（search icon）**，而不是点击搜索框的文字区域，这样更准确。
   - 放大镜图标通常位于搜索框右端，x 坐标接近搜索框右边界，y 坐标与搜索框垂直居中对齐。
   - 小程序内部的搜索框**通常是一个跳转按钮**，点击后跳转到搜索页面再输入。
   - 正确流程：① 点击搜索 icon → ② 在搜索页输入文字 → ③ 按回车触发搜索：`{"type": "hotkey", "keys": ["enter"]}`
4. **【最高优先级】处理协议弹窗（登录前必须先处理）**：
   - 在执行任何登录操作之前，必须先扫描当前界面是否存在以下任意一种弹窗：
     - 用户服务协议（”用户协议”、”服务协议”、”使用条款”等）
     - 隐私政策（”隐私政策”、”隐私协议”、”个人信息保护”等）
     - 授权确认（”授权登录”、”允许获取信息”等）
   - **只要检测到上述弹窗，必须先完成协议确认，再继续登录流程**：
     - 如果有**多个协议勾选框**，使用 `multi_action` **一次性全部勾选**，再点击确认按钮：
       ```json
       {“type”: “multi_action”, “actions”: [
           {“type”: “click”, “x”: 勾选框1_x, “y”: 勾选框1_y},
           {“type”: “click”, “x”: 勾选框2_x, “y”: 勾选框2_y},
           {“type”: “click”, “x”: 确认按钮_x, “y”: 确认按钮_y}
       ]}
       ```
     - 如果只有一个确认按钮（”同意”、”接受”、”我已阅读并同意”），直接点击
     - 如果需要滚动查看协议全文才能点击确认，先滚动到底部再点击确认
   - 协议确认完成后，再继续执行登录操作。
4. **处理小程序内部弹窗（如”隐私保护提示”、”登录授权”等）**：
   - 识别到绿色的”同意”、”允许”或”确定”按钮时，请务必仔细寻找按钮的**绝对物理中心**进行点击。
   - **【极其重要：死循环跳出机制】**：请仔细查看”历史操作”记录！如果发现你前几步已经执行了点击”同意”，但当前截图中该弹窗**依然存在**，这说明**你上一次猜测的坐标偏了，没有点到按钮的有效区域内！**
   - **此时绝对不能再输出与上次一模一样的坐标！** 你必须在之前坐标的基础上，向按钮的中心方向**偏移 20~40 像素**重新估算坐标（例如之前是 X: 1380, Y: 710 没生效，这次就换成 X: 1350, Y: 710 或者 Y 轴稍微调整），否则任务将陷入死循环失败。

## 已完成的目标绝不重复执行
- 仔细阅读历史操作记录，如果某个子目标已经在之前的步骤中**明确确认完成**，**绝对不要再重复执行**：
  - **已登录** = 历史中出现过用户名、手机号、头像、个人主页等登录成功的标志 → 直接跳过登录，执行下一个子任务
  - **已进入某页面** = 历史中已确认打开了目标页面 → 不要再返回重新打开
  - **已完成某操作** = 历史中已确认操作成功 → 不要重复
- 在 thinking 中**必须明确写出**："已确认[XX]完成（见步骤N），跳过，当前执行[YY]"

## 返回格式
请严格按照以下 JSON 格式返回，只返回 JSON，不要包含其他文本：

{
    "observation": "描述你在截图中看到了什么",
    "thinking": "你的思考过程。当前正在执行子任务[ID]，已完成子任务[IDs]",
    "completed_task_ids": [1, 2],
    "action": {
        "type": "click",
        "x": 1350,
        "y": 710
    }
}

- `completed_task_ids`：本步执行完成后，所有已完成的子任务 ID 列表（包含之前已完成的）
- 如果没有新完成的子任务，保持与上一步相同的列表
"""


PLAN_PROMPT = """你是一个任务规划助手。根据用户描述的自动化任务，将其拆解为有序的子任务列表。

要求：
- 子任务要具体、可执行、粒度适中（不要太细也不要太粗）
- 每个子任务对应一个可明确判断"是否完成"的操作目标
- 按执行顺序排列

请严格返回以下 JSON 格式，只返回 JSON：
{
    "tasks": [
        {"id": 1, "description": "子任务描述"},
        {"id": 2, "description": "子任务描述"}
    ]
}
"""


class VisionAnalyzer:
    """Analyzes screenshots using a multimodal LLM and returns structured actions."""

    def __init__(self):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL

    def plan_tasks(self, task: str) -> List[Dict[str, Any]]:
        """将自然语言任务拆解为子任务列表。返回 [{"id": 1, "description": "...", "status": "pending"}, ...]"""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": PLAN_PROMPT},
                    {"role": "user", "content": f"任务：{task}"},
                ],
                max_tokens=512,
                temperature=0.1,
                timeout=30,
            )
            content = response.choices[0].message.content.strip()
            if content.startswith("```"):
                content = content.split("\n", 1)[1]
                content = content[: content.rfind("```")].strip()
            data = json.loads(content)
            tasks = data.get("tasks", [])
            for t in tasks:
                t["status"] = "pending"
            return tasks
        except Exception as e:
            print(f"[WARN] Task planning failed: {e}, using single-task fallback")
            return [{"id": 1, "description": task, "status": "pending"}]

    def _image_to_base64(self, image: Image.Image) -> str:
        """Convert a PIL Image to a base64-encoded PNG string."""
        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def analyze(
        self,
        screenshot: Image.Image,
        task: str,
        history: Optional[List[Dict[str, Any]]] = None,
        task_plan: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:

        img_b64 = self._image_to_base64(screenshot)
        width, height = screenshot.size

        # Build the user message
        user_text_parts = [
            f"## 【核心任务 - 始终牢记】\n{task}\n",
        ]

        # 注入任务列表
        if task_plan:
            user_text_parts.append("## 任务列表（全局共享，始终参考）")
            for t in task_plan:
                status_icon = "✅" if t["status"] == "done" else "⏳"
                user_text_parts.append(f"{status_icon} [{t['id']}] {t['description']}")
            done_ids = [t["id"] for t in task_plan if t["status"] == "done"]
            pending = [t for t in task_plan if t["status"] == "pending"]
            if pending:
                user_text_parts.append(f"\n当前应执行：[{pending[0]['id']}] {pending[0]['description']}")
            user_text_parts.append("")

        user_text_parts.append(
            f"## 当前截图信息\n截图尺寸: 宽 {width} 像素, 高 {height} 像素。\n"
        )

        if history:
            user_text_parts.append("## 历史操作（注意是否陷入死循环）")
            for i, h in enumerate(history, 1):
                obs = h.get("observation", "N/A")
                if len(obs) > 100:
                    obs = obs[:100] + "…"
                act = h.get("action", {})
                user_text_parts.append(
                    f"步骤 {i}: 观察={obs} | 操作={json.dumps(act, ensure_ascii=False)}"
                )
            user_text_parts.append("")

        user_text_parts.append("## 请分析截图，更新任务列表状态，决定下一步操作")
        user_text = "\n".join(user_text_parts)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_text},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{img_b64}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ]

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=1024,
                    temperature=0.1,
                    timeout=120, 
                )

                content = response.choices[0].message.content.strip()
                
                if content.startswith("```"):
                    content = content.split("\n", 1)[1]
                    if content.endswith("```"):
                        content = content[: content.rfind("```")]
                    content = content.strip()
                
                if content.startswith("json\n"):
                    content = content[5:]

                result = json.loads(content)
                return result

            except json.JSONDecodeError as e:
                print(f"[ERROR] Failed to parse LLM response as JSON: {e}")
                print(f"[DEBUG] Raw response: {content}")
                return {
                    "observation": "Failed to parse response",
                    "thinking": f"JSON parse error: {e}",
                    "action": {"type": "wait", "seconds": 2},
                }
            except Exception as e:
                error_msg = str(e).lower()
                if "timed out" in error_msg or "timeout" in error_msg:
                    print(f"[WARNING] API request timed out (Attempt {attempt + 1}/{max_retries}). Retrying in 2 seconds...")
                    time.sleep(2)
                    if attempt == max_retries - 1:
                        return {
                            "observation": "API timeout after multiple attempts",
                            "thinking": "Network is unstable or model is too slow.",
                            "action": {"type": "wait", "seconds": 3}
                        }
                    continue
                else:
                    print(f"[ERROR] LLM API call failed: {e}")
                    return {
                        "observation": "API call failed",
                        "thinking": str(e),
                        "action": {"type": "wait", "seconds": 3},
                    }