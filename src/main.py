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
from lark_oapi.api.im.v1 import *
from lark_oapi.event import *
from lark_oapi import *

from llm import init_gemini
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
    
    def handle_p2_im_message_receive_v1(self, data: P2ImMessageReceiveV1) -> None:
        """
        处理飞书消息事件
        
        Args:
            data: 飞书消息事件数据
        """
        try:
            self.logger.info(f"收到飞书消息事件: {data}")
            
            # 获取消息内容
            message = data.event.message
            content = message.content
            
            # 解析消息内容
            import json
            content_json = json.loads(content)
            user_text = content_json.get("text", "").strip()
            
            if not user_text:
                return
            
            self.logger.info(f"用户消息: {user_text}")
            
            # 调用Gemini获取回复
            response_text = self.llm_model.generate_content(user_text).text
            self.logger.info(f"Gemini回复: {response_text}")
            
            # 回复消息
            reply_request = ReplyMessageRequest.builder().message_id(message.message_id).request_body(ReplyMessageRequestBody.builder().content(json.dumps({"text": response_text})).msg_type("text").build()).build()
            
            self.client.im.v1.message.reply(reply_request)
            self.logger.info("消息回复成功")
            
        except Exception as e:
            self.logger.error(f"处理消息事件失败: {str(e)}")
    
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
            ).register_p2_im_message_receive_v1(self.handle_p2_im_message_receive_v1).build()
            
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
            ws_client.run()
            
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
