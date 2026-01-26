"""
OpenCode API接口封装模块

提供与OpenCode模型交互的功能，包括初始化、生成内容等操作
"""

import requests
from typing import Optional, Any, Dict, List
import os
import json
import time


class OpenCodeClient:
    """
    OpenCode 客户端类

    提供与 OpenCode 服务交互的完整功能
    """

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, max_retries: int = 3):
        """
        初始化 OpenCode 客户端

        Args:
            api_key: API密钥，如果为None则从环境变量获取
            base_url: API基础URL，如果为None则从环境变量获取
            max_retries: 最大重试次数，默认3次
        """
        self.api_key = api_key or os.getenv("OPENCODE_API_KEY")
        self.base_url = base_url or os.getenv("OPENCODE_API_BASE_URL")
        self.max_retries = max_retries
        self.timeout = 30

        if not self.api_key:
            raise ValueError("OpenCode API Key未配置，请设置OPENCODE_API_KEY环境变量或传入api_key参数")

        if not self.base_url:
            raise ValueError("OpenCode API Base URL未配置，请设置OPENCODE_API_BASE_URL环境变量或传入base_url参数")

    def _make_request(self, endpoint: str, payload: Dict, method: str = "POST") -> Dict:
        """
        发起API请求（带重试机制）

        Args:
            endpoint: API端点
            payload: 请求数据
            method: HTTP方法

        Returns:
            Dict: API响应

        Raises:
            Exception: 所有重试失败后抛出异常
        """
        url = f"{self.base_url}{endpoint}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }

        last_exception = None

        for attempt in range(self.max_retries):
            try:
                if method.upper() == "POST":
                    response = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
                else:
                    response = requests.get(url, headers=headers, timeout=self.timeout)

                response.raise_for_status()
                return response.json()

            except requests.exceptions.ConnectionError as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    time.sleep(wait_time)
                    continue
                raise Exception(f"无法连接到 OpenCode 服务: {str(e)}")

            except requests.exceptions.Timeout as e:
                last_exception = e
                if attempt < self.max_retries - 1:
                    wait_time = (attempt + 1) * 2
                    time.sleep(wait_time)
                    continue
                raise Exception(f"OpenCode 服务超时: {str(e)}")

            except requests.exceptions.HTTPError as e:
                status_code = e.response.status_code
                if status_code == 401:
                    raise Exception(f"OpenCode 认证失败: 无效的API密钥")
                elif status_code == 429:
                    if attempt < self.max_retries - 1:
                        wait_time = (attempt + 1) * 5
                        time.sleep(wait_time)
                        continue
                    raise Exception(f"OpenCode 请求频率超限，请稍后重试")
                else:
                    raise Exception(f"OpenCode HTTP错误 ({status_code}): {str(e)}")

            except requests.RequestException as e:
                raise Exception(f"OpenCode API调用失败: {str(e)}")

        raise Exception(f"OpenCode 请求失败，已重试 {self.max_retries} 次: {str(last_exception)}")

    def chat(self, message: str, history: Optional[List[Dict]] = None, model: str = "opencode-1.0",
             temperature: float = 0.7, max_tokens: int = 1000) -> str:
        """
        发送聊天消息

        Args:
            message: 用户消息
            history: 对话历史
            model: 模型名称
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            str: AI生成的回复
        """
        messages = []

        if history:
            for h in history:
                messages.append({
                    "role": h.get("role", "user"),
                    "content": h.get("content", "")
                })

        messages.append({
            "role": "user",
            "content": message
        })

        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }

        result = self._make_request("/chat/completions", payload)
        return result["choices"][0]["message"]["content"]

    def execute_code(self, code: str, language: str = "python") -> str:
        """
        执行代码

        Args:
            code: 要执行的代码
            language: 编程语言

        Returns:
            str: 执行结果
        """
        messages = [
            {
                "role": "user",
                "content": f"请运行以下 {language} 代码：\n```{language}\n{code}\n```"
            }
        ]

        payload = {
            "model": "opencode-1.0",
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 2000
        }

        result = self._make_request("/chat/completions", payload)
        return result["choices"][0]["message"]["content"]

    def list_models(self) -> List[Dict]:
        """
        获取可用模型列表

        Returns:
            List[Dict]: 模型列表
        """
        result = self._make_request("/models", {}, method="GET")
        return result.get("data", [])

    def health_check(self) -> Dict:
        """
        健康检查

        Returns:
            Dict: 健康状态信息
        """
        result = self._make_request("/health", {}, method="GET")
        return result


def init_opencode(api_key: Optional[str] = None, base_url: Optional[str] = None) -> OpenCodeClient:
    """
    初始化OpenCode客户端

    Args:
        api_key: OpenCode API密钥，如果为None则从环境变量OPENCODE_API_KEY获取
        base_url: OpenCode API基础URL，如果为None则从环境变量OPENCODE_API_BASE_URL获取

    Returns:
        OpenCodeClient: 初始化的客户端实例

    Raises:
        ValueError: 当配置缺失时抛出
    """
    return OpenCodeClient(api_key=api_key, base_url=base_url)


def get_response(config: OpenCodeClient, user_message: str, model: str = "opencode-1.0") -> str:
    """
    获取OpenCode生成的回复（兼容旧接口）

    Args:
        config: OpenCodeClient实例
        user_message: 用户发送的消息内容
        model: 模型名称，默认为opencode-1.0

    Returns:
        str: OpenCode生成的回复文本

    Raises:
        Exception: API调用失败时抛出异常
    """
    return config.chat(user_message, model=model)


def get_response_with_history(config: OpenCodeClient,
                              user_message: str,
                              history: Optional[List[Dict]] = None,
                              model: str = "opencode-1.0") -> str:
    """
    获取OpenCode生成的回复（支持对话历史）

    Args:
        config: OpenCodeClient实例
        user_message: 用户发送的消息内容
        history: 对话历史列表，每条记录为{'role': 'user'/'assistant', 'content': 'text'}
        model: 模型名称，默认为opencode-1.0

    Returns:
        str: OpenCode生成的回复文本

    Raises:
        Exception: API调用失败时抛出异常
    """
    return config.chat(user_message, history=history, model=model)
