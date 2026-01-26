"""
Clawdbot主程序入口

飞书机器人与Google Gemini AI的集成应用
支持长连接模式接收飞书消息并通过Gemini进行智能回复
"""

import os
import sys
import signal
import logging
from dotenv import load_dotenv

import lark_oapi as lark
from lark_oapi.event import *
from lark_oapi import *

from llm import init_gemini
from opencode import init_opencode, get_response
from utils import setup_logging


class ClawdbotApplication:
    """
    Clawdbot应用程序类
    
    整合飞书客户端和Gemini模型，提供完整的机器人功能
    """
    
    def __init__(self):
        """
        初始化应用程序
        """
        load_dotenv()
        self.logger = setup_logging(os.getenv("LOG_LEVEL", "INFO"))
        self.logger.info("正在初始化Clawdbot应用...")
        
        self.llm_model = None
        self.is_running = False
        self.client = None
        self.processed_messages = set()  # 用于消息去重
    
    def initialize(self) -> None:
        """
        初始化所有组件
        
        Raises:
            Exception: 初始化失败时抛出异常
        """
        try:
            self.logger.info("正在初始化Gemini模型...")
            self.llm_model = init_gemini()
            self.logger.info("Gemini模型初始化成功")
            
            self.logger.info("正在初始化飞书长连接客户端...")
            
            # 创建飞书长连接客户端
            self.client = lark.Client.builder().app_id(os.getenv("FEISHU_APP_ID")).app_secret(os.getenv("FEISHU_APP_SECRET")).log_level(lark.LogLevel.INFO).build()
            
            self.logger.info("飞书长连接客户端初始化成功")
            self.logger.info("所有组件初始化完成")
            
        except Exception as e:
            self.logger.error(f"初始化失败: {str(e)}")
            raise
    
    def handle_message(self, message) -> None:
        """
        统一处理消息逻辑
        
        Args:
            message: 消息对象（EventMessage类型）
        """
        try:
            # 消息去重检查
            if hasattr(message, 'message_id') and message.message_id:
                message_id = message.message_id
                if message_id in self.processed_messages:
                    self.logger.info(f"消息 {message_id} 已处理，跳过重复处理")
                    return
                self.processed_messages.add(message_id)
            
            # 解析消息内容
            import json
            content_json = json.loads(message.content)
            user_text = content_json.get("text", "").strip()
            
            if not user_text:
                self.logger.info("收到空消息，跳过处理")
                return
            
            # 群聊消息需要移除@机器人的部分
            if message.chat_type == "group":
                # 移除@机器人的标记
                import re
                user_text = re.sub(r"@_user_\d+", "", user_text).strip()
                if not user_text:
                    self.logger.info("群聊消息仅包含@机器人标记，跳过处理")
                    return
            
            self.logger.info(f"用户消息: {user_text}, 消息类型: {message.message_type}, 聊天类型: {message.chat_type}")
            
            # 默认使用OpenCode
            self.logger.info("默认调用OpenCode")
            try:
                # 初始化OpenCode
                opencode_client = init_opencode()
                # 获取OpenCode回复
                response_text = get_response(opencode_client, user_text)
                self.logger.info(f"OpenCode回复: {response_text}")
            except Exception as e:
                self.logger.error(f"OpenCode调用失败: {str(e)}")
                # 失败时回退到Gemini
                self.logger.info("OpenCode调用失败，回退到Gemini")
                from llm import get_response
                response_text = get_response(self.llm_model, user_text)
                self.logger.info(f"Gemini回复: {response_text}")
            
            # 回复消息
            self.reply_message(message.message_id, response_text, message.chat_type == "group")
            
        except Exception as e:
            self.logger.error(f"处理消息失败: {str(e)}")
    
    def reply_message(self, message_id: str, content: str, is_group: bool = False, reply_in_thread: bool = False) -> None:
        """
        回复飞书消息
        
        Args:
            message_id: 消息ID
            content: 回复内容
            is_group: 是否为群聊消息
            reply_in_thread: 是否以话题形式回复
        """
        try:
            import json
            import uuid
            
            # 构建回复请求
            reply_request = ReplyMessageRequest.builder().message_id(message_id).request_body(ReplyMessageRequestBody.builder().content(json.dumps({"text": content})).msg_type("text").reply_in_thread(reply_in_thread).uuid(str(uuid.uuid4())).build()).build()
            
            # 发送回复
            response = self.client.im.v1.message.reply(reply_request)
            if response.code == 0:
                self.logger.info(f"消息回复成功，回复消息ID: {response.data.message_id}")
            else:
                self.logger.error(f"消息回复失败，错误码: {response.code}, 错误信息: {response.msg}")
                
        except Exception as e:
            self.logger.error(f"回复消息失败: {str(e)}")
    
    def send_message(self, receive_id: str, receive_id_type: str, content: str, msg_type: str = "text") -> str:
        """
        主动发送消息
        
        Args:
            receive_id: 接收者ID
            receive_id_type: 接收者类型 (open_id/union_id/user_id/email/chat_id)
            content: 消息内容
            msg_type: 消息类型
            
        Returns:
            str: 发送成功返回消息ID，失败返回空字符串
        """
        try:
            import json
            import uuid
            
            # 构建发送请求
            create_message_request = CreateMessageRequest.builder().receive_id_type(receive_id_type).request_body(CreateMessageRequestBody.builder().receive_id(receive_id).msg_type(msg_type).content(json.dumps({"text": content})).uuid(str(uuid.uuid4())).build()).build()
            
            # 发送消息
            response = self.client.im.v1.message.create(create_message_request)
            if response.code == 0:
                self.logger.info(f"消息发送成功，消息ID: {response.data.message_id}")
                return response.data.message_id
            else:
                self.logger.error(f"消息发送失败，错误码: {response.code}, 错误信息: {response.msg}")
                return ""
                
        except Exception as e:
            self.logger.error(f"发送消息失败: {str(e)}")
            return ""
    
    def handle_p2_im_message_receive_v1(self, data: dict) -> None:
        """
        处理飞书单聊消息事件
        
        Args:
            data: 飞书单聊消息事件数据
        """
        try:
            self.logger.info(f"收到单聊消息事件: {data}")
            
            # 获取消息内容
            message = data.event.message
            self.handle_message(message)
            
        except Exception as e:
            self.logger.error(f"处理单聊消息事件失败: {str(e)}")
    
    def handle_group_at_message_receive_v1(self, data) -> None:
        """
        处理飞书群聊@机器人消息事件
        
        Args:
            data: 飞书群聊@机器人消息事件数据
        """
        try:
            self.logger.info(f"收到群聊@机器人消息事件: {data}")
            
            # 获取消息内容
            message = data.event.message
            self.handle_message(message)
            
        except Exception as e:
            self.logger.error(f"处理群聊@机器人消息事件失败: {str(e)}")
    
    def start(self) -> None:
        """
        启动应用程序
        """
        try:
            self.initialize()
            self.is_running = True
            
            self.logger.info("正在注册事件处理器...")
            
            # 创建事件处理器
            event_handler = EventDispatcherHandler.builder(
                os.getenv("FEISHU_ENCRYPT_KEY"),
                os.getenv("FEISHU_VERIFICATION_TOKEN"),
                lark.LogLevel.INFO
            )
            
            # 注册单聊消息处理器
            event_handler = event_handler.register_p2_im_message_receive_v1(self.handle_p2_im_message_receive_v1)
            
            # 构建事件处理器
            event_handler = event_handler.build()
            
            # 启动长连接监听
            self.logger.info("正在启动长连接监听...")
            
            # 使用飞书SDK的长连接功能
            from lark_oapi import ws
            
            # 创建长连接客户端
            ws_client = ws.Client(
                app_id=os.getenv("FEISHU_APP_ID"),
                app_secret=os.getenv("FEISHU_APP_SECRET"),
                event_handler=event_handler,
                log_level=lark.LogLevel.INFO
            )
            
            self.logger.info("Clawdbot已启动，正在监听飞书消息...")
            self.logger.info("按Ctrl+C可停止服务")
            
            # 启动长连接客户端
            ws_client.start()
            
            # 保持程序运行
            while self.is_running:
                import time
                time.sleep(1)
                
        except KeyboardInterrupt:
            self.logger.info("收到停止信号，正在退出...")
            self.stop()
        except Exception as e:
            self.logger.error(f"运行时发生错误: {str(e)}")
            self.stop()
            raise
    
    def stop(self) -> None:
        """
        停止应用程序
        """
        self.is_running = False
        self.logger.info("Clawdbot已停止")


def main():
    """
    程序主入口
    """
    app = ClawdbotApplication()
    
    def signal_handler(signum, frame):
        app.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    app.start()


if __name__ == "__main__":
    main()