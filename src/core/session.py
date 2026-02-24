"""
会话管理模块

提供基于Redis的用户会话上下文管理
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta


class SessionManager:
    """
    会话管理器类
    
    负责管理用户会话上下文，提供短期记忆功能
    """
    
    def __init__(self, redis_host: str = "localhost",
                 redis_port: int = 6379,
                 redis_db: int = 0,
                 redis_password: Optional[str] = None,
                 max_history: int = 10):
        """
        初始化会话管理器
        
        Args:
            redis_host: Redis服务器地址
            redis_port: Redis服务器端口
            redis_db: Redis数据库编号
            redis_password: Redis密码
            max_history: 最大历史消息数量
        """
        # 默认禁用 Redis，优先使用内存确性能。如果环境变量显示开启则尝试。
        self.redis_enabled = os.getenv("REDIS_ENABLED", "false").lower() == "true"
        self.redis_host = redis_host or os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(redis_port or os.getenv("REDIS_PORT", 6379))
        self.redis_db = int(redis_db or os.getenv("REDIS_DB", 0))
        self.redis_password = redis_password or os.getenv("REDIS_PASSWORD")
        self.max_history = max_history
        
        self.logger = logging.getLogger(__name__)
        self._redis_client = None
        self._redis_connection_failed = False
    
    def _get_redis_client(self):
        """
        获取Redis客户端实例
        
        Returns:
            Redis客户端实例
        """
        if not self.redis_enabled or self._redis_connection_failed:
            return None

        if self._redis_client is None:
            try:
                import redis
                self._redis_client = redis.Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    db=self.redis_db,
                    password=self.redis_password,
                    decode_responses=True,
                    socket_connect_timeout=2.0, # 缩短连接超时
                    socket_timeout=2.0
                )
                # 测试连接
                self._redis_client.ping()
                self.logger.info(f"Redis连接成功: {self.redis_host}:{self.redis_port}")
            except Exception as e:
                self.logger.warning(f"Redis连接失败且已禁用: {str(e)}")
                self._redis_connection_failed = True
                self._redis_client = None
        
        return self._redis_client
    
    def _get_session_key(self, session_id: str) -> str:
        """
        生成会话存储键
        
        Args:
            session_id: 会话ID
            
        Returns:
            str: Redis键名
        """
        return f"clawdbot:session:{session_id}"
    
    def add_message(self, session_id: str, role: str, content: str) -> None:
        """
        添加消息到会话历史
        
        Args:
            session_id: 会话ID
            role: 消息角色（user/assistant/system）
            content: 消息内容
        """
        redis_client = self._get_redis_client()
        session_key = self._get_session_key(session_id)
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        }
        
        if redis_client:
            try:
                # 使用List结构存储消息
                redis_client.rpush(session_key, json.dumps(message))
                # 设置过期时间（24小时）
                redis_client.expire(session_key, timedelta(hours=24))
                # 限制历史长度
                self._trim_history(redis_client, session_key)
            except Exception as e:
                self.logger.error(f"保存消息到Redis失败: {str(e)}")
        else:
            # 使用内存存储（降级方案）
            self._memory_history = getattr(self, "_memory_history", {})
            if session_id not in self._memory_history:
                self._memory_history[session_id] = []
            self._memory_history[session_id].append(message)
            # 限制历史长度
            if len(self._memory_history[session_id]) > self.max_history * 2:
                self._memory_history[session_id] = self._memory_history[session_id][-self.max_history * 2:]
    
    def _trim_history(self, redis_client, session_key: str) -> None:
        """
        修剪会话历史，保持在最大长度内
        
        Args:
            redis_client: Redis客户端
            session_key: 会话键
        """
        try:
            length = redis_client.llen(session_key)
            if length > self.max_history * 2:
                redis_client.ltrim(session_key, -self.max_history * 2, -1)
        except Exception as e:
            self.logger.error(f"修剪历史失败: {str(e)}")
    
    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """
        获取会话历史
        
        Args:
            session_id: 会话ID
            
        Returns:
            List[Dict]: 消息历史列表
        """
        redis_client = self._get_redis_client()
        session_key = self._get_session_key(session_id)
        
        if redis_client:
            try:
                raw_messages = redis_client.lrange(session_key, 0, -1)
                return [json.loads(msg) for msg in raw_messages]
            except Exception as e:
                self.logger.error(f"从Redis获取历史失败: {str(e)}")
                return []
        else:
            # 内存存储
            memory_history = getattr(self, "_memory_history", {})
            return memory_history.get(session_id, [])
    
    def get_conversation_text(self, session_id: str, 
                               include_system: bool = False) -> str:
        """
        获取会话的纯文本历史（用于LLM调用）
        
        Args:
            session_id: 会话ID
            include_system: 是否包含系统消息
            
        Returns:
            str: 格式化的对话历史
        """
        history = self.get_history(session_id)
        texts = []
        
        for msg in history:
            if not include_system and msg.get("role") == "system":
                continue
            role = msg.get("role", "user")
            content = msg.get("content", "")
            texts.append(f"{role}: {content}")
        
        return "\n".join(texts)
    
    def clear_session(self, session_id: str) -> None:
        """
        清空会话历史
        
        Args:
            session_id: 会话ID
        """
        redis_client = self._get_redis_client()
        session_key = self._get_session_key(session_id)
        
        if redis_client:
            try:
                redis_client.delete(session_key)
                self.logger.info(f"已清空会话: {session_id}")
            except Exception as e:
                self.logger.error(f"清空会话失败: {str(e)}")
        else:
            # 内存存储
            memory_history = getattr(self, "_memory_history", {})
            if session_id in memory_history:
                del memory_history[session_id]
    
    def add_user_message(self, session_id: str, content: str) -> None:
        """
        添加用户消息
        
        Args:
            session_id: 会话ID
            content: 消息内容
        """
        self.add_message(session_id, "user", content)
    
    def add_assistant_message(self, session_id: str, content: str) -> None:
        """
        添加助手消息
        
        Args:
            session_id: 会话ID
            content: 消息内容
        """
        self.add_message(session_id, "assistant", content)
    
    def get_last_messages(self, session_id: str, count: int = 5) -> List[Dict[str, str]]:
        """
        获取最近N条消息
        
        Args:
            session_id: 会话ID
            count: 消息数量
            
        Returns:
            List[Dict]: 最近的消息列表
        """
        history = self.get_history(session_id)
        return history[-count:] if len(history) > count else history
    
    def session_exists(self, session_id: str) -> bool:
        """
        检查会话是否存在
        
        Args:
            session_id: 会话ID
            
        Returns:
            bool: 会话是否存在
        """
        redis_client = self._get_redis_client()
        if redis_client:
            session_key = self._get_session_key(session_id)
            try:
                return redis_client.exists(session_key) > 0
            except Exception:
                return False
        else:
            memory_history = getattr(self, "_memory_history", {})
            return session_id in memory_history


# 单例实例
_session_manager: Optional[SessionManager] = None


def create_session_manager(redis_host: Optional[str] = None,
                           redis_port: Optional[int] = None,
                           redis_db: Optional[int] = None,
                           redis_password: Optional[str] = None,
                           max_history: int = 10) -> SessionManager:
    """
    创建会话管理器单例
    
    Args:
        redis_host: Redis主机地址
        redis_port: Redis端口
        redis_db: 数据库编号
        redis_password: 密码
        max_history: 最大历史消息数
        
    Returns:
        SessionManager: 会话管理器实例
    """
    global _session_manager
    
    if _session_manager is None:
        _session_manager = SessionManager(
            redis_host=redis_host,
            redis_port=redis_port,
            redis_db=redis_db,
            redis_password=redis_password,
            max_history=max_history
        )
    
    return _session_manager


def get_session_manager() -> SessionManager:
    """
    获取会话管理器单例
    
    Returns:
        SessionManager: 会话管理器实例
    """
    global _session_manager
    
    if _session_manager is None:
        _session_manager = create_session_manager()
    
    return _session_manager
