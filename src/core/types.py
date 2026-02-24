
from enum import Enum

class AgentMode(Enum):
    """
    智能体工作模式
    """
    CONVERSATION = "conversation"
    CODE_GENERATION = "code_generation"
    CODE_EXPLANATION = "code_explanation"
    DEBUGGING = "debugging"
