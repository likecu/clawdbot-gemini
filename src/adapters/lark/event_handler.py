"""
事件处理器模块

处理飞书WebSocket事件，实现消息分发和事件路由
"""

import json
import logging
import re
from typing import Callable, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class EventType(Enum):
    """
    事件类型枚举
    """
    P2P_MESSAGE = "im.message.p2p_msg"  # 私聊消息
    GROUP_MESSAGE = "im.message.group_msg"  # 群聊消息
    MESSAGE_RECEIVE = "im.message.receive_v1"  # 消息接收（通用）
    UNKNOWN = "unknown"


@dataclass
class ParsedMessage:
    """
    解析后的消息结构
    """
    message_id: str
    chat_id: str
    chat_type: str
    sender_id: str
    sender_type: str
    text: str
    message_type: str
    mentions: list
    
    @classmethod
    def from_event_data(cls, data: Dict[str, Any]) -> 'ParsedMessage':
        """
        从事件数据创建ParsedMessage实例
        
        Args:
            data: 飞书事件数据字典
            
        Returns:
            ParsedMessage: 解析后的消息对象
        """
        event = data.get("event", {})
        message = event.get("message", {})
        
        content_str = message.get("content", "{}")
        try:
            content = json.loads(content_str)
            text = content.get("text", "").strip()
        except json.JSONDecodeError:
            text = content_str.strip()
        
        # 群聊消息需要处理@提及
        if message.get("chat_type") == "group":
            text = cls._process_mentions(text, message.get("mentions", []))
        
        return cls(
            message_id=message.get("message_id", ""),
            chat_id=message.get("chat_id", ""),
            chat_type=message.get("chat_type", ""),
            sender_id=message.get("sender_id", {}).get("open_id", ""),
            sender_type=message.get("sender_type", ""),
            text=text,
            message_type=message.get("message_type", ""),
            mentions=message.get("mentions", [])
        )
    
    @staticmethod
    def _process_mentions(text: str, mentions: list) -> str:
        """
        处理群聊中的@提及
        
        Args:
            text: 原始文本
            mentions: 提及列表
            
        Returns:
            str: 处理后的文本
        """
        for mention in mentions:
            key = mention.get("key", "")
            if key:
                text = text.replace(f"@{key}", "").strip()
        
        return text


class EventDispatcher:
    """
    事件分发器类
    
    负责解析飞书事件并分发给对应的处理器
    """
    
    def __init__(self):
        """
        初始化事件分发器
        """
        self.logger = logging.getLogger(__name__)
        self._handlers: Dict[EventType, Callable] = {}
        self._message_handlers: Dict[str, Callable] = {}
        self._processed_messages: set = set()  # 消息去重
        self._filter_self_messages = True  # 是否过滤机器人自己的消息
    
    def register_handler(self, event_type: EventType, handler: Callable) -> None:
        """
        注册事件处理器
        
        Args:
            event_type: 事件类型
            handler: 处理函数
        """
        self._handlers[event_type] = handler
        self.logger.info(f"已注册事件处理器: {event_type.value}")
    
    def register_message_handler(self, handler: Callable) -> None:
        """
        注册消息处理器
        
        Args:
            handler: 消息处理函数，接收ParsedMessage参数
        """
        self._message_handlers["default"] = handler
        self.logger.info("已注册默认消息处理器")
    
    def dispatch(self, event_type: str, data: Dict[str, Any]) -> Any:
        """
        分发事件
        
        Args:
            event_type: 事件类型字符串
            data: 事件数据
            
        Returns:
            Any: 处理器返回的结果
        """
        try:
            # 消息接收事件
            if event_type == "im.message.receive_v1":
                return self._handle_message_receive(data)
            else:
                self.logger.debug(f"收到未处理事件: {event_type}")
                return None
                
        except Exception as e:
            self.logger.error(f"事件分发失败: {str(e)}")
            raise
    
    def _handle_message_receive(self, data: Dict[str, Any]) -> Any:
        """
        处理消息接收事件
        
        Args:
            data: 事件数据
            
        Returns:
            Any: 处理器返回的结果
        """
        try:
            message = ParsedMessage.from_event_data(data)
            
            # 消息去重检查
            if message.message_id in self._processed_messages:
                self.logger.debug(f"消息 {message.message_id} 已处理，跳过")
                return None
            
            self._processed_messages.add(message.message_id)
            
            # 过滤机器人自己的消息
            if self._filter_self_messages and message.sender_type == "user":
                if self._is_bot_message(data):
                    self.logger.debug("跳过机器人自己的消息")
                    return None
            
            # 忽略空消息
            if not message.text:
                self.logger.debug("收到空消息，跳过处理")
                return None
            
            self.logger.info(f"处理消息: message_id={message.message_id}, chat_type={message.chat_type}, text={message.text[:50]}...")
            
            # 调用消息处理器
            handler = self._message_handlers.get("default")
            if handler:
                return handler(message)
            else:
                self.logger.warning("没有注册消息处理器")
                return None
                
        except Exception as e:
            self.logger.error(f"处理消息接收事件失败: {str(e)}")
            raise
    
    def _is_bot_message(self, data: Dict[str, Any]) -> bool:
        """
        判断是否为机器人自己的消息
        
        Args:
            data: 事件数据
            
        Returns:
            bool: 是否为机器人消息
        """
        try:
            sender_id = data.get("event", {}).get("message", {}).get("sender_id", {})
            if isinstance(sender_id, dict):
                return sender_id.get("open_id", "") == os.getenv("FEISHU_APP_ID")
            return False
        except Exception:
            return False
    
    def clear_processed_messages(self) -> None:
        """
        清空已处理消息记录
        """
        self._processed_messages.clear()
        self.logger.info("已清空消息去重记录")


def create_event_handler(event_dispatcher: EventDispatcher) -> Callable:
    """
    创建符合飞书SDK要求的事件处理函数
    
    Args:
        event_dispatcher: 事件分发器实例
        
    Returns:
        Callable: 事件处理函数
    """
    def handler(data: Dict[str, Any]) -> None:
        event_type = data.get("event_type", "unknown")
        event_dispatcher.dispatch(event_type, data)
    
    return handler


def default_message_handler(message: ParsedMessage) -> str:
    """
    默认消息处理函数
    
    Args:
        message: 解析后的消息
        
    Returns:
        str: 响应文本
    """
    logging.getLogger(__name__).info(f"收到消息: {message.text}")
    return "消息已收到"
