"""
OpenRouter客户端模块

提供与OpenRouter API的交互功能，支持DeepSeek等多种模型
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta

import requests


class OpenRouterClient:
    """
    OpenRouter服务客户端类
    
    封装与OpenRouter API的通信逻辑，支持多种AI模型的统一调用
    """
    
    def __init__(self, api_key: Optional[str] = None,
                 model: str = "tngtech/deepseek-r1t2-chimera:free",
                 base_url: str = "https://openrouter.ai/api/v1"):
        """
        初始化OpenRouter客户端
        
        Args:
            api_key: OpenRouter API密钥
            model: 默认使用的模型名称
            base_url: API基础URL
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model
        self.base_url = base_url or os.getenv("OPENROUTER_API_BASE_URL", "https://openrouter.ai/api/v1")
        
        if not self.api_key:
            raise ValueError("OpenRouter API密钥未配置")
        
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("APP_URL", "http://localhost:8000"),
            "X-Title": os.getenv("APP_NAME", "Clawdbot")
        })
        
        self.conversation_history: List[Dict[str, str]] = []
        self._last_request_time: Optional[datetime] = None
        self._min_request_interval = 1.0  # 最小请求间隔（秒）
    
    def _check_rate_limit(self) -> None:
        """
        检查并应用速率限制
        
        Raises:
            RuntimeError: 请求过于频繁时抛出
        """
        if self._last_request_time:
            elapsed = (datetime.now() - self._last_request_time).total_seconds()
            if elapsed < self._min_request_interval:
                wait_time = self._min_request_interval - elapsed
                self.logger.warning(f"请求过于频繁，等待 {wait_time:.2f} 秒")
                import time
                time.sleep(wait_time)
        
        self._last_request_time = datetime.now()
    
    def chat(self, message: str,
             model: Optional[str] = None,
             system_prompt: Optional[str] = None,
             temperature: float = 0.7,
             max_tokens: int = 4096) -> Dict[str, Any]:
        """
        发送聊天消息并获取回复
        
        Args:
            message: 用户消息
            model: 使用的模型（可选，默认使用初始化时的模型）
            system_prompt: 系统提示词（可选）
            temperature: 温度参数，控制回复随机性
            max_tokens: 最大生成token数
            
        Returns:
            Dict: 包含reply_text和usage信息的字典
            
        Raises:
            Exception: API调用失败时抛出异常
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
            self.logger.info(f"调用OpenRouter API，模型: {model or self.model}")
            
            response = self.session.post(url, json=payload, timeout=120)
            response.raise_for_status()
            
            data = response.json()
            
            assistant_message = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            
            # 更新对话历史
            self.conversation_history.append({"role": "user", "content": message})
            self.conversation_history.append({"role": "assistant", "content": assistant_message})
            
            # 限制历史长度
            max_history = 20
            if len(self.conversation_history) > max_history * 2:
                self.conversation_history = self.conversation_history[-max_history * 2:]
            
            self.logger.info(f"OpenRouter回复成功，消耗tokens: {usage.get('total_tokens', 'unknown')}")
            
            return {
                "reply_text": assistant_message,
                "usage": usage,
                "model": data.get("model", self.model)
            }
            
        except requests.exceptions.Timeout:
            error_msg = "OpenRouter服务响应超时"
            self.logger.error(error_msg)
            raise Exception(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"OpenRouter服务请求失败: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            error_msg = f"OpenRouter服务响应格式错误: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
    
    def chat_with_thinking(self, message: str,
                           model: Optional[str] = None,
                           system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        发送聊天消息并获取包含思考过程的回复（适用于R1等推理模型）
        
        Args:
            message: 用户消息
            model: 使用的模型
            system_prompt: 系统提示词
            
        Returns:
            Dict: 包含thinking、reply_text和usage的字典
        """
        result = self.chat(message, model, system_prompt)
        
        # 尝试分离思考过程和最终回复
        reply_text = result["reply_text"]
        
        # R1模型的思考过程通常以<thinking>标签包裹
        thinking = ""
        if "<thinking>" in reply_text and "</thinking>" in reply_text:
            import re
            thinking_match = re.search(r'<thinking>(.*?)</thinking>', reply_text, re.DOTALL)
            if thinking_match:
                thinking = thinking_match.group(1).strip()
                reply_text = re.sub(r'<thinking>.*?</thinking>', '', reply_text, flags=re.DOTALL).strip()
        
        result["thinking"] = thinking
        result["reply_text"] = reply_text
        
        return result
    
    def clear_history(self) -> None:
        """
        清空对话历史
        """
        self.conversation_history.clear()
        self.logger.info("对话历史已清空")
    
    def get_history(self) -> List[Dict[str, str]]:
        """
        获取当前对话历史
        
        Returns:
            List[Dict]: 对话历史列表
        """
        return self.conversation_history.copy()
    
    def set_model(self, model: str) -> None:
        """
        设置使用的模型
        
        Args:
            model: 模型名称
        """
        self.model = model
        self.logger.info(f"模型已切换为: {model}")
    
    def get_models(self) -> List[Dict[str, Any]]:
        """
        获取可用模型列表
        
        Returns:
            List[Dict]: 模型列表
        """
        try:
            url = f"{self.base_url}/models"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])
        except Exception as e:
            self.logger.error(f"获取模型列表失败: {str(e)}")
            return []
    
    def get_credits(self) -> Dict[str, Any]:
        """
        获取账户积分信息
        
        Returns:
            Dict: 包含积分信息的字典
        """
        try:
            url = f"{self.base_url}/auth/credits"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.error(f"获取积分信息失败: {str(e)}")
            return {"error": str(e)}


_client_instance: Optional[OpenRouterClient] = None


def init_client(api_key: Optional[str] = None,
                model: str = "tngtech/deepseek-r1t2-chimera:free",
                base_url: Optional[str] = None) -> OpenRouterClient:
    """
    初始化OpenRouter客户端单例
    
    Args:
        api_key: OpenRouter API密钥
        model: 默认模型名称
        base_url: API基础URL
        
    Returns:
        OpenRouterClient: 客户端实例
    """
    global _client_instance
    
    if _client_instance is None:
        _client_instance = OpenRouterClient(api_key, model, base_url)
    else:
        if api_key:
            _client_instance.api_key = api_key
        if model:
            _client_instance.set_model(model)
        if base_url:
            _client_instance.base_url = base_url
    
    return _client_instance


def get_response(client: OpenRouterClient, user_message: str) -> str:
    """
    获取OpenRouter生成的回复（便捷函数）
    
    Args:
        client: 已初始化的客户端实例
        user_message: 用户消息
        
    Returns:
        str: 生成的回复文本
    """
    result = client.chat(user_message)
    return result["reply_text"]


def reset_client() -> None:
    """
    重置客户端实例
    """
    global _client_instance
    _client_instance = None


if __name__ == "__main__":
    print("OpenRouter客户端测试")
    print("=" * 50)
    
    try:
        client = init_client()
        print(f"使用模型: {client.model}")
        
        response = get_response(client, "你好，请介绍一下你自己")
        print(f"\n回复: {response}")
        
        print("\n" + "=" * 50)
        print("测试完成")
        
    except Exception as e:
        print(f"测试失败: {e}")
