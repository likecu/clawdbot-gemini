import asyncio
import json
import logging
import websockets
import requests
from typing import Callable, Optional, Dict, Any
from .models import MessageRequest, QQMessage

class NapCatClient:
    def __init__(self, host: str, http_port: int, ws_port: int, access_token: Optional[str] = None):
        self.host = host
        self.http_port = http_port
        self.ws_port = ws_port
        self.access_token = access_token
        self.base_url = f"http://{host}:{http_port}"
        self.ws_url = f"ws://{host}:{ws_port}"
        
        self.logger = logging.getLogger("NapCatClient")
        self.message_handler: Optional[Callable[[QQMessage], None]] = None
        self._is_running = False
        self._ws_task = None

    def register_message_handler(self, handler: Callable[[QQMessage], None]):
        self.message_handler = handler

    def send_message(self, request: MessageRequest) -> Dict[str, Any]:
        url = f"{self.base_url}/send_msg"
        headers = {"Content-Type": "application/json"}
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
            
        data = request.dict(exclude_none=True)
        self.logger.info(f"Sending message to QQ: {data}")
        
        try:
            response = requests.post(url, json=data, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to send message: {e}")
            raise

    async def _connect_ws(self):
        while self._is_running:
            try:
                headers = {}
                if self.access_token:
                    headers["Authorization"] = f"Bearer {self.access_token}"

                if headers:
                    async with websockets.connect(self.ws_url, extra_headers=headers) as websocket:
                        self.logger.info(f"Connected to NapCat WebSocket at {self.ws_url}")
                        await self._handle_ws_messages(websocket)
                else:
                    async with websockets.connect(self.ws_url) as websocket:
                        self.logger.info(f"Connected to NapCat WebSocket at {self.ws_url}")
                        await self._handle_ws_messages(websocket)
            
            except websockets.exceptions.ConnectionClosed:
                self.logger.warning("WebSocket connection closed. Reconnecting...")
            except Exception as e:
                self.logger.error(f"WebSocket connection error: {e}")
            
            if self._is_running:
                await asyncio.sleep(5)  # Reconnect delay

    async def _handle_ws_messages(self, websocket):
        """
        处理从 WebSocket 接收到的原始消息
        
        Args:
            websocket: websockets.connect 返回的 WebSocket 连接对象
            
        Returns:
            None
            
        Raises:
            Exception: 处理消息请求过程中产生的任何异常
        """
        async for message in websocket:
            try:
                data = json.loads(message)
                # Only process incoming message events, ignore self-sent messages to avoid duplication
                if data.get("post_type") == "message":
                    qq_message = QQMessage(**data)
                    if self.message_handler:
                        if asyncio.iscoroutinefunction(self.message_handler):
                            await self.message_handler(qq_message)
                        else:
                            self.message_handler(qq_message)
            except Exception as e:
                self.logger.error(f"Error processing WebSocket message: {e}")

    def start(self):
        self._is_running = True
        self._ws_task = asyncio.create_task(self._connect_ws())

    def stop(self):
        self._is_running = False
        if self._ws_task:
            self._ws_task.cancel()
