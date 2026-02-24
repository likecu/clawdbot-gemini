"""
会话管理单元测试
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

from core.session import SessionManager, create_session_manager


class TestSessionManager(unittest.TestCase):
    """
    会话管理器测试类
    """
    
    def setUp(self):
        """
        测试前置条件
        """
        self.manager = SessionManager(
            redis_host="localhost",
            redis_port=6379,
            max_history=5
        )
        # Mock _get_redis_client to always return None (force memory mode)
        self.manager._get_redis_client = Mock(return_value=None)
        self.manager._memory_history = {} # Ensure clean slate

    def test_add_message(self):
        """
        测试添加消息
        """
        session_id = "test_user:test_chat"
        
        self.manager.add_message(session_id, "user", "Hello")
        self.manager.add_message(session_id, "assistant", "Hi there!")
        
        history = self.manager.get_history(session_id)
        
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[0]["content"], "Hello")
        self.assertEqual(history[1]["role"], "assistant")
        self.assertEqual(history[1]["content"], "Hi there!")
    
    def test_get_history_empty(self):
        """
        测试获取空会话历史
        """
        history = self.manager.get_history("nonexistent_session")
        
        self.assertEqual(len(history), 0)
    
    def test_clear_session(self):
        """
        测试清空会话
        """
        session_id = "test_user:clear_chat"
        
        self.manager.add_message(session_id, "user", "test")
        self.assertTrue(self.manager.session_exists(session_id))
        
        self.manager.clear_session(session_id)
        
        self.assertFalse(self.manager.session_exists(session_id))
        self.assertEqual(len(self.manager.get_history(session_id)), 0)
    
    def test_add_user_message(self):
        """
        测试添加用户消息
        """
        session_id = "test_user:add_user"
        
        self.manager.add_user_message(session_id, "User message")
        
        history = self.manager.get_history(session_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["role"], "user")
    
    def test_add_assistant_message(self):
        """
        测试添加助手消息
        """
        session_id = "test_user:add_assistant"
        
        self.manager.add_assistant_message(session_id, "Assistant message")
        
        history = self.manager.get_history(session_id)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["role"], "assistant")
    
    def test_get_last_messages(self):
        """
        测试获取最近N条消息
        """
        session_id = "test_user:last_messages"
        
        for i in range(10):
            self.manager.add_message(session_id, "user", f"Message {i}")
        
        last_5 = self.manager.get_last_messages(session_id, 5)
        
        self.assertEqual(len(last_5), 5)
        # 应该是最后5条消息
        self.assertEqual(last_5[0]["content"], "Message 5")
    
    def test_get_conversation_text(self):
        """
        测试获取对话文本
        """
        session_id = "test_user:text_format"
        
        self.manager.add_message(session_id, "user", "Hello")
        self.manager.add_message(session_id, "assistant", "Hi")
        
        text = self.manager.get_conversation_text(session_id)
        
        self.assertIn("user: Hello", text)
        self.assertIn("assistant: Hi", text)
    
    def test_max_history_limit(self):
        """
        测试历史长度限制
        """
        session_id = "test_user:limit"
        
        # 添加超过限制的消息
        for i in range(20):
            self.manager.add_message(session_id, "user", f"Message {i}")
        
        history = self.manager.get_history(session_id)
        
        # 应该保留最近的消息. Implementation uses max_history * 2 for buffer
        self.assertLessEqual(len(history), self.manager.max_history * 2)
    
    def test_session_exists(self):
        """
        测试会话存在性检查
        """
        session_id = "test_user:exists"
        
        self.assertFalse(self.manager.session_exists(session_id))
        
        self.manager.add_message(session_id, "user", "test")
        
        self.assertTrue(self.manager.session_exists(session_id))


class TestSessionManagerWithRedis(unittest.TestCase):
    """
    带Redis的会话管理器测试类
    """
    
    def setUp(self):
        """
        测试前置条件
        """
        self.manager = SessionManager(
            redis_host="localhost",
            redis_port=6379,
            max_history=5
        )
    
    @patch('redis.Redis')
    def test_redis_connection(self, mock_redis_class):
        """
        测试Redis连接
        """
        # Ensure redis is imported/available for patching
        import redis
        
        mock_redis = Mock()
        mock_redis.ping.return_value = True
        mock_redis_class.return_value = mock_redis
        
        # Reset _redis_client to trigger connection
        self.manager.redis_enabled = True
        self.manager._redis_client = None
        
        client = self.manager._get_redis_client()
        
        # Check against the patched class
        self.assertEqual(client, mock_redis)
    
    @patch('redis.Redis')
    def test_redis_failure_fallback(self, mock_redis_class):
        """
        测试Redis连接失败时的降级处理
        """
        import redis
        
        # Simulate ping failure
        mock_redis = Mock()
        mock_redis.ping.side_effect = Exception("Connection refused")
        mock_redis_class.return_value = mock_redis
        
        self.manager.redis_enabled = True
        self.manager._redis_client = None
        
        # 应该降级到内存存储
        client = self.manager._get_redis_client()
        self.assertIsNone(client)
        
        # 添加消息应该使用内存存储
        self.manager.add_message("test_session", "user", "test")
        history = self.manager.get_history("test_session")
        self.assertEqual(len(history), 1)


class TestSessionManagerSingleton(unittest.TestCase):
    """
    会话管理器单例测试类
    """
    
    def tearDown(self):
        """
        测试后清理
        """
        # 重置单例
        import core.session
        core.session._session_manager = None
    
    def test_create_session_manager(self):
        """
        测试创建会话管理器单例
        """
        manager1 = create_session_manager()
        manager2 = create_session_manager()
        
        self.assertIs(manager1, manager2)


if __name__ == "__main__":
    unittest.main()
