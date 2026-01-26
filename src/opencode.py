"""
OpenCode服务集成模块

提供与官方OpenCode服务交互的功能，支持通过OpenAI兼容的API调用Gemini模型
"""

import os
import json
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta


class OpenCodeClient:
    """
    OpenCode服务客户端类
    
    封装与OpenCode服务的通信逻辑，提供消息发送和响应接收功能
    """
    
    def __init__(self, api_base_url: str = None, api_key: str = None):
        """
        初始化OpenCode客户端
        
        Args:
            api_base_url: OpenCode服务的基础URL，默认从环境变量获取
            api_key: API认证密钥，默认从环境变量获取
        """
        self.api_base_url = api_base_url or os.getenv("OPENCODE_API_BASE_URL", "http://opencode_service:8080/v1")
        self.api_key = api_key or os.getenv("OPENCODE_API_KEY", "my_internal_secret_2024")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
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
    
    def chat(self, message: str, model: str = "deepseek/deepseek-r1") -> str:
        """
        发送消息并获取回复
        
        Args:
            message: 用户发送的消息内容
            model: 使用的模型名称，默认deepseek/deepseek-r1 (通过OpenRouter)
            
        Returns:
            str: OpenCode服务生成的回复文本
            
        Raises:
            Exception: API调用失败时抛出异常，包含详细错误信息
        """
        self._check_rate_limit()
        
        url = f"{self.api_base_url}/chat/completions"
        
        payload = {
            "model": model,
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
            raise Exception("OpenCode服务响应超时，请稍后重试")
        except requests.exceptions.RequestException as e:
            raise Exception(f"OpenCode服务请求失败: {str(e)}")
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise Exception(f"OpenCode服务响应格式错误: {str(e)}")
    
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
    
    def health_check(self) -> bool:
        """
        检查OpenCode服务健康状态
        
        Returns:
            bool: 服务健康返回True，否则返回False
        """
        try:
            url = f"{self.api_base_url.replace('/v1', '')}/health"
            response = self.session.get(url, timeout=10)
            return response.status_code == 200
        except Exception:
            return False


_client_instance: Optional[OpenCodeClient] = None


def init_opencode(api_base_url: str = None, api_key: str = None) -> OpenCodeClient:
    """
    初始化OpenCode服务客户端
    
    Args:
        api_base_url: OpenCode服务的基础URL
        api_key: API认证密钥
        
    Returns:
        OpenCodeClient: 初始化的客户端实例
        
    Raises:
        ValueError: 参数无效时抛出
    """
    global _client_instance
    
    if _client_instance is None:
        _client_instance = OpenCodeClient(api_base_url, api_key)
    else:
        if api_base_url:
            _client_instance.api_base_url = api_base_url
        if api_key:
            _client_instance.api_key = api_key
    
    return _client_instance


def get_response(client: OpenCodeClient, user_message: str) -> str:
    """
    获取OpenCode生成的回复
    
    Args:
        client: 已初始化的OpenCodeClient实例
        user_message: 用户发送的消息内容
        
    Returns:
        str: OpenCode生成的回复文本
        
    Raises:
        Exception: API调用失败时抛出异常
    """
    return client.chat(user_message)


def reset_opencode_client() -> None:
    """
    重置OpenCode客户端实例，用于重新初始化
    """
    global _client_instance
    _client_instance = None


if __name__ == "__main__":
    print("OpenCode服务客户端测试")
    print("=" * 50)
    
    try:
        client = init_opencode()
        
        if client.health_check():
            print("OpenCode服务健康检查通过")
            
            response = get_response(client, "你好，请介绍一下你自己")
            print(f"\n回复: {response}")
        else:
            print("警告: OpenCode服务健康检查失败")
            
    except Exception as e:
        print(f"测试失败: {e}")
