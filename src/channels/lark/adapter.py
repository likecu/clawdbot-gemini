from typing import Dict, Any, Optional
import logging
import asyncio
import json
import threading
import sys
import os
import uuid
from io import BytesIO

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

            from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody
            import uuid

            msg_type = "text"
            content_dict = {}

            if request.message_type == "text":
                content_dict = {"text": request.content}
                msg_type = "text"
            elif request.message_type == "image":
                 # 假设 request.content 是 image_key，或者我们需要上传？
                 # 这里简化处理，假设 request.content 就是 image_key
                 content_dict = {"image_key": request.content}
                 msg_type = "image"
            else:
                # Fallback / TODO: support other types
                content_dict = {"text": f"[Unsupported type: {request.message_type}] {request.content}"}
                msg_type = "text"

            # Determine receive_id_type
            # 默认优先使用 chat_id，如果 request.chat_id 看起来像 open_id (ou_开头) 则使用 open_id
            # 实际上 Lark 的 chat_id (oc_开头) 和 open_id (ou_开头) 格式很明显
            
            receive_id_type = "chat_id"
            if request.chat_id.startswith("ou_"):
                receive_id_type = "open_id"
            
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

            # 使用 _client 直接发送，绕过 self.client.send_message 的限制
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
            
            msg_type = message.get("message_type", "text")
            msg_content = message.get("content", "{}")
            text = ""
            
            logger.info(f"Receiving Lark Message: type={msg_type}, content_preview={msg_content[:100]}...")

            try:
                content_json = json.loads(msg_content)
                
                # Check for image_key regardless of reported type (fallback)
                image_key = content_json.get("image_key")
                
                if msg_type == "text":
                    text = content_json.get("text", "")
                elif msg_type == "image" or image_key:
                    if not image_key:
                        logger.warning("Message type is image but no image_key found")
                        return

                    message_id = message.get("message_id")
                    logger.info(f"Detected Image Message! key={image_key}, starting process task.")
                    
                    # 异步处理图片下载和识别
                    asyncio.create_task(self._process_image_message(message_id, image_key, chat_id or sender_id))
                    return # Handled
            except Exception as e:
                logger.error(f"Error parsing message content: {e}")
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

    async def _process_image_message(self, message_id: str, image_key: str, chat_id: str):
        """
        处理图片消息：下载 -> OCR -> 回复
        """
        try:
            logger.info(f"开始处理图片消息: {message_id}, key: {image_key}")
            
            # 1. 立即回复"正在分析图片..."
            await self.send_message(UnifiedSendRequest(
                chat_id=chat_id,
                message_type="text",
                content="👀 收到图片，正在使用 Gemini 进行语义分析..."
            ))
            
            # 2. 下载图片
            image_data = self.client.get_message_resource(message_id, image_key, "image")
            if not image_data:
                await self.send_message(UnifiedSendRequest(
                    chat_id=chat_id,
                    message_type="text",
                    content="❌ 图片下载失败，请重试。"
                ))
                return

            # 3. 保存临时文件
            temp_path = f"/tmp/lark_img_{message_id}.jpg"
            with open(temp_path, "wb") as f:
                f.write(image_data)
            
            logger.info(f"图片已保存到: {temp_path}")

            # 4. 调用 Gemini OCR
            try:
                from config import get_settings
                from adapters.gemini.gemini_ocr import GeminiOCR
                
                settings = get_settings()
                # 初始化 OCR (优先使用配置的 Key)
                ocr = GeminiOCR(api_key=settings.gemini_api_key)
                
                
                # 在线程池中运行识别，避免阻塞异步循环
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    None, 
                    lambda: ocr.recognize_image(temp_path, "请详细描述这张图片的内容，如果包含文字请提取出来。")
                )
                
                if result and result.get("success"):
                    response_text = result.get("response", "识别成功，但没有返回内容")
                    
                    # 5. 回复识别结果
                    await self.send_message(UnifiedSendRequest(
                        chat_id=chat_id,
                        message_type="text",
                        content=f"📝 **图片分析结果**:\n\n{response_text}"
                    ))
                    
                    # 6. (可选) 重新上传图片并发送，演示发送图片能力
                    # new_image_key = self.client.upload_image(image_data)
                    # if new_image_key:
                    #     await self.send_message(UnifiedSendRequest(
                    #         chat_id=chat_id,
                    #         message_type="image",
                    #         content=new_image_key
                    #     ))
                else:
                    await self.send_message(UnifiedSendRequest(
                        chat_id=chat_id,
                        message_type="text",
                        content="⚠️ 图片识别失败，可能是 API 限额或网络问题。"
                    ))

            except ImportError:
                logger.error("无法导入 gemini_ocr，请检查路径")
                await self.send_message(UnifiedSendRequest(
                        chat_id=chat_id,
                        message_type="text",
                        content="⚠️ 系统配置错误：无法加载 OCR 模块。"
                    ))
            except Exception as e:
                logger.error(f"OCR 过程出错: {e}")
                await self.send_message(UnifiedSendRequest(
                        chat_id=chat_id,
                        message_type="text",
                        content=f"⚠️ 处理出错: {str(e)}"
                    ))
            
            # 清理临时文件
            try:
                os.remove(temp_path)
            except:
                pass

        except Exception as e:
            logger.error(f"处理图片消息流程异常: {e}")
