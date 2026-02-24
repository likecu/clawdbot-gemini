"""
OpenRouter API集成模块

提供与OpenRouter服务的交互功能，支持多种AI模型的统一调用接口
"""

import os
import json
import requests
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta


class OpenRouterClient:
    """
    OpenRouter服务客户端类

    封装与OpenRouter API的通信逻辑，提供消息发送和响应接收功能
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "tngtech/deepseek-r1t2-chimera:free"):
        """
        初始化OpenRouter客户端

        Args:
            api_key: OpenRouter API密钥，默认从环境变量获取
            model: 使用的模型名称，默认为tngtech/deepseek-r1t2-chimera:free
        """
        self.api_key = api_key or os.getenv("OPENROUTER_API_KEY")
        self.model = model
        self.base_url = "https://openrouter.ai/api/v1"
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": os.getenv("APP_URL", "http://localhost:8000"),
            "X-Title": os.getenv("APP_NAME", "Clawdbot-Gemini")
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

    def chat(self, message: str, model: Optional[str] = None, system_prompt: Optional[str] = None) -> str:
        """
        发送消息并获取回复

        Args:
            message: 用户发送的消息内容
            model: 使用的模型名称，如果为None则使用默认模型
            system_prompt: 系统提示词，可选

        Returns:
            str: OpenRouter服务生成的回复文本

        Raises:
            Exception: API调用失败时抛出异常，包含详细错误信息
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

    def generate_content(self, prompt: str, model: Optional[str] = None, **kwargs) -> str:
        """
        生成内容（简化接口）

        Args:
            prompt: 提示词
            model: 使用的模型名称
            **kwargs: 其他参数（temperature、max_tokens等）

        Returns:
            str: 生成的内容
        """
        self._check_rate_limit()

        url = f"{self.base_url}/chat/completions"

        messages = [{"role": "user", "content": prompt}]

        payload = {
            "model": model or self.model,
            "messages": messages,
            **kwargs
        }

        try:
            response = self.session.post(url, json=payload, timeout=60)
            response.raise_for_status()

            data = response.json()
            return data["choices"][0]["message"]["content"]

        except Exception as e:
            raise Exception(f"内容生成失败: {str(e)}")

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
            raise Exception(f"获取模型列表失败: {str(e)}")

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
            raise Exception(f"获取积分信息失败: {str(e)}")


_client_instance: Optional[OpenRouterClient] = None


def init_openrouter(api_key: Optional[str] = None, model: str = "tngtech/deepseek-r1t2-chimera:free") -> OpenRouterClient:
    """
    初始化OpenRouter服务客户端

    Args:
        api_key: OpenRouter API密钥
        model: 默认使用的模型名称

    Returns:
        OpenRouterClient: 初始化的客户端实例

    Raises:
        ValueError: 参数无效时抛出
    """
    global _client_instance

    if _client_instance is None:
        _client_instance = OpenRouterClient(api_key, model)
    else:
        if api_key:
            _client_instance.api_key = api_key
        if model:
            _client_instance.model = model

    return _client_instance


def get_response(client: OpenRouterClient, user_message: str) -> str:
    """
    获取OpenRouter生成的回复

    Args:
        client: 已初始化的OpenRouterClient实例
        user_message: 用户发送的消息内容

    Returns:
        str: OpenRouter生成的回复文本

    Raises:
        Exception: API调用失败时抛出异常
    """
    return client.chat(user_message)


def generate_code(client: OpenRouterClient, requirement: str, language: str = "python") -> str:
    """
    生成代码

    Args:
        client: 已初始化的OpenRouterClient实例
        requirement: 代码需求描述
        language: 编程语言

    Returns:
        str: 生成的代码
    """
    prompt = f"""请用{language}语言实现以下需求：

{requirement}

要求：
1. 代码简洁、高效
2. 添加必要的注释
3. 处理可能的异常情况
4. 返回完整的可运行代码
"""

    return client.chat(prompt)


def explain_code(client: OpenRouterClient, code: str, language: str = "python") -> str:
    """
    解释代码

    Args:
        client: 已初始化的OpenRouterClient实例
        code: 要解释的代码
        language: 编程语言

    Returns:
        str: 代码解释
    """
    prompt = f"""请解释以下{language}代码：

```{language}
{code}
```

请详细说明：
1. 代码的功能
2. 关键逻辑
3. 可能的问题和优化建议
"""

    return client.chat(prompt)


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

        print(f"使用模型: {client.model}")
        print(f"API基础URL: {client.base_url}")

        response = get_response(client, "你好，请介绍一下你自己")
        print(f"\n回复: {response}")

        print("\n" + "=" * 50)
        print("测试完成")

    except Exception as e:
        print(f"测试失败: {e}")
