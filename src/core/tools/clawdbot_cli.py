import asyncio
import logging
import aiohttp
from typing import Callable, Optional

logger = logging.getLogger(__name__)

class ClawdbotCliTool:
    """
    Clawdbot 命令行工具封装 (HTTP Wrapper 版)
    
    负责通过 HTTP 请求调用 clawdbot_wrapper 服务，并将结果通过回调传回。
    """
    
    def __init__(self, wrapper_url: str = "http://host.docker.internal:3009"):
        self.wrapper_url = wrapper_url

    async def run_async(self, task_prompt: str, session_id: str, callback: Callable[[str, str], None], callback_session_id: Optional[str] = None) -> None:
        """
        异步运行 clawdbot 命令
        
        Args:
            task_prompt: 以此Prompt运行clawdbot
            session_id: 会话ID，用于识别用户
            callback: 任务完成后的回调函数，签名 func(session_id, result_content)
            callback_session_id:用于回调的会话ID (包含消息类型和chat_id)
        """
        # 启动后台任务，避免阻塞当前协程
        asyncio.create_task(self._execute_http_request(task_prompt, session_id, callback, callback_session_id))
        logger.info(f"已启动后台 Clawdbot 任务: {task_prompt[:50]}... (Session: {session_id})")

    async def _execute_http_request(self, task_prompt: str, session_id: str, callback: Callable[[str, str], None], callback_session_id: Optional[str] = None) -> None:
        """
        执行 HTTP 请求的具体逻辑
        """
        try:
            logger.info(f"开始请求 Clawdbot Wrapper: {self.wrapper_url}/chat")
            
            payload = {
                "message": task_prompt,
                "session_id": session_id,
                "callback_session_id": callback_session_id
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{self.wrapper_url}/chat", json=payload, timeout=300) as response:
                    if response.status == 200:
                        data = await response.json()
                        reply = data.get("reply", "")
                        
                        logger.info(f"Clawdbot 任务请求成功，Wrapper 已接收")
                        
                        # 如果 wrapper 返回了同步回复（非流式/非回调模式），我们直接回调
                        # 但通常 wrapper 会处理回调，这里作为备用
                        if reply and not data.get("is_callback_mode", False):
                             result_msg = f"[Clawdbot 执行结果]\n\n{reply}"
                             if callback:
                                if asyncio.iscoroutinefunction(callback):
                                    await callback(session_id, result_msg)
                                else:
                                    callback(session_id, result_msg)
                    else:
                        error_text = await response.text()
                        logger.error(f"Clawdbot Wrapper 请求失败: {response.status} - {error_text}")
                        err_msg = f"[系统错误] Clawdbot 服务请求失败 ({response.status})"
                        if callback:
                             if asyncio.iscoroutinefunction(callback):
                                await callback(session_id, err_msg)
            
        except asyncio.TimeoutError:
             err_msg = "[系统错误] Clawdbot 服务请求超时"
             logger.error(err_msg)
             if callback:
                 if asyncio.iscoroutinefunction(callback):
                    await callback(session_id, err_msg)
        except Exception as e:
            err_msg = f"[系统错误] 执行 Clawdbot 请求时发生异常: {str(e)}"
            logger.error(err_msg, exc_info=True)
            if callback:
                 if asyncio.iscoroutinefunction(callback):
                    await callback(session_id, err_msg)
