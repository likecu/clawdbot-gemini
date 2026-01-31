"""
智能体核心模块

实现OpenCode范式的智能体协调器
"""

import logging
from typing import Optional, Dict, Any, List
from enum import Enum

from .session import get_session_manager, SessionManager
from .prompt import get_prompt_builder, PromptBuilder


class AgentMode(Enum):
    """
    智能体工作模式
    """
    CONVERSATION = "conversation"  # 对话模式
    CODE_GENERATION = "code_generation"  # 代码生成模式
    CODE_EXPLANATION = "code_explanation"  # 代码解释模式
    DEBUGGING = "debugging"  # 调试模式


class Agent:
    """
    智能体核心类
    
    模仿OpenCode的Plan -> Build两阶段思考模式，协调LLM调用和工具执行
    """
    
    def __init__(self, llm_client,
                 session_manager: Optional[SessionManager] = None,
                 prompt_builder: Optional[PromptBuilder] = None):
        """
        初始化智能体
        
        Args:
            llm_client: LLM客户端实例
            session_manager: 会话管理器实例
            prompt_builder: 提示词构建器实例
        """
        self.llm_client = llm_client
        self.session_manager = session_manager or get_session_manager()
        self.prompt_builder = prompt_builder or get_prompt_builder()
        
        self.logger = logging.getLogger(__name__)
        self.current_mode = AgentMode.CONVERSATION
        self.thinking_enabled = True  # 是否显示思考过程
    
    def process_message(self, user_id: str,
                        chat_id: str,
                        message: str) -> Dict[str, Any]:
        """
        处理用户消息
        
        Args:
            user_id: 用户ID
            chat_id: 聊天会话ID
            message: 用户消息
            
        Returns:
            Dict: 包含响应文本和处理元信息的字典
        """
        session_id = f"{user_id}:{chat_id}"
        
        try:
            self.logger.info(f"处理消息: user={user_id}, chat={chat_id}, message={message[:50]}...")
            
            # 检测用户意图
            intent = self._detect_intent(message)
            mode = self._get_mode_from_intent(intent)
            self.current_mode = mode
            
            # 构建提示词
            history = self.session_manager.get_history(session_id)
            prompt_messages = self.prompt_builder.build_conversation_prompt(
                history, message, include_system=True
            )
            
            # 为 OpenClaw 添加 session_id 到消息列表
            # 将 chat_id 转换为 OpenClaw 兼容格式
            # 格式：qq_<user_id>_<message_type>
            openclaw_session_id = chat_id.replace(":", "_").replace("qq_qq_", "qq_")
            if len(prompt_messages) > 0 and isinstance(prompt_messages[0], dict):
                # 在第一条消息中添加 session_id
                prompt_messages[0]["session_id"] = openclaw_session_id
            
            self.logger.debug(f"OpenClaw session ID: {openclaw_session_id}")
            
            # 调用LLM
            response = self._call_llm(prompt_messages, mode)
            
            # 保存到会话历史
            self.session_manager.add_user_message(session_id, message)
            self.session_manager.add_assistant_message(session_id, response["text"])
            
            self.logger.info(f"响应生成成功: {response['text'][:50]}...")
            
            return {
                "success": True,
                "text": response["text"],
                "mode": mode.value,
                "usage": response.get("usage", {})
            }
            
        except Exception as e:
            self.logger.error(f"处理消息失败: {str(e)}")
            return {
                "success": False,
                "text": f"抱歉，处理您消息时出现了问题：{str(e)}",
                "mode": self.current_mode.value,
                "error": str(e)
            }
    
    def _detect_intent(self, message: str) -> str:
        """
        检测用户意图
        
        Args:
            message: 用户消息
            
        Returns:
            str: 意图类型
        """
        message_lower = message.lower().strip()
        
        # 代码生成相关关键词
        code_keywords = ["写代码", "生成代码", "实现", "create", "write code", "implement"]
        if any(kw in message_lower for kw in code_keywords):
            return "code_generation"
        
        # 代码解释相关关键词
        explain_keywords = ["解释", "说明", "explain", "what does", "这段代码"]
        if any(kw in message_lower for kw in explain_keywords):
            return "code_explanation"
        
        # 调试相关关键词
        debug_keywords = ["报错", "错误", "bug", "debug", "修复", "问题"]
        if any(kw in message_lower for kw in debug_keywords):
            return "debugging"
        
        return "conversation"
    
    def _get_mode_from_intent(self, intent: str) -> AgentMode:
        """
        根据意图获取工作模式
        
        Args:
            intent: 意图类型
            
        Returns:
            AgentMode: 工作模式
        """
        intent_mode_map = {
            "code_generation": AgentMode.CODE_GENERATION,
            "code_explanation": AgentMode.CODE_EXPLANATION,
            "debugging": AgentMode.DEBUGGING
        }
        
        return intent_mode_map.get(intent, AgentMode.CONVERSATION)
    
    def _call_llm(self, messages: List[Dict[str, str]],
                  mode: AgentMode) -> Dict[str, Any]:
        """
        调用LLM生成响应
        
        Args:
            messages: 消息列表
            mode: 工作模式
            
        Returns:
            Dict: 包含响应文本和使用信息的字典
        """
        # 检查是否是 clawdbot 客户端（有 async chat 方法）
        import inspect
        import asyncio
        
        if hasattr(self.llm_client, 'chat') and inspect.iscoroutinefunction(self.llm_client.chat):
            # clawdbot 客户端（async）
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 已经在事件循环中，需要在新线程中运行
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, self.llm_client.chat(messages))
                    response_text = future.result()
            else:
                # 没有运行的事件循环，直接运行
                response_text = asyncio.run(self.llm_client.chat(messages))
            
            return {
                "text": response_text,
                "usage": {}
            }
        elif hasattr(self.llm_client, 'chat_with_thinking'):
            # 支持推理模型的客户端
            response = self.llm_client.chat_with_thinking(
                message=messages[-1]["content"],
                system_prompt=messages[0]["content"] if messages[0]["role"] == "system" else None
            )
            
            thinking = response.get("thinking", "")
            reply_text = response.get("reply_text", "")
            
            if thinking and self.thinking_enabled:
                self.logger.debug(f"模型思考过程: {thinking[:200]}...")
            
            return {
                "text": reply_text,
                "thinking": thinking,
                "usage": response.get("usage", {})
            }
        else:
            # 标准聊天客户端
            import json
            content = json.dumps(messages)
            response = self.llm_client.chat(content)
            
            return {
                "text": response.get("reply_text", str(response)),
                "usage": response.get("usage", {})
            }
    
    def generate_code(self, requirement: str,
                      language: str = "python",
                      constraints: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        生成代码
        
        Args:
            requirement: 代码需求描述
            language: 编程语言
            constraints: 约束条件列表
            
        Returns:
            Dict: 包含代码和元信息的字典
        """
        prompt = self.prompt_builder.build_code_generation_prompt(
            requirement, language, constraints
        )
        
        try:
            response = self.llm_client.chat(prompt)
            
            return {
                "success": True,
                "code": response.get("reply_text", str(response)),
                "language": language
            }
            
        except Exception as e:
            self.logger.error(f"代码生成失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "code": ""
            }
    
    def explain_code(self, code: str,
                     language: str = "python") -> Dict[str, Any]:
        """
        解释代码
        
        Args:
            code: 要解释的代码
            language: 编程语言
            
        Returns:
            Dict: 包含解释内容的字典
        """
        prompt = self.prompt_builder.build_code_explanation_prompt(code, language)
        
        try:
            response = self.llm_client.chat(prompt)
            
            return {
                "success": True,
                "explanation": response.get("reply_text", str(response))
            }
            
        except Exception as e:
            self.logger.error(f"代码解释失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "explanation": ""
            }
    
    def debug_code(self, code: str,
                   error_message: str,
                   language: str = "python") -> Dict[str, Any]:
        """
        调试代码
        
        Args:
            code: 有问题的代码
            error_message: 错误信息
            language: 编程语言
            
        Returns:
            Dict: 包含调试结果的字典
        """
        prompt = self.prompt_builder.build_debug_prompt(code, error_message, language)
        
        try:
            response = self.llm_client.chat(prompt)
            
            return {
                "success": True,
                "suggestion": response.get("reply_text", str(response))
            }
            
        except Exception as e:
            self.logger.error(f"代码调试失败: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "suggestion": ""
            }
    
    def clear_memory(self, user_id: str, chat_id: str) -> None:
        """
        清空对话记忆
        
        Args:
            user_id: 用户ID
            chat_id: 聊天会话ID
        """
        session_id = f"{user_id}:{chat_id}"
        self.session_manager.clear_session(session_id)
        self.logger.info(f"已清空会话记忆: {session_id}")
    
    def set_mode(self, mode: AgentMode) -> None:
        """
        设置工作模式
        
        Args:
            mode: 工作模式
        """
        self.current_mode = mode
        self.logger.info(f"智能体模式已切换为: {mode.value}")
    
    def enable_thinking_display(self, enabled: bool) -> None:
        """
        设置是否显示思考过程
        
        Args:
            enabled: 是否显示
        """
        self.thinking_enabled = enabled


# 创建智能体的便捷函数
def create_agent(llm_client,
                 session_manager: Optional[SessionManager] = None,
                 prompt_builder: Optional[PromptBuilder] = None) -> Agent:
    """
    创建智能体实例
    
    Args:
        llm_client: LLM客户端实例
        session_manager: 会话管理器实例
        prompt_builder: 提示词构建器实例
        
    Returns:
        Agent: 智能体实例
    """
    return Agent(llm_client, session_manager, prompt_builder)
