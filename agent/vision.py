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
1. 分析当前截图，描述你看到的界面内容
2. 对照任务目标，判断当前进展
3. 决定下一步要执行的操作

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

## 坐标说明与视觉限制（非常重要！）
- 坐标是相对于截图的绝对像素位置。请务必结合用户传入的【截图尺寸】（如 2576x1416）来按比例计算坐标！
- 请仔细观察界面元素的位置，尽量点击元素的中心位置。

## ⚠️ 微信与小程序核心防错机制（避免死循环）
1. **全新搜索时与左侧边栏下拉建议**：
   -发起全新搜索时，点击左上角的搜索框（大概坐标 x: 140到180, y: 45）。
   - **注意！在左侧边栏（如拉出的下拉列表）点击时，必须把 X 坐标设在 140 到 220 之间！**（如果 X 设在 80~100 附近，会点到最左侧的黑色导航栏边缘导致无效）。
   - 若出现左侧下拉搜索结果，请优先点击带有“小程序”标识且高度匹配的选项。
2. **处理屏幕中央搜索悬浮弹窗**：
   - 屏幕**正中央**弹出详细搜索结果时，说明搜索成功。
   - **绝对禁止此时再去点击左侧背景或搜索框！** 也绝对不要点击弹窗顶部的分类标签。
   - 必须在**屏幕中央的弹窗内部**点击搜索结果。**请仔细阅读结果列表，优先点击与目标名称匹配度最高、并且具有“小程序”标识或字样的选项**；如果无法明确区分，再选择最匹配的第一项。
3. **处理小程序内部弹窗（如“隐私保护提示”、“登录授权”等）**：
   - 识别到绿色的“同意”、“允许”或“确定”按钮时，请务必仔细寻找按钮的**绝对物理中心**进行点击。
   - **【极其重要：死循环跳出机制】**：请仔细查看“历史操作”记录！如果发现你前几步已经执行了点击“同意”，但当前截图中该弹窗**依然存在**，这说明**你上一次猜测的坐标偏了，没有点到按钮的有效区域内！**
   - **此时绝对不能再输出与上次一模一样的坐标！** 你必须在之前坐标的基础上，向按钮的中心方向**偏移 20~40 像素**重新估算坐标（例如之前是 X: 1380, Y: 710 没生效，这次就换成 X: 1350, Y: 710 或者 Y 轴稍微调整），否则任务将陷入死循环失败。

## 返回格式
请严格按照以下 JSON 格式返回，只返回 JSON，不要包含其他文本：

{
    "observation": "描述你在截图中看到了什么",
    "thinking": "你的思考过程。如果发现卡在同一界面，必须强调坐标偏移逻辑",
    "action": {
        "type": "click",
        "x": 1350,
        "y": 710
    }
}
"""


class VisionAnalyzer:
    """Analyzes screenshots using a multimodal LLM and returns structured actions."""

    def __init__(self):
        self.client = OpenAI(api_key=LLM_API_KEY, base_url=LLM_BASE_URL)
        self.model = LLM_MODEL

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
    ) -> Dict[str, Any]:
        
        img_b64 = self._image_to_base64(screenshot)
        
        # 获取图片尺寸，动态注入给大模型以减少坐标幻觉
        width, height = screenshot.size

        # Build the user message
        user_text_parts = [
            f"## 当前任务\n{task}\n",
            f"## 当前截图信息\n截图尺寸: 宽 {width} 像素, 高 {height} 像素。\n请根据此尺寸准确估算目标元素的像素坐标。\n"
        ]

        if history:
            user_text_parts.append("## 历史操作 (请务必注意是否陷入了重复点击的死循环！)")
            for i, h in enumerate(history[-5:], 1):   
                obs = h.get("observation", "N/A")
                act = h.get("action", {})
                user_text_parts.append(f"步骤 {i}: 观察={obs} | 操作={json.dumps(act, ensure_ascii=False)}")
            user_text_parts.append("")

        user_text_parts.append("## 请分析当前截图，决定下一步操作")
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