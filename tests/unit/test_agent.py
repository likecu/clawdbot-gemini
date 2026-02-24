
import pytest
from unittest.mock import MagicMock, AsyncMock
from core.agent import Agent
from core.types import AgentMode

@pytest.fixture
def mock_llm():
    llm = MagicMock()
    # Mock chat_with_thinking (同步或异步取决于实现，Agent使用同步思考？)
    # Agent._call_llm 逻辑: 
    # if hasattr(self.llm_client, 'chat') and inspect.iscoroutinefunction... -> await chat
    # elif hasattr(self.llm_client, 'chat_with_thinking') -> sync call
    
    # 为了简单起见，mock 异步 chat 方法，因为它覆盖了第一个分支
    llm.chat = AsyncMock(return_value="Mocked LLM Response")
    return llm

@pytest.fixture
def mock_session_manager():
    return MagicMock()

@pytest.fixture
def agent(mock_llm, mock_session_manager):
    return Agent(llm_client=mock_llm, session_manager=mock_session_manager)

@pytest.mark.asyncio
async def test_process_message_conversation(agent, mock_llm):
    # 设置
    user_id = "test_user"
    chat_id = "test_chat"
    message = "Hello"
    
    # 执行
    result = await agent.process_message(user_id, chat_id, message)
    
    # 验证
    assert result["success"] is True
    assert result["text"] == "Mocked LLM Response"
    assert result["mode"] == AgentMode.CONVERSATION.value
    
    # 验证 LLM 调用
    mock_llm.chat.assert_called_once()
    call_args = mock_llm.chat.call_args[0][0] # messages list
    assert len(call_args) > 0
    assert call_args[-1]["content"] == message

@pytest.mark.asyncio
async def test_process_message_code_generation(agent, mock_llm):
    # 设置
    user_id = "test_user"
    chat_id = "test_chat"
    message = "Write a python script"
    
    # 执行
    result = await agent.process_message(user_id, chat_id, message)
    
    # 验证模式切换
    assert result["mode"] == AgentMode.CODE_GENERATION.value
