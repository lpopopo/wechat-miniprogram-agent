print("Starting import test...")
try:
    import agent.core
    print("Successfully imported agent.core")
except Exception as e:
    print(f"FAILED to import agent.core: {e}")
    import traceback
    traceback.print_exc()

try:
    from agent.core import WeChatMiniProgramAgent
    print("Successfully imported WeChatMiniProgramAgent")
except Exception as e:
    print(f"FAILED to import WeChatMiniProgramAgent: {e}")

print("Import test done.")
