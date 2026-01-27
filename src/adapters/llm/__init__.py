"""
LLM适配器模块

提供与不同LLM服务商的集成支持
"""

from .openrouter_client import OpenRouterClient, init_client, get_response
from .deepseek_client import DeepSeekClient, create_deepseek_client

__all__ = [
    'OpenRouterClient',
    'init_client',
    'get_response',
    'DeepSeekClient',
    'create_deepseek_client'
]
