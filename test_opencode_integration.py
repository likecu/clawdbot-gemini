"""
OpenCode集成测试模块

测试OpenCode服务与飞书机器人的集成功能
"""

import sys
import os
import unittest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import requests


sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from opencode import OpenCodeClient, init_opencode, get_response, reset_opencode_client


class TestOpenCodeClient(unittest.TestCase):
    """
    OpenCodeClient测试类
    
    测试客户端的初始化、消息发送和响应处理功能
    """
    
    def setUp(self):
        """
        测试初始化
        """
        reset_opencode_client()
        self.mock_api_base_url = "http://opencode_service:8080/v1"
        self.mock_api_key = "test_api_key"
    
    def tearDown(self):
        """
        测试清理
        """
        reset_opencode_client()
    
    def test_init_with_parameters(self):
        """
        测试使用参数初始化客户端
        """
        client = OpenCodeClient(
            api_base_url=self.mock_api_base_url,
            api_key=self.mock_api_key
        )
        
        self.assertEqual(client.api_base_url, self.mock_api_base_url)
        self.assertEqual(client.api_key, self.mock_api_key)
        self.assertIsInstance(client.session, requests.Session)
        self.assertEqual(
            client.session.headers["Authorization"],
            f"Bearer {self.mock_api_key}"
        )
    
    @patch.dict(os.environ, {"OPENCODE_API_BASE_URL": "http://test:8080/v1", "OPENCODE_API_KEY": "env_key"})
    def test_init_from_environment(self):
        """
        测试从环境变量初始化客户端
        """
        reset_opencode_client()
        client = OpenCodeClient()
        
        self.assertEqual(client.api_base_url, "http://test:8080/v1")
        self.assertEqual(client.api_key, "env_key")
    
    def test_chat_adds_to_history(self):
        """
        测试聊天功能会添加对话历史
        """
        client = OpenCodeClient(
            api_base_url=self.mock_api_base_url,
            api_key=self.mock_api_key
        )
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "你好！我是OpenCode助手"
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        
        with patch('requests.Session.post', return_value=mock_response):
            response = client.chat("你好")
            
            self.assertEqual(response, "你好！我是OpenCode助手")
            self.assertEqual(len(client.conversation_history), 2)
            self.assertEqual(client.conversation_history[0]["role"], "user")
            self.assertEqual(client.conversation_history[1]["role"], "assistant")
    
    def test_chat_maintains_conversation_history(self):
        """
        测试聊天功能维护对话历史
        """
        client = OpenCodeClient(
            api_base_url=self.mock_api_base_url,
            api_key=self.mock_api_key
        )
        client.request_interval = 0  # 禁用速率限制用于测试
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "回复2"
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        
        with patch('requests.Session.post', return_value=mock_response):
            client.chat("消息1")
            client.chat("消息2")
            
            self.assertEqual(len(client.conversation_history), 4)
            self.assertEqual(client.conversation_history[0]["content"], "消息1")
            self.assertEqual(client.conversation_history[2]["content"], "消息2")
    
    def test_clear_history(self):
        """
        测试清空对话历史
        """
        client = OpenCodeClient(
            api_base_url=self.mock_api_base_url,
            api_key=self.mock_api_key
        )
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "回复"
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        
        with patch('requests.Session.post', return_value=mock_response):
            client.chat("测试消息")
            self.assertEqual(len(client.conversation_history), 2)
            
            client.clear_history()
            self.assertEqual(len(client.conversation_history), 0)
    
    def test_get_history(self):
        """
        测试获取对话历史
        """
        client = OpenCodeClient(
            api_base_url=self.mock_api_base_url,
            api_key=self.mock_api_key
        )
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "回复"
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        
        with patch('requests.Session.post', return_value=mock_response):
            client.chat("测试消息")
            history = client.get_history()
            
            self.assertEqual(len(history), 2)
            self.assertEqual(history[0]["content"], "测试消息")
    
    def test_health_check_success(self):
        """
        测试健康检查成功
        """
        client = OpenCodeClient(
            api_base_url=self.mock_api_base_url,
            api_key=self.mock_api_key
        )
        
        mock_response = Mock()
        mock_response.status_code = 200
        
        with patch('requests.Session.get', return_value=mock_response):
            self.assertTrue(client.health_check())
    
    def test_health_check_failure(self):
        """
        测试健康检查失败
        """
        client = OpenCodeClient(
            api_base_url=self.mock_api_base_url,
            api_key=self.mock_api_key
        )
        
        with patch('requests.Session.get', side_effect=Exception("连接失败")):
            self.assertFalse(client.health_check())
    
    def test_chat_with_custom_model(self):
        """
        测试使用自定义模型
        """
        client = OpenCodeClient(
            api_base_url=self.mock_api_base_url,
            api_key=self.mock_api_key
        )
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "回复"
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        
        with patch('requests.Session.post') as mock_post:
            mock_post.return_value = mock_response
            client.chat("测试消息", model="gemma-3-27b-it")
            
            call_args = mock_post.call_args
            self.assertEqual(call_args[1]["json"]["model"], "gemma-3-27b-it")


