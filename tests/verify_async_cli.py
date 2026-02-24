
import asyncio
import sys
import os
from unittest.mock import MagicMock, AsyncMock

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "../src"))

from core.agent import Agent
from core.tools.clawdbot_cli import ClawdbotCliTool

async def mock_notification_callback(session_id, content):
    print(f"\n[Mock Callback] Session: {session_id}")
    print(f"[Mock Callback] Content: {content}")

async def test_async_cli():
    print("--- Starting Async CLI Verification ---")
    
    # 1. Mock LLM Client
    mock_llm = MagicMock()
    # Simulate LLM reacting as Product Manager
    mock_llm.chat = AsyncMock(return_value="好的，我来安排开发。\n[Clawdbot: echo 'Hello Async World']")
    
    # 2. Mock Clawdbot Tool (to avoid actual subprocess in simple test)
    # We want to verify the Agent calls run_async
    mock_tool = ClawdbotCliTool()
    mock_tool.run_async = AsyncMock() 
    
    # Define side effect to simulate callback
    async def run_async_side_effect(prompt, session_id, callback):
        print(f"[Tool] Executing prompt: {prompt}")
        await asyncio.sleep(0.1)
        await callback(session_id, f"Tool Output for: {prompt}")
        
    mock_tool.run_async.side_effect = run_async_side_effect

    # 3. Create Agent
    agent = Agent(
        llm_client=mock_llm,
        session_manager=MagicMock(),
        prompt_builder=MagicMock(),
        clawdbot_tool=mock_tool,
        notification_callback=mock_notification_callback
    )
    
    # 4. Process Message
    print("Sending user message...")
    result = await agent.process_message(
        user_id="qq:123",
        chat_id="qq:user:123:date",
        message="Please echo hello",
        callback_session_id="qq:private:123"
    )
    
    # 5. Verify Immediate Response
    print(f"\nImmediate Response Text: {result['text']}")
    assert "正在调用 Clawdbot" in result['text']
    assert "异步发送" in result['text']
    
    # 6. Wait for Callback
    print("Waiting for background task...")
    await asyncio.sleep(0.2)
    
    # 7. Verify Tool Call
    mock_tool.run_async.assert_called_once()
    args = mock_tool.run_async.call_args
    assert args[0][0] == "echo 'Hello Async World'"
    assert args[0][1] == "qq:private:123" # Should match callback_session_id
    
    print("\n--- Verification Passed ---")

if __name__ == "__main__":
    asyncio.run(test_async_cli())
