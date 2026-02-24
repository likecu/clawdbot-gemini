
import sys
import os

# 添加 src 到路径
sys.path.append(os.path.join(os.getcwd(), "src"))

try:
    print("导入 MessageProcessor...")
    from core.services.message_processor import MessageProcessor
    print("MessageProcessor 导入成功。")

    print("导入 ClawdbotApplication...")
    from main import ClawdbotApplication
    print("ClawdbotApplication 导入成功。")
    
    print("导入 IntentDetector...")
    from core.services.intent_detector import IntentDetector
    print("IntentDetector 导入成功。")
    
    print("导入 Agent 以检查实例化...")
    from core.agent import Agent
    # Mock Agent 的依赖
    class MockLLM: pass
    agent = Agent(llm_client=MockLLM())
    print("Agent 实例化成功（包含 IntentDetector）。")
    
    print("重构验证通过。")
except Exception as e:
    print(f"验证失败: {e}")
    sys.exit(1)
