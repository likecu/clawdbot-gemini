"""
LLM模型封装模块

提供统一的AI模型调用接口，支持OpenRouter和Gemini等多种模型后端
"""

import os
from typing import Optional, Any, List, Dict
from enum import Enum


class ModelProvider(Enum):
    """
    模型提供商枚举
    """
    OPENROUTER = "openrouter"
    GEMINI = "gemini"


class LLMManager:
    """
    LLM管理器类

    负责管理不同AI模型提供商的初始化和调用，提供统一的接口
    """

    def __init__(self):
        """
        初始化LLM管理器
        """
        self.openrouter_client = None
        self.gemini_client = None
        self.current_provider = ModelProvider.OPENROUTER
        self.default_model = "tngtech/deepseek-r1t2-chimera:free"

    def init_openrouter(self, api_key: Optional[str] = None, model: Optional[str] = None) -> Any:
        """
        初始化OpenRouter客户端

        Args:
            api_key: OpenRouter API密钥
            model: 默认模型名称

        Returns:
            OpenRouterClient实例
        """
        from openrouter import OpenRouterClient

        if api_key is None:
            api_key = os.getenv("OPENROUTER_API_KEY")

        if model is None:
            model = self.default_model

        self.openrouter_client = OpenRouterClient(api_key, model)
        self.current_provider = ModelProvider.OPENROUTER

        return self.openrouter_client

    def init_gemini(self, api_key: Optional[str] = None, model: str = "") -> Any:
        """
        初始化Gemini客户端

        Args:
            api_key: Google API密钥
            model: 模型名称

        Returns:
            Gemini客户端实例
        """
        import google.genai as genai

        if api_key is None:
            api_key = os.getenv("GOOGLE_API_KEY")

        if not api_key:
            raise ValueError("Google API Key未配置")

        client = genai.Client(api_key=api_key)
        self.gemini_client = client
        self.current_provider = ModelProvider.GEMINI

        return client

    def get_response(self, user_message: str, model: Optional[str] = None) -> str:
        """
        获取AI生成的回复

        Args:
            user_message: 用户消息
            model: 使用的模型（可选）

        Returns:
            str: AI生成的回复
        """
        if self.current_provider == ModelProvider.OPENROUTER:
            if self.openrouter_client is None:
                self.init_openrouter()

            from openrouter import get_response as or_get_response
            return or_get_response(self.openrouter_client, user_message)

        elif self.current_provider == ModelProvider.GEMINI:
            if self.gemini_client is None:
                self.init_gemini()

            try:
                response = self.gemini_client.models.generate_content(
                    model=model or "",
                    contents=user_message
                )
                return response.text
            except Exception as e:
                raise Exception(f"Gemini API调用失败: {str(e)}")

        else:
            raise ValueError(f"未知的模型提供商: {self.current_provider}")

    def switch_provider(self, provider: ModelProvider) -> None:
        """
        切换模型提供商

        Args:
            provider: 新的模型提供商
        """
        self.current_provider = provider

    def get_current_provider(self) -> ModelProvider:
        """
        获取当前使用的模型提供商

        Returns:
            ModelProvider: 当前模型提供商
        """
        return self.current_provider


_llm_manager: Optional[LLMManager] = None


def get_llm_manager() -> LLMManager:
    """
    获取LLM管理器单例

    Returns:
        LLMManager实例
    """
    global _llm_manager

    if _llm_manager is None:
        _llm_manager = LLMManager()

    return _llm_manager


def init_llm(provider: str = "openrouter", api_key: Optional[str] = None) -> Any:
    """
    初始化LLM服务

    Args:
        provider: 模型提供商（openrouter或gemini）
        api_key: API密钥

    Returns:
        初始化的客户端实例
    """
    manager = get_llm_manager()

    if provider == "openrouter":
        return manager.init_openrouter(api_key)
    elif provider == "gemini":
        return manager.init_gemini(api_key)
    else:
        raise ValueError(f"不支持的模型提供商: {provider}")


def get_llm_response(user_message: str, model: Optional[str] = None) -> str:
    """
    获取LLM生成的回复

    Args:
        user_message: 用户消息
        model: 使用的模型

    Returns:
        str: 生成的回复
    """
    manager = get_llm_manager()
    return manager.get_response(user_message, model)


def reset_llm_manager() -> None:
    """
    重置LLM管理器
    """
    global _llm_manager
    _llm_manager = None
