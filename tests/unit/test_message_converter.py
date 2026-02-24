"""
消息转换器单元测试
"""

import unittest
import json
import sys
import os

# 添加src目录到Python路径
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "src"
))

from adapters.lark.message_converter import MessageConverter, markdown_to_feishu_post


class TestMessageConverter(unittest.TestCase):
    """
    消息转换器测试类
    """
    
    def setUp(self):
        """
        测试前置条件
        """
        self.converter = MessageConverter()
    
    def test_empty_text_raises_error(self):
        """
        测试空文本抛出异常
        """
        with self.assertRaises(ValueError):
            self.converter.markdown_to_lark_post("")
        
        with self.assertRaises(ValueError):
            self.converter.markdown_to_lark_post("   ")
    
    def test_plain_text_conversion(self):
        """
        测试纯文本转换
        """
        text = "这是一个简单的文本消息"
        result = self.converter.markdown_to_lark_post(text)
        
        self.assertEqual(result["msg_type"], "post")
        
        content = json.loads(result["content"])
        self.assertIn("zh_cn", content)
        
        nodes = content["zh_cn"]["content"]
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["tag"], "text")
        self.assertEqual(nodes[0]["text"], text)
    
    def test_single_code_block(self):
        """
        测试单个代码块转换
        """
        code = '''def hello():
    print("Hello, World!")'''
        
        markdown = f"```python\n{code}\n```"
        result = self.converter.markdown_to_lark_post(markdown)
        
        self.assertEqual(result["msg_type"], "post")
        
        content = json.loads(result["content"])
        nodes = content["zh_cn"]["content"]
        
        self.assertEqual(len(nodes), 1)
        self.assertEqual(nodes[0]["tag"], "code_block")
        self.assertEqual(nodes[0]["language"], "PYTHON")
        self.assertEqual(nodes[0]["text"], code)
    
    def test_text_with_code_block(self):
        """
        测试文本和代码块混合
        """
        text = "请看以下代码："
        code = "print('hello')"
        markdown = f"{text}\n\n```python\n{code}\n```\n\n这是代码执行结果。"
        
        result = self.converter.markdown_to_lark_post(markdown)
        
        content = json.loads(result["content"])
        nodes = content["zh_cn"]["content"]
        
        self.assertEqual(len(nodes), 3)
        
        # 第一个节点是文本
        self.assertEqual(nodes[0]["tag"], "text")
        self.assertEqual(nodes[0]["text"], text + "\n")
        
        # 第二个节点是代码块
        self.assertEqual(nodes[1]["tag"], "code_block")
        self.assertEqual(nodes[1]["language"], "PYTHON")
        
        # 第三个节点是剩余文本
        self.assertEqual(nodes[2]["tag"], "text")
    
    def test_multiple_code_blocks(self):
        """
        测试多个代码块
        """
        markdown = '''```python
code1
```

```javascript
code2
```
'''
        
        result = self.converter.markdown_to_lark_post(markdown)
        
        content = json.loads(result["content"])
        nodes = content["zh_cn"]["content"]
        
        self.assertEqual(len(nodes), 3)
        self.assertEqual(nodes[0]["tag"], "code_block")
        self.assertEqual(nodes[0]["language"], "PYTHON")
        self.assertEqual(nodes[1]["tag"], "code_block")
        self.assertEqual(nodes[1]["language"], "JAVASCRIPT")
    
    def test_language_mapping(self):
        """
        测试语言标识映射
        """
        test_cases = [
            ("py", "PYTHON"),
            ("python", "PYTHON"),
            ("js", "JAVASCRIPT"),
            ("javascript", "JAVASCRIPT"),
            ("ts", "TYPESCRIPT"),
            ("go", "GO"),
            ("java", "JAVA"),
            ("cpp", "CPP"),
            ("c++", "CPP"),
            ("unknown", "UNKNOWN"),
            ("", "TEXT"),
        ]
        
        for input_lang, expected_lang in test_cases:
            with self.subTest(lang=input_lang):
                code_block = self.converter._create_code_block_node("test", input_lang)
                self.assertEqual(code_block["language"], expected_lang)
    
    def test_markdown_formatting(self):
        """
        测试Markdown格式处理
        """
        text = "**粗体** *斜体* `行内代码` ~~删除线~~"
        processed = self.converter._process_markdown_formatting(text)
        
        self.assertNotIn("**", processed)
        self.assertNotIn("*", processed)
        self.assertNotIn("`", processed)
        self.assertNotIn("~~", processed)
    
    def test_extract_code_blocks(self):
        """
        测试代码块提取
        """
        markdown = '''这是一个文本
```python
code1
```
中间文本
```javascript
code2
```
结束文本'''
        
        code_blocks = self.converter.extract_code_blocks(markdown)
        
        self.assertEqual(len(code_blocks), 2)
        self.assertEqual(code_blocks[0]["language"], "python")
        self.assertEqual(code_blocks[0]["code"], "code1")
        self.assertEqual(code_blocks[1]["language"], "javascript")
        self.assertEqual(code_blocks[1]["code"], "code2")
    
    def test_split_text_and_code(self):
        """
        测试文本和代码分割
        """
        markdown = "前面文本\n```python\ncode\n```\n后面文本"
        
        parts = self.converter.split_text_and_code(markdown)
        
        self.assertEqual(len(parts), 3)
        self.assertEqual(parts[0]["type"], "text")
        self.assertEqual(parts[1]["type"], "code")
        self.assertEqual(parts[2]["type"], "text")
    
    def test_convenience_function(self):
        """
        测试便捷函数
        """
        result = markdown_to_feishu_post("测试文本")
        
        self.assertEqual(result["msg_type"], "post")
        content = json.loads(result["content"])
        self.assertIn("zh_cn", content)


class TestFormatCodeBlock(unittest.TestCase):
    """
    代码块格式化测试类
    """
    
    def test_format_code_block(self):
        """
        测试代码块格式化函数
        """
        from adapters.lark.message_converter import format_code_block
        
        code = "print('hello')"
        result = format_code_block(code, "python")
        
        self.assertEqual(result["tag"], "code_block")
        self.assertEqual(result["language"], "PYTHON")
        self.assertEqual(result["text"], code)
    
    def test_default_language(self):
        """
        测试默认语言
        """
        from adapters.lark.message_converter import format_code_block
        
        result = format_code_block("test", "")
        
        self.assertEqual(result["language"], "TEXT")


if __name__ == "__main__":
    unittest.main()