class TestInitOpencode(unittest.TestCase):
    """
    init_opencode函数测试类
    """
    
    def setUp(self):
        """
        测试初始化
        """
        reset_opencode_client()
    
    def tearDown(self):
        """
        测试清理
        """
        reset_opencode_client()
    
    def test_init_creates_client(self):
        """
        测试初始化创建客户端
        """
        client = init_opencode(
            api_base_url="http://test:8080/v1",
            api_key="test_key"
        )
        
        self.assertIsInstance(client, OpenCodeClient)
        self.assertEqual(client.api_base_url, "http://test:8080/v1")
    
    def test_init_returns_same_instance(self):
        """
        测试多次初始化返回相同实例
        """
        client1 = init_opencode(
            api_base_url="http://test1:8080/v1",
            api_key="test_key1"
        )
        client2 = init_opencode(
            api_base_url="http://test2:8080/v1",
            api_key="test_key2"
        )
        
        self.assertIs(client1, client2)
    
    def test_reset_client(self):
        """
        测试重置客户端
        """
        client1 = init_opencode(
            api_base_url="http://test1:8080/v1",
            api_key="test_key1"
        )
        
        reset_opencode_client()
        
        client2 = init_opencode(
            api_base_url="http://test2:8080/v1",
            api_key="test_key2"
        )
        
        self.assertIsNot(client1, client2)


class TestGetResponse(unittest.TestCase):
    """
    get_response函数测试类
    """
    
    def setUp(self):
        """
        测试初始化
        """
        reset_opencode_client()
    
    def tearDown(self):
        """
        测试清理
        """
        reset_opencode_client()
    
    def test_get_response_calls_chat(self):
        """
        测试get_response调用chat方法
        """
        client = init_opencode(
            api_base_url="http://test:8080/v1",
            api_key="test_key"
        )
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "测试回复"
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        
        with patch('requests.Session.post', return_value=mock_response):
            response = get_response(client, "测试消息")
            
            self.assertEqual(response, "测试回复")


class TestCalculatorIntegration(unittest.TestCase):
    """
    计算器集成测试类
    
    测试OpenCode服务生成和执行计算器代码的能力
    """
    
    def setUp(self):
        """
        测试初始化
        """
        reset_opencode_client()
    
    def tearDown(self):
        """
        测试清理
        """
        reset_opencode_client()
    
    def test_calculator_code_generation(self):
        """
        测试计算器代码生成
        """
        client = init_opencode(
            api_base_url="http://opencode_service:8080/v1",
            api_key="my_internal_secret_2024"
        )
        
        mock_response = Mock()
        mock_response.json.return_value = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": """```python
def calculator(a, b, operator):
    '''
    简单计算器函数
    
    Args:
        a: 第一个操作数
        b: 第二个操作数  
        operator: 运算符 (+, -, *, /)
    
    Returns:
        计算结果
    '''
    if operator == '+':
        return a + b
    elif operator == '-':
        return a - b
    elif operator == '*':
        return a * b
    elif operator == '/':
        if b == 0:
            raise ValueError("除数不能为零")
        return a / b
    else:
        raise ValueError(f"不支持的运算符: {operator}")

# 测试计算器
if __name__ == "__main__":
    print(calculator(10, 5, '+'))  # 输出: 15
    print(calculator(10, 5, '-'))  # 输出: 5
    print(calculator(10, 5, '*'))  # 输出: 50
    print(calculator(10, 5, '/'))  # 输出: 2.0
```"""
                }
            }]
        }
        mock_response.raise_for_status = Mock()
        
        with patch('requests.Session.post', return_value=mock_response):
            response = get_response(
                client, 
                "请开发一个Python计算器代码，支持加减乘除运算"
            )
            
            self.assertIn("def calculator", response)
            self.assertIn("+", response)
            self.assertIn("-", response)
            self.assertIn("*", response)
            self.assertIn("/", response)


if __name__ == "__main__":
    import requests
    unittest.main(verbosity=2)
