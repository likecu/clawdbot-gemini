"""
提示词构建器单元测试
"""

import unittest
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "src"
))

from core.prompt import PromptBuilder, create_prompt_builder


class TestPromptBuilder(unittest.TestCase):
    """
    提示词构建器测试类
    """
    
    def setUp(self):
        """
        测试前置条件
        """
        self.builder = PromptBuilder()
    
    def test_default_system_prompt(self):
        """
        测试默认系统提示词
        """
        prompt = self.builder.system_prompt
        
        self.assertIn("AI编程助手", prompt)
        self.assertIn("代码生成", prompt)
        self.assertIn("代码解释", prompt)
    
    def test_build_system_prompt(self):
        """
        测试构建系统提示词
        """
        prompt = self.builder.build_system_prompt()
        
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 0)
    
    def test_build_system_prompt_with_context(self):
        """
        测试带上下文的系统提示词
        """
        context = "当前项目使用Python 3.11和FastAPI框架"
        prompt = self.builder.build_system_prompt(context)
        
        self.assertIn(context, prompt)
    
    def test_build_conversation_prompt(self):
        """
        测试构建对话提示词
        """
        history = [
            {"role": "user", "content": "你好"},
            {"role": "assistant", "content": "你好！有什么可以帮助你的？"}
        ]
        current_message = "请帮我写一段代码"
        
        messages = self.builder.build_conversation_prompt(history, current_message)
        
        self.assertEqual(len(messages), 4)  # system + 2 history + current
        
        # 检查消息顺序和内容
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[1]["role"], "user")
        self.assertEqual(messages[1]["content"], "你好")
        self.assertEqual(messages[2]["role"], "assistant")
        self.assertEqual(messages[3]["role"], "user")
        self.assertEqual(messages[3]["content"], current_message)
    
    def test_build_conversation_prompt_without_system(self):
        """
        测试不包含系统提示词的对话
        """
        history = [{"role": "user", "content": "Hello"}]
        current_message = "World"
        
        messages = self.builder.build_conversation_prompt(history, current_message, include_system=False)
        
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["role"], "user")
    
    def test_build_code_generation_prompt(self):
        """
        测试构建代码生成提示词
        """
        requirement = "实现一个计算斐波那契数列的函数"
        language = "python"
        constraints = ["使用递归", "添加类型注解"]
        
        prompt = self.builder.build_code_generation_prompt(requirement, language, constraints)
        
        self.assertIn(language, prompt)
        self.assertIn(requirement, prompt)
        self.assertIn("约束条件", prompt)
        self.assertIn("使用递归", prompt)
    
    def test_build_code_generation_prompt_without_constraints(self):
        """
        测试不带约束的代码生成提示词
        """
        prompt = self.builder.build_code_generation_prompt(
            "实现快速排序",
            "python"
        )
        
        self.assertIn("python", prompt)
        self.assertIn("实现快速排序", prompt)
    
    def test_build_code_explanation_prompt(self):
        """
        测试构建代码解释提示词
        """
        code = '''
def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)
'''
        language = "python"
        
        prompt = self.builder.build_code_explanation_prompt(code, language)
        
        self.assertIn(language, prompt)
        self.assertIn("代码的整体功能", prompt)
        self.assertIn("核心逻辑", prompt)
    
    def test_build_debug_prompt(self):
        """
        测试构建调试提示词
        """
        code = "print(undefined_variable)"
        error_message = "NameError: name 'undefined_variable' is not defined"
        
        prompt = self.builder.build_debug_prompt(code, error_message)
        
        self.assertIn(error_message, prompt)
        self.assertIn("分析问题原因", prompt)
        self.assertIn("提供修复方案", prompt)
    
    def test_set_system_prompt(self):
        """
        测试更新系统提示词
        """
        new_prompt = "你是我的专属编程助手"
        
        self.builder.set_system_prompt(new_prompt)
        
        self.assertEqual(self.builder.system_prompt, new_prompt)


class TestPromptBuilderSingleton(unittest.TestCase):
    """
    提示词构建器单例测试类
    """
    
    def tearDown(self):
        """
        测试后清理
        """
        import core.prompt
        core.prompt._prompt_builder = None
    
    def test_create_prompt_builder(self):
        """
        测试创建提示词构建器单例
        """
        builder1 = create_prompt_builder()
        builder2 = create_prompt_builder()
        
        self.assertIs(builder1, builder2)


class TestPromptBuilderCustom(unittest.TestCase):
    """
    自定义提示词构建器测试类
    """
    
    def test_custom_system_prompt(self):
        """
        测试自定义系统提示词
        """
        custom_prompt = "你是一个数据分析专家"
        
        builder = PromptBuilder(system_prompt=custom_prompt)
        
        self.assertEqual(builder.system_prompt, custom_prompt)
    
    def test_build_with_custom_prompt(self):
        """
        测试使用自定义提示词构建
        """
        custom_prompt = "你是一个数据分析专家"
        builder = PromptBuilder(system_prompt=custom_prompt)
        
        messages = builder.build_conversation_prompt([], "请分析这个数据")
        
        self.assertEqual(messages[0]["role"], "system")
        self.assertEqual(messages[0]["content"], custom_prompt)


if __name__ == "__main__":
    unittest.main()
