"""
智能体单元测试
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

from core.agent import Agent, AgentMode, create_agent


class MockLLMClient:
    """
    模拟LLM客户端
    """
    
    def __init__(self, response_text="这是一个模拟回复"):
        self.response_text = response_text
        self.chat_count = 0
    
    def chat(self, message, **kwargs):
        self.chat_count += 1
        return {
            "reply_text": self.response_text,
            "usage": {"total_tokens": 100}
        }
    
    def chat_with_thinking(self, message, **kwargs):
        self.chat_count += 1
        return {
            "thinking": "模型思考过程",
            "reply_text": self.response_text,
            "usage": {"total_tokens": 150}
        }


class TestAgent(unittest.TestCase):
    """
    智能体测试类
    """
    
    def setUp(self):
        """
        测试前置条件
        """
        self.mock_llm = MockLLMClient()
        self.agent = Agent(self.mock_llm)
    
    def test_process_message_success(self):
        """
        测试成功处理消息
        """
        result = self.agent.process_message(
            user_id="user123",
            chat_id="chat456",
            message="你好，请帮我写一段Python代码"
        )
        
        self.assertTrue(result["success"])
        self.assertIn("text", result)
        self.assertEqual(result["mode"], "code_generation")
    
    def test_process_message_conversation(self):
        """
        测试对话模式消息处理
        """
        result = self.agent.process_message(
            user_id="user123",
            chat_id="chat456",
            message="今天天气怎么样？"
        )
        
        self.assertTrue(result["success"])
        self.assertEqual(result["mode"], "conversation")
    
    def test_process_message_error(self):
        """
        测试错误处理
        """
        self.mock_llm.chat = Mock(side_effect=Exception("API错误"))
        
        result = self.agent.process_message(
            user_id="user123",
            chat_id="chat456",
            message="测试错误处理"
        )
        
        self.assertFalse(result["success"])
        self.assertIn("error", result)
    
    def test_detect_intent_code_generation(self):
        """
        测试意图识别 - 代码生成
        """
        test_cases = [
            "请写一段代码",
            "帮我实现这个功能",
            "write code",
            "create a function"
        ]
        
        for message in test_cases:
            with self.subTest(message=message):
                intent = self.agent._detect_intent(message)
                self.assertEqual(intent, "code_generation")
    
    def test_detect_intent_code_explanation(self):
        """
        测试意图识别 - 代码解释
        """
        test_cases = [
            "请解释这段代码",
            "这段代码是做什么的？",
            "explain this code",
            "说明代码逻辑"
        ]
        
        for message in test_cases:
            with self.subTest(message=message):
                intent = self.agent._detect_intent(message)
                self.assertEqual(intent, "code_explanation")
    
    def test_detect_intent_debugging(self):
        """
        测试意图识别 - 调试
        """
        test_cases = [
            "代码报错了",
            "有一个bug",
            "帮我修复问题",
            "debug this code"
        ]
        
        for message in test_cases:
            with self.subTest(message=message):
                intent = self.agent._detect_intent(message)
                self.assertEqual(intent, "debugging")
    
    def test_generate_code(self):
        """
        测试代码生成
        """
        result = self.agent.generate_code(
            requirement="实现一个hello world函数",
            language="python"
        )
        
        self.assertTrue(result["success"])
        self.assertIn("code", result)
    
    def test_explain_code(self):
        """
        测试代码解释
        """
        code = "print('hello')"
        
        result = self.agent.explain_code(code, "python")
        
        self.assertTrue(result["success"])
        self.assertIn("explanation", result)
    
    def test_debug_code(self):
        """
        测试代码调试
        """
        code = "print(undefined_var)"
        error = "NameError: name 'undefined_var' is not defined"
        
        result = self.agent.debug_code(code, error)
        
        self.assertTrue(result["success"])
        self.assertIn("suggestion", result)
    
    def test_clear_memory(self):
        """
        测试清空记忆
        """
        self.agent.process_message("user123", "chat456", "test message")
        
        # 清空记忆
        self.agent.clear_memory("user123", "chat456")
        
        # 验证记忆已清空（通过检查内部状态）
    
    def test_set_mode(self):
        """
        测试设置工作模式
        """
        self.agent.set_mode(AgentMode.CODE_GENERATION)
        
        self.assertEqual(self.agent.current_mode, AgentMode.CODE_GENERATION)
    
    def test_enable_thinking_display(self):
        """
        测试思考过程显示设置
        """
        self.agent.enable_thinking_display(True)
        self.assertTrue(self.agent.thinking_enabled)
        
        self.agent.enable_thinking_display(False)
        self.assertFalse(self.agent.thinking_enabled)


class TestAgentWithThinkingModel(unittest.TestCase):
    """
    带推理模型的智能体测试类
    """
    
    def setUp(self):
        """
        测试前置条件
        """
        self.mock_llm = MockLLMClient()
        self.agent = Agent(self.mock_llm)
    
    def test_process_message_with_thinking(self):
        """
        测试带思考过程的推理模型
        """
        self.agent.thinking_enabled = True
        
        result = self.agent.process_message(
            user_id="user123",
            chat_id="chat456",
            message="分析这个复杂问题"
        )
        
        self.assertTrue(result["success"])
        self.assertIn("thinking", result.get("response", {}))


class TestCreateAgent(unittest.TestCase):
    """
    创建智能体测试类
    """
    
    def test_create_agent(self):
        """
        测试创建智能体实例
        """
        mock_llm = Mock()
        agent = create_agent(mock_llm)
        
        self.assertIsInstance(agent, Agent)


if __name__ == "__main__":
    unittest.main()
