"""
飞书长连接客户端模块

提供与飞书开放平台建立长连接的功能，处理事件接收和消息发送
"""

import lark_oapi as lark
from typing import Callable, Optional
import os


def create_client(app_id: Optional[str] = None, 
                  app_secret: Optional[str] = None,
                  log_level: lark.LogLevel = lark.LogLevel.INFO) -> lark.Client:
    """
    创建飞书客户端实例

    Args:
        app_id: 飞书应用ID，如果为None则从环境变量FEISHU_APP_ID获取
        app_secret: 飞书应用密钥，如果为None则从环境变量FEISHU_APP_SECRET获取
        log_level: 日志级别，默认为INFO

    Returns:
        配置好的lark.Client实例

    Raises:
        ValueError: 当app_id或app_secret为空且环境变量中也不存在时抛出
    """
    if app_id is None:
        app_id = os.getenv("FEISHU_APP_ID")
    
    if app_secret is None:
        app_secret = os.getenv("FEISHU_APP_SECRET")
    
    if not app_id:
        raise ValueError("飞书App ID未配置，请设置FEISHU_APP_ID环境变量或传入app_id参数")
    
    if not app_secret:
        raise ValueError("飞书App Secret未配置，请设置FEISHU_APP_SECRET环境变量或传入app_secret参数")
    
    return (lark.Client.builder()
            .app_id(app_id)
            .app_secret(app_secret)
            .log_level(log_level)
            .build())


class FeishuBot:
    """
    飞书机器人客户端类
    
    封装长连接模式下的机器人功能，包括事件处理和消息发送
    """
    
    def __init__(self, app_id: Optional[str] = None, 
                 app_secret: Optional[str] = None):
        """
        初始化飞书机器人
        
        Args:
            app_id: 飞书应用ID
            app_secret: 飞书应用密钥
        """
        self.client = create_client(app_id, app_secret)
        self.handlers = {}
    
    def register_handler(self, event_type: str, handler: Callable) -> None:
        """
        注册事件处理器
        
        Args:
            event_type: 事件类型，如'im.message.message_v1'
            handler: 事件处理函数，接收事件数据作为参数
        """
        self.handlers[event_type] = handler
    
    def send_message(self, receive_id: str, msg_type: str, content: str) -> dict:
        """
        发送消息给用户或群组
        
        Args:
            receive_id: 接收者ID（用户ID或群组ID）
            msg_type: 消息类型，如'text'
            content: 消息内容（JSON格式字符串）
            
        Returns:
            dict: API响应结果
        """
        try:
            response = self.client.im.v1.message.create(
                CreateMessageRequest.builder()
                .receive_id(receive_id)
                .msg_type(msg_type)
                .content(content)
                .build()
            )
            return response.dict()
        except Exception as e:
            raise Exception(f"发送消息失败: {str(e)}")
    
    def reply_message(self, message_id: str, msg_type: str, content: str) -> dict:
        """
        回复消息（通过message_id）
        
        Args:
            message_id: 原消息的message_id
            msg_type: 消息类型
            content: 消息内容
            
        Returns:
            dict: API响应结果
        """
        try:
            response = self.client.im.v1.message.reply(
                ReplyMessageRequest.builder()
                .message_id(message_id)
                .request_body(ReplyMessageRequestBody.builder()
                    .msg_type(msg_type)
                    .content(content)
                    .build())
                .build()
            )
            return response.dict()
        except Exception as e:
            raise Exception(f"回复消息失败: {str(e)}")
