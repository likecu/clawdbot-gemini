"""
DeepSeek客户端模块

提供与DeepSeek API的直接集成
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

import requests


class DeepSeekClient:
    """
    DeepSeek API客户端类
    
    封装与DeepSeek API的通信逻辑，支持DeepSeek-V3和R1推理模型
    """
    
    def __init__(self, api_key: Optional[str] = None,
                 base_url: str = "https://api.deepseek.com",
                 model: str = "deepseek-chat"):
        """
        初始化DeepSeek客户端
        
        Args:
            api_key: DeepSeek API密钥
            base_url: API基础URL
            model: 使用的模型名称
        """
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")
        self.base_url = base_url or os.getenv("DEEPSEEK_API_BASE_URL", "https://api.deepseek.com")
        self.model = model
        
        if not self.api_key:
            raise ValueError("DeepSeek API密钥未配置，请设置DEEPSEEK_API_KEY环境变量")
        
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })
        
        self.conversation_history: List[Dict[str, str]] = []
        self._last_request_time: Optional[datetime] = None
    
    def _check_rate_limit(self) -> None:
        """
        检查并应用速率限制
        """
        import time
        if self._last_request_time:
            elapsed = (datetime.now() - self._last_request_time).total_seconds()
            if elapsed < 1.0:  # 最小间隔1秒
                time.sleep(1.0 - elapsed)
        self._last_request_time = datetime.now()
    
    def chat(self, message: str,
             model: Optional[str] = None,
             system_prompt: Optional[str] = None,
             temperature: float = 0.7,
             max_tokens: int = 4096) -> Dict[str, Any]:
        """
        发送聊天消息
        
        Args:
            message: 用户消息
            model: 使用的模型
            system_prompt: 系统提示词
            temperature: 温度参数
            max_tokens: 最大token数
            
        Returns:
            Dict: 包含reply_text和usage的字典
        """
        self._check_rate_limit()
        
        url = f"{self.base_url}/chat/completions"
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": message})
        
        payload = {
            "model": model or self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=120)
            response.raise_for_status()
            
            data = response.json()
            assistant_message = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            
            self.conversation_history.append({"role": "user", "content": message})
            self.conversation_history.append({"role": "assistant", "content": assistant_message})
            
            return {
                "reply_text": assistant_message,
                "usage": usage,
                "model": data.get("model", self.model)
            }
            
        except Exception as e:
            self.logger.error(f"DeepSeek API调用失败: {str(e)}")
            raise
    
    def chat_with_reasoning(self, message: str,
                            reasoning_model: str = "deepseek-reasoner") -> Dict[str, Any]:
        """
        使用推理模型（R1）进行推理
        
        Args:
            message: 用户消息
            reasoning_model: 推理模型名称
            
        Returns:
            Dict: 包含reasoning_content、reply_text和usage的字典
        """
        self._check_rate_limit()
        
        url = f"{self.base_url}/chat/completions"
        
        messages = [{"role": "user", "content": message}]
        
        payload = {
            "model": reasoning_model,
            "messages": messages,
            "max_tokens": 8192
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=180)
            response.raise_for_status()
            
            data = response.json()
            
            # 推理模型的特殊响应格式
            reasoning_content = ""
            reply_text = ""
            
            if "reasoning_content" in data.get("choices", [{}])[0]:
                reasoning_content = data["choices"][0]["reasoning_content"]
            
            if "message" in data["choices"][0]:
                reply_text = data["choices"][0]["message"].get("content", "")
            
            usage = data.get("usage", {})
            
            return {
                "reasoning_content": reasoning_content,
                "reply_text": reply_text,
                "usage": usage,
                "model": reasoning_model
            }
            
        except Exception as e:
            self.logger.error(f"DeepSeek推理模型调用失败: {str(e)}")
            raise
    
    def clear_history(self) -> None:
        """
        清空对话历史
        """
        self.conversation_history.clear()
    
    def set_model(self, model: str) -> None:
        """
        设置使用的模型
        
        Args:
            model: 模型名称
        """
        self.model = model


def create_deepseek_client(api_key: Optional[str] = None,
                           base_url: Optional[str] = None,
                           model: str = "deepseek-chat") -> DeepSeekClient:
    """
    创建DeepSeek客户端实例
    
    Args:
        api_key: API密钥
        base_url: API基础URL
        model: 默认模型
        
    Returns:
        DeepSeekClient: 客户端实例
    """
    return DeepSeekClient(api_key, base_url, model)
