"""
Clawdbot主程序入口

基于飞书WebSocket长连接和DeepSeek大模型的智能编程助手
"""

import os
import sys
import signal
import logging
import asyncio
from typing import Optional

from dotenv import load_dotenv

import lark_oapi as lark

from adapters.lark import LarkWSClient, EventDispatcher, ParsedMessage
from adapters.llm import init_client, OpenRouterClient
from core import Agent, create_agent
from core.session import create_session_manager
from core.prompt import create_prompt_builder
from infrastructure.redis_client import create_redis_client
from config import get_settings


class ClawdbotApplication:
    """
    Clawdbot应用程序类
    
    整合飞书WebSocket客户端和LLM智能体，提供完整的机器人功能
    """
    
    def __init__(self):
        """
        初始化应用程序
        """
        load_dotenv()
        
        self.settings = get_settings()
        self.logger = self._setup_logging()
        
        self.logger.info("正在初始化Clawdbot应用...")
        
        self.llm_client: Optional[OpenRouterClient] = None
        self.agent: Optional[Agent] = None
        self.ws_client: Optional[LarkWSClient] = None
        self.event_dispatcher: Optional[EventDispatcher] = None
        
        self._is_running = False
    
    def _setup_logging(self) -> logging.Logger:
        """
        配置日志系统
        
        Returns:
            logging.Logger: 日志记录器
        """
        log_level = getattr(logging, self.settings.log_level.upper(), logging.INFO)
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        return logging.getLogger("Clawdbot")
    
    def _validate_config(self) -> None:
        """
        验证配置有效性
        
        Raises:
            ValueError: 配置无效时抛出
        """
        is_valid, errors = self.settings.validate()
        if not is_valid:
            error_msg = "\n".join(errors)
            self.logger.error(f"配置验证失败:\n{error_msg}")
            raise ValueError(f"配置错误: {error_msg}")
        
        self.logger.info("配置验证通过")
    
    def initialize(self) -> None:
        """
        初始化所有组件
        
        Raises:
            Exception: 初始化失败时抛出
        """
        try:
            self.logger.info("正在验证配置...")
            self._validate_config()
            
            self.logger.info(f"使用模型: {self.settings.active_model}")
            self.logger.info(f"模型: {self.settings.openrouter_default_model}")
            
            # 初始化LLM客户端
            self.logger.info("正在初始化LLM客户端...")
            self.llm_client = init_client(
                api_key=self.settings.openrouter_api_key,
                model=self.settings.openrouter_default_model,
                base_url=self.settings.openrouter_api_base_url
            )
            self.logger.info("LLM客户端初始化成功")
            
            # 初始化会话管理器
            self.logger.info("正在初始化会话管理器...")
            session_manager = create_session_manager(
                redis_host=self.settings.redis_host,
                redis_port=self.settings.redis_port,
                redis_db=self.settings.redis_db,
                redis_password=self.settings.redis_password,
                max_history=self.settings.session_max_history
            )
            self.logger.info("会话管理器初始化成功")
            
            # 初始化提示词构建器
            self.logger.info("正在初始化提示词构建器...")
            prompt_builder = create_prompt_builder()
            self.logger.info("提示词构建器初始化成功")
            
            # 初始化智能体
            self.logger.info("正在初始化智能体...")
            self.agent = create_agent(
                llm_client=self.llm_client,
                session_manager=session_manager,
                prompt_builder=prompt_builder
            )
            self.logger.info("智能体初始化成功")
            
            # 初始化事件分发器
            self.logger.info("正在初始化事件分发器...")
            self.event_dispatcher = EventDispatcher()
            self.event_dispatcher.register_message_handler(self._handle_message)
            self.logger.info("事件分发器初始化成功")
            
            # 初始化飞书WebSocket客户端
            self.logger.info("正在初始化飞书WebSocket客户端...")
            self.ws_client = LarkWSClient(
                app_id=self.settings.lark_app_id,
                app_secret=self.settings.lark_app_secret,
                encrypt_key=self.settings.lark_encrypt_key,
                verification_token=self.settings.lark_verification_token
            )
            
            # 注册事件处理函数
            self.ws_client.register_event_handler(
                "im.message.receive_v1",
                self._create_event_handler()
            )
            
            self.logger.info("飞书WebSocket客户端初始化成功")
            self.logger.info("所有组件初始化完成")
            
        except Exception as e:
            self.logger.error(f"初始化失败: {str(e)}")
            raise
    
    def _create_event_handler(self):
        """
        创建事件处理函数
        
        Returns:
            Callable: 事件处理函数
        """
        def handler(data: dict):
            if self.event_dispatcher:
                self.event_dispatcher.dispatch("im.message.receive_v1", data)
        return handler
    
    def _handle_message(self, message: ParsedMessage) -> None:
        """
        处理消息（事件分发器回调）
        
        Args:
            message: 解析后的消息对象
        """
        try:
            self.logger.info(f"收到消息: {message.text[:50]}... (chat={message.chat_id})")
            
            # 调用智能体处理消息
            result = self.agent.process_message(
                user_id=message.sender_id,
                chat_id=message.chat_id,
                message=message.text
            )
            
            if result["success"]:
                response_text = result["text"]
                
                # 发送回复
                self._send_response(message, response_text)
                
                self.logger.info(f"回复发送成功: {response_text[:50]}...")
            else:
                error_text = result.get("text", "抱歉，处理消息时出现了问题")
                self._send_response(message, error_text)
                self.logger.error(f"处理失败: {result.get('error', '未知错误')}")
                
        except Exception as e:
            self.logger.error(f"处理消息异常: {str(e)}")
            self._send_response(message, f"抱歉，处理消息时出现了问题：{str(e)}")
    
    def _send_response(self, message: ParsedMessage, text: str) -> None:
        """
        发送响应消息
        
        Args:
            message: 原始消息
            text: 响应文本
        """
        if not self.ws_client or not self.ws_client.is_connected():
            self.logger.warning("WebSocket客户端未连接，无法发送消息")
            return
        
        try:
            # 发送文本消息
            self.ws_client.send_text_message(
                receive_id=message.sender_id,
                text=text
            )
        except Exception as e:
            self.logger.error(f"发送消息失败: {str(e)}")
    
    def start(self) -> None:
        """
        启动应用程序
        """
        try:
            self.initialize()
            self._is_running = True
            
            self.logger.info("正在启动Clawdbot...")
            self.logger.info(f"监听地址: {self.settings.app_host}:{self.settings.app_port}")
            self.logger.info("按Ctrl+C可停止服务")
            
            # 启动WebSocket客户端
            self.ws_client.start(blocking=True)
            
        except KeyboardInterrupt:
            self.logger.info("收到停止信号，正在退出...")
        except Exception as e:
            self.logger.error(f"运行时发生错误: {str(e)}")
            raise
        finally:
            self.stop()
    
    def stop(self) -> None:
        """
        停止应用程序
        """
        self._is_running = False
        
        if self.ws_client:
            self.ws_client.stop()
        
        self.logger.info("Clawdbot已停止")
    
    def health_check(self) -> dict:
        """
        健康检查
        
        Returns:
            dict: 健康状态信息
        """
        status = {
            "status": "healthy",
            "components": {}
        }
        
        # 检查LLM客户端
        try:
            if self.llm_client:
                status["components"]["llm"] = "connected"
            else:
                status["components"]["llm"] = "not_initialized"
        except Exception as e:
            status["components"]["llm"] = f"error: {str(e)}"
            status["status"] = "unhealthy"
        
        # 检查WebSocket连接
        try:
            if self.ws_client and self.ws_client.is_connected():
                status["components"]["websocket"] = "connected"
            else:
                status["components"]["websocket"] = "disconnected"
        except Exception as e:
            status["components"]["websocket"] = f"error: {str(e)}"
            status["status"] = "unhealthy"
        
        return status


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
