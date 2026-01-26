"""
代码执行器模块

负责安全地分析和执行用户提交的代码
集成 Gemini 模型进行代码生成
"""

import os
import sys
import json
import time
import subprocess
import tempfile
import shutil
import re
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, List

# 导入 Gemini 集成
from llm import init_gemini, get_response_with_history


class CodeExecutor:
    """
    代码执行器类

    提供安全的代码分析和执行功能，支持多种编程语言
    """

    def __init__(self):
        """
        初始化代码执行器
        """
        self.gemini_model = None
        self.execution_history = []
        self.supported_languages = {
            'python': ['py', 'python'],
            'javascript': ['js', 'javascript'],
            'bash': ['sh', 'bash', 'shell']
        }
        self._init_gemini()

    def _init_gemini(self):
        """
        初始化 Gemini 模型

        Raises:
            Exception: 初始化失败时抛出
        """
        try:
            api_key = os.getenv('GOOGLE_API_KEY')
            if api_key:
                self.gemini_model = init_gemini(api_key)
                print('Gemini 模型初始化成功')
            else:
                print('警告: 未配置 GOOGLE_API_KEY，代码生成功能将受限')
        except Exception as e:
            print(f'初始化 Gemini 模型失败: {e}')

    def get_gemini_model(self):
        """
        获取 Gemini 模型实例

        Returns:
            Any: Gemini 模型实例，如果未初始化则返回 None
        """
        return self.gemini_model

    def detect_language(self, code: str) -> Optional[str]:
        """
        检测代码语言

        Args:
            code: 代码字符串

        Returns:
            str: 检测到的语言标识符，未知时返回 None
        """
        code_lower = code.lower().strip()

        # Python 检测
        python_patterns = [
            r'^import\s+\w+',
            r'^from\s+\w+\s+import',
            r'^def\s+\w+\s*\(',
            r'^class\s+\w+\s*[:(]',
            r'print\s*\(',
            r'if\s+__name__\s*==\s*[\'"]__main__[\'"]',
            r'\[.*for\s+\w+\s+in\s+.*\]',
            r'\.append\s*\(',
            r'\.extend\s*\('
        ]

        for pattern in python_patterns:
            if re.search(pattern, code):
                return 'python'

        # JavaScript 检测
        js_patterns = [
            r'console\.log\s*\(',
            r'function\s+\w+\s*\(',
            r'const\s+\w+\s*=',
            r'let\s+\w+\s*=',
            r'=>\s*\{',
            r'require\s*\(',
            r'module\.exports',
            r'\.forEach\s*\(',
            r'\.map\s*\('
        ]

        for pattern in js_patterns:
            if re.search(pattern, code):
                return 'javascript'

        # Bash 检测
        bash_patterns = [
            r'^#!\s*/bin/(ba)?sh',
            r'echo\s+["\']',
            r'\$\(',
            r'if\s+\[\s+.*\s+\]',
            r'for\s+\w+\s+in\s+.*;',
            r'sudo\s+',
            r'apt-get\s+',
            r'yum\s+'
        ]

        for pattern in bash_patterns:
            if re.search(pattern, code, re.MULTILINE):
                return 'bash'

        return 'python'

    def analyze_and_execute(self, user_message: str) -> Tuple[bool, Optional[str]]:
        """
        分析用户消息并执行代码（如需要）

        Args:
            user_message: 用户输入的消息

        Returns:
            Tuple[bool, str]: (是否执行了代码, 执行结果)
        """
        # 检测是否需要执行代码
        execution_keywords = [
            '运行代码',
            '执行代码',
            '运行这段代码',
            'execute this code',
            'run this code',
            '帮我运行',
            '代码执行',
            'run python',
            '运行 python',
            'execute python'
        ]

        should_execute = any(keyword in user_message for keyword in execution_keywords)

        if not should_execute:
            return False, None

        # 提取代码块
        code_blocks = self._extract_code_blocks(user_message)

        if not code_blocks:
            return False, None

        # 执行代码
        results = []
        for i, code_info in enumerate(code_blocks):
            language = code_info.get('language', 'python')
            code = code_info.get('code', '')

            if code:
                print(f'执行第 {i+1} 个代码块 ({language})...')
                result = self._safe_execute(code, language)
                results.append(f'代码块 {i+1} ({language}):\n{result}')

        if results:
            return True, '\n\n'.join(results)

        return False, None

    def _extract_code_blocks(self, text: str) -> List[Dict[str, str]]:
        """
        从文本中提取代码块

        Args:
            text: 包含代码的文本

        Returns:
            List[Dict]: 代码块列表，每个包含 language 和 code
        """
        code_blocks = []

        # 处理 Markdown 代码块
        markdown_pattern = r'```(\w+)?\n([\s\S]*?)```'
        matches = re.findall(markdown_pattern, text, re.MULTILINE)

        for lang, code in matches:
            language = lang.lower() if lang else self.detect_language(code)
            code_blocks.append({
                'language': language or 'python',
                'code': code.strip()
            })

        # 处理行内代码
        if not code_blocks:
            inline_pattern = r'`([^`]+)`'
            matches = re.findall(inline_pattern, text)

            for code in matches:
                language = self.detect_language(code)
                if language:
                    code_blocks.append({
                        'language': language,
                        'code': code.strip()
                    })

        return code_blocks

    def _safe_execute(self, code: str, language: str = 'python') -> str:
        """
        安全地执行代码

        Args:
            code: 要执行的代码
            language: 编程语言

        Returns:
            str: 执行结果或错误信息
        """
        start_time = time.time()
        output_lines = []
        error_lines = []

        try:
            if language == 'python':
                return self._execute_python(code)
            elif language == 'javascript':
                return self._execute_javascript(code)
            elif language == 'bash':
                return self._execute_bash(code)
            else:
                return self._execute_python(code)

        except subprocess.TimeoutExpired:
            return '错误: 代码执行超时（超过30秒）'
        except Exception as e:
            return f'错误: {str(e)}'
        finally:
            execution_time = time.time() - start_time
            self.execution_history.append({
                'timestamp': datetime.now().isoformat(),
                'language': language,
                'execution_time': execution_time,
                'success': '错误' not in output_lines and 'Error' not in output_lines
            })

    def _execute_python(self, code: str) -> str:
        """
        执行 Python 代码

        Args:
            code: Python 代码

        Returns:
            str: 执行结果
        """
        output_capture = OutputCapture()

        try:
            # 创建临时文件执行
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp_file:
                tmp_file.write(code)
                tmp_file_path = tmp_file.name

            try:
                # 使用子进程执行，限制时间和资源
                result = subprocess.run(
                    [sys.executable, tmp_file_path],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    cwd=tmp_file_path.replace('.py', '_files') if os.path.exists(tmp_file_path.replace('.py', '_files')) else None
                )

                output = result.stdout
                error = result.stderr

                if output:
                    output_capture.add_output(output)
                if error:
                    output_capture.add_error(error)

                if not output and not error:
                    output_capture.add_output('代码执行完成，无输出')

                return output_capture.get_output()

            finally:
                # 清理临时文件
                if os.path.exists(tmp_file_path):
                    os.remove(tmp_file_path)

        except subprocess.TimeoutExpired:
            return '错误: Python 代码执行超时（超过30秒）'
        except Exception as e:
            return f'错误: Python 执行失败 - {str(e)}'

    def _execute_javascript(self, code: str) -> str:
        """
        执行 JavaScript 代码

        Args:
            code: JavaScript 代码

        Returns:
            str: 执行结果
        """
        try:
            # 检查是否有 Node.js
            result = subprocess.run(
                ['which', 'node'],
                capture_output=True,
                text=True
            )

            if result.returncode != 0:
                return '错误: 系统未安装 Node.js，无法执行 JavaScript'

            with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as tmp_file:
                tmp_file.write(code)
                tmp_file_path = tmp_file.name

            try:
                result = subprocess.run(
                    ['node', tmp_file_path],
                    capture_output=True,
                    text=True,
                    timeout=30
                )

                output = result.stdout
                error = result.stderr

                if output:
                    return output
                if error:
                    return f'错误: {error}'
                return '代码执行完成，无输出'

            finally:
                if os.path.exists(tmp_file_path):
                    os.remove(tmp_file_path)

        except subprocess.TimeoutExpired:
            return '错误: JavaScript 代码执行超时（超过30秒）'
        except Exception as e:
            return f'错误: JavaScript 执行失败 - {str(e)}'

    def _execute_bash(self, code: str) -> str:
        """
        执行 Bash 脚本

        Args:
            code: Bash 脚本代码

        Returns:
            str: 执行结果
        """
        try:
            result = subprocess.run(
                ['/bin/bash', '-c', code],
                capture_output=True,
                text=True,
                timeout=30,
                shell=False
            )

            output = result.stdout
            error = result.stderr
            return_code = result.returncode

            if output:
                return output
            if error:
                return f'错误 (退出码 {return_code}): {error}'
            return f'命令执行完成，退出码: {return_code}'

        except subprocess.TimeoutExpired:
            return '错误: Bash 命令执行超时（超过30秒）'
        except Exception as e:
            return f'错误: Bash 执行失败 - {str(e)}'

    def generate_code(self, instruction: str, language: str = 'python') -> str:
        """
        使用 Gemini 生成代码

        Args:
            instruction: 代码生成指令
            language: 目标编程语言

        Returns:
            str: 生成的代码
        """
        if not self.gemini_model:
            return f'错误: Gemini 模型未初始化，无法生成代码'

        try:
            prompt = f"""请根据以下要求生成 {language} 代码：

要求: {instruction}

请只返回代码，不要解释。如果需要注释，请使用中文。代码要用 markdown 代码块包裹，例如：
```{language}
# 你的代码
```
"""

            response = get_response_with_history(
                self.gemini_model,
                prompt,
                []
            )

            # 提取代码块
            code_blocks = self._extract_code_blocks(response)
            if code_blocks:
                return response

            return response

        except Exception as e:
            return f'错误: 代码生成失败 - {str(e)}'

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """
        获取执行历史

        Returns:
            List[Dict]: 执行历史记录列表
        """
        return self.execution_history

    def clear_history(self):
        """
        清空执行历史
        """
        self.execution_history = []


