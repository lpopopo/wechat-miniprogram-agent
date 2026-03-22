"""Quick test: CLI proxy connectivity + LLM vision analysis"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from openai import OpenAI

print("=== Test 1: Basic LLM connectivity ===", flush=True)
try:
    client = OpenAI(api_key='your-api-key-1', base_url='http://127.0.0.1:8045/v1')
    r = client.chat.completions.create(
        model='gemini-3-flash',
        messages=[{'role': 'user', 'content': '回复OK两个字'}],
        max_tokens=10,
        timeout=30,
    )
    print(f"SUCCESS! Response: {r.choices[0].message.content}", flush=True)
    print(f"Model used: {r.model}", flush=True)
except Exception as e:
    print(f"FAILED: {e}", flush=True)
    sys.exit(1)

print("\n=== Test 2: Vision analysis of WeChat screenshot ===", flush=True)
try:
    import base64
    from PIL import Image
    import io

    # Load the test screenshot we captured earlier
    img_path = "screenshots/wechat_test.png"
    if not os.path.exists(img_path):
        print(f"No screenshot found at {img_path}, skipping vision test", flush=True)
        sys.exit(0)

    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    print(f"Screenshot loaded, sending to LLM...", flush=True)

    r = client.chat.completions.create(
        model='gemini-3-flash',
        messages=[
            {
                'role': 'user',
                'content': [
                    {'type': 'text', 'text': '请描述这个截图中的界面内容，包括左侧的聊天列表和右侧的聊天内容。列出你能看到的所有文字和按钮。'},
                    {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{img_b64}', 'detail': 'high'}},
                ],
            }
        ],
        max_tokens=1024,
        timeout=60,
    )
    print(f"SUCCESS! Vision analysis:", flush=True)
    print(r.choices[0].message.content, flush=True)
except Exception as e:
    print(f"Vision test FAILED: {e}", flush=True)

print("\nDone.", flush=True)
