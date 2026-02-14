"""
智能体核心模块

实现OpenCode范式的智能体协调器
"""

import logging
from typing import Optional, Dict, Any, List
from enum import Enum

from .session import get_session_manager, SessionManager
from .prompt import get_prompt_builder, PromptBuilder
from .memory import get_memory_bank, MemoryBank


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
        self.memory_bank = get_memory_bank()
        
        self.logger = logging.getLogger(__name__)
        self.current_mode = AgentMode.CONVERSATION
        self.thinking_enabled = True  # 是否显示思考过程
    
    async def process_message(self, user_id: str,
                        chat_id: str,
                        message: str,
                        callback_session_id: Optional[str] = None) -> Dict[str, Any]:
    async def process_message(self, user_id: str,
                        chat_id: str,
                        message: str,
                        callback_session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        核心消息处理函数
        
        负责：
        1. 意图检测 (Intent Detection)
        2. 上下文管理 (Session Management)
        3. 提示词构建 (Prompt Construction)
        4. LLM 调用 (LLM Invocation)
        5. 结果返回 (Response Generation)

        :param user_id: 用户唯一标识（格式: platform:user_id）
        :param chat_id: 会话唯一标识（格式: platform:user:user_id:DATE，用于隔离记忆）
        :param message: 用户发送的原始文本消息
        :param callback_session_id: 用于回调路由的ID（格式: platform:type:chat_id），若为空则默认使用 chat_id
        
        :return: Dict 包含响应文本、状态码、usage信息和调试信息
        """
        # 直接使用 chat_id 作为会话键（已经是按用户隔离的格式）
        session_id = chat_id
        
        try:
            self.logger.info(f"处理消息: user={user_id}, session={session_id}, message={message[:50]}...")
            
            # [新增] 处理重置指令
            if message.strip() in ["/reset", "/clear", "重置", "清除记忆"]:
                self.session_manager.clear_session(session_id)
                return {
                    "success": True,
                    "text": "记忆已重擦除。我是全新的小汉堡，我们重新开始吧！",
                    "mode": "conversation",
                    "usage": {}
                }
            
            # 检测用户意图
            intent = self._detect_intent(message)
            mode = self._get_mode_from_intent(intent)
            self.current_mode = mode
            
            # 构建提示词
            # 1. 获取全局人格
            base_system = self.prompt_builder.system_prompt
            
            # 2. 获取用户专属记忆
            real_user_id = user_id.split(":")[-1] # extract user id part if formatted like platform:user_id
            if ":" in user_id: 
                 # user_id passed is "qq:123456", memory needs unique ID. Using full string is fine too but user requested per user.
                 real_user_id = user_id 
            
            user_memory = self.memory_bank.get_user_memory(real_user_id)
            
            # 3. 动态合并
            # [Optimization] 注入强身份边界，防止串台
            strict_session_context = (
                f"\n\n## ⚠️ Session Context Enforcement (CRITICAL)\n"
                f"Current Session User ID: {real_user_id}\n"
                f"You are communicating EXCLUSIVELY with the user identified as '{real_user_id}'.\n"
                f"Do NOT reference or confuse this user with any other users (e.g. 'Xiao Yang' vs 'Han Zong') unless explicitly asked.\n"
                f"Treat this session's memory as isolated."
            )

            if user_memory:
                full_system_prompt = f"{base_system}\n{strict_session_context}\n\n## 关于该用户的长期记忆 (Always Remember)\n{user_memory}"
            else:
                full_system_prompt = f"{base_system}\n{strict_session_context}"

            history = self.session_manager.get_history(session_id)
            prompt_messages = self.prompt_builder.build_conversation_prompt(
                history, message, include_system=True, system_prompt_override=full_system_prompt
            )
            
            # 在第一条消息中注入 session 信息，供 ClawdbotClient 提取
            # session_id: 用于 OpenClaw 的 sessionKey（按用户隔离）
            # callback_session_id: 用于回调路由（包含消息类型和目标 chat_id）
            if len(prompt_messages) > 0 and isinstance(prompt_messages[0], dict):
                prompt_messages[0]["session_id"] = session_id
                prompt_messages[0]["callback_session_id"] = callback_session_id or session_id
                self.logger.info(f"Injecting session info -> session_id: {session_id}, callback_session_id: {prompt_messages[0]['callback_session_id']}")
            
            self.logger.info(f"OpenClaw session: {session_id}, callback: {callback_session_id}")
            
            # [Debug] 检测调试指令
            debug_info = None
            if "/debug" in message or "/debug_prompt" in message:
                import json
                try:
                    # 序列化提示词以便阅读
                    debug_info = json.dumps(prompt_messages, ensure_ascii=False, indent=2)
                    self.logger.info("Debug flag detected, attaching prompt info.")
                except Exception as e:
                    debug_info = f"Error serializing prompt: {str(e)}"

            # 调用LLM
            response = await self._call_llm(prompt_messages, mode)
            
            # 保存到会话历史
            self.session_manager.add_user_message(session_id, message)
            self.session_manager.add_assistant_message(session_id, response["text"])
            
            self.logger.info(f"响应生成成功: {response['text'][:50]}...")
            
            return {
                "success": True,
                "text": response["text"],
                "mode": mode.value,
                "usage": response.get("usage", {}),
                "debug_info": debug_info  # 返回调试信息
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
    
    async def _call_llm(self, messages: List[Dict[str, Any]],
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
        
        if hasattr(self.llm_client, 'chat') and inspect.iscoroutinefunction(self.llm_client.chat):
            # clawdbot 客户端（async）
            response_text = await self.llm_client.chat(messages)
            
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
