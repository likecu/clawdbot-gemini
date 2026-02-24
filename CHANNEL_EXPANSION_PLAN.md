# 多渠道架构拓展方案

## 1. 背景与目标
当前 Clawdbot 的架构中，QQ (NapCat) 和飞书 (Lark) 的实现是硬编码在 `ClawdbotApplication` 类中的。这意味着每增加一个新的渠道（如 Telegram, WeChat, Discord），都需要修改主程序逻辑，导致代码耦合度高、难以维护。

本方案旨在设计一套**插件化、统一接口**的多渠道架构，使得：
1.  **易于拓展**：新增渠道只需实现标准接口，无需修改核心逻辑。
2.  **统一管理**：通过 `ChannelManager` 统一管理所有渠道的生命周期（启动、停止、重启）。
3.  **消息归一**：拥有统一的消息模型，核心 Agent 逻辑不再感知具体平台差异。

## 2. 核心架构设计

### 2.1 抽象基类 (BaseChannel)
定义所有渠道必须遵循的接口规范。

```python
from abc import ABC, abstractmethod
from typing import Callable, Any, Dict, Optional
from pydantic import BaseModel

# 统一的消息体
class UnifiedMessage(BaseModel):
    platform: str        # 平台标识: "qq", "lark", "telegram"
    user_id: str         # 发送者ID
    chat_id: str         # 会话ID (群组ID或私聊ID)
    message_type: str    # "private", "group"
    content: str         # 文本内容
    raw_data: Dict       # 原始数据(用于调试或特殊处理)
    timestamp: float

# 统一的发送请求
class UnifiedSendRequest(BaseModel):
    chat_id: str
    content: str
    message_type: str = "text"  # text, image, file...
    reply_to_id: Optional[str] = None

class BaseChannel(ABC):
    """渠道抽象基类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.message_handler: Optional[Callable[[UnifiedMessage], None]] = None

    @abstractmethod
    async def start(self):
        """启动渠道服务（如建立WebSocket连接）"""
        pass

    @abstractmethod
    async def stop(self):
        """停止渠道服务"""
        pass

    @abstractmethod
    async def send_message(self, request: UnifiedSendRequest) -> bool:
        """发送消息到该渠道"""
        pass

    def register_handler(self, handler: Callable[[UnifiedMessage], None]):
        """注册通用消息处理器"""
        self.message_handler = handler

    async def on_message_received(self, message: UnifiedMessage):
        """内部调用，当收到平台消息并转换为UnifiedMessage后调用"""
        if self.message_handler:
            await self.message_handler(message)
```

### 2.2 渠道管理器 (ChannelManager)
负责加载、初始化和路由消息。

```python
class ChannelManager:
    def __init__(self):
        self.channels: Dict[str, BaseChannel] = {}
        self.global_handler: Optional[Callable[[UnifiedMessage], None]] = None

    def register_channel(self, name: str, channel: BaseChannel):
        self.channels[name] = channel
        if self.global_handler:
            channel.register_handler(self.global_handler)

    async def start_all(self):
        for name, channel in self.channels.items():
            try:
                await channel.start()
                logger.info(f"Channel {name} started")
            except Exception as e:
                logger.error(f"Failed to start channel {name}: {e}")

    async def stop_all(self):
        for channel in self.channels.values():
            await channel.stop()

    def set_global_handler(self, handler: Callable[[UnifiedMessage], None]):
        """设置全局消息处理器（即连接到 Agent 的入口）"""
        self.global_handler = handler
        for channel in self.channels.values():
            channel.register_handler(handler)

    async def send_message(self, platform: str, request: UnifiedSendRequest):
        """路由消息到指定平台"""
        channel = self.channels.get(platform)
        if not channel:
            raise ValueError(f"Channel {platform} not found")
        return await channel.send_message(request)
```

## 3. 目录结构调整

建议将代码重构为以下结构：

```
src/
├── channels/           # [NEW] 渠道模块
│   ├── __init__.py
│   ├── base.py         # BaseChannel 定义
│   ├── manager.py      # ChannelManager 定义
│   ├── qq/             # QQ 渠道实现
│   │   ├── __init__.py
│   │   ├── adapter.py  # 继承 BaseChannel
│   │   └── client.py   # 原有的 NapCatClient (可复用或重构)
│   ├── lark/           # 飞书 渠道实现
│   │   ...
│   └── telegram/       # [FUTURE] Telegram 实现
├── core/
│   ├── agent.py        # 核心 Agent (只处理 UnifiedMessage)
│   ...
├── main.py             # 入口文件 (仅负责组装 ChannelManager 和 Agent)
```

## 4. 实施步骤

### 第一阶段：定义核心接口 (Infrastructure)
1.  创建 `src/channels/base.py` 定义 `BaseChannel` 和 `UnifiedMessage`。
2.  创建 `src/channels/manager.py` 实现 `ChannelManager`。

### 第二阶段：适配现有渠道 (Refactor)
1.  **Refactor QQ**: 创建 `src/channels/qq/adapter.py`，包装现有的 `NapCatClient`，使其符合 `BaseChannel` 接口。
2.  **Refactor Lark**: 创建 `src/channels/lark/adapter.py`，包装现有的 `LarkWSClient`。

### 第三阶段：重构主程序 (Integration)
1.  修改 `src/main.py`，不再直接实例化 Client，而是使用 `ChannelManager`。
2.  配置加载逻辑更新，根据配置自动注册启用的渠道。

### 第四阶段：新增渠道 (Expansion)
1.  例如添加 Telegram：
    *   在 `src/channels/telegram/` 下实现 `TelegramChannel(BaseChannel)`。
    *   在配置中添加 Telegram Token。
    *   在 `main.py` 中注册。

## 5. 示例：如何实现一个新的渠道 (Telegram)

```python
# src/channels/telegram/adapter.py
from ..base import BaseChannel, UnifiedMessage, UnifiedSendRequest

class TelegramChannel(BaseChannel):
    def __init__(self, config):
        super().__init__(config)
        self.token = config["telegram_token"]
        # 初始化 Telegram Bot Client...

    async def start(self):
        # 启动 Long Polling 或 Webhook
        pass

    async def send_message(self, request: UnifiedSendRequest):
        # 调用 Telegram API 发送消息
        # api.send_message(chat_id=request.chat_id, text=request.content)
        pass
        
    # 当收到 Telegram 消息时
    async def _on_telegram_update(self, update):
        msg = UnifiedMessage(
            platform="telegram",
            user_id=str(update.effective_user.id),
            chat_id=str(update.effective_chat.id),
            content=update.message.text,
            ...
        )
        await self.on_message_received(msg)
```

## 6. 带来的好处
*   **解耦**：核心业务逻辑（Agent, Tool Use）与消息传输层完全分离。
*   **灵活性**：可以随时开关某个渠道，不影响其他服务。
*   **测试性**：可以轻松编写 MockChannel 进行单元测试，无需真实的 QQ 或飞书环境。
