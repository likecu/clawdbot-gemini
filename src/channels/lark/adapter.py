from typing import Dict, Any, Optional
import logging
import asyncio
import json
import threading

from ..base import BaseChannel, UnifiedMessage, UnifiedSendRequest
from adapters.lark.lark_client import LarkWSClient

logger = logging.getLogger("LarkChannel")

class LarkChannel(BaseChannel):
    """
    Channel implementation for Lark (Feishu) using the existing LarkWSClient.
    """
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        
        self.app_id = config.get("app_id")
        self.app_secret = config.get("app_secret")
        self.encrypt_key = config.get("encrypt_key")
        self.verification_token = config.get("verification_token")
        
        if not all([self.app_id, self.app_secret, self.encrypt_key, self.verification_token]):
            logger.warning("Lark configuration incomplete. Some features might not work.")

        self.client = LarkWSClient(
            app_id=self.app_id,
            app_secret=self.app_secret,
            encrypt_key=self.encrypt_key,
            verification_token=self.verification_token
        )
        self._is_running = False

    async def start(self):
        """
        Start the Lark WebSocket client.
        Note: The underlying Lark client uses a blocking start() call by default, 
        so we need to be careful not to block the event loop.
        """
        # Register event handler for messages
        self.client.register_event_handler(
            "im.message.receive_v1", 
            self._handle_lark_message_event
        )

        self._is_running = True
        logger.info("Starting Lark WebSocket client in background thread...")
        
        # Run the blocking client in a separate thread
        self.thread = threading.Thread(target=self.client.start, kwargs={'blocking': True}, daemon=True)
        self.thread.start()
        logger.info("Lark WebSocket client thread started.")

    async def stop(self):
        self._is_running = False
        if self.client:
            self.client.stop()
        logger.info("Lark channel stopped.")

    async def send_message(self, request: UnifiedSendRequest) -> bool:
        """
        Send a message through Lark API.
        """
        try:
            if not self.client.is_connected():
                logger.warning("Lark client not connected, attempting to send anyway (might fail)")

            # Convert UnifiedSendRequest specialized for Lark
            # receive_id_type defaults to "open_id" usually, but for group chats we might need "chat_id"
            # Our UnifiedMessage stores chat_id as the primary identifier.
            # We need to determine if it's a chat_id or open_id. 
            # Simplified heuristic: assume chat_id if request.chat_id starts with 'oc_' (common for groups) 
            # or just use receive_id_type="chat_id" which works for both P2P chats and Group chats in some contexts?
            # Actually create_message allows receive_id_type="chat_id"
            
            # If the original message was from a group, we should reply to the group (chat_id).
            
            # Simple approach: Always use "chat_id" for receive_id_type if possible, 
            # but usually for private messages we use open_id.
            
            # Let's rely on the metadata if available or just try.
            # The client.send_text_message implementation uses receive_id_type="open_id" by default inside (if not specified).
            # But wait, looking at my refactored send_text_message in lark_client.py:
            # It calls send_message(receive_id, content) which calls CreateMessageRequest... receive_id_type("open_id") HARDCODED in line 233.
            # This is a limitation of the existing client I need to work around or fix.
            
            # I will modify the call to `send_message` on the client to support `chat_id` if I can, 
            # or I'll override the method here if the client exposes enough.
            
            # Actually, let's use the `send_text_message` method if it's text.
            # But the underlying `send_message` in LarkWSClient hardcodes "open_id". 
            # I should probably fix LarkWSClient to accept receive_id_type or handle it here if I access the protected _client.
            
            # For now, let's assume `send_text_message` works or I will patch `LarkWSClient` in a separate step if needed. 
            # Wait, `LarkWSClient.send_text_message` in current codebase calls `send_message` which hardcodes `open_id`.
            # This is a BUG in the existing code if we want to support groups (chat_id).
            # I will fix `src/channels/lark/adapter.py` by implementing a proper send using the raw _client if needed, 
            # effectively bypassing the helper method if it's broken.
            
            # Let's inspect `LarkWSClient` again... 
            # Yes, line 233: .receive_id_type("open_id")
            
            # Strategy: Implement proper sending logic here using the `lark-oapi` library directly if possible,
            # since `self.client._client` is the `ws.Client` which might expose the API client?
            # `ws.Client` usually has an `im` property for API access? No, ws.Client is for WebSocket.
            # The API client is usually separate. 
            # BUT `LarkWSClient` initializes `ws.Client`. `ws.Client` in `lark_oapi` 2.x+ combines both?
            # Actually `lark_oapi.Client` is for API, `lark_oapi.ws.Client` is for WS.
            # The existing code sends messages via `self._client.im.v1.message.create`. 
            # So `self.client._client` IS able to send messages.

            from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
            import uuid

            if request.message_type == "text":
                content_dict = {"text": request.content}
                msg_type = "text"
            else:
                # Fallback / TODO: support other types
                content_dict = {"text": f"[Unsupported type: {request.message_type}] {request.content}"}
                msg_type = "text"

            # Determine receive_id_type
            # If it looks like a UUID or specific format?
            # For now, let's try "chat_id" as default for our unified system as 'chat_id' usually implies the conversation container.
            receive_id_type = "chat_id" 
            
            # Construction of request
            req = (CreateMessageRequest.builder()
                   .receive_id_type(receive_id_type)
                   .request_body(CreateMessageRequestBody.builder()
                       .receive_id(request.chat_id)
                       .msg_type(msg_type)
                       .content(json.dumps(content_dict))
                       .uuid(str(uuid.uuid4()))
                       .build())
                   .build())

            resp = self.client._client.im.v1.message.create(req)
            
            if resp.code == 0:
                return True
            else:
                logger.error(f"Lark API Error: {resp.code} - {resp.msg}")
                return False

        except Exception as e:
            logger.error(f"Error sending Lark message: {e}")
            return False

    def _handle_lark_message_event(self, event_data: Dict):
        """
        Callback for Lark message events.
        Converts to UnifiedMessage and dispatches.
        """
        try:
            # We need to extract the event payload
            # event_data structure depends on the raw event.
            # Usually: {"header": {...}, "event": {"message": {...}, "sender": {...}}}
            
            event = event_data.get("event", {})
            message = event.get("message", {})
            sender = event.get("sender", {})
            
            msg_content = message.get("content", "{}")
            try:
                content_json = json.loads(msg_content)
                text = content_json.get("text", "")
            except:
                text = str(msg_content)

            chat_id = message.get("chat_id")
            sender_id = sender.get("sender_id", {}).get("open_id") # or union_id
            
            # Determine message type (private vs group)
            # chat_type: "p2p" or "group"
            chat_type = message.get("chat_type", "p2p")
            unified_type = "group" if chat_type == "group" else "private"

            unified_msg = UnifiedMessage(
                platform="lark",
                user_id=sender_id,
                chat_id=chat_id,
                message_type=unified_type,
                content=text,
                raw_data=event_data,
                timestamp=float(message.get("create_time", 0)) / 1000.0 
            )

            # Fire and forget (it's async)
            asyncio.run_coroutine_threadsafe(
                self.on_message_received(unified_msg),
                asyncio.get_event_loop()
            )

        except Exception as e:
            logger.error(f"Error handling Lark event: {e}")
