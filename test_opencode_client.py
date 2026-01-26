"""
OpenCode 客户端单元测试

测试 OpenCode 客户端的各种功能
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch

# 添加 src 目录到路径
_src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

from opencode import OpenCodeClient, init_opencode


class TestOpenCodeClientInit(unittest.TestCase):
    """
    测试 OpenCodeClient 初始化功能
    """

    def test_init_with_parameters(self):
        """
        测试使用参数初始化
        """
        client = OpenCodeClient(
            api_key='custom_key',
            base_url='http://custom.url/v1'
        )
        self.assertEqual(client.api_key, 'custom_key')
        self.assertEqual(client.base_url, 'http://custom.url/v1')
        self.assertEqual(client.max_retries, 3)

    def test_init_with_custom_retries(self):
        """
        测试自定义重试次数
        """
        client = OpenCodeClient(
            api_key='test_key',
            base_url='http://test.com/v1',
            max_retries=5
        )
        self.assertEqual(client.max_retries, 5)


class TestOpenCodeClientChat(unittest.TestCase):
    """
    测试 OpenCodeClient 聊天功能
    """

    def setUp(self):
        """
        设置测试环境
        """
        self.client = OpenCodeClient(
            api_key='test_key',
            base_url='http://test.example.com/v1'
        )

    @patch('opencode.requests.post')
    def test_chat_simple_message(self, mock_post):
        """
        测试发送简单消息
        """
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': 'Hello, World!'}}]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        result = self.client.chat("Hello")

        self.assertEqual(result, 'Hello, World!')
        mock_post.assert_called_once()

    @patch('opencode.requests.post')
    def test_chat_with_history(self, mock_post):
        """
        测试发送带历史记录的消息
        """
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': '继续对话'}}]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        history = [
            {'role': 'user', 'content': '第一句话'},
            {'role': 'assistant', 'content': '第一句回复'}
        ]

        result = self.client.chat("第二句话", history=history)

        self.assertEqual(result, '继续对话')

        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertEqual(len(payload['messages']), 3)

    @patch('opencode.requests.post')
    def test_chat_custom_parameters(self, mock_post):
        """
        测试自定义参数
        """
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': '测试结果'}}]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        result = self.client.chat(
            message="测试",
            model="gemma-3-27b-it",
            temperature=0.5,
            max_tokens=500
        )

        self.assertEqual(result, '测试结果')

        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertEqual(payload['model'], 'gemma-3-27b-it')
        self.assertEqual(payload['temperature'], 0.5)
        self.assertEqual(payload['max_tokens'], 500)


class TestOpenCodeClientRetry(unittest.TestCase):
    """
    测试 OpenCodeClient 重试机制
    """

    def setUp(self):
        """
        设置测试环境
        """
        self.client = OpenCodeClient(
            api_key='test_key',
            base_url='http://test.example.com/v1',
            max_retries=2
        )

    @patch('opencode.requests.post')
    def test_max_retries_exceeded(self, mock_post):
        """
        测试超过最大重试次数时抛出异常
        """
        import requests
        mock_post.side_effect = requests.exceptions.ConnectionError("Connection failed")

        with self.assertRaises(Exception) as context:
            self.client.chat("Test message")

        self.assertIn('无法连接到 OpenCode 服务', str(context.exception))
        self.assertEqual(mock_post.call_count, 2)  # max_retries=2 means 2 total attempts


class TestOpenCodeClientHealthCheck(unittest.TestCase):
    """
    测试 OpenCodeClient 健康检查
    """

    def setUp(self):
        """
        设置测试环境
        """
        self.client = OpenCodeClient(
            api_key='test_key',
            base_url='http://test.example.com/v1'
        )

    @patch('opencode.requests.get')
    def test_health_check_success(self, mock_get):
        """
        测试健康检查成功
        """
        mock_response = Mock()
        mock_response.json.return_value = {
            'status': 'healthy',
            'timestamp': '2024-01-01T00:00:00'
        }
        mock_response.raise_for_status = Mock()
        mock_get.return_value = mock_response

        result = self.client.health_check()

        self.assertEqual(result['status'], 'healthy')
        mock_get.assert_called_once()


class TestOpenCodeClientExecuteCode(unittest.TestCase):
    """
    测试 OpenCodeClient 代码执行
    """

    def setUp(self):
        """
        设置测试环境
        """
        self.client = OpenCodeClient(
            api_key='test_key',
            base_url='http://test.example.com/v1'
        )

    @patch('opencode.requests.post')
    def test_execute_python_code(self, mock_post):
        """
        测试执行 Python 代码
        """
        mock_response = Mock()
        mock_response.json.return_value = {
            'choices': [{'message': {'content': '执行结果: Hello'}}]
        }
        mock_response.raise_for_status = Mock()
        mock_post.return_value = mock_response

        code = '''
def greet():
    print("Hello")
    return "Hello"

greet()
'''

        result = self.client.execute_code(code, language='python')

        self.assertEqual(result, '执行结果: Hello')

        call_args = mock_post.call_args
        payload = call_args[1]['json']
        self.assertIn('```python', payload['messages'][0]['content'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
