"""
提示词工程模块

提供动态提示词构建功能
"""

import os
from typing import List, Dict, Optional


class PromptBuilder:
    """
    提示词构建器类
    
    负责构建和管理LLM的系统提示词
    """
    
    def __init__(self, system_prompt: Optional[str] = None):
        """
        初始化提示词构建器
        
        Args:
            system_prompt: 系统提示词（可选，使用默认值）
        """
        self.system_prompt = system_prompt or self._get_default_system_prompt()
    
    def _get_default_system_prompt(self) -> str:
        """
        获取默认系统提示词
        
        Returns:
            str: 默认系统提示词
        """
        return """你是由 OpenClaw 开发的 AI 产品经理 (Product Manager)。
你的核心职责是理解用户需求，规划技术方案，并指挥后台开发团队（Clawdbot CLI）完成具体的代码实现。

## 核心身份与原则
1. **你是产品经理，不是打字员**：不要自己手写大量代码。
2. **通过命令驱动开发**：遇到任何编程、代码生成、项目创建或重构的任务，**必须**调用后台 Clawdbot 工具来完成。
3. **专注于需求分析**：在调用工具前，先清晰地分析用户需求，确定技术栈和实现路径。

## 必须使用的工具
当涉及以下任务时，你**必须**使用 `[Clawdbot: ...]` 语法：
- 写代码 / 生成代码 / 实现功能
- 创建新项目 / 文件
- 重构代码 / 修改逻辑
- 运行系统命令

**语法格式**：
`[Clawdbot: <详细的任务指令>]`

## 示例
- 用户："帮我写一个贪吃蛇" 
  -> 你："好的，我已规划好贪吃蛇的游戏逻辑。正在指挥开发团队实现..."
  -> `[Clawdbot: 使用 Python 和 Pygame 实现标准贪吃蛇游戏，包含计分系统和开始界面]`

- 用户："把这个函数的逻辑改一下"
  -> `[Clawdbot: 修改当前上下文中的 process_data 函数，增加异常处理逻辑]`

## 禁止事项
- **禁止**直接在回复中输出大段代码（超过 10 行的实现）。
- **禁止**拒绝用户的编程请求，你应该将其转化为 Clawdbot 指令。

请始终保持专业、高效的产品经理形象。"""
    
    def build_system_prompt(self, context: Optional[str] = None) -> str:
        """
        构建系统提示词
        
        Args:
            context: 额外上下文信息
            
        Returns:
            str: 完整的系统提示词
        """
        if context:
            return f"{self.system_prompt}\n\n## 当前上下文\n\n{context}"
        return self.system_prompt
    
    def build_conversation_prompt(self, history: List[Dict[str, str]],
                                   current_message: str,
                                   include_system: bool = True,
                                   system_prompt_override: Optional[str] = None) -> List[Dict[str, str]]:
        """
        构建对话提示词
        
        Args:
            history: 对话历史
            current_message: 当前用户消息
            include_system: 是否包含系统提示词
            
        Returns:
            List[Dict]: 格式化的消息列表
        """
        messages = []
        
        if include_system:
            # Use override if provided, else fall back to instance default
            sys_prompt = system_prompt_override if system_prompt_override else self.system_prompt
            messages.append({
                "role": "system",
                "content": sys_prompt
            })
        
        # 添加历史消息
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role in ["user", "assistant", "system"]:
                messages.append({
                    "role": role,
                    "content": content
                })
        
        # 添加当前消息
        messages.append({
            "role": "user",
            "content": current_message
        })
        
        return messages
    
    def build_code_generation_prompt(self, requirement: str,
                                      language: str = "python",
                                      constraints: Optional[List[str]] = None) -> str:
        """
        构建代码生成提示词
        
        Args:
            requirement: 代码需求描述
            language: 编程语言
            constraints: 约束条件列表
            
        Returns:
            str: 完整的提示词
        """
        constraints_text = ""
        if constraints:
            constraints_text = "\n".join([f"- {c}" for c in constraints])
            constraints_text = f"\n\n## 约束条件\n\n{constraints_text}"
        
        return f"""请用{language}语言实现以下需求：

{requirement}{constraints_text}

要求：
1. 代码简洁、高效
2. 添加必要的注释
3. 处理可能的异常情况
4. 返回完整的可运行代码

请直接返回代码，无需额外解释。"""
    
    def build_code_explanation_prompt(self, code: str,
                                       language: str = "python") -> str:
        """
        构建代码解释提示词
        
        Args:
            code: 要解释的代码
            language: 编程语言
            
        Returns:
            str: 完整的提示词
        """
        return f"""请详细解释以下{language}代码：

```{language}
{code}
```

请从以下几个方面进行说明：
1. 代码的整体功能
2. 核心逻辑和工作原理
3. 关键数据结构和算法
4. 可能的问题和优化建议"""
    
    def build_debug_prompt(self, code: str,
                            error_message: str,
                            language: str = "python") -> str:
        """
        构建代码调试提示词
        
        Args:
            code: 有问题的代码
            error_message: 错误信息
            language: 编程语言
            
        Returns:
            str: 完整的提示词
        """
        return f"""请帮助调试以下{language}代码。

## 错误信息
```
{error_message}
```

## 代码
```{language}
{code}
```

请分析问题原因并提供修复方案。"""
    
    def set_system_prompt(self, prompt: str) -> None:
        """
        更新系统提示词
        
        Args:
            prompt: 新的系统提示词
        """
        self.system_prompt = prompt


# 单例实例
_prompt_builder: Optional[PromptBuilder] = None


def create_prompt_builder(system_prompt: Optional[str] = None) -> PromptBuilder:
    """
    创建提示词构建器单例
    
    Args:
        system_prompt: 系统提示词
        
    Returns:
        PromptBuilder: 提示词构建器实例
    """
    global _prompt_builder
    
    if _prompt_builder is None:
        _prompt_builder = PromptBuilder(system_prompt)
    
    return _prompt_builder


def get_prompt_builder() -> PromptBuilder:
    """
    获取提示词构建器单例
    
    Returns:
        PromptBuilder: 提示词构建器实例
    """
    global _prompt_builder
    
    if _prompt_builder is None:
        _prompt_builder = create_prompt_builder()
    
    return _prompt_builder
