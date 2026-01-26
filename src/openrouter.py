"""
OpenRouter服务集成模块

提供与OpenRouter服务交互的功能，支持通过OpenAI兼容的API调用多种大语言模型
"""

import os
import json
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta


class OpenRouterClient:
    """
    OpenRouter服务客户端类
    
    封装与OpenRouter服务的通信逻辑，提供消息发送和响应接收功能
    """
    
    def __init__(self, api_base_url: str = None, api_key: str = None, default_model: str = None):
        """
        初始化OpenRouter客户端
        
        Args:
            api_base_url: OpenRouter服务的基础URL，默认从环境变量获取
            api_key: API认证密钥，默认从环境变量获取
            default_model: 默认使用的模型名称，默认从环境变量获取
        """
        self.api_base_url = api_base_url or os.getenv("OPENROUTER_API_BASE_URL", "https://openrouter.ai/api/v1")
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.default_model = default_model or os.getenv("OPENROUTER_DEFAULT_MODEL", "deepseek/deepseek-r1")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://github.com/likecu/clawdbot-gemini",
            "X-Title": "Clawdbot-Gemini"
        })
        self.conversation_history: List[Dict[str, str]] = []
        self.last_request_time: Optional[datetime] = None
        self.request_interval: float = 1.0
    
    def _check_rate_limit(self) -> None:
        """
        检查并应用速率限制
        
        Raises:
            RuntimeError: 请求过于频繁时抛出
        """
        if self.last_request_time:
            elapsed = (datetime.now() - self.last_request_time).total_seconds()
            if elapsed < self.request_interval:
                raise RuntimeError(f"请求过于频繁，请等待 {self.request_interval - elapsed:.2f} 秒")
        self.last_request_time = datetime.now()
    
    def chat(self, message: str, model: str = None) -> str:
        """
        发送消息并获取回复
        
        Args:
            message: 用户发送的消息内容
            model: 使用的模型名称，为None时使用默认模型
            
        Returns:
            str: OpenRouter服务生成的回复文本
            
        Raises:
            ValueError: API密钥未配置时抛出
            Exception: API调用失败时抛出异常，包含详细错误信息
        """
        if not self.api_key:
            raise ValueError("OpenRouter API Key未配置，请设置OPENROUTER_API_KEY环境变量或传入api_key参数")
        
        self._check_rate_limit()
        
        url = f"{self.api_base_url}/chat/completions"
        
        selected_model = model or self.default_model
        
        payload = {
            "model": selected_model,
            "messages": self.conversation_history + [{"role": "user", "content": message}],
            "temperature": 0.7,
            "max_tokens": 4096
        }
        
        try:
            response = self.session.post(url, json=payload, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            
            assistant_message = data["choices"][0]["message"]["content"]
            
            self.conversation_history.append({"role": "user", "content": message})
            self.conversation_history.append({"role": "assistant", "content": assistant_message})
            
            if len(self.conversation_history) > 20:
                self.conversation_history = self.conversation_history[-20:]
            
            return assistant_message
            
        except requests.exceptions.Timeout:
            raise Exception("OpenRouter服务响应超时，请稍后重试")
        except requests.exceptions.RequestException as e:
            raise Exception(f"OpenRouter服务请求失败: {str(e)}")
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise Exception(f"OpenRouter服务响应格式错误: {str(e)}")
    
    def clear_history(self) -> None:
        """
        清空对话历史
        """
        self.conversation_history.clear()
    
    def get_history(self) -> List[Dict[str, str]]:
        """
        获取当前对话历史
        
        Returns:
            List[Dict]: 对话历史列表
        """
        return self.conversation_history.copy()
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """
        获取可用的模型列表
        
        Returns:
            List[Dict]: 模型信息列表，包含id、name、pricing等字段
            
        Raises:
            Exception: API调用失败时抛出异常
        """
        try:
            url = f"{self.api_base_url}/models"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return data.get("data", [])
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"获取模型列表失败: {str(e)}")
        except (KeyError, json.JSONDecodeError) as e:
            raise Exception(f"模型列表响应格式错误: {str(e)}")
    
    def get_model_info(self, model_id: str) -> Dict[str, Any]:
        """
        获取指定模型的详细信息
        
        Args:
            model_id: 模型ID
            
        Returns:
            Dict[str, Any]: 模型详细信息
            
        Raises:
            Exception: API调用失败时抛出异常
        """
        try:
            url = f"{self.api_base_url}/models/{model_id}"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            return data.get("data", {})
            
        except requests.exceptions.RequestException as e:
            raise Exception(f"获取模型信息失败: {str(e)}")
        except (KeyError, json.JSONDecodeError) as e:
            raise Exception(f"模型信息响应格式错误: {str(e)}")


_client_instance: Optional[OpenRouterClient] = None


def init_openrouter(api_base_url: str = None, api_key: str = None, default_model: str = None) -> OpenRouterClient:
    """
    初始化OpenRouter服务客户端
    
    Args:
        api_base_url: OpenRouter服务的基础URL
        api_key: API认证密钥
        default_model: 默认使用的模型名称
        
    Returns:
        OpenRouterClient: 初始化的客户端实例
        
    Raises:
        ValueError: 参数无效时抛出
    """
    global _client_instance
    
    if _client_instance is None:
        _client_instance = OpenRouterClient(api_base_url, api_key, default_model)
    else:
        if api_base_url:
            _client_instance.api_base_url = api_base_url
        if api_key:
            _client_instance.api_key = api_key
        if default_model:
            _client_instance.default_model = default_model
    
    return _client_instance


def get_response(client: OpenRouterClient, user_message: str, model: str = None) -> str:
    """
    获取OpenRouter生成的回复
    
    Args:
        client: 已初始化的OpenRouterClient实例
        user_message: 用户发送的消息内容
        model: 使用的模型名称，为None时使用默认模型
        
    Returns:
        str: OpenRouter生成的回复文本
        
    Raises:
        Exception: API调用失败时抛出异常
    """
    return client.chat(user_message, model)


def reset_openrouter_client() -> None:
    """
    重置OpenRouter客户端实例，用于重新初始化
    """
    global _client_instance
    _client_instance = None


if __name__ == "__main__":
    print("OpenRouter服务客户端测试")
    print("=" * 50)
    
    try:
        client = init_openrouter()
        
        if client.api_key:
            print("API密钥已配置")
            
            try:
                models = client.get_available_models()
                print(f"获取到 {len(models)} 个可用模型")
                for model in models[:5]:
                    print(f"  - {model.get('id', 'unknown')}")
            except Exception as e:
                print(f"获取模型列表失败（可能是网络问题）: {e}")
            
            response = get_response(client, "你好，请介绍一下你自己")
            print(f"\n回复: {response}")
        else:
            print("错误: OPENROUTER_API_KEY未配置")
            
    except Exception as e:
        print(f"测试失败: {e}")
