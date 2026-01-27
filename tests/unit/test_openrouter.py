"""
OpenRouter客户端单元测试
"""

import unittest
import sys
import os
from unittest.mock import Mock, patch, MagicMock

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "src"
))

from adapters.llm.openrouter_client import OpenRouterClient, init_client


class TestOpenRouterClient(unittest.TestCase):
    """
    OpenRouter客户端测试类
    """
    
    def setUp(self):
        """
        测试前置条件
        """
        self.client = OpenRouterClient(
            api_key="test_api_key",
            model="tngtech/deepseek-r1t2-chimera:free"
        )
    
    def test_initialization(self):
        """
        测试初始化
        """
        self.assertEqual(self.client.api_key, "test_api_key")
        self.assertEqual(self.client.model, "tngtech/deepseek-r1t2-chimera:free")
        self.assertIsNotNone(self.client.session)
    
    def test_initialization_without_api_key(self):
        """
        测试无API密钥初始化
        """
        with self.assertRaises(ValueError):
            OpenRouterClient(api_key="")
    
    @patch('adapters.llm.openrouter_client.requests.Session')
    def test_chat_success(self, mock_session_class):
        """
        测试成功发送聊天消息
        """
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello!"}}],
            "usage": {"total_tokens": 50}
        }
        mock_response.raise_for_status = Mock()
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        # 替换session
        self.client.session = mock_session
        
        result = self.client.chat("Hello, world!")
        
        self.assertEqual(result["reply_text"], "Hello!")
        self.assertIn("usage", result)
    
    @patch('adapters.llm.openrouter_client.requests.Session')
    def test_chat_with_system_prompt(self, mock_session_class):
        """
        测试带系统提示词的聊天
        """
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Response with system prompt"}}],
            "usage": {}
        }
        mock_response.raise_for_status = Mock()
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        self.client.session = mock_session
        
        result = self.client.chat(
            "User message",
            system_prompt="You are a helpful assistant"
        )
        
        # 验证请求中包含系统提示词
        call_args = mock_session.post.call_args
        payload = call_args[1]["json"]
        messages = payload["messages"]
        
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], "You are a helpful assistant")
    
    @patch('adapters.llm.openrouter_client.requests.Session')
    def test_chat_with_thinking(self, mock_session_class):
        """
        测试带思考过程的聊天
        """
        mock_session = Mock()
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "<thinking>Thinking process</thinking>\n\nFinal answer"}}],
            "usage": {}
        }
        mock_response.raise_for_status = Mock()
        mock_session.post.return_value = mock_response
        mock_session_class.return_value = mock_session
        
        self.client.session = mock_session
        
        result = self.client.chat_with_thinking("Complex question")
        
        self.assertEqual(result["thinking"], "Thinking process")
        self.assertEqual(result["reply_text"], "Final answer")
    
    def test_clear_history(self):
        """
        测试清空历史
        """
        self.client.conversation_history = [{"role": "user", "content": "test"}]
        
        self.client.clear_history()
        
        self.assertEqual(len(self.client.conversation_history), 0)
    
    def test_get_history(self):
        """
        测试获取历史
        """
        self.client.conversation_history = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi!"}
        ]
        
        history = self.client.get_history()
        
        self.assertEqual(len(history), 2)
        # 验证是副本
        history.clear()
        self.assertEqual(len(self.client.conversation_history), 2)
    
    def test_set_model(self):
        """
        测试设置模型
        """
        self.client.set_model("new_model")
        
        self.assertEqual(self.client.model, "new_model")
    
    @patch('adapters.llm.openrouter_client.requests.Session')
    def test_chat_timeout(self, mock_session_class):
        """
        测试聊天超时处理
        """
        import requests
        mock_session = Mock()
        mock_session.post.side_effect = requests.exceptions.Timeout()
        mock_session_class.return_value = mock_session
        
        self.client.session = mock_session
        
        with self.assertRaises(Exception) as context:
            self.client.chat("Test message")
        
        self.assertIn("超时", str(context.exception))
    
    @patch('adapters.llm.openrouter_client.requests.Session')
    def test_chat_request_error(self, mock_session_class):
        """
        测试聊天请求错误处理
        """
        import requests
        mock_session = Mock()
        mock_session.post.side_effect = requests.exceptions.RequestException("Connection error")
        mock_session_class.return_value = mock_session
        
        self.client.session = mock_session
        
        with self.assertRaises(Exception) as context:
            self.client.chat("Test message")
        
        self.assertIn("请求失败", str(context.exception))


class TestOpenRouterClientSingleton(unittest.TestCase):
    """
    OpenRouter客户端单例测试类
    """
    
    def tearDown(self):
        """
        测试后清理
        """
        import adapters.llm.openrouter_client
        adapters.llm.openrouter_client._client_instance = None
    
    def test_init_client(self):
        """
        测试初始化客户端单例
        """
        client1 = init_client(api_key="test_key")
        client2 = init_client()
        
        self.assertIs(client1, client2)


if __name__ == "__main__":
    unittest.main()
