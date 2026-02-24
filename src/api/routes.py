
from fastapi import APIRouter, HTTPException, WebSocket, Depends
from pydantic import BaseModel
import logging
import os
import asyncio
from typing import Optional, Dict

from core.agent import Agent
from channels.manager import ChannelManager
from channels.base import UnifiedSendRequest
from config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Models ---
class SendMessageRequest(BaseModel):
    """
    发送消息请求模型
    """
    platform: str = "qq"
    target_id: str
    message_type: str = "private"
    content: str

class ClawdbotCallbackRequest(BaseModel):
    """
    Clawdbot 回调请求模型
    """
    session_id: str
    content: str

# --- Dependencies ---
from starlette.requests import Request

def get_channel_manager(request: Request) -> ChannelManager:
    """
    获取 ChannelManager 依赖
    """
    return request.app.state.channel_manager

def get_agent(request: Request) -> Agent:
    """
    获取 Agent 依赖
    """
    return request.app.state.agent

# --- Routes ---

@router.post("/send_msg")
async def send_message(
    request: SendMessageRequest,
    channel_manager: ChannelManager = Depends(get_channel_manager)
):
    """
    统一发送消息接口
    
    Args:
        request: 发送消息请求体
        channel_manager: 渠道管理器依赖
        
    Returns:
        Dict: 发送结果
    """
    try:
        req = UnifiedSendRequest(
            chat_id=request.target_id,
            content=request.content,
            message_type=request.message_type
        )
        
        success = await channel_manager.send_message(request.platform, req)
        if success:
            return {"status": "success", "platform": request.platform}
        else:
            raise HTTPException(status_code=500, detail="Failed to send message via channel")

    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/clawdbot/callback")
async def clawdbot_callback(
    data: ClawdbotCallbackRequest,
    channel_manager: ChannelManager = Depends(get_channel_manager)
):
    """
    Clawdbot 异步任务回调接口
    
    Args:
        data: 回调数据
        channel_manager: 渠道管理器依赖
        
    Returns:
        Dict: 处理状态
    """
    try:
        session_id = data.session_id
        content = data.content
        
        if not session_id or not content:
            return {"status": "ignored", "reason": "missing content or session_id"}
        
        logger.info(f"收到 Clawdbot 实时推送 [Session: {session_id}]: {content[:50]}...")
        
        # 解析 session_id 以获取平台和目标ID
        if ":" in session_id:
            parts = session_id.split(":")
            if len(parts) >= 3:
                platform = parts[0]
                msg_type = parts[1]
                chat_id = ":".join(parts[2:])
            elif len(parts) == 2:
                platform = parts[0]
                chat_id = parts[1]
                msg_type = "private"
            else:
                return {"status": "error", "message": "Invalid colon session format"}
        elif "_" in session_id:
            parts = session_id.split("_")
            if len(parts) >= 3:
                platform = parts[0]
                msg_type = parts[1]
                chat_id = "_".join(parts[2:])
            elif len(parts) == 2:
                platform = parts[0]
                chat_id = parts[1]
                msg_type = "private"
            else:
                return {"status": "error", "message": "Invalid underscore session format"}
        else:
            return {"status": "error", "message": "Unknown session format"}
        
        req = UnifiedSendRequest(
            chat_id=chat_id,
            content=content,
            message_type=msg_type
        )

        success = await channel_manager.send_message(platform, req)
        
        return {"status": "success"}
    except Exception as e:
        logger.error(f"Clawdbot callback error: {e}")
        return {"status": "error", "message": str(e)}

@router.get("/api/qq/status")
async def get_qq_status(
    channel_manager: ChannelManager = Depends(get_channel_manager)
):
    """
    获取 QQ 登录状态
    
    Args:
        channel_manager: 渠道管理器依赖
        
    Returns:
        Dict: QQ 状态信息
    """
    channel = channel_manager.get_channel("qq")
    if not channel:
            return {"status": "not_configured"}
    
    if hasattr(channel, 'client'):
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
    
    settings = get_settings()
    qr_path = settings.qr_code_path
    if os.path.exists(qr_path):
        return {"status": "qr_code_available"}
    return {"status": "not_logged_in"}

@router.get("/api/qq/qr")
async def get_qq_qr():
    """
    获取 QQ 登录二维码 URL
    
    Returns:
        Dict: 二维码 URL
    """
    settings = get_settings()
    qr_path = settings.qr_code_path
    if os.path.exists(qr_path):
        with open(qr_path, "r") as f:
            content = f.read().strip()
        if "二维码解码URL:" in content:
            url = content.split("二维码解码URL:", 1)[1].strip()
            return {"url": url}
    raise HTTPException(status_code=404, detail="QR Code not found")

@router.post("/api/qq/refresh_qr")
async def refresh_qq_qr():
    """
    刷新 QQ 二维码（重启 NapCat 容器）
    
    Returns:
        Dict: 操作结果
    """
    try:
        import docker
        client = docker.from_env()
        settings = get_settings()
        container_name = settings.napcat_container_name
        container = client.containers.get(container_name)
        container.restart()
        
        qr_path = settings.qr_code_path
        if os.path.exists(qr_path):
            os.remove(qr_path)
            
        return {"status": "success", "message": "Container restarted."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
