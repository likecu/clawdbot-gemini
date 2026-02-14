from typing import Dict, Any, Optional
import logging
import asyncio
from typing import Callable, Optional

from ..base import BaseChannel, UnifiedMessage, UnifiedSendRequest

# We can import NapCatClient but might need modification
from adapters.qq.client import NapCatClient
from adapters.qq.models import QQMessage, MessageRequest

logger = logging.getLogger("QQChannel")

class QQChannel(BaseChannel):
    """
    Channel implementation for QQ using NapCatClient
    """
    def __init__(self, config: Dict[str, Any]):
        """
        初始化 QQ 渠道适配器
        :param config: 包含 host, http_port, ws_port, token 等配置的字典
        """
        super().__init__(config)
        self.host = config.get("host")
        self.http_port = config.get("http_port")
        self.ws_port = config.get("ws_port")
        self.token = config.get("token")
        
        self.client = NapCatClient(
            host=self.host,
            http_port=self.http_port,
            ws_port=self.ws_port,
            access_token=self.token
        )
        
        # 注册消息处理器回调
        self.client.register_message_handler(self._handle_qq_message)

    async def start(self):
        """启动 QQ 客户端（建立 WebSocket 连接）"""
        logger.info("正在启动 QQ 渠道适配器...")
        self.client.start()
        logger.info("QQ 渠道适配器启动成功。")

    async def stop(self):
        """停止 QQ 客户端并释放资源"""
        logger.info("正在停止 QQ 渠道适配器...")
        self.client.stop()
        logger.info("QQ 渠道适配器已停止。")

    async def send_message(self, request: UnifiedSendRequest) -> bool:
        """
        发送消息到 QQ 平台
        :param request: 包含目标 ID、内容和消息类型的统一发送请求
        :return: 发送是否成功
        """
        try:
            # Determine if it's user or group
            # In UnifiedMessage, chat_id is the primary target.
            # For QQ:
            # "private": user_id=123
            # "group": group_id=456
            
            target_id = int(request.chat_id)
            
            qq_req = MessageRequest(
                message_type=request.message_type,
                user_id=target_id if request.message_type == "private" else None,
                group_id=target_id if request.message_type == "group" else None,
                message=request.content
            )
            
            resp = self.client.send_message(qq_req)
            # NapCat returns {"retcode": 0...} if success?
            # self.client.send_message returns response.json()
            
            if resp.get("retcode") == 0:
                return True
            else:
                logger.error(f"QQ API Error: {resp}")
                return False

        except ValueError:
            logger.error(f"Invalid QQ ID (must be integer): {request.chat_id}")
            return False
        except Exception as e:
            logger.error(f"Error sending QQ message: {e}")
            return False

    async def _handle_qq_message(self, message: QQMessage):
        """
        处理来自 NapCat 的原始 QQ 消息回调
        :param message: QQ 消息对象，包含发送者、内容、类型等
        """
        try:
            # Filter valid messages
            if not message.text:
                return

            # 发送响应确认（仅针对较长或复杂的问题）
            try:
                # 如果消息很简单（如：你好，在吗），直接透传给 LLM 即可，不需要“思考中”提示
                message_complexity = len(message.text) + (len(images) * 20)
                if message_complexity > 30:
                    ack_msg = "收到你的问题啦，我正在思考哦..."
                    msg_type = message.message_type or "private"
                    target_id = message.group_id if msg_type == "group" else message.user_id
                    
                    ack_req = MessageRequest(
                        message_type=msg_type,
                        user_id=target_id if msg_type == "private" else None,
                        group_id=target_id if msg_type == "group" else None,
                        message=ack_msg
                    )
                    self.client.send_message(ack_req)
                    logger.debug(f"Sent thinking acknowledgement for message length {len(message.text)}")
            except Exception as e:
                logger.error(f"Failed to send acknowledgement: {e}")
            
            # 解析CQ码
            from utils.cq_parser import parse_cq_code
            parsed = parse_cq_code(message.text)
            
            # Convert to UnifiedMessage
            msg_type = message.message_type or "private"
            
            # For groups, chat_id is group_id. For private, it's user_id.
            chat_id = str(message.group_id) if msg_type == "group" else str(message.user_id)
            user_id = str(message.user_id)
            
            # 构建消息内容，如果有图片URL，添加到content中
            content = parsed['text']
            images = parsed.get('images', [])
            
            unified_msg = UnifiedMessage(
                platform="qq",
                user_id=user_id,
                chat_id=chat_id,
                message_type=msg_type,
                content=content,
                images=images,  # 将图片URL列表传递
                raw_data=message.dict(),
                timestamp=float(message.time) if message.time else 0.0
            )
            
            await self.on_message_received(unified_msg)

        except Exception as e:
            logger.error(f"Error handling QQ message: {e}")
