
import pytest
from core.services.intent_detector import IntentDetector
from core.types import AgentMode

def test_detect_intent_code_generation():
    """
    测试代码生成意图识别
    """
    detector = IntentDetector()
    assert detector.detect_intent("帮我写个贪吃蛇代码") == "code_generation"
    assert detector.detect_intent("create a react app") == "code_generation"
    assert detector.detect_intent("实现一个快排") == "code_generation"

def test_detect_intent_code_explanation():
    """
    测试代码解释意图识别
    """
    detector = IntentDetector()
    assert detector.detect_intent("解释一下这段代码") == "code_explanation"
    assert detector.detect_intent("what does this function do?") == "code_explanation"

def test_detect_intent_debugging():
    """
    测试调试意图识别
    """
    detector = IntentDetector()
    assert detector.detect_intent("代码报错了 help fix") == "debugging"
    assert detector.detect_intent("debug this error") == "debugging"

def test_detect_intent_conversation_fallback():
    """
    测试对话模式回退（默认意图）
    """
    detector = IntentDetector()
    assert detector.detect_intent("你好") == "conversation"
    assert detector.detect_intent("今天天气不错") == "conversation"

def test_get_mode_from_intent():
    """
    测试意图到模式的映射
    """
    detector = IntentDetector()
    assert detector.get_mode_from_intent("code_generation") == AgentMode.CODE_GENERATION
    assert detector.get_mode_from_intent("code_explanation") == AgentMode.CODE_EXPLANATION
    assert detector.get_mode_from_intent("debugging") == AgentMode.DEBUGGING
    assert detector.get_mode_from_intent("unknown") == AgentMode.CONVERSATION
