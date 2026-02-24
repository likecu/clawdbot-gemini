"""
记忆提取器模块

利用 Gemini Flash 模型从对话历史中提取用户关键信息，
与已有记忆合并后写回用户记忆文件。
"""

import logging
import asyncio
from typing import List, Dict, Optional

from .memory import get_memory_bank

logger = logging.getLogger(__name__)

# 记忆提取 Prompt 模板
MEMORY_EXTRACT_PROMPT = """你是一个记忆档案管理员。请从下面的对话历史中提取关于【用户】的关键信息。

## 已有记忆档案
{existing_memory}

## 最近对话历史
{conversation}

## 输出要求
将已有记忆和新发现的信息合并，输出完整的用户档案。格式如下（Markdown）：

# 用户档案 (User Profile)
- **称呼**: （用户的名字/昵称）
- **性别**: （如果提到）
- **年龄/职业**: （如果提到）

# 助手档案 (Assistant Persona)
- **称呼**: （用户对你的称呼，如“小汉堡”）
- **性格设定**: （用户约定的互动风格）

# 关系动态
- （你们之间的互动模式、昵称、权力关系等）

# 情感锚点
- （重要的话、承诺、争吵、甜蜜时刻等）

# 生活细节
- （喜好、习惯、近况、宠物、朋友等）

# 重要日期
- （生日、纪念日等）

## 规则
1. 保留已有记忆中所有仍然有效的信息
2. 如果对话中没有新信息可提取，直接返回已有记忆原文
3. 如果新信息与旧信息矛盾，以新信息为准
4. 删除空的章节（如果某个类别完全没有信息就不要输出）
5. 保持简洁，每条信息一行，不要写长段落
"""


class MemoryExtractor:
    """
    记忆提取器

    异步地从对话历史中提取用户信息并更新记忆文件。
    复用 GeminiOCR 的 ask_question 方法作为轻量级 LLM 调用。
    """

    def __init__(self, trigger_interval: int = 10):
        """
        初始化记忆提取器

        Args:
            trigger_interval: 触发提取的消息间隔（默认10条消息 = 5轮对话）
        """
        self.trigger_interval = trigger_interval
        self.memory_bank = get_memory_bank()
        self._gemini = None  # 懒加载

    def _get_gemini(self):
        """
        懒加载 Gemini 客户端实例

        Returns:
            GeminiOCR: Gemini 客户端实例，加载失败则返回 None
        """
        if self._gemini is None:
            try:
                from adapters.gemini.gemini_ocr import GeminiOCR
                self._gemini = GeminiOCR()
                logger.info("记忆提取器: Gemini 客户端初始化成功")
            except Exception as e:
                logger.error(f"记忆提取器: 无法初始化 Gemini 客户端: {e}")
        return self._gemini

    def should_trigger(self, history_length: int) -> bool:
        """
        判断是否应该触发记忆提取

        Args:
            history_length: 当前会话历史消息数量

        Returns:
            bool: 是否应该触发
        """
        return history_length > 0 and history_length % self.trigger_interval == 0

    async def extract_and_update(self, user_id: str,
                                  history: List[Dict[str, str]]) -> bool:
        """
        从对话历史中提取用户信息并更新记忆文件

        Args:
            user_id: 用户ID (e.g. "qq:254067848")
            history: 对话历史列表

        Returns:
            bool: 是否更新成功
        """
        try:
            gemini = self._get_gemini()
            if not gemini:
                logger.warning("记忆提取器: Gemini 不可用，跳过记忆更新")
                return False

            # 1. 获取已有记忆
            existing_memory = self.memory_bank.get_user_memory(user_id)
            if not existing_memory:
                existing_memory = "（暂无已有记忆）"

            # 2. 格式化最近对话（取最近20条消息 = 10轮）
            recent = history[-20:] if len(history) > 20 else history
            conversation_lines = []
            for msg in recent:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                # 截断过长的消息
                if len(content) > 200:
                    content = content[:200] + "..."
                label = "用户" if role == "user" else "小汉堡"
                conversation_lines.append(f"{label}: {content}")

            conversation_text = "\n".join(conversation_lines)

            # 3. 构建提取 prompt
            prompt = MEMORY_EXTRACT_PROMPT.format(
                existing_memory=existing_memory,
                conversation=conversation_text
            )

            # 4. 调用 Gemini 提取信息（在线程池中运行同步调用）
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: gemini.ask_question(prompt)
            )

            if not result or not result.get("success"):
                logger.warning("记忆提取器: Gemini 提取失败")
                return False

            new_memory = result.get("response", "").strip()

            # 5. 基础校验：新记忆不能为空或太短
            if len(new_memory) < 20:
                logger.warning(f"记忆提取器: 提取结果过短 ({len(new_memory)} 字), 跳过更新")
                return False

            # 6. 保存更新后的记忆
            success = self.memory_bank.save_user_memory(user_id, new_memory)
            if success:
                logger.info(f"记忆提取器: 用户 {user_id} 的记忆已自动更新 (长度: {len(new_memory)})")
            else:
                logger.error(f"记忆提取器: 保存用户 {user_id} 的记忆失败")

            return success

        except Exception as e:
            logger.error(f"记忆提取器: 更新失败 - {e}", exc_info=True)
            return False


# 单例实例
_memory_extractor: Optional[MemoryExtractor] = None


def get_memory_extractor(trigger_interval: int = 10) -> MemoryExtractor:
    """
    获取记忆提取器单例

    Args:
        trigger_interval: 触发间隔（消息数）

    Returns:
        MemoryExtractor: 提取器实例
    """
    global _memory_extractor
    if _memory_extractor is None:
        _memory_extractor = MemoryExtractor(trigger_interval)
    return _memory_extractor
