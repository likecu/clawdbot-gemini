from abc import ABC, abstractmethod
from typing import Callable, Any, Dict, Optional, List
from pydantic import BaseModel
import time

class UnifiedMessage(BaseModel):
    """
    Unified representation of a message from any platform.
    """
    platform: str          # e.g., "qq", "lark", "telegram"
    user_id: str           # Unique identifier of the sender on the platform
    chat_id: str           # Unique identifier of the conversation/group
    message_type: str      # "private" or "group"
    content: str           # Text content of the message
    images: List[str] = [] # List of image URLs (支持多模态消息)
    raw_data: Dict[str, Any] = {} # Original platform message for advanced use
    timestamp: float = 0.0

    def __init__(self, **data):
        super().__init__(**data)
        if not self.timestamp:
            self.timestamp = time.time()


class UnifiedSendRequest(BaseModel):
    """
    Unified request to send a message to any platform.
    """
    chat_id: str
    content: str
    message_type: str = "text"   # text, image, file... (default: text)
    reply_to_id: Optional[str] = None
    platform_specific: Optional[Dict[str, Any]] = None # Any extra params for specific platforms


class BaseChannel(ABC):
    """
    Abstract base class for all communication channels.
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.message_handler: Optional[Callable[[UnifiedMessage], None]] = None

    @abstractmethod
    async def start(self):
        """Start the channel service (e.g., connect WebSocket, start polling)."""
        pass

    @abstractmethod
    async def stop(self):
        """Stop the channel service."""
        pass

    @abstractmethod
    async def send_message(self, request: UnifiedSendRequest) -> bool:
        """Send a compiled UnifiedSendRequest to this channel."""
        pass

    def register_handler(self, handler: Callable[[UnifiedMessage], None]):
        """Register the central message processing handler."""
        self.message_handler = handler

    async def on_message_received(self, message: UnifiedMessage):
        """
        Called by subclasses when a message is received from the platform.
        Dispatches to the registered handler.
        """
        if self.message_handler:
            # We assume the handler is async
            await self.message_handler(message)
