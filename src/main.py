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

# New Channel Architecture
from channels.manager import ChannelManager
from channels.base import UnifiedMessage, UnifiedSendRequest
from channels.lark.adapter import LarkChannel
from channels.qq.adapter import QQChannel

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
        
        # New Channel Manager
        self.channel_manager = ChannelManager()
        self.ws_manager = ConnectionManager() # For UI
        
        self._setup_routes()

    def _setup_routes(self):
        @self.app.post("/send_msg")
        async def send_message(request: SendMessageRequest):
            try:
                # Wrap into UnifiedSendRequest
                # Note: UnifiedSendRequest takes chat_id. 
                # For QQ, user passes target_id.
                
                req = UnifiedSendRequest(
                    chat_id=request.target_id,
                    content=request.content,
                    message_type=request.message_type
                )
                
                success = await self.channel_manager.send_message(request.platform, req)
                if success:
                    return {"status": "success", "platform": request.platform}
                else:
                    raise HTTPException(status_code=500, detail="Failed to send message via channel")

            except ValueError as ve:
                raise HTTPException(status_code=400, detail=str(ve))
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
                
                # Session ID parsing strategy needs to align with how we generate it in _handle_unified_message
                # Format: "{platform}:{chat_id}"
                
                parts = session_id.split(":", 1)
                if len(parts) != 2:
                    # Legacy fallback or error
                    # If legacy format: qq_123456_private
                    if session_id.startswith("qq"):
                         platform = "qq"
                         # Legacy parsing logic
                         legacy_parts = session_id.split("_")
                         if "group" in legacy_parts:
                            idx = legacy_parts.index("group")
                            chat_id = legacy_parts[idx + 1] if len(legacy_parts) > idx + 1 else None
                            # We treat group_id as chat_id for QQ group
                         else:
                            chat_id = legacy_parts[1] if len(legacy_parts) > 1 else None
                    else:
                        # Fallback for lark if needed, or error
                        return {"status": "ignored", "reason": "invalid session_id format"}
                else:
                    platform = parts[0]
                    chat_id = parts[1]

                if not chat_id:
                    return {"status": "error", "message": "Could not extract chat_id"}

                req = UnifiedSendRequest(
                    chat_id=chat_id,
                    content=content,
                    message_type="text" # default
                )
                
                # If QQ, we need to handle private/group distinction if the chat_id doesn't encode it.
                # In our new adapter, we just pass chat_id. Adapter logic determines user_id vs group_id.
                # BUT, our QQ adapter expects chat_id to be int string.
                # And for MessageRequest inside adapter: if message_type...
                # Wait, UnifiedSendRequest has message_type. We need to know it.
                # The callback doesn't provide message_type explicitly. 
                # Ideally, session_id should encode it or we assume 'text' and let adapter handle routing?
                # No, 'private' or 'group' is needed for QQ.
                # Our session_id format: platform:chat_id.
                # QQ adapter implementation: 
                #   target_id = int(request.chat_id)
                #   qq_req = MessageRequest(..., message_type=request.message_type, ...)
                # So we MUST provide correct message_type in UnifiedSendRequest.
                
                # Heuristic: 
                # If platform is QQ, check if we can deduce type.
                # Actually, in _handle_unified_message, we set session_id. 
                # If we include type in session_id: "qq:group:123" or "qq:private:456".
                # Let's adjust _handle_unified_message to use "platform:type:id" or similar to be robust.
                # Parsing extended format: platform_type_id
                parts = session_id.split("_")
                if len(parts) >= 3:
                     platform = parts[0]
                     msg_type = parts[1]
                     # Join the rest in case chat_id has underscores
                     chat_id = "_".join(parts[2:])
                elif len(parts) == 2:
                     # Legacy or simple format fallback
                     platform = parts[0]
                     chat_id = parts[1]
                     msg_type = "private" # default fallback
                else:
                     return {"status": "error", "message": "Invalid session format"}
                
                req.message_type = msg_type
                req.chat_id = chat_id

                success = await self.channel_manager.send_message(platform, req)
                
                if success and platform == "qq":
                    # Broadcast to UI
                    await self._broadcast_sent_message(platform, chat_id, content, msg_type)

                return {"status": "success"}
            except Exception as e:
                logger.error(f"Clawdbot callback error: {e}")
                return {"status": "error", "message": str(e)}

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

        # Legacy QQ Status APIs - Route to QQ Channel logic if possible or keep simplified
        @self.app.get("/api/qq/status")
        async def get_qq_status():
            # Check if QQ channel exists
            channel = self.channel_manager.get_channel("qq")
            if not channel:
                 return {"status": "not_configured"}
            
            # Simple check if running
            # Real status check requires calling client method.
            # We can cast to QQChannel if we know the type, or add is_connected to BaseChannel?
            # For now, let's replicate the logic but accessed via the channel instance
            
            # Access underlying client for check
            # This violates abstraction slightly but practical for API specific endpoint
            if hasattr(channel, 'client'):
                # ... reuse the aiohttp logic ...
                import aiohttp
                try:
                    url = f"http://{channel.client.host}:{channel.client.http_port}/get_login_info"
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=2) as resp:
                             if resp.status == 200:
                                  data = await resp.json()
                                  if data.get("retcode") == 0:
                                      return {"status": "logged_in", "data": data}
                except Exception:
                    pass
            
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
                container_name = self.settings.qq_host
                container = client.containers.get(container_name)
                container.restart()
                
                qr_path = "logs/qr_code.txt"
                if os.path.exists(qr_path):
                    os.remove(qr_path)
                    
                return {"status": "success", "message": "Container restarted."}
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

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
            
            prompt_builder = create_prompt_builder()
            
            self.agent = create_agent(
                llm_client=self.llm_client,
                session_manager=session_manager,
                prompt_builder=prompt_builder
            )
            
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
        """
        try:
            # 1. Broadcast to UI (if it's a message we want to show)
            if message.platform == "qq":
                # Reconstruct legacy format for UI compatibility if needed
                await self._broadcast_ui_message_from_unified(message, direction="received")

            # 2. Ignore self messages logic (handled by channel typically, but good to have safety)
            # UnifiedMessage doesn't explicitly store self_id yet, but we can assume we generally want to process incoming.
            
            user_text = message.content or ""
            
            # 3. 处理图片（全局图片识别拦截器）
            if message.images and len(message.images) > 0:
                logger.info(f"[OCR] 开始处理 {len(message.images)} 张图片...")
                ocr_results = []
                
                try:
                    from config.settings import get_settings
                    from adapters.gemini.gemini_ocr import GeminiOCR
                    import aiohttp
                    
                    settings = get_settings()
                    ocr = GeminiOCR(api_key=settings.gemini_api_key)
                    logger.info(f"[OCR] 准备处理 {len(message.images)} 张图片: {message.images}")
                    for idx, img_source in enumerate(message.images):
                        try:
                            logger.info(f"[OCR] 处理第 {idx+1} 张图片, 来源: {img_source}")
                            temp_path = f"/tmp/unified_img_{message.platform}_{idx}_{message.timestamp}.jpg"
                            
                            # 处理不同来源的图片
                            if img_source.startswith("http"):
                                # QQ 渠道的 URL 模式: 下载
                                logger.info(f"[OCR] 正在从 URL 下载图片: {img_source[:50]}...")
                                headers = {
                                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                                    "Referer": "https://q.qq.com/"
                                }
                                async with aiohttp.ClientSession() as session:
                                    async with session.get(img_source, headers=headers, timeout=30) as resp:
                                        if resp.status == 200:
                                            with open(temp_path, "wb") as f:
                                                f.write(await resp.read())
                                        else:
                                            logger.error(f"[OCR] 下载失败: HTTP {resp.status}")
                                            ocr_results.append(f"--- 图片 {idx+1} 获取失败 (HTTP {resp.status}) ---")
                                            continue
                            else:
                                # 飞书渠道的本地路径模式
                                temp_path = img_source
                            
                            # 执行 OCR 识别
                            if os.path.exists(temp_path):
                                logger.info(f"[OCR] 正在执行 Gemini 识别: {temp_path}")
                                loop = asyncio.get_running_loop()
                                result = await loop.run_in_executor(
                                    None, 
                                    lambda: ocr.recognize_image(temp_path, "请详细描述这张图片的内容，如果包含文字请提取出来并保持原有排版。")
                                )
                                
                                if result and result.get("success"):
                                    ocr_text = result.get("response", "")
                                    ocr_results.append(f"--- 图片 {idx+1} 识别结果 ---\n{ocr_text}")
                                else:
                                    ocr_results.append(f"--- 图片 {idx+1} 识别失败 ---")
                        except Exception as img_err:
                            logger.error(f"[OCR] 处理单张图片失败: {img_err}")
                    
                    # 4. 注入 OCR 结果到用户文本中
                    if ocr_results:
                        combined_ocr = "\n\n".join(ocr_results)
                        user_text = f"{user_text}\n\n[图片分析报告]:\n{combined_ocr}"
                        logger.info(f"[OCR] 成功将 OCR 结果注入消息，识别内容长度: {len(combined_ocr)}")
                    elif not user_text:
                        # OCR 失败且无其他文本内容的兜底
                        user_text = f"{user_text}\n[系统通知: 收到图片但 OCR 解析失败，请联系用户确认图片内容]"
                
                except Exception as ocr_err:
                    logger.error(f"[OCR] 全局 OCR 处理链崩溃: {ocr_err}")
                    if not user_text:
                        user_text = "[系统错误: OCR 模块异常]"
            
            if not user_text and not message.images:
                return

            logger.info(f"[{message.platform}] Received: {user_text[:100]}... from {message.user_id} in {message.chat_id}")

            # 5. Construct Session ID
            session_id = f"{message.platform}_{message.message_type}_{message.chat_id}"
            
            # 6. Agent Processing
            result = await self.agent.process_message(
                user_id=f"{message.platform}:{message.user_id}",
                chat_id=session_id,
                message=user_text
            )

            if result["success"]:
                response_text = result["text"]
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
        """Broadcast received unified message to UI"""
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
        """Monitor NapCat logs for QR code"""
        logger.info("Starting NapCat log monitor...")
        try:
            import docker
            client = docker.from_env()
            container_name = "napcatqq" # Hardcode or use config? Config uses qq_host usually mapped to container name
            # In settings.py, qq_host default "napcat". docker-compose says "napcatqq".
            # Let's try to use the name from settings if possible, or fallback/check if settings.qq_host matches.
            # In docker-compose, container_name is "napcatqq".
            # In settings.py: qq_host: str = "napcat" (default) or "127.0.0.1". 
            # If running in docker network, host is "napcat" (service name) or "napcatqq" (container name).
            # The docker client needs CONTAINER NAME or ID. 
            container_name = "napcatqq" 

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
                                
                                qr_path = "logs/qr_code.txt"
                                current_content = ""
                                if os.path.exists(qr_path):
                                    with open(qr_path, "r", encoding="utf-8") as f:
                                        current_content = f.read().strip()
                                
                                if current_content != url_line:
                                    os.makedirs("logs", exist_ok=True)
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
    settings = get_settings()
    uvicorn.run(app_instance.app, host=settings.app_host, port=settings.app_port)

if __name__ == "__main__":
    main()
