"""
飞书WebSocket客户端模块

提供与飞书开放平台建立WebSocket长连接的功能
"""

import os
import json
import logging
from typing import Callable, Optional, Dict, Any
from datetime import datetime

import lark_oapi as lark
from lark_oapi import ws
from lark_oapi.event import EventDispatcherHandler

from .message_converter import MessageConverter


class LarkWSClient:
    """
    飞书WebSocket客户端类
    
    负责管理与飞书开放平台的WebSocket长连接，处理事件接收和消息发送
    """
    
    def __init__(self, app_id: Optional[str] = None, 
                 app_secret: Optional[str] = None,
                 encrypt_key: Optional[str] = None,
                 verification_token: Optional[str] = None,
                 log_level: lark.LogLevel = lark.LogLevel.INFO):
        """
        初始化飞书WebSocket客户端
        
        Args:
            app_id: 飞书应用ID
            app_secret: 飞书应用密钥
            encrypt_key: 飞书加密密钥
            verification_token: 飞书验证令牌
            log_level: 日志级别
        """
        self.app_id = app_id or os.getenv("FEISHU_APP_ID")
        self.app_secret = app_secret or os.getenv("FEISHU_APP_SECRET")
        self.encrypt_key = encrypt_key or os.getenv("FEISHU_ENCRYPT_KEY")
        self.verification_token = verification_token or os.getenv("FEISHU_VERIFICATION_TOKEN")
        self.log_level = log_level
        
        self.logger = logging.getLogger(__name__)
        self._client: Optional[ws.Client] = None
        self._is_connected = False
        self._event_handlers: Dict[str, Callable] = {}
        self._message_converter = MessageConverter()
        
        self._processed_events: set = set()  # 事件去重
        self._event_ttl = 3600  # 事件ID有效期（秒）
    
    def _validate_config(self) -> None:
        """
        验证配置有效性
        
        Raises:
            ValueError: 配置缺失时抛出
        """
        if not self.app_id:
            raise ValueError("飞书App ID未配置，请设置FEISHU_APP_ID环境变量")
        if not self.app_secret:
            raise ValueError("飞书App Secret未配置，请设置FEISHU_APP_SECRET环境变量")
        if not self.encrypt_key:
            raise ValueError("飞书Encrypt Key未配置，请设置FEISHU_ENCRYPT_KEY环境变量")
        if not self.verification_token:
            raise ValueError("飞书Verification Token未配置，请设置FEISHU_VERIFICATION_TOKEN环境变量")
    
    def create_client(self) -> ws.Client:
        """
        创建飞书WebSocket客户端实例
        
        Returns:
            ws.Client: 飞书WebSocket客户端实例
        """
        self._validate_config()
        
        self.logger.info("正在创建飞书WebSocket客户端...")
        
        event_handler = EventDispatcherHandler.builder(
            self.encrypt_key,
            self.verification_token,
            self.log_level
        )
        
        for event_type, handler in self._event_handlers.items():
            event_handler = self._register_event_handler(event_handler, event_type, handler)
        
        event_handler = event_handler.build()
        
        self._client = ws.Client(
            app_id=self.app_id,
            app_secret=self.app_secret,
            event_handler=event_handler,
            log_level=self.log_level
        )
        
        self.logger.info("飞书WebSocket客户端创建成功")
        return self._client
    
    def _register_event_handler(self, handler_builder: EventDispatcherHandler, 
                                 event_type: str, 
                                 callback: Callable) -> EventDispatcherHandler:
        """
        注册事件处理器
        
        Args:
            handler_builder: 事件处理器构建器
            event_type: 事件类型
            callback: 回调函数
            
        Returns:
            EventDispatcherHandler: 更新后的处理器构建器
        """
        if event_type == "im.message.receive_v1":
            return handler_builder.register_p2_im_message_receive_v1(callback)
        else:
            self.logger.warning(f"未支持的事件类型: {event_type}")
            return handler_builder
    
    def register_event_handler(self, event_type: str, callback: Callable) -> None:
        """
        注册事件处理器
        
        Args:
            event_type: 事件类型，如"im.message.receive_v1"
            callback: 事件处理回调函数
        """
        self._event_handlers[event_type] = callback
        self.logger.info(f"已注册事件处理器: {event_type}")
    
    def register_message_handler(self, callback: Callable) -> None:
        """
        注册消息处理器
        
        Args:
            callback: 消息处理回调函数，接收(message_id, chat_id, user_id, text, message_type)
        """
        self.register_event_handler("im.message.receive_v1", callback)
    
    def start(self, blocking: bool = True) -> None:
        """
        启动WebSocket客户端
        
        Args:
            blocking: 是否阻塞模式运行
        """
        if not self._client:
            self.create_client()
        
        self.logger.info("正在启动飞书WebSocket客户端...")
        self._is_connected = True
        
        try:
            self._client.start()
        except KeyboardInterrupt:
            self.logger.info("收到停止信号")
            self.stop()
        except Exception as e:
            self.logger.error(f"WebSocket客户端运行错误: {str(e)}")
            self.stop()
            raise
    
    def stop(self) -> None:
        """
        停止WebSocket客户端
        """
        self._is_connected = False
        self._client = None
        self.logger.info("飞书WebSocket客户端已停止")
    
    def is_connected(self) -> bool:
        """
        检查连接状态
        
        Returns:
            bool: 是否已连接
        """
        return self._is_connected
    
    def send_text_message(self, receive_id: str, text: str, 
                          msg_type: str = "text") -> Dict[str, Any]:
        """
        发送文本消息
        
        Args:
            receive_id: 接收者ID
            text: 消息内容
            msg_type: 消息类型
            
        Returns:
            Dict: API响应结果
        """
        if not self._client:
            raise RuntimeError("客户端未初始化，请先调用create_client()或start()")
        
        try:
            from lark_oapi.api.im.v1 import (
                CreateMessageRequest, CreateMessageRequestBody
            )
            
            import uuid
            
            content = json.dumps({"text": text})
            
            request = (CreateMessageRequest.builder()
                      .receive_id_type("open_id")
                      .request_body(CreateMessageRequestBody.builder()
                          .receive_id(receive_id)
                          .msg_type(msg_type)
                          .content(content)
                          .uuid(str(uuid.uuid4()))
                          .build())
                      .build())
            
            response = self._client.im.v1.message.create(request)
            
            if response.code == 0:
                self.logger.info(f"消息发送成功，消息ID: {response.data.message_id}")
                return {"success": True, "message_id": response.data.message_id}
            else:
                self.logger.error(f"消息发送失败，错误码: {response.code}, 错误信息: {response.msg}")
                return {"success": False, "error": response.msg}
                
        except Exception as e:
            self.logger.error(f"发送消息失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def send_rich_text_message(self, receive_id: str, markdown_text: str) -> Dict[str, Any]:
        """
        发送富文本消息
        
        Args:
            receive_id: 接收者ID
            markdown_text: Markdown格式的消息内容
            
        Returns:
            Dict: API响应结果
        """
        try:
            message_content = self._message_converter.markdown_to_lark_post(markdown_text)
            return self.send_message(receive_id, message_content)
        except Exception as e:
            self.logger.error(f"发送富文本消息失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def send_message(self, receive_id: str, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送消息
        
        Args:
            receive_id: 接收者ID
            content: 消息内容字典
            
        Returns:
            Dict: API响应结果
        """
        if not self._client:
            raise RuntimeError("客户端未初始化")
        
        try:
            from lark_oapi.api.im.v1 import (
                CreateMessageRequest, CreateMessageRequestBody
            )
            import uuid
            
            request = (CreateMessageRequest.builder()
                      .receive_id_type("open_id")
                      .request_body(CreateMessageRequestBody.builder()
                          .receive_id(receive_id)
                          .msg_type(content.get("msg_type", "text"))
                          .content(json.dumps(content.get("content", {})))
                          .uuid(str(uuid.uuid4()))
                          .build())
                      .build())
            
            response = self._client.im.v1.message.create(request)
            
            if response.code == 0:
                return {"success": True, "message_id": response.data.message_id}
            else:
                return {"success": False, "error": response.msg}
                
        except Exception as e:
            self.logger.error(f"发送消息失败: {str(e)}")
            return {"success": False, "error": str(e)}
    
    def reply_message(self, message_id: str, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        回复消息
        
        Args:
            message_id: 原消息ID
            content: 回复内容
            
        Returns:
            Dict: API响应结果
        """
        if not self._client:
            raise RuntimeError("客户端未初始化")
        
        try:
            from lark_oapi.api.im.v1 import (
                ReplyMessageRequest, ReplyMessageRequestBody
            )
            import uuid
            
            request = (ReplyMessageRequest.builder()
                      .message_id(message_id)
                      .request_body(ReplyMessageRequestBody.builder()
                          .msg_type(content.get("msg_type", "text"))
                          .content(json.dumps(content.get("content", {})))
                          .uuid(str(uuid.uuid4()))
                          .build())
                      .build())
            
            response = self._client.im.v1.message.reply(request)
            
            if response.code == 0:
                return {"success": True, "message_id": response.data.message_id}
            else:
                return {"success": False, "error": response.msg}
                
        except Exception as e:
            self.logger.error(f"回复消息失败: {str(e)}")
            return {"success": False, "error": str(e)}


def create_ws_client(app_id: Optional[str] = None,
                     app_secret: Optional[str] = None,
                     encrypt_key: Optional[str] = None,
                     verification_token: Optional[str] = None,
                     log_level: lark.LogLevel = lark.LogLevel.INFO) -> LarkWSClient:
    """
    创建飞书WebSocket客户端的便捷函数
    
    Args:
        app_id: 飞书应用ID
        app_secret: 飞书应用密钥
        encrypt_key: 飞书加密密钥
        verification_token: 飞书验证令牌
        log_level: 日志级别
        
    Returns:
        LarkWSClient: 配置好的客户端实例
    """
    return LarkWSClient(
        app_id=app_id,
        app_secret=app_secret,
        encrypt_key=encrypt_key,
        verification_token=verification_token,
        log_level=log_level
    )
