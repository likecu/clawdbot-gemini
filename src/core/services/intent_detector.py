
from typing import Optional
from core.types import AgentMode

class IntentDetector:
    """
    负责识别用户意图并决定智能体的工作模式
    """
    
    def detect_intent(self, message: str) -> str:
        """
        检测用户意图
        
        Args:
            message: 用户消息
            
        Returns:
            str: 意图类型
        """
        message_lower = message.lower().strip()
        
        # 代码解释相关关键词
        explain_keywords = ["解释", "说明", "explain", "what does", "这段代码"]
        if any(kw in message_lower for kw in explain_keywords):
            return "code_explanation"
        
        # 代码生成相关关键词
        code_keywords = [
            "写代码", "生成代码", "实现", "create", "write code", "implement", 
            "写一个", "写个", "用python", "用js",
            "python script", "write a script", "coding"
        ]
        if any(kw in message_lower for kw in code_keywords):
            return "code_generation"
        
        # 调试相关关键词
        debug_keywords = ["报错", "错误", "bug", "debug", "修复", "问题"]
        if any(kw in message_lower for kw in debug_keywords):
            return "debugging"
        
        return "conversation"

    def get_mode_from_intent(self, intent: str) -> AgentMode:
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

    def determine_mode(self, message: str) -> AgentMode:
        """
        直接根据消息确定工作模式
        """
        intent = self.detect_intent(message)
        return self.get_mode_from_intent(intent)
