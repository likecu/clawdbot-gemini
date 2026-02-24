"""
Clawdbot主程序入口

基于飞书WebSocket、NapCat(QQ)和LLM的智能编程助手
包含FastAPI服务器，用于暴露API接口
"""

import os
import sys
import signal
import logging
import asyncio
from typing import Optional, Dict
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket
from pydantic import BaseModel
import uvicorn

# New Channel Architecture
from channels.manager import ChannelManager
from channels.base import UnifiedMessage, UnifiedSendRequest
from channels.lark.adapter import LarkChannel
from channels.qq.adapter import QQChannel

from api.routes import router as api_router

from adapters.llm import init_client, OpenRouterClient
from adapters.llm.clawdbot_client import ClawdbotClient
from adapters.llm.clawdbot_client import ClawdbotClient
from core import Agent, create_agent
from core.session import create_session_manager
from core.prompt import create_prompt_builder
from core.memory import create_memory_bank
from core.tools.clawdbot_cli import ClawdbotCliTool
from core.services.message_processor import MessageProcessor
from infrastructure.redis_client import create_redis_client
from config import get_settings

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("Clawdbot")

# API Models
class SendMessageRequest(BaseModel):
    platform: str = "qq"  # 'qq' or 'lark'
    target_id: str  # user_id or group_id/chat_id
    message_type: str = "private"  # 'private' or 'group'
    content: str


