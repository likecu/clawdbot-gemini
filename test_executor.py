"""
代码执行器单元测试

测试代码执行器的各种功能
"""

import os
import sys
import unittest
from unittest.mock import Mock, patch

# 添加 src 目录到路径
_src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src')
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

from executor import CodeExecutor, OutputCapture


class TestCodeExecutorDetectLanguage(unittest.TestCase):
    """
    测试 CodeExecutor 语言检测功能
    """

    def setUp(self):
        """
        设置测试环境
        """
        self.executor = CodeExecutor()

    def test_detect_python(self):
        """
        测试 Python 代码检测
        """
        python_codes = [
            'def hello():\n    print("Hello")',
            'import os\nimport sys',
            'class MyClass:\n    def __init__(self):',
            'data = [x for x in range(10)]',
            'result.append(item)'
        ]

        for code in python_codes:
            with self.subTest(code=code[:20]):
                result = self.executor.detect_language(code)
                self.assertEqual(result, 'python')

    def test_detect_javascript(self):
        """
        测试 JavaScript 代码检测
        """
        js_codes = [
            'console.log("Hello")',
            'function greet() { return "Hello"; }',
            'const x = 10;',
            'items.forEach(item => console.log(item));'
        ]

        for code in js_codes:
            with self.subTest(code=code[:20]):
                result = self.executor.detect_language(code)
                self.assertEqual(result, 'javascript')

    def test_detect_bash(self):
        """
        测试 Bash 脚本检测
        """
        bash_codes = [
            '#!/bin/bash',
            'echo "Hello World"',
            'for i in {1..10}; do echo $i; done'
        ]

        for code in bash_codes:
            with self.subTest(code=code[:20]):
                result = self.executor.detect_language(code)
                self.assertEqual(result, 'bash')

    def test_detect_unknown(self):
        """
        测试未知语言检测（默认为 Python）
        """
        unknown_code = 'unknown code text'
        result = self.executor.detect_language(unknown_code)
        self.assertEqual(result, 'python')


class TestCodeExecutorExtractCodeBlocks(unittest.TestCase):
    """
    测试 CodeExecutor 代码块提取功能
    """

    def setUp(self):
        """
        设置测试环境
        """
        self.executor = CodeExecutor()

    def test_extract_markdown_code_blocks(self):
        """
        测试提取 Markdown 代码块
        """
        text = '''
这是一个文本。

```python
def hello():
    print("Hello")
```

中间文本。

```javascript
function greet() {
    return "Hello";
}
```
'''

        blocks = self.executor._extract_code_blocks(text)

        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]['language'], 'python')
        self.assertIn('def hello():', blocks[0]['code'])
        self.assertEqual(blocks[1]['language'], 'javascript')
        self.assertIn('function greet()', blocks[1]['code'])

    def test_extract_empty_text(self):
        """
        测试空文本提取
        """
        blocks = self.executor._extract_code_blocks('')
        self.assertEqual(len(blocks), 0)

    def test_extract_no_code_blocks(self):
        """
        测试无代码块的文本
        """
        text = '这是一个普通文本消息，不包含任何代码。'

        blocks = self.executor._extract_code_blocks(text)

        self.assertEqual(len(blocks), 0)


class TestCodeExecutorAnalyzeAndExecute(unittest.TestCase):
    """
    测试 CodeExecutor 分析和执行功能
    """

    def setUp(self):
        """
        设置测试环境
        """
        self.executor = CodeExecutor()

    def test_detect_execution_request(self):
        """
        测试检测执行请求
        """
        messages = [
            '请运行这段代码',
            'execute this code',
            '帮我运行 python 代码',
            '运行代码',
            '代码执行'
        ]

        for message in messages:
            with self.subTest(message=message):
                should_execute, _ = self.executor.analyze_and_execute(message)
                self.assertTrue(should_execute)

    def test_detect_non_execution_request(self):
        """
        测试检测非执行请求
        """
        messages = [
            '你好',
            '今天天气怎么样',
            '帮我解释一下什么是机器学习'
        ]

        for message in messages:
            with self.subTest(message=message):
                should_execute, _ = self.executor.analyze_and_execute(message)
                self.assertFalse(should_execute)


class TestOutputCapture(unittest.TestCase):
    """
    测试 OutputCapture 类
    """

    def test_add_output(self):
        """
        测试添加输出
        """
        capture = OutputCapture()
        capture.add_output('Line 1')
        capture.add_output('Line 2')

        result = capture.get_output()
        self.assertIn('Line 1', result)
        self.assertIn('Line 2', result)

    def test_add_error(self):
        """
        测试添加错误
        """
        capture = OutputCapture()
        capture.add_error('Error message')

        result = capture.get_output()
        self.assertIn('Error message', result)
        self.assertIn('错误输出', result)

    def test_empty_output(self):
        """
        测试空输出
        """
        capture = OutputCapture()

        result = capture.get_output()
        self.assertEqual(result, '代码执行完成，无输出')

    def test_combined_output(self):
        """
        测试组合输出
        """
        capture = OutputCapture()
        capture.add_output('Normal output')
        capture.add_error('Error details')

        result = capture.get_output()
        self.assertIn('Normal output', result)
        self.assertIn('Error details', result)

    def test_whitespace_handling(self):
        """
        测试空白字符处理
        """
        capture = OutputCapture()
        capture.add_output('  ')
        capture.add_output('Valid output')

        result = capture.get_output()
        self.assertIn('Valid output', result)


class TestCodeExecutorExecutionHistory(unittest.TestCase):
    """
    测试 CodeExecutor 执行历史功能
    """

    def setUp(self):
        """
        设置测试环境
        """
        self.executor = CodeExecutor()

    def test_get_empty_history(self):
        """
        测试获取空历史
        """
        history = self.executor.get_execution_history()
        self.assertEqual(len(history), 0)

    def test_clear_history(self):
        """
        测试清空历史
        """
        self.executor.execution_history = [{'test': 'entry'}]

        self.executor.clear_history()

        history = self.executor.get_execution_history()
        self.assertEqual(len(history), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
