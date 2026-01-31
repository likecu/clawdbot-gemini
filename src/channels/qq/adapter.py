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
        
        # Register the callback
        self.client.register_message_handler(self._handle_qq_message)

    async def start(self):
        """Start the QQ client (websocket)"""
        logger.info("Starting QQ Channel...")
        self.client.start()
        logger.info("QQ Channel started.")

    async def stop(self):
        logger.info("Stopping QQ Channel...")
        self.client.stop()
        logger.info("QQ Channel stopped.")

    async def send_message(self, request: UnifiedSendRequest) -> bool:
        """Send message to QQ"""
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
        """Callback for NapCat messages"""
        try:
            # Filter valid messages
            if not message.text:
                return
                
            # Convert to UnifiedMessage
            msg_type = message.message_type or "private"
            
            # For groups, chat_id is group_id. For private, it's user_id.
            chat_id = str(message.group_id) if msg_type == "group" else str(message.user_id)
            user_id = str(message.user_id)
            
            unified_msg = UnifiedMessage(
                platform="qq",
                user_id=user_id,
                chat_id=chat_id,
                message_type=msg_type,
                content=message.text,
                raw_data=message.dict(),
                timestamp=float(message.time) if message.time else 0.0
            )
            
            await self.on_message_received(unified_msg)

        except Exception as e:
            logger.error(f"Error handling QQ message: {e}")
