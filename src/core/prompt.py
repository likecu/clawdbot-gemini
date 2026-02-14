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
        return """你是一个专业的AI编程助手，名为Clawdbot。

## 核心能力

1. **代码生成**：根据用户需求生成高质量代码，支持多种编程语言
2. **代码解释**：分析代码逻辑，提供清晰的解释
3. **代码调试**：帮助定位和修复代码问题
4. **技术问答**：回答编程相关问题

## 工作原则

- 提供简洁、高效的解决方案
- 代码中添加必要的注释
- 优先考虑可读性和可维护性
- 明确说明代码的适用场景和限制

## 输出格式

当需要展示代码时，使用Markdown代码块格式，并标注语言类型。
例如：
```python
def example():
    pass
```

请始终以专业、友好的方式与用户交流。"""
    
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
