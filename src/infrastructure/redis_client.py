"""
Redis客户端模块

提供Redis连接池管理和基础操作
"""

import os
import logging
from typing import Optional, Any, Dict, List
from datetime import timedelta


class RedisClient:
    """
    Redis客户端包装类
    
    提供连接管理、连接池和基础操作功能
    """
    
    _instance: Optional['RedisClient'] = None
    
    def __init__(self, host: str = "localhost",
                 port: int = 6379,
                 db: int = 0,
                 password: Optional[str] = None,
                 max_connections: int = 10):
        """
        初始化Redis客户端
        
        Args:
            host: Redis服务器地址
            port: Redis服务器端口
            db: 数据库编号
            password: 密码
            max_connections: 最大连接数
        """
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = int(port or os.getenv("REDIS_PORT", 6379))
        self.db = int(db or os.getenv("REDIS_DB", 0))
        self.password = password or os.getenv("REDIS_PASSWORD")
        self.max_connections = max_connections
        
        self.logger = logging.getLogger(__name__)
        self._pool = None
        self._client = None
    
    def _get_connection_params(self) -> Dict[str, Any]:
        """
        获取连接参数
        
        Returns:
            Dict: 连接参数字典
        """
        params = {
            "host": self.host,
            "port": self.port,
            "db": self.db,
            "decode_responses": True,
            "socket_connect_timeout": 5,
            "socket_timeout": 5
        }
        if self.password:
            params["password"] = self.password
        return params
    
    def get_client(self):
        """
        获取Redis客户端实例
        
        Returns:
            Redis客户端实例
        """
        if self._client is None:
            try:
                import redis
                self._client = redis.Redis(**self._get_connection_params())
                # 测试连接
                self._client.ping()
                self.logger.info(f"Redis连接成功: {self.host}:{self.port}")
            except Exception as e:
                self.logger.warning(f"Redis连接失败: {str(e)}，将使用降级方案")
                self._client = None
        return self._client
    
    def is_available(self) -> bool:
        """
        检查Redis是否可用
        
        Returns:
            bool: Redis是否可用
        """
        try:
            client = self.get_client()
            if client:
                client.ping()
                return True
            return False
        except Exception:
            return False
    
    def get(self, key: str) -> Optional[str]:
        """
        获取键对应的值
        
        Args:
            key: 键名
            
        Returns:
            Optional[str]: 值，不存在返回None
        """
        client = self.get_client()
        if client:
            return client.get(key)
        return None
    
    def set(self, key: str, value: str,
            ex: Optional[int] = None) -> bool:
        """
        设置键值对
        
        Args:
            key: 键名
            value: 值
            ex: 过期时间（秒）
            
        Returns:
            bool: 是否成功
        """
        client = self.get_client()
        if client:
            return client.set(key, value, ex=ex)
        return False
    
    def delete(self, *keys: str) -> int:
        """
        删除键
        
        Args:
            *keys: 键名列表
            
        Returns:
            int: 删除的键数量
        """
        client = self.get_client()
        if client:
            return client.delete(*keys)
        return 0
    
    def exists(self, *keys: str) -> int:
        """
        检查键是否存在
        
        Args:
            *keys: 键名列表
            
        Returns:
            int: 存在的键数量
        """
        client = self.get_client()
        if client:
            return client.exists(*keys)
        return 0
    
    def expire(self, key: str, seconds: int) -> bool:
        """
        设置键的过期时间
        
        Args:
            key: 键名
            seconds: 过期秒数
            
        Returns:
            bool: 是否成功
        """
        client = self.get_client()
        if client:
            return client.expire(key, seconds)
        return False
    
    def lpush(self, key: str, *values: str) -> int:
        """
        从列表左侧插入值
        
        Args:
            key: 列表键名
            *values: 要插入的值
            
        Returns:
            int: 列表长度
        """
        client = self.get_client()
        if client:
            return client.lpush(key, *values)
        return 0
    
    def rpush(self, key: str, *values: str) -> int:
        """
        从列表右侧插入值
        
        Args:
            key: 列表键名
            *values: 要插入的值
            
        Returns:
            int: 列表长度
        """
        client = self.get_client()
        if client:
            return client.rpush(key, *values)
        return 0
    
    def lrange(self, key: str, start: int, end: int) -> List[str]:
        """
        获取列表范围内的元素
        
        Args:
            key: 列表键名
            start: 起始索引
            end: 结束索引
            
        Returns:
            List[str]: 元素列表
        """
        client = self.get_client()
        if client:
            return client.lrange(key, start, end)
        return []
    
    def llen(self, key: str) -> int:
        """
        获取列表长度
        
        Args:
            key: 列表键名
            
        Returns:
            int: 列表长度
        """
        client = self.get_client()
        if client:
            return client.llen(key)
        return 0
    
    def ltrim(self, key: str, start: int, end: int) -> bool:
        """
        修剪列表
        
        Args:
            key: 列表键名
            start: 起始索引
            end: 结束索引
            
        Returns:
            bool: 是否成功
        """
        client = self.get_client()
        if client:
            return client.ltrim(key, start, end)
        return False
    
    def hset(self, name: str, key: str, value: str) -> int:
        """
        设置哈希表字段值
        
        Args:
            name: 哈希表名
            key: 字段名
            value: 字段值
            
        Returns:
            int: 新增字段返回1，更新返回0
        """
        client = self.get_client()
        if client:
            return client.hset(name, key, value)
        return 0
    
    def hget(self, name: str, key: str) -> Optional[str]:
        """
        获取哈希表字段值
        
        Args:
            name: 哈希表名
            key: 字段名
            
        Returns:
            Optional[str]: 字段值，不存在返回None
        """
        client = self.get_client()
        if client:
            return client.hget(name, key)
        return None
    
    def hgetall(self, name: str) -> Dict[str, str]:
        """
        获取哈希表所有字段和值
        
        Args:
            name: 哈希表名
            
        Returns:
            Dict[str, str]: 字段值字典
        """
        client = self.get_client()
        if client:
            return client.hgetall(name)
        return {}
    
    def close(self) -> None:
        """
        关闭连接
        """
        if self._client:
            self._client.close()
            self._client = None
            self.logger.info("Redis连接已关闭")


def create_redis_client(host: Optional[str] = None,
                        port: Optional[int] = None,
                        db: Optional[int] = None,
                        password: Optional[str] = None) -> RedisClient:
    """
    创建Redis客户端实例（单例）
    
    Args:
        host: Redis主机地址
        port: Redis端口
        db: 数据库编号
        password: 密码
        
    Returns:
        RedisClient: 客户端实例
    """
    if RedisClient._instance is None:
        RedisClient._instance = RedisClient(host, port, db, password)
    return RedisClient._instance


def get_redis_client() -> RedisClient:
    """
    获取Redis客户端单例
    
    Returns:
        RedisClient: 客户端实例
    """
    return create_redis_client()
