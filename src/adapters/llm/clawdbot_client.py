"""
Clawdbot HTTP 客户端
通过HTTP调用宿主机的 clawdbot 服务
"""

import aiohttp
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ClawdbotClient:
    """
    Clawdbot HTTP 客户端
    """
    
    def __init__(self, host: str = "172.17.0.1", port: int = 3009):
        """
        初始化 Clawdbot 客户端
        
        Args:
            host: clawdbot HTTP 服务的主机地址
            port: clawdbot HTTP 服务的端口
        """
        self.base_url = f"http://{host}:{port}"
        
    async def chat(
        self,
        messages: list,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000
    ) -> str:
        """
        发送聊天请求到 Clawdbot
        
        Args:
            messages: 消息列表
            model: 模型名称（clawdbot会自动选择）
            temperature: 温度参数（暂不使用）
            max_tokens: 最大token数（暂不使用）
            
        Returns:
            回复文本
        """
        try:
            # 获取最后一条用户消息
            user_message = ""
            
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    user_message = msg.get("content", "")
                    break
            
            if not user_message:
                return "抱歉，我没有收到您的消息。"
            
            # 尝试从消息列表中提取 session_id
            # Agent 应该在第一条消息的 metadata 中传递 session_id
            session_id = "qq_default"
            if len(messages) > 0 and isinstance(messages[0], dict):
                # 检查是否有 session_id 在消息中
                if "session_id" in messages[0]:
                    session_id = messages[0]["session_id"]
                # 或者从 content 中提取（如果 Agent 使用特殊格式）
                elif messages[0].get("role") == "system" and isinstance(messages[0].get("content"), str):
                    content = messages[0]["content"]
                    if "[SESSION:" in content:
                        # 提取格式如 [SESSION:qq_254067848_private]
                        import re
                        match = re.search(r'\[SESSION:([^\]]+)\]', content)
                        if match:
                            session_id = match.group(1)
            
            # 构建请求数据
            payload = {
                "message": user_message,
                "session_id": session_id
            }
            
            logger.info(f"调用 Clawdbot HTTP API: {self.base_url}/chat")
            logger.info(f"Session ID: {session_id}")
            logger.debug(f"消息: {user_message[:50]}...")
            
            # 发送 HTTP 请求（增加超时时间以支持工具执行）
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=200)  # 200秒，给带有工具执行的任务充足时间
                ) as response:
                    if response.status == 200:
                        result = await response.json()
                        reply_text = result.get("reply", "")
                        is_callback = result.get("is_callback_mode", False)
                        
                        if is_callback:
                            # 如果是回调模式，中间过程已经发过了
                            # 返回一个简单的结束标志
                            logger.info("Clawdbot 以回调模式完成任务")
                            return "(执行完毕)"
                        
                        if reply_text:
                            logger.info(f"Clawdbot 回复: {reply_text[:100]}...")
                            return reply_text
                        else:
                            logger.warning("未收到有效回复")
                            return "收到消息，但暂时无法生成回复。"
                    else:
                        error_text = await response.text()
                        logger.error(f"HTTP 错误 {response.status}: {error_text}")
                        return f"抱歉，服务暂时不可用。"
                        
        except aiohttp.ClientError as e:
            logger.error(f"HTTP 请求失败: {str(e)}", exc_info=True)
            return "抱歉，无法连接到 AI 服务。"
        except Exception as e:
            logger.error(f"Clawdbot 调用异常: {str(e)}", exc_info=True)
            return f"抱歉，处理消息时遇到错误。"
