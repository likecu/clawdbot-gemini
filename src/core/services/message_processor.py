
import logging
import os
import asyncio
import aiohttp
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List

from config.settings import get_settings
from channels.base import UnifiedMessage
from core.agent import Agent
from adapters.gemini.gemini_ocr import GeminiOCR

logger = logging.getLogger(__name__)

class MessageProcessor:
    """
    Core service for processing unified messages.
    Handles OCR, Session Management, and Agent interaction.
    """
    def __init__(self, agent: Agent):
        self.agent = agent
        self.settings = get_settings()
        self.ocr: Optional[GeminiOCR] = None
        
        if self.settings.ocr_enabled:
            if not self.settings.gemini_api_key:
                logger.warning("OCR is enabled but GEMINI_API_KEY is missing. OCR will not work.")
            else:
                self.ocr = GeminiOCR(api_key=self.settings.gemini_api_key)
                logger.info("OCR Service initialized.")

    async def process(self, message: UnifiedMessage) -> Dict[str, Any]:
        """
        Process a unified message through the full pipeline.
        
        1. OCR Extraction (if images present)
        2. Session ID Generation
        3. Agent Execution
        
        Returns:
            Dict containing the agent's response and status.
        """
        # 1. OCR Processing
        user_text = message.content or ""
        if self.settings.ocr_enabled and message.images:
            ocr_text = await self._process_ocr(message)
            if ocr_text:
                user_text = f"{user_text}\n\n{ocr_text}"
        
        # If no text and no images (or OCR failed/disabled), and it's not a pure image message, we might have nothing to do.
        # But we pass it to agent anyway if there is *some* content.
        if not user_text.strip():
            logger.info("Message content is empty after processing. Skipping agent.")
            return {"success": False, "error": "Empty message"}

        # 2. Session ID Generation
        session_id, callback_session_id = self._get_session_ids(message)
        
        # 3. Agent Processing
        logger.info(f"Processing message for session {session_id}")
        
        # Pass constructed user_id (platform:id) for memory isolation
        user_id_str = f"{message.platform}:{message.user_id}"
        
        result = await self.agent.process_message(
            user_id=user_id_str,
            chat_id=session_id,
            message=user_text,
            callback_session_id=callback_session_id
        )
        
        return result

    async def _process_ocr(self, message: UnifiedMessage) -> str:
        """
        Extract text from images in the message using Gemini OCR.
        Returns formatted string with OCR results.
        """
        if not self.ocr:
            return ""

        logger.info(f"[OCR] Processing {len(message.images)} images...")
        ocr_results = []
        
        for idx, img_source in enumerate(message.images):
            try:
                temp_path = f"/tmp/unified_img_{message.platform}_{idx}_{int(datetime.now().timestamp())}.jpg"
                
                # Download or use local path
                if img_source.startswith("http"):
                    success = await self._download_image(img_source, temp_path)
                    if not success:
                        ocr_results.append(f"--- 图片 {idx+1} 获取失败 ---")
                        continue
                else:
                    temp_path = img_source

                # Execute OCR
                if os.path.exists(temp_path):
                    logger.info(f"[OCR] Recognizing: {temp_path}")
                    # Run in executor to avoid blocking event loop
                    loop = asyncio.get_running_loop()
                    result = await loop.run_in_executor(
                        None, 
                        lambda: self.ocr.recognize_image(temp_path, "请详细描述这张图片的内容，如果包含文字请提取出来并保持原有排版。")
                    )
                    
                    if result and result.get("success"):
                        text = result.get("response", "")
                        ocr_results.append(f"（图片 {idx+1} 内容：\n{text}）")
                    else:
                        ocr_results.append(f"（图片 {idx+1} 识别失败）")
                    
                    # Cleanup temp file if we downloaded it
                    if img_source.startswith("http") and os.path.exists(temp_path):
                        os.remove(temp_path)
                        
            except Exception as e:
                logger.error(f"[OCR] Error processing image {idx}: {e}")
                ocr_results.append(f"（图片 {idx+1} 处理出错）")

        return "\n".join(ocr_results) if ocr_results else ""

    async def _download_image(self, url: str, target_path: str) -> bool:
        """Helper to download image from URL"""
        try:
            # QQ specialized headers
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Referer": "https://q.qq.com/"
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, timeout=30) as resp:
                    if resp.status == 200:
                        with open(target_path, "wb") as f:
                            f.write(await resp.read())
                        return True
                    else:
                        logger.error(f"Download failed: {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"Download exception: {e}")
            return False

    def _get_session_ids(self, message: UnifiedMessage) -> Tuple[str, str]:
        """
        Generate strict session IDs for context management.
        
        Returns:
            (session_id, callback_session_id)
        """
        # Session ID: Platform:User:ID:Date:Version
        # Ensures daily isolation and user isolation
        today_str = datetime.now().strftime("%Y%m%d")
        session_id = f"{message.platform}:user:{message.user_id}:{today_str}:v2"
        
        # Callback ID: Platform:Type:ChatID
        # Used for routing async responses back to the correct channel
        callback_session_id = f"{message.platform}:{message.message_type}:{message.chat_id}"
        
        return session_id, callback_session_id
