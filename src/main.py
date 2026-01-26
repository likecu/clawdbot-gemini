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

from client import FeishuBot, create_client
from llm import init_gemini
from bot import create_message_handler
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
        
        self.feishu_bot = None
        self.llm_model = None
        self.message_handler = None
        self.is_running = False
    
    def initialize(self) -> None:
        """
        初始化所有组件
        
        Raises:
            Exception: 初始化失败时抛出异常
        """
        try:
            self.logger.info("正在初始化飞书客户端...")
            self.feishu_bot = FeishuBot()
            self.logger.info("飞书客户端初始化成功")
            
            self.logger.info("正在初始化Gemini模型...")
            self.llm_model = init_gemini()
            self.logger.info("Gemini模型初始化成功")
            
            self.logger.info("正在创建消息处理器...")
            self.message_handler = create_message_handler(
                self.feishu_bot, 
                self.llm_model
            )
            self.logger.info("消息处理器创建成功")
            
            self.logger.info("所有组件初始化完成")
            
        except Exception as e:
            self.logger.error(f"初始化失败: {str(e)}")
            raise
    
    def start(self) -> None:
        """
        启动应用程序
        """
        try:
            self.initialize()
            self.is_running = True
            
            self.logger.info("正在启动飞书长连接客户端...")
            
            self.feishu_bot.client.im.v1.event.listen(
                event_type="im.message.message_v1",
                handler=self._handle_message_event
            )
            
            self.logger.info("Clawdbot已启动，正在监听飞书消息...")
            self.logger.info("按Ctrl+C可停止服务")
            
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
    
    def _handle_message_event(self, event_data: dict) -> None:
        """
        处理飞书消息事件
        
        Args:
            event_data: 飞书推送的事件数据
        """
        try:
            event_type = event_data.get("type", "")
            self.logger.info(f"收到事件: {event_type}")
            
            if self.message_handler:
                self.message_handler.handle_message(event_type, event_data)
            else:
                self.logger.warning("消息处理器未初始化，无法处理消息")
                
        except Exception as e:
            self.logger.error(f"处理消息事件失败: {str(e)}")
    
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
