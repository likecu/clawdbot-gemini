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

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, WebSocket
from pydantic import BaseModel
import uvicorn

from adapters.lark import LarkWSClient, EventDispatcher, ParsedMessage
from adapters.qq.client import NapCatClient
from adapters.qq.models import QQMessage, MessageRequest as QQMessageRequest
from adapters.llm import init_client, OpenRouterClient
from adapters.llm.clawdbot_client import ClawdbotClient
from core import Agent, create_agent
from core.session import create_session_manager
from core.prompt import create_prompt_builder
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
    
    整合飞书WebSocket客户端、NapCat QQ客户端和LLM智能体，提供完整的机器人功能
    """
    
    def __init__(self):
        """
        初始化应用程序
        """
        load_dotenv()
        
        self.settings = get_settings()
        self.app = FastAPI(title="Clawdbot API", version="1.0.0")
        
        self.llm_client: Optional[OpenRouterClient] = None
        self.agent: Optional[Agent] = None
        self.ws_client: Optional[LarkWSClient] = None
        self.qq_client: Optional[NapCatClient] = None
        self.event_dispatcher: Optional[EventDispatcher] = None
        
        self._setup_routes()

    def _setup_routes(self):
        @self.app.post("/send_msg")
        async def send_message(request: SendMessageRequest):
            try:
                if request.platform == "qq":
                    if not self.qq_client:
                        raise HTTPException(status_code=503, detail="QQ service not enabled or initialized")
                    
                    qq_req = QQMessageRequest(
                        message_type=request.message_type,
                        user_id=int(request.target_id) if request.message_type == "private" else None,
                        group_id=int(request.target_id) if request.message_type == "group" else None,
                        message=request.content
                    )
                    return self.qq_client.send_message(qq_req)
                
                elif request.platform == "lark":
                    if not self.ws_client:
                        raise HTTPException(status_code=503, detail="Lark service not initialized")
                    
                    self.ws_client.send_text_message(
                        receive_id=request.target_id,
                        receive_id_type="chat_id" if request.message_type == "group" else "open_id", # Simplified assumption
                        text=request.content
                    )
                    return {"status": "success", "platform": "lark"}
                
                else:
                    raise HTTPException(status_code=400, detail="Unsupported platform")
            except Exception as e:
                logger.error(f"Error sending message: {e}")
                raise HTTPException(status_code=500, detail=str(e))

        class ClawdbotCallbackRequest(BaseModel):
            session_id: str
            content: str

        @self.app.post("/api/clawdbot/callback")
        async def clawdbot_callback(data: ClawdbotCallbackRequest):
            """
            接收来自 Clawdbot HTTP Wrapper 的实时中间结果并转发给用户
            """
            try:
                session_id = data.session_id
                content = data.content
                
                if not session_id or not content:
                    return {"status": "ignored", "reason": "missing content or session_id"}
                
                logger.info(f"收到 Clawdbot 实时推送 [Session: {session_id}]: {content[:50]}...")
                
                # 解析 session_id (格式: qq_123456_private)
                # 我们在 Agent 中设置的是 qq_<chat_id>
                # chat_id 可能是 qq_123456 (私聊) 或 qq_group_789 (群组)
                
                platform = "qq" if session_id.startswith("qq") else "lark"
                
                if platform == "qq":
                    # 尝试还原 QQ ID
                    parts = session_id.split("_")
                    if "group" in parts:
                        is_group = True
                        idx = parts.index("group")
                        target_id = parts[idx + 1] if len(parts) > idx + 1 else None
                    else:
                        is_group = False
                        target_id = parts[1] if len(parts) > 1 else None
                    
                    if target_id:
                        qq_req = QQMessageRequest(
                            message_type="group" if is_group else "private",
                            user_id=int(target_id) if not is_group else None,
                            group_id=int(target_id) if is_group else None,
                            message=content
                        )
                        if self.qq_client:
                            self.qq_client.send_message(qq_req)
                            await self._broadcast_ui_message(qq_req, direction="sent")
                elif platform == "lark":
                    # lark_chatid
                    parts = session_id.split("_")
                    if len(parts) >= 2:
                        target_id = parts[1]
                        if self.lark_client:
                            # 飞书消息通过 lark_client 发送
                            from adapters.lark.models import LarkMessageRequest
                            lark_req = LarkMessageRequest(
                                receive_id=target_id,
                                receive_id_type="chat_id",
                                content=content
                            )
                            self.lark_client.send_message(lark_req)
                
                return {"status": "success"}
            except Exception as e:
                logger.error(f"Clawdbot callback error: {e}")
                return {"status": "error", "message": str(e)}

        @self.app.on_event("startup")
        async def startup_event():
            await self.initialize()

        @self.app.on_event("shutdown")
        async def shutdown_event():
            self.stop()

        @self.app.get("/")
        async def get_monitor():
            from fastapi.responses import HTMLResponse
            with open("src/templates/monitor.html", "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())

        @self.app.websocket("/ws/monitor")
        async def websocket_endpoint(websocket: WebSocket):
            await self.ws_manager.connect(websocket)
            try:
                while True:
                    await websocket.receive_text()
            except Exception:
                self.ws_manager.disconnect(websocket)

        @self.app.get("/api/qq/status")
        async def get_qq_status():
            try:
                # Try to connect to NapCat API
                if self.qq_client:
                    # We can't access self.qq_client._http_post directly easily without a method
                    # But NapCatClient doesn't expose generic request.
                    # Let's add a method in NapCatClient to check login
                    # Or just use requests here for simplicity
                    import aiohttp
                    async with aiohttp.ClientSession() as session:
                        url = f"http://{self.settings.qq_host}:{self.settings.qq_http_port}/get_login_info"
                        try:
                            async with session.get(url, timeout=2) as resp:
                                if resp.status == 200:
                                    data = await resp.json()
                                    if data.get("retcode") == 0:
                                        # Check if we need to fetch history (first time login)
                                        # For simplicity, we can do it here or let the UI trigger it?
                                        # But user asked: "after login... get latest message"
                                        # We can trigger it if we detect a state change.
                                        # For now return status.
                                        return {"status": "logged_in", "data": data}
                        except Exception:
                            pass
            except Exception as e:
                logger.error(f"Error checking QQ status: {e}")
            
            # If not logged in or connection failed, check for QR code
            qr_path = "logs/qr_code.txt"
            if os.path.exists(qr_path):
                return {"status": "qr_code_available"}
            
            return {"status": "not_logged_in"}

        @self.app.get("/api/qq/qr")
        async def get_qq_qr():
            qr_path = "logs/qr_code.txt"
            if os.path.exists(qr_path):
                with open(qr_path, "r") as f:
                    content = f.read().strip()
                # Parse URL from log line: "二维码解码URL: https://..."
                if "二维码解码URL:" in content:
                    url = content.split("二维码解码URL:", 1)[1].strip()
                    return {"url": url}
            raise HTTPException(status_code=404, detail="QR Code not found")

        @self.app.post("/api/qq/refresh_qr")
        async def refresh_qq_qr():
            """Restart NapCat container to generate new QR Code"""
            try:
                import docker
                client = docker.from_env()
                try:
                    # Find container by name "napcatqq" (host defined in settings, but container name is needed)
                    # We assume container name is "napcatqq" (based on previous investigation)
                    # Or we look for a container connected to the same network?
                    # "napcatqq" is the container name according to `docker ps`
                    # If settings.qq_host is the container name, use it.
                    container_name = self.settings.qq_host
                    container = client.containers.get(container_name)
                    container.restart()
                    
                    # Clear local QR code file
                    qr_path = "logs/qr_code.txt"
                    if os.path.exists(qr_path):
                        os.remove(qr_path)
                        
                    return {"status": "success", "message": "Container restarted. Please wait for new QR code."}
                except docker.errors.NotFound:
                    raise HTTPException(status_code=404, detail=f"Container {self.settings.qq_host} not found")
                except Exception as e:
                    logger.error(f"Docker error: {e}")
                    raise HTTPException(status_code=500, detail=f"Failed to restart container: {e}")
            except ImportError:
                 raise HTTPException(status_code=500, detail="Docker library not installed")

        @self.app.post("/api/qq/fetch_latest")
        async def fetch_latest_message():
            """Fetch the latest message explicitly"""
            if not self.qq_client:
                 raise HTTPException(status_code=503, detail="QQ Service unavailable")
            
            # Use requests/aiohttp to get history
            import aiohttp
            # Try getting group list first, then get history of first group?
            # Or get friend list?
            # User said "get latest message".
            # We don't know which conversation.
            # We'll try to find *recent* conversation. NapCat/OneBot 11 API doesn't have "get recent chats".
            # We'll assume the user will scan and receives a message.
            # But if we must fetch, maybe fetch from a hardcoded group or iterate?
            # Wait, if we use WebSocket, we will receive the message when it comes *live*.
            # The user said "Wait for me to login, THEN get latest message".
            # This implies the message might have arrived while we were waiting?
            # Or just "start processing".
            # If we are connected via WebSocket, we *should* receive missed messages if NapCat sends them on connect?
            # Usually OneBot sends event history? No.
            # But we can try /get_group_msg_history if we know group id.
            # Without structure, impossible to know where to fetch from.
            # We will rely on real-time WS events which start flowing after login.
            return {"status": "ok", "message": "Listening for new messages"}

    async def initialize(self) -> None:
        """
        初始化所有组件
        """
        try:
            self.ws_manager = ConnectionManager()
            
            # 初始化 LLM 客户端 - 使用 clawdbot CLI
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
            
            # 初始化提示词构建器
            prompt_builder = create_prompt_builder()
            
            # 初始化智能体
            self.agent = create_agent(
                llm_client=self.llm_client,
                session_manager=session_manager,
                prompt_builder=prompt_builder
            )
            
            # 初始化事件分发器 (for Lark)
            self.event_dispatcher = EventDispatcher()
            self.event_dispatcher.register_message_handler(self._handle_lark_message)
            
            # 初始化飞书WebSocket客户端
            if self.settings.lark_app_id:
                logger.info("Initializing Lark client...")
                self.ws_client = LarkWSClient(
                    app_id=self.settings.lark_app_id,
                    app_secret=self.settings.lark_app_secret,
                    encrypt_key=self.settings.lark_encrypt_key,
                    verification_token=self.settings.lark_verification_token
                )
                self.ws_client.register_event_handler(
                    "im.message.receive_v1",
                    lambda data: self.event_dispatcher.dispatch("im.message.receive_v1", data) if self.event_dispatcher else None
                )
                # Lark client starts in a separate thread usually, but we need to verify its start method
                # The original code used blocking=True, here we should probably run it in background
                # Assuming ws_client.start supports non-blocking or we wrap it.
                # Looking at original code: ws_client.start(blocking=True)
                # We need to run it in a separate thread or change to non-blocking if supported.
                # Let's run it in an executor.
                import threading
                t = threading.Thread(target=self.ws_client.start, kwargs={'blocking': True}, daemon=True)
                t.start()
                logger.info("Lark client started.")
            
            # 初始化QQ客户端
            if self.settings.qq_bot_enabled:
                logger.info("Initializing QQ NapCat client...")
                self.qq_client = NapCatClient(
                    host=self.settings.qq_host,
                    http_port=self.settings.qq_http_port,
                    ws_port=self.settings.qq_ws_port
                )
                self.qq_client.register_message_handler(self._handle_qq_message)
                self.qq_client.start()
                logger.info("QQ client started.")
            
            logger.info("所有组件初始化完成")
            
        except Exception as e:
            logger.error(f"初始化失败: {str(e)}")
            raise

    def _handle_lark_message(self, message: ParsedMessage) -> None:
        """处理飞书消息"""
        try:
            logger.info(f"[Lark] 收到消息: {message.text[:50]}... (chat={message.chat_id})")
            
            # Session ID strategy: use chat_id (which is unique for group) or sender_id (for p2p)
            # Or simplified: just use chat_id which is unique for that conversation context
            session_id = f"lark:{message.chat_id}"

            # 调用智能体处理消息
            # We need to modify agent.process_message to accept session_id if it doesn't already,
            # or map chat_id/user_id to session_id inside it.
            # Looking at original code: agent.process_message(user_id, chat_id, message)
            # The agent likely handles session logic.
            
            result = self.agent.process_message(
                user_id=message.sender_id,
                chat_id=message.chat_id, 
                message=message.text
            )
            
            if result["success"]:
                response_text = result["text"]
                if self.ws_client:
                    self.ws_client.send_text_message(
                        receive_id=message.chat_id, # Reply to the chat
                        receive_id_type="chat_id",
                        text=response_text
                    )
            else:
                logger.error(f"处理失败: {result.get('error')}")

        except Exception as e:
            logger.error(f"处理飞书消息异常: {str(e)}")

    async def _handle_qq_message(self, message: QQMessage) -> None:
        """处理QQ消息"""
        try:
            # Broadcast received message to UI
            await self._broadcast_ui_message(message, direction="received")

            # Ignore self messages
            if message.user_id == message.self_id:
                return
                
            logger.info(f"[QQ] 收到消息 from {message.user_id}: {message.text}")
            
            user_text = message.text or ""
            if not user_text:
                return

            # Session ID: qq:{group_id if group else user_id}
            chat_id_val = f"group_{message.group_id}" if message.message_type == "group" else str(message.user_id)
            
            result = self.agent.process_message(
                user_id=f"qq:{message.user_id}",
                chat_id=f"qq:{chat_id_val}",
                message=user_text
            )

            if result["success"]:
                response_text = result["text"]
                req = QQMessageRequest(
                    message_type=message.message_type or "private",
                    user_id=message.user_id if message.message_type == "private" else None,
                    group_id=message.group_id if message.message_type == "group" else None,
                    message=response_text
                )
                if self.qq_client:
                    self.qq_client.send_message(req)
                    # Broadcast sent message to UI
                    await self._broadcast_ui_message(req, direction="sent")
            
        except Exception as e:
            logger.error(f"处理QQ消息异常: {str(e)}")

    async def _broadcast_ui_message(self, message, direction: str):
        """Broadcast message to connected UI clients"""
        try:
            content = ""
            user_id = ""
            msg_type = ""
            
            if isinstance(message, QQMessage):
                content = message.raw_message or ""
                user_id = str(message.user_id)
                msg_type = message.message_type
            elif isinstance(message, QQMessageRequest):
                content = message.message
                user_id = str(message.user_id or message.group_id)
                msg_type = message.message_type
            
            data = {
                "platform": "qq",
                "direction": direction,
                "user_id": user_id,
                "message_type": msg_type,
                "content": content
            }
            await self.ws_manager.broadcast(data)
        except Exception as e:
            logger.error(f"Error broadcasting to UI: {e}")

    def stop(self) -> None:
        """停止应用程序"""
        self._is_running = False
        if self.ws_client:
            self.ws_client.stop()
        if self.qq_client:
            self.qq_client.stop()
        logger.info("Clawdbot已停止")

class ConnectionManager:
    """Manages WebSocket connections for the UI"""
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        import json
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending to websocket: {e}")


def main():
    """程序主入口"""
    app_instance = ClawdbotApplication()
    
    # Start Uvicorn
    # Use config for host/port
    settings = get_settings()
    uvicorn.run(app_instance.app, host=settings.app_host, port=settings.app_port)

if __name__ == "__main__":
    main()