class ClawdbotApplication:
    """
    Clawdbot应用程序类
    
    整合多渠道管理(ChannelManager)和LLM智能体，提供完整的机器人功能
    """
    
    def __init__(self):
        """
        初始化应用程序
        """
        load_dotenv()
        
        self.settings = get_settings()
        self.app = FastAPI(title="Clawdbot API", version="2.0.0")
        
        self.llm_client: Optional[OpenRouterClient] = None
        self.agent: Optional[Agent] = None
        self.message_processor: Optional[MessageProcessor] = None
        
        # New Channel Manager
        # New Channel Manager
        self.channel_manager = ChannelManager()
        self.app.state.channel_manager = self.channel_manager # Inject for API Router
        
        self.ws_manager = ConnectionManager() # For UI
        
        self.app.include_router(api_router)
        self._setup_routes()

    def _setup_routes(self):

        @self.app.on_event("startup")
        async def startup_event():
            await self.initialize()
            asyncio.create_task(self._monitor_napcat_logs())

        @self.app.on_event("shutdown")
        async def shutdown_event():
            await self.stop() # Make stop async

        @self.app.get("/")
        async def get_monitor():
            from fastapi.responses import HTMLResponse
            try:
                with open("src/templates/monitor.html", "r", encoding="utf-8") as f:
                    return HTMLResponse(content=f.read())
            except FileNotFoundError:
                return HTMLResponse(content="Monitor template not found.", status_code=404)

        @self.app.websocket("/ws/monitor")
        async def websocket_endpoint(websocket: WebSocket):
            await self.ws_manager.connect(websocket)
            try:
                while True:
                    await websocket.receive_text()
            except Exception:
                self.ws_manager.disconnect(websocket)


    async def initialize(self) -> None:
        """
        初始化所有组件
        """
        try:
            # 初始化 LLM 客户端
            logger.info("使用模型: clawdbot")
            self.llm_client = ClawdbotClient()
            
            # 初始化会话管理器
            session_manager = create_session_manager(
                redis_host=self.settings.redis_host,
                redis_port=self.settings.redis_port,
                redis_db=self.settings.redis_db,
                redis_password=self.settings.redis_password,
                max_history=self.settings.session_max_history
            )
            
            # 初始化记忆库
            create_memory_bank()
            
            # 尝试加载外部人格文件
            system_prompt = None
            soul_path = self.settings.soul_path
            if os.path.exists(soul_path):
                try:
                    with open(soul_path, "r", encoding="utf-8") as f:
                        system_prompt = f.read()
                    logger.info(f"已加载外部人格文件 SOUL.md (长度: {len(system_prompt)})")
                except Exception as e:
                    logger.error(f"加载 SOUL.md 失败: {e}")

            prompt_builder = create_prompt_builder(system_prompt=system_prompt)
            
            # [Clawdbot Integration] define async callback
            async def agent_notification_callback(session_id: str, content: str):
                """
                回调函数：处理来自后台任务（如Clawdbot CLI）的异步通知
                """
                try:
                    logger.info(f"Received async notification for session {session_id}")
                    
                    # 解析 session_id 以获取目标 chat_id 和 platform
                    # 格式可能是 "platform:user:id:date" 或 "platform:type:chat_id"
                    # 这里我们依赖 agent.py 中传递的 callback_session_id
                    
                    platform = "qq"
                    chat_id = session_id
                    msg_type = "private"
                    
                    if ":" in session_id:
                        parts = session_id.split(":")
                        if len(parts) >= 3:
                            platform = parts[0]
                            # Assuming format platform:type:chat_id
                            if parts[1] in ["private", "group"]:
                                msg_type = parts[1]
                                chat_id = ":".join(parts[2:])
                            else:
                                # Fallback or other format
                                chat_id = ":".join(parts[1:]) 
                        elif len(parts) == 2:
                            platform = parts[0]
                            chat_id = parts[1]
                    
                    # 发送消息
                    from channels.base import UnifiedSendRequest
                    req = UnifiedSendRequest(
                        chat_id=chat_id,
                        content=content,
                        message_type=msg_type
                    )
                    
                    success = await self.channel_manager.send_message(platform, req)
                    if success and platform == "qq":
                        await self._broadcast_sent_message(platform, chat_id, content, msg_type)
                        
                except Exception as e:
                    logger.error(f"Async Notification Callback failed: {e}")

            # 初始化工具
            clawdbot_tool = ClawdbotCliTool()

            self.agent = create_agent(
                llm_client=self.llm_client,
                session_manager=session_manager,
                prompt_builder=prompt_builder,
                clawdbot_tool=clawdbot_tool,
                notification_callback=agent_notification_callback
            )
            
            # Initialize Message Processor
            self.message_processor = MessageProcessor(self.agent)
            self.app.state.agent = self.agent
            
            # --- Initialize Channels ---
            
            # 1. Lark
            if self.settings.lark_app_id:
                lark_config = {
                    "app_id": self.settings.lark_app_id,
                    "app_secret": self.settings.lark_app_secret,
                    "encrypt_key": self.settings.lark_encrypt_key,
                    "verification_token": self.settings.lark_verification_token
                }
                self.channel_manager.register_channel("lark", LarkChannel(lark_config))

            # 2. QQ
            if self.settings.qq_bot_enabled:
                qq_config = {
                    "host": self.settings.qq_host,
                    "http_port": self.settings.qq_http_port,
                    "ws_port": self.settings.qq_ws_port,
                    "token": None # Access token if needed
                }
                self.channel_manager.register_channel("qq", QQChannel(qq_config))
            
            # Set Global Handler
            self.channel_manager.set_global_handler(self._handle_unified_message)
            
            # Start Channels
            await self.channel_manager.start_all()
            
            logger.info("所有组件初始化完成")
            
        except Exception as e:
            logger.error(f"初始化失败: {str(e)}")
            raise

    async def _handle_unified_message(self, message: UnifiedMessage) -> None:
        """
        统一的消息处理入口
        
        所有渠道（QQ, Lark）的消息都会汇聚到这里进行处理。
        流程包含：
        1. 广播消息到前端 UI
        2. 文本/图片内容提取与 OCR 处理
        3. 会话 ID 生成 (按用户+日期隔离)
        4. 调用 Agent 进行智能处理
        5. 发送处理结果回原渠道

        :param message: 统一消息对象，屏蔽了底层渠道差异
        :return: None
        """
        try:
            # 1. Broadcast to UI (if it's a message we want to show)
            if message.platform == "qq":
                # Reconstruct legacy format for UI compatibility if needed
                await self._broadcast_ui_message_from_unified(message, direction="received")

            # 2. Process via Service (OCR + Session + Agent)
            result = await self.message_processor.process(message)

            # [Debug] 发送调试信息
            if result.get("success") and result.get("debug_info"):
                debug_msg = f"[Debug Prompt Info]:\n{result.get('debug_info')}"
                # 分段发送以防过长（简单的分段逻辑，或者直接发送尝试）
                # 为了不影响主回复，单独发送
                debug_req = UnifiedSendRequest(
                    chat_id=message.chat_id,
                    content=debug_msg,
                    message_type=message.message_type
                )
                await self.channel_manager.send_message(message.platform, debug_req)
                logger.info("已发送调试提示词信息。")

            if result["success"]:
                response_text = result["text"]
                
                # [Fix] 如果响应文本为空（例如已通过回调发送），则不发送消息
                if not response_text:
                    logger.info(f"Response text is empty (handled via callback?), skipping UnifiedSendRequest.")
                    return

                reply = UnifiedSendRequest(
                    chat_id=message.chat_id, # Reply to the same chat_id
                    content=response_text,
                    message_type=message.message_type
                )
                
                success = await self.channel_manager.send_message(message.platform, reply)
                
                if success and message.platform == "qq":
                    await self._broadcast_sent_message(message.platform, message.chat_id, response_text, message.message_type)
            else:
                 logger.error(f"Agent processing failed: {result.get('error')}")

        except Exception as e:
            logger.error(f"Error processing unified message: {e}")

    async def _broadcast_ui_message_from_unified(self, message: UnifiedMessage, direction: str):
        """
        将统一的消息格式广播到前端 UI 监控界面
        :param message: 统一消息对象
        :param direction: 消息方向 (received/sent)
        """
        try:
             data = {
                "platform": message.platform,
                "direction": direction,
                "user_id": message.user_id,
                "message_type": message.message_type,
                "content": message.content
            }
             await self.ws_manager.broadcast(data)
        except Exception as e:
             logger.error(f"UI Broadcast error: {e}")

    async def _broadcast_sent_message(self, platform: str, chat_id: str, content: str, msg_type: str):
         """
         广播已发送的消息到 UI 面板
         """
         try:
             data = {
                "platform": platform,
                "direction": "sent",
                "user_id": chat_id, # For sent messages, we often show target
                "message_type": msg_type,
                "content": content
            }
             await self.ws_manager.broadcast(data)
         except Exception as e:
             logger.error(f"UI Broadcast error: {e}")

    async def _monitor_napcat_logs(self):
        """
        持续监控 NapCat 容器日志，用于提取登录二维码
        """
        logger.info("Starting NapCat log monitor...")
        try:
            import docker
            client = docker.from_env()
            container_name = self.settings.napcat_container_name

            while True:
                try:
                    try:
                        container = client.containers.get(container_name)
                    except docker.errors.NotFound:
                        # logger.warning(f"Container {container_name} not found")
                        await asyncio.sleep(5)
                        continue

                    if container.status != "running":
                        await asyncio.sleep(5)
                        continue

                    # Get last 50 lines
                    logs = container.logs(tail=50).decode("utf-8", errors="ignore")
                    
                    if "二维码解码URL:" in logs:
                        for line in logs.split("\n"):
                            if "二维码解码URL:" in line:
                                url_line = line.strip()
                                
                                qr_path = self.settings.qr_code_path
                                current_content = ""
                                if os.path.exists(qr_path):
                                    with open(qr_path, "r", encoding="utf-8") as f:
                                        current_content = f.read().strip()
                                
                                if current_content != url_line:
                                    os.makedirs(os.path.dirname(qr_path), exist_ok=True)
                                    with open(qr_path, "w", encoding="utf-8") as f:
                                        f.write(url_line)
                                    logger.info(f"Updated QR code: {url_line}")
                                break
                    
                except Exception as e:
                    logger.error(f"Error monitoring logs: {e}")
                
                await asyncio.sleep(2)
                
        except Exception as e:
             logger.error(f"Failed to start log monitor: {e}")

    async def stop(self) -> None:
        """停止应用程序"""
        await self.channel_manager.stop_all()
        logger.info("Clawdbot已停止")

class ConnectionManager:
    """
    管理前端 UI 的 WebSocket 连接
    """
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        """接受并保存新的 WebSocket 连接"""
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        """断开并移除 WebSocket 连接"""
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        """向所有活跃的 WebSocket 连接广播 JSON 消息"""
        import json
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending to websocket: {e}")


def main():
    """程序主入口"""
    app_instance = ClawdbotApplication()
    settings = get_settings()
    uvicorn.run(app_instance.app, host=settings.app_host, port=settings.app_port)

if __name__ == "__main__":
    main()
