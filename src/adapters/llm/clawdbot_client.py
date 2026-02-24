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
            # 从 messages 中提取系统提示词和最后一条用户消息
            system_prompts = []
            user_message = ""
            
            for msg in reversed(messages):
                if msg.get("role") == "user" and not user_message:
                    user_message = msg.get("content", "")
                elif msg.get("role") == "system":
                    system_prompts.append(msg.get("content", ""))
            
            if not user_message:
                return "抱歉，我没有收到您的消息。"
                
            system_text = "\n\n".join(reversed(system_prompts))
            
            combined_message = user_message
            if system_text:
                # 为了防止指令丢失，将系统上下文强行注入到对话末尾
                combined_message = f"【系统级强制上下文】\n{system_text}\n\n====================\n\n【用户当前输入】\n{user_message}"
            # session_id: 用于 OpenClaw 的 sessionKey（按用户维度隔离）
            # callback_session_id: 用于消息回调路由（包含消息类型和目标 chat_id）
            session_id = "qq:user:unknown"
            callback_session_id = session_id
            
            if len(messages) > 0 and isinstance(messages[0], dict):
                if "session_id" in messages[0]:
                    session_id = messages[0]["session_id"]
                if "callback_session_id" in messages[0]:
                    callback_session_id = messages[0]["callback_session_id"]
                else:
                    callback_session_id = session_id
            
            # 构建请求数据
            payload = {
                "message": combined_message,
                "session_id": session_id,
                "callback_session_id": callback_session_id
            }
            
            logger.info(f"调用 Clawdbot HTTP API: {self.base_url}/chat")
            logger.info(f"Request Payload SessionID: {session_id}, CallbackID: {callback_session_id}")
            logger.debug(f"消息: {combined_message[:50]}...")
            
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
                        
                        logger.info(f"Clawdbot 响应: is_callback={is_callback}, reply_length={len(reply_text)}")
                        
                        if is_callback:
                            # 如果是回调模式，且最终回复是默认占位符，说明所有内容都已通过回调发出了
                            if reply_text == "任务已完成。" or not reply_text:
                                logger.info("所有响应已通过回调发送，忽略此占位符回复")
                                return ""  # 返回空字符串，防止重复发送
                            
                            # 如果是回调模式，假设内容已通过实时推送发送，此处不再返回文本
                            logger.info(f"回调模式: 忽略HTTP响应文本 (长度: {len(reply_text)})，防止重复发送")
                            return ""  # 返回空字符串，防止重复发送
                        
                        if reply_text:
                            # 过滤掉默认的占位符回复
                            if reply_text.strip() == "任务已完成。":
                                logger.info("屏蔽默认占位符回复: 任务已完成。")
                                return "" # 虽然一般非callback不会这样，但也屏蔽吧
                            return reply_text
                        else:
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
