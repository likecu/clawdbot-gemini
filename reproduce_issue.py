import asyncio
import logging
import sys
from unittest.mock import MagicMock

# Mock src.adapters.lark to avoid ImportError in src/__init__.py
sys.modules["src.adapters.lark"] = MagicMock()

from src.core.agent import Agent, AgentMode
from src.core.session import SessionManager
from src.core.prompt import PromptBuilder

# Mock LLM Client
class MockLLMClient:
    async def chat(self, messages):
        # Simulate delay
        await asyncio.sleep(0.1)
        # return the last message content to verify context
        return f"Echo: {messages[-1]['content']}"

async def main():
    logging.basicConfig(level=logging.INFO)
    
    # Initialize components
    session_manager = SessionManager(redis_host=None) # Use memory storage
    prompt_builder = PromptBuilder()
    llm_client = MockLLMClient()
    agent = Agent(llm_client, session_manager, prompt_builder)
    
    # Simulate concurrent requests from different users
    users = ["user1", "user2", "user3"]
    tasks = []
    
    for user in users:
        # User ID format: platform:user_id
        user_id = f"qq:{user}"
        # Chat ID format: unique session
        chat_id = f"qq:user:{user}:20260214"
        message = f"Hello from {user}"
        
        tasks.append(agent.process_message(user_id, chat_id, message))
        
    results = await asyncio.gather(*tasks)
    
    for i, user in enumerate(users):
        print(f"User: {user}, Response: {results[i]['text']}")
        # Verify history
        history = session_manager.get_history(f"qq:user:{user}:20260214")
        print(f"History for {user}: {history}")
        
        # Check if history contains other users' messages
        for msg in history:
            if user not in msg['content'] and "Echo" not in msg['content']:
                 print(f"ERROR: Cross-talk detected! {user} has unexpected message: {msg['content']}")

if __name__ == "__main__":
    asyncio.run(main())
