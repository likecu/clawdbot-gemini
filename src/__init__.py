"""
__init__.py

Clawdbot包初始化

提供项目各模块的便捷访问
"""

from .config import Settings, get_settings, reload_settings
from .infrastructure import RedisClient, create_redis_client
from .adapters.lark import (
    MessageConverter,
    LarkWSClient,
    EventDispatcher,
    create_ws_client
)
from .adapters.llm import (
    OpenRouterClient,
    DeepSeekClient,
    init_client
)
from .core import (
    Agent,
    SessionManager,
    PromptBuilder,
    create_agent,
    create_session_manager,
    create_prompt_builder
)

__version__ = "2.0.0"

__all__ = [
    # 配置
    'Settings',
    'get_settings',
    'reload_settings',
    
    # 基础设施
    'RedisClient',
    'create_redis_client',
    
    # Lark适配器
    'MessageConverter',
    'LarkWSClient',
    'EventDispatcher',
    'create_ws_client',
    
    # LLM适配器
    'OpenRouterClient',
    'DeepSeekClient',
    'init_client',
    
    # 核心模块
    'Agent',
    'SessionManager',
    'PromptBuilder',
    'create_agent',
    'create_session_manager',
    'create_prompt_builder',
    
    # 版本
    '__version__'
]
