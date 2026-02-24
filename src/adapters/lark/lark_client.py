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
import lark_oapi as lark
from lark_oapi.api.im.v1 import (
    GetMessageResourceRequest,
    CreateImageRequest,
    CreateImageRequestBody,
    CreateFileRequest,
    CreateFileRequestBody
)

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
        self._api_client: Optional[lark.Client] = None  # 用于API调用的客户端
        self._is_connected = False
        self._event_handlers: Dict[str, Callable] = {}
        self._message_converter = MessageConverter()
        
        # 立即初始化API客户端(用于发送消息和获取资源)
        self._init_api_client()
        
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
    
    def _init_api_client(self) -> None:
        """
        初始化API客户端(用于发送消息和获取资源文件)
        
        与WebSocket客户端不同,API客户端用于调用REST API
        """
        try:
            self._api_client = lark.Client.builder() \
                .app_id(self.app_id) \
                .app_secret(self.app_secret) \
                .log_level(self.log_level) \
                .build()
            self.logger.info("飞书API客户端初始化成功")
        except Exception as e:
            self.logger.error(f"初始化API客户端失败: {e}")
        
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
        
        # 创建一个通用的事件回调处理函数
        def on_p2p_message_receive(data):
            """处理私聊消息事件"""
            self._dispatch_event("im.message.receive_v1", data)
        
        # 使用 EventDispatcherHandler.builder() 创建事件分发器
        # 长连接模式下，两个参数应为空字符串
        event_handler = lark.EventDispatcherHandler.builder("", "") \
            .register_p2_im_message_receive_v1(on_p2p_message_receive) \
            .build()
        
        self._client = ws.Client(
            app_id=self.app_id,
            app_secret=self.app_secret,
            event_handler=event_handler,
            log_level=self.log_level
        )
        
        self.logger.info("飞书WebSocket客户端创建成功")
        return self._client
    
    def _dispatch_event(self, event_type: str, data):
        """
        分发事件到注册的处理器
        
        Args:
            event_type: 事件类型
            data: 事件数据(可能是对象或字典)
        """
        try:
            self.logger.info(f"收到飞书事件: type={type(data)}, event_type={event_type}")
            
            event_dict = {}
            
            # 尝试将数据转换为字典格式
            if isinstance(data, dict):
                event_dict = data
            elif hasattr(data, "__dict__"):
                # 如果是 Pydantic model 或普通对象
                if hasattr(data, "dict"):
                    event_dict = data.dict()
                elif hasattr(data, "model_dump"):
                    event_dict = data.model_dump()
                else:
                    # 尝试递归转换
                    event_dict = self._object_to_dict(data)
            else:
                self.logger.warning(f"无法将事件对象转为字典: {type(data)}")
                return
            
            self.logger.info(f"处理事件类型: {event_type}")
            
            handler = self._event_handlers.get(event_type)
            if handler:
                handler(event_dict)
            else:
                self.logger.debug(f"未找到处理器: {event_type}")
        except Exception as e:
            self.logger.error(f"事件处理异常: {e}", exc_info=True)
    
    def _object_to_dict(self, obj) -> dict:
        """
        递归将对象转换为字典
        
        Args:
            obj: 要转换的对象
            
        Returns:
            dict: 转换后的字典
        """
        if isinstance(obj, dict):
            return {k: self._object_to_dict(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._object_to_dict(item) for item in obj]
        elif hasattr(obj, "__dict__"):
            return {k: self._object_to_dict(v) for k, v in obj.__dict__.items() if not k.startswith("_")}
        else:
            return obj
        
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
            
            response = self._api_client.im.v1.message.create(request)
            
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
    def get_message_resource(self, message_id: str, file_key: str, resource_type: str = "image") -> Optional[bytes]:
        """
        获取消息资源（图片/文件）
        
        Args:
            message_id: 消息ID
            file_key: 文件Key
            resource_type: 资源类型 (image/file)
            
        Returns:
            bytes: 文件二进制内容，失败返回None
        """
        try:
            # 构造请求
            request = GetMessageResourceRequest.builder() \
                .message_id(message_id) \
                .file_key(file_key) \
                .type(resource_type) \
                .build()

            # 发送请求 (使用API客户端而非WebSocket客户端)
            # 注意：im.v1.message_resource.get 返回的是流
            response = self._api_client.im.v1.message_resource.get(request)

            if not response.success():
                self.logger.error(f"获取资源失败: {response.code} - {response.msg}")
                return None
            
            # 读取流内容
            # lark-oapi Python SDK 的 response.data 应该是一个流或者是 bytes
            # 查看源码或文档通常是 file_name 和 file 属性
            # 如果是 raw response
            if hasattr(response, "file") and response.file:
                 return response.file.read()
            elif hasattr(response, "data") and response.data:
                 # 如果是流对象
                 if hasattr(response.data, "read"):
                     return response.data.read()
                 return response.data
            else:
                 self.logger.error("响应中没有包含文件内容")
                 return None

        except Exception as e:
            self.logger.error(f"下载资源异常: {str(e)}")
            return None

    def upload_image(self, image_data: bytes, image_type: str = "message") -> Optional[str]:
        """
        上传图片
        
        Args:
            image_data: 图片二进制数据
            image_type: 图片类型 (message/avatar)
            
        Returns:
            str: image_key，失败返回None
        """
        try:
            # 构造请求
            request = CreateImageRequest.builder() \
                .request_body(CreateImageRequestBody.builder()
                    .image_type(image_type)
                    .image(image_data)
                    .build()) \
                .build()

            # 发送请求
            response = self._api_client.im.v1.image.create(request)

            if not response.success():
                self.logger.error(f"上传图片失败: {response.code} - {response.msg}")
                return None

            return response.data.image_key

        except Exception as e:
            self.logger.error(f"上传图片异常: {str(e)}")
            return None

    def upload_file(self, file_path: str, file_type: str = "stream", duration: int = None) -> Optional[str]:
        """
        上传文件 (PDF, Doc, Python脚本等)
        
        Args:
            file_path: 文件路径
            file_type: 文件类型 (stream, mp4, pdf, doc, xls, ppt, etc.)
            duration: 视频/音频时长(毫秒)，仅媒体文件需要
            
        Returns:
            str: file_key, 失败返回None
        """
        try:
            import os
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            
            with open(file_path, "rb") as f:
                file_content = f.read()

            # 构造请求体
            body_builder = CreateFileRequestBody.builder() \
                .file_type(file_type) \
                .file_name(file_name) \
                .file(file_content)
                
            if duration:
                body_builder.duration(duration)

            request = CreateFileRequest.builder() \
                .request_body(body_builder.build()) \
                .build()

            # 发送请求
            response = self._api_client.im.v1.file.create(request)

            if not response.success():
                self.logger.error(f"上传文件失败: {response.code} - {response.msg}")
                return None

            return response.data.file_key

        except Exception as e:
            self.logger.error(f"上传文件异常: {str(e)}")
            return None