class OutputCapture:
    """
    输出捕获类

    辅助捕获和管理代码执行输出
    """

    def __init__(self):
        """
        初始化输出捕获器
        """
        self.outputs = []
        self.errors = []

    def add_output(self, text: str):
        """
        添加标准输出

        Args:
            text: 输出文本
        """
        if text and text.strip():
            self.outputs.append(text.strip())

    def add_error(self, text: str):
        """
        添加错误输出

        Args:
            text: 错误文本
        """
        if text and text.strip():
            self.errors.append(text.strip())

    def get_output(self) -> str:
        """
        获取完整输出

        Returns:
            str: 合并后的输出字符串
        """
        result_parts = []

        if self.outputs:
            result_parts.append('\n'.join(self.outputs))

        if self.errors:
            result_parts.append(f'错误输出:\n{chr(10).join(self.errors)}')

        if not result_parts:
            return '代码执行完成，无输出'

        return '\n'.join(result_parts)


# 模块初始化测试
if __name__ == '__main__':
    print('代码执行器模块测试')
    print('=' * 50)

    executor = CodeExecutor()

    # 测试代码检测
    test_code = '''
def hello():
    print("Hello, World!")
    return "Success"

hello()
'''

    language = executor.detect_language(test_code)
    print(f'检测到的语言: {language}')

    print('\n测试完成')
