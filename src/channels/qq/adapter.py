import re
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
            
            # Try to parse chat_id which might be prefixed or suffixed
            # Examples: "qq:user:123456:20260214", "private_123456", "123456"
            raw_id = str(request.chat_id)
            
            # 1. 优先处理冒号分隔格式
            if ":" in raw_id:
                parts = raw_id.split(":")
                # 如果是 "platform:user:id:date" 或 "platform:type:id"
                # 我们寻找中间可能是数字的部分，或者取倒数第二位(如果有日期后缀)
                # 最稳妥的方法是取所有部分中第一个由纯数字组成的，或者特定的偏移量
                for p in parts:
                    if p.isdigit():
                        raw_id = p
                        break
            # 2. 处理下划线分隔格式
            elif "_" in raw_id:
                raw_id = raw_id.split("_")[-1]
            
            target_id = int(raw_id)
            
            # Prepare message request
            # Filter asterisks as requested by user
            cleaned_content = request.content.replace("*", "")

            # 将连续多个换行符压缩为单个换行符，保持紧凑排版
            cleaned_content = re.sub(r'\n{2,}', '\n', cleaned_content)
            
            msg_type = request.message_type
            if msg_type == "user":
                msg_type = "private"
                
            qq_req = MessageRequest(
                message_type=msg_type,
                user_id=target_id if msg_type == "private" else None,
                group_id=target_id if msg_type == "group" else None,
                message=cleaned_content
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
        
        将其转换为统一消息格式并分发给全局消息处理器。
        同时负责解析 CQ 码（如图片）和发送即时接收确认。

        :param message: QQMessage 实例，包含发送者、内容、类型等详细数据
        :return: None
        :raises Exception: 处理或转换消息过程中的异常
        """
        try:
            # Filter valid messages
            if not message.text:
                return

            # 解析CQ码
            from utils.cq_parser import parse_cq_code
            parsed = parse_cq_code(message.text)
            images = parsed.get('images', [])

            # 发送响应确认
            try:
                # 统一发送提示消息
                ack_msg = "收到你的问题啦，我正在思考哦"
                msg_type = message.message_type or "private"
                target_id = message.group_id if msg_type == "group" else message.user_id
                
                ack_req = MessageRequest(
                    message_type=msg_type,
                    user_id=target_id if msg_type == "private" else None,
                    group_id=target_id if msg_type == "group" else None,
                    message=ack_msg
                )
                self.client.send_message(ack_req)
                logger.info(f"Sent acknowledgment for message from {message.user_id}")
            except Exception as e:
                logger.error(f"Failed to send acknowledgment: {e}")
            
            # Convert to UnifiedMessage
            
            # Convert to UnifiedMessage
            msg_type = message.message_type or "private"
            
            # For groups, chat_id is group_id. For private, it's user_id.
            chat_id = str(message.group_id) if msg_type == "group" else str(message.user_id)
            user_id = str(message.user_id)
            
            # 提取发信人名称（群名片 > 昵称 > QQ号）
            sender_name = str(message.user_id)
            if message.sender:
                sender_name = message.sender.card or message.sender.nickname or sender_name
            
            # 构建消息内容，并增加发信人身份标识
            content = f"[{sender_name}]: {parsed['text']}"
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
