"""
智能体核心模块

实现OpenCode范式的智能体协调器
"""

import logging
import asyncio
from typing import Optional, Dict, Any, List, Callable
from datetime import datetime
from core.types import AgentMode
from core.services.intent_detector import IntentDetector
from .session import get_session_manager, SessionManager
from .prompt import get_prompt_builder, PromptBuilder
from .memory import get_memory_bank, MemoryBank
from .memory_extractor import get_memory_extractor
from .tools.clawdbot_cli import ClawdbotCliTool


class Agent:
    """
    智能体核心类
    
    模仿OpenCode的Plan -> Build两阶段思考模式，协调LLM调用和工具执行
    """
    
    def __init__(self, llm_client,
                 session_manager: Optional[SessionManager] = None,
                 prompt_builder: Optional[PromptBuilder] = None,
                 clawdbot_tool: Optional[ClawdbotCliTool] = None,
                 notification_callback: Optional[Callable] = None):
        """
        初始化智能体
        
        Args:
            llm_client: LLM客户端实例
            session_manager: 会话管理器实例
            prompt_builder: 提示词构建器实例
            clawdbot_tool: Clawdbot CLI 工具实例
            notification_callback: 异步通知回调函数
        """
        self.llm_client = llm_client
        self.session_manager = session_manager or get_session_manager()
        self.prompt_builder = prompt_builder or get_prompt_builder()
        self.memory_bank = get_memory_bank()
        self.memory_extractor = get_memory_extractor()
        self.clawdbot_tool = clawdbot_tool
        self.notification_callback = notification_callback
        self.intent_detector = IntentDetector()
        
        self.logger = logging.getLogger(__name__)
        self.current_mode = AgentMode.CONVERSATION
        self.thinking_enabled = True  # 是否显示思考过程
    

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
            
            # 1. 获取全局人格
            base_system = self.prompt_builder.system_prompt
            
            # 2. 获取用户专属记忆
            real_user_id = user_id.split(":")[-1] # extract user id part if formatted like platform:user_id
            if ":" in user_id: 
                 # user_id passed is "qq:123456", memory needs unique ID. Using full string is fine too but user requested per user.
                 real_user_id = user_id 
            
            # [Security] Sanitize user_id to prevent prompt injection
            import re
            real_user_id = re.sub(r'[^a-zA-Z0-9_\-:]', '', real_user_id)

            # [新增] 处理重置指令
            if message.strip() in ["/reset", "/clear", "重置", "清除记忆"]:
                # 1. 清除会话历史
                self.session_manager.clear_session(session_id)
                # 2. 清除长期记忆文件
                if hasattr(self.memory_bank, 'delete_user_memory'):
                    self.memory_bank.delete_user_memory(real_user_id)
                
                return {
                    "success": True,
                    "text": "记忆已重置。我是全新的小汉堡，我们重新开始吧！\n(已清除对话历史和长期记忆文件)",
                    "mode": "conversation",
                    "usage": {}
                }
            
            # 检测用户意图
            intent = self.intent_detector.detect_intent(message)
            mode = self.intent_detector.get_mode_from_intent(intent)
            self.current_mode = mode
            
            # 构建提示词
            
            user_memory = self.memory_bank.get_user_memory(real_user_id)
            
            # 3. 动态合并
            # [Optimization] 注入强身份边界，防止串台
            # [Optimization] Inject System Time & Identity Boundary
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S %A")
            
            strict_session_context = (
                f"\n\n## ⚠️ Session Context Enforcement (CRITICAL)\n"
                f"Current System Time: {current_time} (Trusted Source)\n"
                f"Current Session User ID: {real_user_id}\n"
                f"You are communicating EXCLUSIVELY with the user identified as '{real_user_id}'.\n"
                f"\n### 用户隔离规则 (User Isolation Rules)\n"
                f"1. 你现在只与 '{real_user_id}' 对话。绝对不要把其他用户的记忆、称呼、偏好带入当前对话。\n"
                f"2. 如果你要编辑或更新 MEMORY.md，只修改属于 '{real_user_id}' 的段落，用 '## 用户 {real_user_id}' 作为该用户的记忆区域标记。\n"
                f"3. MEMORY.md 中其他用户（不同 ID）的数据必须原封不动保留，不要删除也不要在当前对话引用。\n"
                f"4. 不要使用其他用户的昵称称呼当前用户。\n"
                f"Do NOT use any tools to verify the time. The time provided above is authoritative.\n"
                f"\n## 🛠️ 内置网页搜索能力 (Native Tool - Search)\n"
                f"如果你需要从互联网查询最新新闻、价格、事实或资料，请**必须严格在此次回复中仅输出**以下格式：\n"
                f"`[Search: 这里填写你的搜索关键词]`\n"
                f"提示：遇到不懂的问题先回答这个指令，系统会自动联网并把网页正文或摘要提供给你。切记：搜索指令必须是独立的文本块，不要混淆其他文字。\n"
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
            
            # [DuckDuckGo Native Search Integration]
            import re
            search_match = re.search(r'\[Search:\s*(.*?)\]', response["text"], re.IGNORECASE | re.DOTALL)
            if search_match:
                query = search_match.group(1).strip()
                self.logger.info(f"Detected Native Search intent, query: {query}")
                
                target_session_id = callback_session_id or session_id
                if self.notification_callback:
                    notify_msg = f"🔍 正在使用 DuckDuckGo 检索: {query}..."
                    if asyncio.iscoroutinefunction(self.notification_callback):
                        await self.notification_callback(target_session_id, notify_msg)
                    else:
                        self.notification_callback(target_session_id, notify_msg)
                
                from core.tools.duckduckgo_search import search_web_duckduckgo
                search_results = await search_web_duckduckgo(query, max_results=4)
                
                observation = f"系统执行搜索 '{query}' 得到如下结果：\n\n{search_results}\n\n请根据上述搜索结果回答用户的最初问题。如果搜索内容不足以回答，可如实告知。"
                
                # Append to messages array to continue the conversation in same context
                prompt_messages.append({"role": "assistant", "content": response["text"]})
                prompt_messages.append({"role": "user", "content": observation})
                
                # Save intermediate thoughts to DB
                self.session_manager.add_assistant_message(session_id, response["text"])
                self.session_manager.add_user_message(session_id, observation)
                
                # Recall LLM
                response = await self._call_llm(prompt_messages, mode)
                self.logger.info(f"LLM Reply after DuckDuckGo search: {response['text'][:50]}...")
            
            
            # [Clawdbot CLI Integration] 检测是否调用了 CLI 工具
            import re
            clawdbot_match = re.search(r'\[Clawdbot:\s*(.*?)\]', response["text"], re.DOTALL)
            if clawdbot_match:
                if self.clawdbot_tool and self.notification_callback:
                    task_prompt = clawdbot_match.group(1).strip()
                    self.logger.info(f"Detected Clawdbot task: {task_prompt}")
                    
                    # 启动异步任务
                    # 注意：我们传递 callback_session_id 作为 session_id，以确保回调能正确路由
                    # 如果 session_id 本身已经包含路由信息（如 agent.py中 session_id = chat_id），
                    # 这里我们使用 callback_session_id 变量，它在 process_message 签名中定义了
                    
                    target_session_id = callback_session_id or session_id
                    await self.clawdbot_tool.run_async(task_prompt, target_session_id, self.notification_callback)
                    
                    # 修改返回给用户的立即响应
                    response["text"] = f"收到，正在调用 Clawdbot 为您处理：{task_prompt}...\n（请稍候，结果将异步发送）"
                else:
                    self.logger.warning("Clawdbot tool detected but tool or callback is missing.")
                    # Optionally append a warning to the text or just log it
            
            # 保存到会话历史
            self.session_manager.add_user_message(session_id, message)
            self.session_manager.add_assistant_message(session_id, response["text"])
            
            # 异步触发记忆更新（每N轮对话自动提取用户信息）
            updated_history = self.session_manager.get_history(session_id)
            if self.memory_extractor.should_trigger(len(updated_history)):
                self.logger.info(f"触发异步记忆更新: user={real_user_id}, history_len={len(updated_history)}")
                asyncio.create_task(
                    self._update_user_memory(real_user_id, updated_history)
                )
            
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
    
    async def _update_user_memory(self, user_id: str,
                                    history: List[Dict[str, str]]) -> None:
        """
        异步更新用户长期记忆
        
        在后台运行，不阻塞主对话流程。
        从对话历史中提取关键信息并合并到用户记忆文件。
        
        Args:
            user_id: 用户ID (e.g. "qq:254067848")
            history: 当前会话的对话历史
        """
        try:
            success = await self.memory_extractor.extract_and_update(user_id, history)
            if success:
                self.logger.info(f"用户 {user_id} 的长期记忆已自动更新")
            else:
                self.logger.warning(f"用户 {user_id} 的长期记忆更新未成功")
        except Exception as e:
            self.logger.error(f"异步记忆更新异常: {e}", exc_info=True)

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
                 prompt_builder: Optional[PromptBuilder] = None,
                 clawdbot_tool: Optional[ClawdbotCliTool] = None,
                 notification_callback: Optional[Callable] = None) -> Agent:
    """
    创建智能体实例
    
    Args:
        llm_client: LLM客户端实例
        session_manager: 会话管理器实例
        prompt_builder: 提示词构建器实例
        clawdbot_tool: Clawdbot CLI 工具实例
        notification_callback: 异步通知回调函数
        
    Returns:
        Agent: 智能体实例
    """
    return Agent(llm_client, session_manager, prompt_builder, clawdbot_tool, notification_callback)
