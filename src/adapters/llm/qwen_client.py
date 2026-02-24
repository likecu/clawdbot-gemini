"""
Qwen Portal OAuth 客户端模块

提供与通义千问（Qwen）Portal的OAuth认证和API调用功能
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field

import requests


QWEN_OAUTH_BASE_URL = "https://chat.qwen.ai"
QWEN_OAUTH_TOKEN_ENDPOINT = f"{QWEN_OAUTH_BASE_URL}/api/v1/oauth2/token"
QWEN_OAUTH_CLIENT_ID = "f0304373b74a44d2b584a3fb70ca9e56"
QWEN_API_BASE_URL = "https://chat.qwen.ai/api/v1"


@dataclass
class QwenCredentials:
    """
    Qwen OAuth 凭证类
    
    存储和管理Qwen Portal的OAuth访问令牌和刷新令牌
    """
    access: str = ""
    refresh: str = ""
    expires: int = 0
    
    def is_valid(self) -> bool:
        """
        检查凭证是否有效
        
        Returns:
            bool: 凭证是否有效
        """
        if not self.access or not self.refresh:
            return False
        if self.expires <= 0:
            return True
        return datetime.now().timestamp() < self.expires
    
    def needs_refresh(self) -> bool:
        """
        检查凭证是否需要刷新
        
        Returns:
            bool: 是否需要刷新
        """
        if not self.is_valid():
            return True
        if self.expires <= 0:
            return False
        return datetime.now().timestamp() > self.expires - 300


class QwenPortalClient:
    """
    Qwen Portal 客户端类
    
    提供与Qwen Portal的OAuth认证和模型API调用功能
    """
    
    def __init__(self, 
                 credentials_path: Optional[str] = None,
                 credentials: Optional[QwenCredentials] = None,
                 model: str = "qwen-turbo"):
        """
        初始化Qwen Portal客户端
        
        Args:
            credentials_path: 凭证文件路径
            credentials: QwenCredentials对象（可选）
            model: 默认使用的模型名称
        """
        self.logger = logging.getLogger(__name__)
        self.model = model
        self.credentials_path = credentials_path
        self._credentials = credentials
        self.session = requests.Session()
        self.session.headers.update({
            "Content-Type": "application/json",
            "Accept": "application/json"
        })
        
        self._last_request_time: Optional[datetime] = None
        self._min_request_interval = 1.0
        self.conversation_history: List[Dict[str, str]] = []
    
    @property
    def credentials(self) -> Optional[QwenCredentials]:
        """
        获取当前凭证
        
        Returns:
            QwenCredentials: 当前凭证对象
        """
        if self._credentials is None and self.credentials_path:
            self._credentials = self._load_credentials()
        return self._credentials
    
    @credentials.setter
    def credentials(self, value: QwenCredentials) -> None:
        """
        设置凭证
        
        Args:
            value: QwenCredentials对象
        """
        self._credentials = value
        if self.credentials_path:
            self._save_credentials(value)
    
    def _load_credentials(self) -> Optional[QwenCredentials]:
        """
        从文件加载凭证
        
        Returns:
            QwenCredentials: 加载的凭证对象，失败返回None
        """
        if not self.credentials_path or not os.path.exists(self.credentials_path):
            self.logger.warning("凭证文件不存在")
            return None
        
        try:
            with open(self.credentials_path, 'r') as f:
                data = json.load(f)
            return QwenCredentials(
                access=data.get('access', ''),
                refresh=data.get('refresh', ''),
                expires=data.get('expires', 0)
            )
        except Exception as e:
            self.logger.error(f"加载凭证失败: {str(e)}")
            return None
    
    def _save_credentials(self, credentials: QwenCredentials) -> bool:
        """
        保存凭证到文件
        
        Args:
            credentials: QwenCredentials对象
            
        Returns:
            bool: 是否保存成功
        """
        if not self.credentials_path:
            self.logger.warning("未配置凭证文件路径")
            return False
        
        try:
            os.makedirs(os.path.dirname(self.credentials_path), exist_ok=True)
            with open(self.credentials_path, 'w') as f:
                json.dump({
                    'access': credentials.access,
                    'refresh': credentials.refresh,
                    'expires': credentials.expires
                }, f, indent=2)
            os.chmod(self.credentials_path, 0o600)
            self.logger.info("凭证已保存")
            return True
        except Exception as e:
            self.logger.error(f"保存凭证失败: {str(e)}")
            return False
    
    def _check_rate_limit(self) -> None:
        """
        检查并应用速率限制
        """
        if self._last_request_time:
            elapsed = (datetime.now() - self._last_request_time).total_seconds()
            if elapsed < self._min_request_interval:
                import time
                wait_time = self._min_request_interval - elapsed
                self.logger.warning(f"请求过于频繁，等待 {wait_time:.2f} 秒")
                time.sleep(wait_time)
        self._last_request_time = datetime.now()
    
    def authenticate(self, refresh_token: Optional[str] = None) -> QwenCredentials:
        """
        使用刷新令牌进行OAuth认证
        
        Args:
            refresh_token: 刷新令牌
            
        Returns:
            QwenCredentials: 认证后的凭证对象
            
        Raises:
            ValueError: 未提供有效的刷新令牌
            Exception: 认证失败
        """
        token = refresh_token or (self.credentials.refresh if self.credentials else None)
        
        if not token:
            raise ValueError(
                "Qwen OAuth refresh token missing. "
                "Please login via: https://chat.qwen.ai"
            )
        
        self.logger.info("正在刷新Qwen OAuth凭证...")
        
        payload = {
            "grant_type": "refresh_token",
            "refresh_token": token,
            "client_id": QWEN_OAUTH_CLIENT_ID
        }
        
        try:
            response = requests.post(
                QWEN_OAUTH_TOKEN_ENDPOINT,
                data=payload,
                timeout=30
            )
            
            if not response.ok:
                error_text = response.text
                if response.status_code == 400:
                    raise Exception(
                        "Qwen OAuth refresh token expired or invalid. "
                        "Please re-authenticate at https://chat.qwen.ai"
                    )
                raise Exception(f"Qwen OAuth refresh failed: {error_text}")
            
            token_data = response.json()
            
            if not token_data.get('access_token'):
                raise Exception("Qwen OAuth response missing access token")
            
            credentials = QwenCredentials(
                access=token_data['access_token'],
                refresh=token_data.get('refresh_token', token),
                expires=datetime.now().timestamp() + token_data.get('expires_in', 3600)
            )
            
            self.credentials = credentials
            self.logger.info("Qwen OAuth认证成功")
            
            return credentials
            
        except requests.exceptions.RequestException as e:
            error_msg = f"Qwen OAuth认证网络错误: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
    
    def ensure_valid_credentials(self) -> QwenCredentials:
        """
        确保拥有有效的访问凭证
        
        Returns:
            QwenCredentials: 有效的凭证对象
            
        Raises:
            Exception: 无法获取有效凭证
        """
        if not self.credentials:
            raise Exception(
                "Qwen credentials not configured. "
                "Please authenticate at https://chat.qwen.ai"
            )
        
        if self.credentials.needs_refresh():
            return self.authenticate()
        
        return self.credentials
    
    def chat(self, 
             message: str,
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
        
        credentials = self.ensure_valid_credentials()
        
        url = f"{QWEN_API_BASE_URL}/chat/completions"
        
        headers = {
            "Authorization": f"Bearer {credentials.access}",
            "Content-Type": "application/json"
        }
        
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
            self.logger.info(f"调用Qwen API，模型: {model or self.model}")
            
            response = self.session.post(url, json=payload, headers=headers, timeout=120)
            response.raise_for_status()
            
            data = response.json()
            
            assistant_message = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            
            self.conversation_history.append({"role": "user", "content": message})
            self.conversation_history.append({"role": "assistant", "content": assistant_message})
            
            max_history = 20
            if len(self.conversation_history) > max_history * 2:
                self.conversation_history = self.conversation_history[-max_history * 2:]
            
            self.logger.info(f"Qwen回复成功，消耗tokens: {usage.get('total_tokens', 'unknown')}")
            
            return {
                "reply_text": assistant_message,
                "usage": usage,
                "model": data.get("model", self.model)
            }
            
        except requests.exceptions.Timeout:
            error_msg = "Qwen服务响应超时"
            self.logger.error(error_msg)
            raise Exception(error_msg)
        except requests.exceptions.RequestException as e:
            error_msg = f"Qwen服务请求失败: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            error_msg = f"Qwen服务响应格式错误: {str(e)}"
            self.logger.error(error_msg)
            raise Exception(error_msg)
    
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


_client_instance: Optional[QwenPortalClient] = None


def init_client(credentials_path: Optional[str] = None,
                credentials: Optional[QwenCredentials] = None,
                model: str = "qwen-turbo") -> QwenPortalClient:
    """
    初始化Qwen Portal客户端单例
    
    Args:
        credentials_path: 凭证文件路径
        credentials: QwenCredentials对象
        model: 默认模型名称
        
    Returns:
        QwenPortalClient: 客户端实例
    """
    global _client_instance
    
    if _client_instance is None:
        _client_instance = QwenPortalClient(credentials_path, credentials, model)
    else:
        if credentials_path:
            _client_instance.credentials_path = credentials_path
        if credentials:
            _client_instance.credentials = credentials
        if model:
            _client_instance.set_model(model)
    
    return _client_instance


def get_response(client: QwenPortalClient, user_message: str) -> str:
    """
    获取Qwen生成的回复（便捷函数）
    
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
    print("Qwen Portal客户端测试")
    print("=" * 50)
    
    try:
        client = init_client(
            credentials_path="/tmp/qwen_credentials.json",
            model="qwen-turbo"
        )
        
        if client.credentials:
            print(f"已加载凭证，有效性: {client.credentials.is_valid()}")
        else:
            print("未找到凭证文件，需要先进行OAuth认证")
            print("请访问 https://chat.qwen.ai 进行登录授权")
            print(f"需要获取 refresh_token 并调用 client.authenticate('your_refresh_token')")
        print(f"使用模型: {client.model}")
        
        print("\n" + "=" * 50)
        print("测试完成")
        
    except Exception as e:
        print(f"测试失败: {e}")
