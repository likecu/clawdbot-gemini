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
            resp = self.client._api_client.im.v1.message.create(req)
            
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
            
            # 提前定义 chat_id 和 sender_id，确保在处理图片时可用
            chat_id = message.get("chat_id")
            sender_id = sender.get("sender_id", {}).get("open_id") if isinstance(sender.get("sender_id"), dict) else None
            
            msg_type = message.get("message_type", "text")
            msg_content = message.get("content", "{}")
            text = ""
            
            logger.info(f"Receiving Lark Message: type={msg_type}, content_preview={msg_content[:100]}...")

            try:
                content_json = json.loads(msg_content)
                
                # 提取各类型资源的key
                image_key = content_json.get("image_key")
                file_key = content_json.get("file_key")
                
                if msg_type == "text":
                    text = content_json.get("text", "")
                elif msg_type == "image" or image_key:
                    # 处理图片消息
                    if not image_key:
                        logger.warning("Message type is image but no image_key found")
                        return

                    message_id = message.get("message_id")
                    logger.info(f"Detected Image Message! key={image_key}, starting process task.")
                    
                    target_id = chat_id or sender_id
                    if not target_id:
                        logger.error("Cannot process image: both chat_id and sender_id are None")
                        return
                    
                    asyncio.create_task(self._process_file_message(
                        message_id=message_id,
                        file_key=image_key,
                        chat_id=target_id,
                        file_type="image"
                    ))
                    return
                elif msg_type == "file":
                    # 处理文件消息(文档、PDF等)
                    if not file_key:
                        logger.warning("Message type is file but no file_key found")
                        return
                    
                    message_id = message.get("message_id")
                    file_name = content_json.get("file_name", "unknown_file")
                    logger.info(f"Detected File Message! key={file_key}, name={file_name}")
                    
                    target_id = chat_id or sender_id
                    if not target_id:
                        logger.error("Cannot process file: both chat_id and sender_id are None")
                        return
                    
                    asyncio.create_task(self._process_file_message(
                        message_id=message_id,
                        file_key=file_key,
                        chat_id=target_id,
                        file_type="file",
                        file_name=file_name
                    ))
                    return
                elif msg_type == "audio":
                    # 处理音频消息
                    audio_key = content_json.get("file_key")
                    if not audio_key:
                        logger.warning("Message type is audio but no file_key found")
                        return
                    
                    message_id = message.get("message_id")
                    logger.info(f"Detected Audio Message! key={audio_key}")
                    
                    target_id = chat_id or sender_id
                    if not target_id:
                        logger.error("Cannot process audio: both chat_id and sender_id are None")
                        return
                    
                    asyncio.create_task(self._process_file_message(
                        message_id=message_id,
                        file_key=audio_key,
                        chat_id=target_id,
                        file_type="audio"
                    ))
                    return
                elif msg_type == "media":
                    # 处理视频消息
                    media_key = content_json.get("file_key")
                    if not media_key:
                        logger.warning("Message type is media but no file_key found")
                        return
                    
                    message_id = message.get("message_id")
                    logger.info(f"Detected Media Message! key={media_key}")
                    
                    target_id = chat_id or sender_id
                    if not target_id:
                        logger.error("Cannot process media: both chat_id and sender_id are None")
                        return
                    
                    asyncio.create_task(self._process_file_message(
                        message_id=message_id,
                        file_key=media_key,
                        chat_id=target_id,
                        file_type="media"
                    ))
                    return
            except Exception as e:
                logger.error(f"Error parsing message content: {e}")
                text = str(msg_content)
            
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

    async def _process_file_message(
        self, 
        message_id: str, 
        file_key: str, 
        chat_id: str,
        file_type: str = "image",
        file_name: str = None
    ):
        """
        处理各类型文件消息：下载 -> 处理 -> 回复
        
        Args:
            message_id: 消息ID
            file_key: 文件Key
            chat_id: 聊天ID
            file_type: 文件类型 (image/file/audio/media)
            file_name: 文件名(仅file类型需要)
        """
        try:
            logger.info(f"开始处理{file_type}消息: {message_id}, key: {file_key}")
            
            # 根据文件类型发送不同的处理提示
            type_emoji = {"image": "🖼️", "file": "📄", "audio": "🎵", "media": "🎬"}
            type_name = {"image": "图片", "file": "文件", "audio": "音频", "media": "视频"}
            
            await self.send_message(UnifiedSendRequest(
                chat_id=chat_id,
                message_type="text",
                content=f"{type_emoji.get(file_type, '📎')} 收到{type_name.get(file_type, '文件')}，正在处理..."
            ))
            
            # 下载文件
            resource_type = "file" if file_type in ["file", "audio", "media"] else "image"
            file_data = self.client.get_message_resource(message_id, file_key, resource_type)
            
            if not file_data:
                await self.send_message(UnifiedSendRequest(
                    chat_id=chat_id,
                    message_type="text",
                    content=f"❌ {type_name.get(file_type, '文件')}下载失败，请重试。"
                ))
                return

            # 确定文件扩展名和保存路径
            if file_type == "image":
                ext = ".jpg"
            elif file_type == "audio":
                ext = ".mp3"
            elif file_type == "media":
                ext = ".mp4"
            elif file_name:
                ext = os.path.splitext(file_name)[1] or ".bin"
            else:
                ext = ".bin"
            
            temp_path = f"/tmp/lark_{file_type}_{message_id}{ext}"
            with open(temp_path, "wb") as f:
                f.write(file_data)
            
            logger.info(f"{type_name.get(file_type, '文件')}已保存到: {temp_path}, 大小: {len(file_data)} bytes")

            # 根据文件类型进行不同处理
            if file_type == "image":
                await self._process_image_with_gemini(temp_path, chat_id)
            elif file_type == "file":
                await self._process_document_file(temp_path, file_name, chat_id)
            elif file_type == "audio":
                await self._process_audio_file(temp_path, chat_id)
            elif file_type == "media":
                await self._process_media_file(temp_path, chat_id)
            
            # 清理临时文件
            try:
                os.remove(temp_path)
            except Exception as e:
                logger.warning(f"清理临时文件失败: {e}")

        except Exception as e:
            logger.error(f"处理{file_type}消息流程异常: {e}")
            await self.send_message(UnifiedSendRequest(
                chat_id=chat_id,
                message_type="text",
                content=f"⚠️ 处理出错: {str(e)}"
            ))

    async def _process_image_with_gemini(self, temp_path: str, chat_id: str):
        """
        使用Gemini处理图片
        
        Args:
            temp_path: 临时文件路径
            chat_id: 聊天ID
        """
        try:
            from config import get_settings
            from adapters.gemini.gemini_ocr import GeminiOCR
            
            settings = get_settings()
            ocr = GeminiOCR(api_key=settings.gemini_api_key)
            
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None, 
                lambda: ocr.recognize_image(temp_path, "请详细描述这张图片的内容，如果包含文字请提取出来。")
            )
            
            if result and result.get("success"):
                response_text = result.get("response", "识别成功，但没有返回内容")
                await self.send_message(UnifiedSendRequest(
                    chat_id=chat_id,
                    message_type="text",
                    content=f"📝 **图片分析结果**:\n\n{response_text}"
                ))
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

    async def _process_document_file(self, temp_path: str, file_name: str, chat_id: str):
        """
        处理文档文件
        
        Args:
            temp_path: 临时文件路径
            file_name: 文件名
            chat_id: 聊天ID
        """
        file_size = os.path.getsize(temp_path)
        file_size_str = f"{file_size / 1024:.1f} KB" if file_size < 1024 * 1024 else f"{file_size / 1024 / 1024:.2f} MB"
        
        await self.send_message(UnifiedSendRequest(
            chat_id=chat_id,
            message_type="text",
            content=f"✅ 文件已接收：\n📄 文件名: {file_name}\n📦 大小: {file_size_str}\n\n暂不支持文档内容解析，请等待后续版本更新。"
        ))

    async def _process_audio_file(self, temp_path: str, chat_id: str):
        """
        处理音频文件
        
        Args:
            temp_path: 临时文件路径
            chat_id: 聊天ID
        """
        file_size = os.path.getsize(temp_path)
        file_size_str = f"{file_size / 1024:.1f} KB" if file_size < 1024 * 1024 else f"{file_size / 1024 / 1024:.2f} MB"
        
        await self.send_message(UnifiedSendRequest(
            chat_id=chat_id,
            message_type="text",
            content=f"✅ 音频已接收：\n📦 大小: {file_size_str}\n\n暂不支持音频转写，请等待后续版本更新。"
        ))

    async def _process_media_file(self, temp_path: str, chat_id: str):
        """
        处理视频文件
        
        Args:
            temp_path: 临时文件路径
            chat_id: 聊天ID
        """
        file_size = os.path.getsize(temp_path)
        file_size_str = f"{file_size / 1024:.1f} KB" if file_size < 1024 * 1024 else f"{file_size / 1024 / 1024:.2f} MB"
        
        await self.send_message(UnifiedSendRequest(
            chat_id=chat_id,
            message_type="text",
            content=f"✅ 视频已接收：\n📦 大小: {file_size_str}\n\n暂不支持视频处理，请等待后续版本更新。"
        ))
