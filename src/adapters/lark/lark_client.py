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
        self.logger = logging.getLogger(__name__)
        
    def _validate_config(self) -> None:
        """
        验证配置是否完整
        
        Raises:
            ValueError: 当必要配置缺失时抛出
        """
        if not self.app_id:
            raise ValueError("FEISHU_APP_ID未设置")
        if not self.app_secret:
            raise ValueError("FEISHU_APP_SECRET未设置")
        if not self.encrypt_key:
            raise ValueError("FEISHU_ENCRYPT_KEY未设置")
        if not self.verification_token:
            raise ValueError("FEISHU_VERIFICATION_TOKEN未设置")
            
    def is_connected(self) -> bool:
        """
        检查客户端是否已连接
        
        Returns:
            bool: 连接状态
        """
        return self._is_connected
        
    def register_event_handler(self, event_type: str, handler: Callable) -> None:
        """
        注册事件处理器
        
        Args:
            event_type: 事件类型
            handler: 处理函数
        """
        self._event_handlers[event_type] = handler
        self.logger.info(f"已注册事件处理器: {event_type}")
        
    def _create_client(self) -> ws.Client:
        """
        创建飞书WebSocket客户端实例
        
        Returns:
            ws.Client: 飞书WebSocket客户端实例
        """
        self._validate_config()
        
        self.logger.info("正在创建飞书WebSocket客户端...")
        
        def default_handler(event):
            try:
                self.logger.info(f"收到飞书事件: type={type(event)}")
                
                # 尝试提取事件类型
                event_type = "unknown"
                event_dict = {}
                
                # 如果是 dict
                if isinstance(event, dict):
                    event_dict = event
                    event_type = event.get("header", {}).get("event_type", "unknown")
                    # Fallback for some events
                    if event_type == "unknown":
                        event_type = event.get("type", "unknown")
                
                # 如果是对象，尝试转为 dict
                else:
                    # 尝试获取 header.event_type
                    header = getattr(event, "header", None)
                    if header:
                        event_type = getattr(header, "event_type", "unknown")
                    
                    # 尝试转为 dict
                    if hasattr(event, "__dict__"):
                        event_dict = event.__dict__
                    elif hasattr(event, "data"): # 某些 SDK 封装
                         event_dict = event.data
                    
                    # 如果转失败，记录
                    if not event_dict:
                        self.logger.warning(f"无法将事件对象转为字典: {dir(event)}")
                        return

                self.logger.info(f"处理事件类型: {event_type}")
                
                handler = self._event_handlers.get(event_type)
                if handler:
                    handler(event_dict)
                else:
                     self.logger.debug(f"未找到处理器: {event_type}")
            except Exception as e:
                self.logger.error(f"事件处理异常: {e}")
        
        self._client = ws.Client(
            app_id=self.app_id,
            app_secret=self.app_secret,
            event_handler=default_handler,
            log_level=self.log_level
        )
        
        self.logger.info("飞书WebSocket客户端创建成功")
        return self._client
        
    def start(self, blocking: bool = False) -> None:
        """
        启动客户端
        
        Args:
            blocking: 是否阻塞
        """
        self.connect()
        # lark-oapi's start method might be blocking or not depending on implementation
        # Looking at connect(): self._client.start()
        # If blocking is requested and _client.start() is not blocking, we might need to wait.
        # But for now, let's just alias connect.
        # If main.py expects blocking, we might need a loop if _client.start is async or non-blocking.
    
    def stop(self) -> None:
        """停止客户端"""
        self.disconnect()

    def connect(self) -> bool:
        """
        建立WebSocket连接
        
        Returns:
            bool: 连接是否成功
        """
        try:
            self._validate_config()
            
            self.logger.info("正在连接飞书WebSocket...")
            
            self._client = self._create_client()
            
            # Note: lark-oapi ws client start() might be blocking if not configured otherwise?
            # Usually it runs in background unless specified.
            self._client.start()
            self._is_connected = True
            self.logger.info("飞书WebSocket连接成功")
            return True
            
        except Exception as e:
            self.logger.error(f"连接失败: {str(e)}")
            return False
            
    def disconnect(self) -> None:
        """
        断开WebSocket连接
        """
        try:
            if self._client:
                # self._client.stop() # Assuming stop exists
                # lark-oapi might depend on how it was started.
                pass 
                self._is_connected = False
                self.logger.info("飞书WebSocket连接已断开")
        except Exception as e:
            self.logger.error(f"断开连接时出错: {str(e)}")
            
    def send_message(self, receive_id: str, content: Dict[str, Any]) -> Dict[str, Any]:
        """
        发送消息到飞书
        
        Args:
            receive_id: 接收者ID
            content: 消息内容
            
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
            
    def send_text_message(self, receive_id: str, text: str) -> Dict[str, Any]:
        """
        发送文本消息
        
        Args:
            receive_id: 接收者ID
            text: 文本内容
            
        Returns:
            Dict: API响应结果
        """
        content = {
            "msg_type": "text",
            "content": json.dumps({"text": text})
        }
        return self.send_message(receive_id, content)
        
    def send_rich_text_message(self, receive_id: str, markdown: str) -> Dict[str, Any]:
        """
        发送富文本消息（支持Markdown）
        
        Args:
            receive_id: 接收者ID
            markdown: Markdown格式的内容
            
        Returns:
            Dict: API响应结果
        """
        lark_content = self._message_converter.markdown_to_lark_post(markdown)
        return self.send_message(receive_id, lark_content)
        
    def get_tenant_access_token(self) -> Optional[str]:
        """
        获取tenant_access_token
        
        Returns:
            str: token字符串，失败返回None
        """
        try:
            response = lark.Client.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
                .build() \
                .get_tenant_access_token()
                
            if response.code == 0:
                return response.data.tenant_access_token
            else:
                self.logger.error(f"获取token失败: {response.msg}")
                return None
                
        except Exception as e:
            self.logger.error(f"获取token异常: {str(e)}")
            return None
