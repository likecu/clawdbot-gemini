from typing import Dict, Any, Optional, Callable
import asyncio
import logging
from .base import BaseChannel, UnifiedMessage, UnifiedSendRequest

logger = logging.getLogger("ChannelManager")

class ChannelManager:
    """
    Manages the lifecycle of all registered communication channels.
    """
    
    def __init__(self):
        self.channels: Dict[str, BaseChannel] = {}
        self.global_handler: Optional[Callable[[UnifiedMessage], None]] = None

    def register_channel(self, name: str, channel: BaseChannel):
        """
        Register a new channel instance.
        """
        self.channels[name] = channel
        logger.info(f"Registered channel: {name}")

        # If a global handler is already set, immediately register it
        if self.global_handler:
            channel.register_handler(self.global_handler)

    def set_global_handler(self, handler: Callable[[UnifiedMessage], None]):
        """
        Set the central function that will process unified messages from all channels.
        """
        self.global_handler = handler
        for channel in self.channels.values():
            channel.register_handler(handler)
        logger.info(f"Global message handler set for {len(self.channels)} channels.")

    async def start_all(self):
        """
        Start all registered channels concurrently.
        """
        tasks = []
        for name, channel in self.channels.items():
            tasks.append(self._start_channel(name, channel))
        
        await asyncio.gather(*tasks)

    async def _start_channel(self, name: str, channel: BaseChannel):
        try:
            logger.info(f"Starting channel '{name}'...")
            await channel.start()
            logger.info(f"Channel '{name}' started successfully.")
        except Exception as e:
            logger.error(f"Failed to start channel '{name}': {e}")

    async def stop_all(self):
        """
        Stop all running channels.
        """
        for name, channel in self.channels.items():
            try:
                await channel.stop()
                logger.info(f"Stopped channel '{name}'")
            except Exception as e:
                logger.error(f"Error stopping channel '{name}': {e}")

    async def send_message(self, platform: str, request: UnifiedSendRequest):
        """
        Route a message to the specified platform channel.
        """
        channel = self.channels.get(platform)
        if not channel:
            raise ValueError(f"Channel not found for platform: {platform}")
        
        return await channel.send_message(request)

    def get_channel(self, name: str) -> Optional[BaseChannel]:
        return self.channels.get(name)
