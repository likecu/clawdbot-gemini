#!/Users/aaa/python-sdk/python3.13.2/bin/python
# -*- coding: utf-8 -*-
"""
Gemini 图片OCR识别Python调用脚本
用于调用Google Gemini API进行图片OCR识别，返回识别结果
"""

import os
import argparse
import json
import datetime
import random
import google.genai as genai
from .gemini_config import GEMINI_API_KEYS

class GeminiOCR:
    def __init__(self, api_key=None):
        """
        初始化Gemini OCR识别类
        :param api_key: 可选，指定的API密钥。如果不提供，则从配置中随机选择。
        """
        if api_key:
            self.api_key = api_key
            self.current_key_index = -1
        elif GEMINI_API_KEYS:
            # 随机选择一个API密钥
            self.current_key_index = random.randint(0, len(GEMINI_API_KEYS) - 1)
            self.api_key = GEMINI_API_KEYS[self.current_key_index]
        else:
            # 如果都没有，尝试从环境变量获取
            self.api_key = os.getenv("GOOGLE_API_KEY", os.getenv("GEMINI_API_KEY"))
            if not self.api_key:
                raise ValueError("未提供 API Key，且 GEMINI_API_KEYS 列表为空，环境变量 GOOGLE_API_KEY/GEMINI_API_KEY 也未设置。")
            self.current_key_index = -1
        
        # 创建客户端实例
        self.client = genai.Client(api_key=self.api_key)
        
        # 本地使用量存储文件路径
        self.usage_file = os.path.join(os.path.dirname(__file__), "gemini_usage.json")
        
        # 模型速率限制数据
        self.rate_limits = {
            # Gemini 3.0 模型
            "gemini-3-pro-preview": {"rpm_limit": 3, "tpm_limit": 100000, "rpd_limit": 10},
            "": {"rpm_limit": 5, "tpm_limit": 250000, "rpd_limit": 20},
            "-lite": {"rpm_limit": 10, "tpm_limit": 100000, "rpd_limit": 40},
            
            # Gemini 2.5 模型
            "gemini-2.5-flash": {"rpm_limit": 5, "tpm_limit": 250000, "rpd_limit": 20},
            "gemini-2.5-flash-lite": {"rpm_limit": 10, "tpm_limit": 100000, "rpd_limit": 40},
            "gemini-2.5-flash-native-audio-dialog": {"rpm_limit": float('inf'), "tpm_limit": float('inf'), "rpd_limit": float('inf')},
            "gemini-2.5-pro": {"rpm_limit": 3, "tpm_limit": 100000, "rpd_limit": 10},
            
            # Gemma 3 模型
            "gemma-3-27b-it": {"rpm_limit": 5, "tpm_limit": 100000, "rpd_limit": 15},
            "gemma-3-12b-it": {"rpm_limit": 10, "tpm_limit": 50000, "rpd_limit": 20},
            "gemma-3-4b-it": {"rpm_limit": 15, "tpm_limit": 75000, "rpd_limit": 30},
            "gemma-3-1b-it": {"rpm_limit": 20, "tpm_limit": 100000, "rpd_limit": 40},
            "gemma-3-2b-it": {"rpm_limit": 20, "tpm_limit": 100000, "rpd_limit": 40},
            "gemma-3-9b-it": {"rpm_limit": 15, "tpm_limit": 75000, "rpd_limit": 30},
            
            # Gemma 2 模型
            "gemma-2-27b-it": {"rpm_limit": 10, "tpm_limit": 50000, "rpd_limit": 20},
            "gemma-2-9b-it": {"rpm_limit": 20, "tpm_limit": 100000, "rpd_limit": 40},
            "gemma-2-2b-it": {"rpm_limit": 50, "tpm_limit": 200000, "rpd_limit": 100},
            
            # Gemma 1.1 模型
            "gemma-1.1-7b-it": {"rpm_limit": 20, "tpm_limit": 100000, "rpd_limit": 40},
            "gemma-1.1-2b-it": {"rpm_limit": 50, "tpm_limit": 200000, "rpd_limit": 100},
            
            # Gemma 1 模型
            "gemma-1-7b-it": {"rpm_limit": 20, "tpm_limit": 100000, "rpd_limit": 40},
            "gemma-1-2b-it": {"rpm_limit": 50, "tpm_limit": 200000, "rpd_limit": 100},
            
            # Gemini 1.5 模型
            "gemini-1.5-pro": {"rpm_limit": 5, "tpm_limit": 10000, "rpd_limit": 10},
            "gemini-1.5-flash": {"rpm_limit": 5, "tpm_limit": 250000, "rpd_limit": 20},
            
            # 其他模型
            "gemini-ultra": {"rpm_limit": 5, "tpm_limit": 10000, "rpd_limit": 10},
            "gemini-nano": {"rpm_limit": 50, "tpm_limit": 200000, "rpd_limit": 100},
            "gemini-experimental": {"rpm_limit": 2, "tpm_limit": 5000, "rpd_limit": 5},
            "gemini-flash-latest": {"rpm_limit": 5, "tpm_limit": 250000, "rpd_limit": 20},
            "gemini-pro-latest": {"rpm_limit": 3, "tpm_limit": 100000, "rpd_limit": 10},
            "gemini-3-pro-preview": {"rpm_limit": 3, "tpm_limit": 100000, "rpd_limit": 10},
            "": {"rpm_limit": 5, "tpm_limit": 250000, "rpd_limit": 20}
        }
        
        # 模型能力配置文件路径
        self.model_capabilities_file = os.path.join(os.path.dirname(__file__), "model_capabilities.json")
        
        # 检查模型能力配置文件是否存在，如果不存在则使用默认配置（避免运行时生成，太慢）
        if not os.path.exists(self.model_capabilities_file):
            print("模型能力配置文件不存在，使用内置默认配置（跳过耗时检测）")
            # self.generate_model_capabilities() # 禁用自动生成
            self.model_capabilities = {} # 将使用下面的默认优先级
        else:
            # 加载模型能力配置
            self.model_capabilities = self.load_model_capabilities()
        
        # 模型优先级列表（优先使用高限额且高性能模型）
        self.model_priority = self.model_capabilities.get("model_priority", {
            "text_only": [
                "gemini-2.5-flash", 
                "gemini-3-pro-preview",
                "gemini-2.5-flash-lite"
            ],
            "image_supported": [
                "gemini-2.5-flash",
                "gemini-3-pro-preview"
            ],
            "document_supported": [
                "gemini-2.5-flash",
                "gemini-3-pro-preview"
            ]
        })

        
        # 选择合适的模型（默认文本模型）
        self.model_name = self.select_best_model(task_type="text_only")
        print(f"使用模型: {self.model_name}")
    
    def ask_question(self, question):
        """
        直接向Gemini提问
        :param question: 提问内容
        :return: 提问结果对象
        """
        # 选择适合文本提问的模型
        self.model_name = self.select_best_model(task_type="text_only")
        print(f"开始提问: {question}")
        print(f"当前使用模型: {self.model_name}")
        
        # 尝试提问，支持模型切换
        max_attempts = 3
        current_attempt = 0
        
        while current_attempt < max_attempts:
            try:
                # 直接使用文本内容
                contents = [question]
                
                # 调用Gemini API
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents
                )
                
                # 估算使用的令牌数（简单估算）
                tokens_used = len(response.text) * 1.5  # 粗略估算：每个汉字约1.5个令牌
                
                # 更新本地使用量记录
                self.update_usage(self.model_name, int(tokens_used))
                
                print(f"使用量更新: {self.model_name} - RPM: +1, TPM: +{int(tokens_used)}")
                
                # 返回结果对象
                return {
                    "success": True,
                    "response": response.text,
                    "model": self.model_name,
                    "tokens_used": int(tokens_used),
                    "chatHistory": [
                        {"type": "user", "content": question},
                        {"type": "ai", "content": response.text}
                    ]
                }
                
            except Exception as e:
                error_msg = str(e)
                print(f"调用Gemini API时发生错误: {error_msg}")
                
                # 检查是否是配额超限错误
                if "quota exceeded" in error_msg.lower() or "429" in error_msg:
                    print(f"模型 {self.model_name} 配额已用完，尝试切换模型或API密钥...")
                    current_attempt += 1
                    
                    # 尝试切换API密钥
                    if len(GEMINI_API_KEYS) > 1:
                        self.current_key_index = (self.current_key_index + 1) % len(GEMINI_API_KEYS)
                        self.api_key = GEMINI_API_KEYS[self.current_key_index]
                        self.client = genai.Client(api_key=self.api_key)
                        print(f"已切换到新API密钥: {self.api_key[:10]}...")
                    
                    # 从优先级列表中移除当前模型
                    if self.model_name in self.model_priority.get("text_only", []):
                        self.model_priority["text_only"].remove(self.model_name)
                    
                    # 选择新的模型
                    new_model = self.select_best_model(task_type="text_only")
                    if new_model != self.model_name:
                        self.model_name = new_model
                        print(f"已切换到新模型: {self.model_name}")
                    else:
                        print("没有可用的替代模型")
                        break
                else:
                    # 其他错误，直接返回
                    return None
        
        print(f"尝试了 {current_attempt} 次后仍无法完成提问")
        return None
    
    def recognize_image(self, image_path, question="图里有什么内容？"):
        """
        通过Gemini API识别图片内容
        :param image_path: 图片路径
        :param question: 向Gemini提问的问题
        :return: 识别结果字符串
        """
        # 验证并获取绝对路径
        image_path = os.path.abspath(image_path)
        
        if not os.path.exists(image_path):
            print(f"图片文件不存在: {image_path}")
            return None
        
        # 选择适合图像识别的模型
        self.model_name = self.select_best_model(task_type="image_supported")
        print(f"开始识别图片: {image_path}")
        print(f"提问内容: {question}")
        print(f"当前使用模型: {self.model_name}")
        
        # 尝试识别图片，支持模型切换
        max_attempts = 3
        current_attempt = 0
        
        while current_attempt < max_attempts:
            try:
                # 使用内嵌方式传递图片数据
                from google.genai import types
                with open(image_path, 'rb') as f:
                    image_bytes = f.read()
                
                # 构建消息内容
                print(f"[DEBUG] 构建请求: 模型={self.model_name}, 图片路径={image_path}")
                contents = [
                    types.Part.from_bytes(
                        data=image_bytes,
                        mime_type='image/jpeg' if image_path.lower().endswith(('.jpg', '.jpeg')) else 'image/png'
                    ),
                    question
                ]
                
                # 调用Gemini API
                print(f"[DEBUG] 正在调用 Gemini API...")
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents
                )
                print(f"[DEBUG] API 调用成功")
                
                # 估算使用的令牌数（简单估算）
                tokens_used = len(response.text) * 1.5  # 粗略估算：每个汉字约1.5个令牌
                
                # 更新本地使用量记录
                self.update_usage(self.model_name, int(tokens_used))
                
                print(f"使用量更新: {self.model_name} - RPM: +1, TPM: +{int(tokens_used)}")
                
                # 返回结果对象
                return {
                    "success": True,
                    "response": response.text,
                    "model": self.model_name,
                    "tokens_used": int(tokens_used),
                    "chatHistory": [
                        {"type": "user", "content": question},
                        {"type": "ai", "content": response.text}
                    ]
                }
                
            except Exception as e:
                error_msg = str(e)
                print(f"调用Gemini API时发生错误: {error_msg}")
                
                # 检查是否是配额超限错误
                if "quota exceeded" in error_msg.lower() or "429" in error_msg:
                    print(f"模型 {self.model_name} 配额已用完，尝试切换模型或API密钥...")
                    current_attempt += 1
                    
                    # 尝试切换API密钥
                    if len(GEMINI_API_KEYS) > 1:
                        self.current_key_index = (self.current_key_index + 1) % len(GEMINI_API_KEYS)
                        self.api_key = GEMINI_API_KEYS[self.current_key_index]
                        self.client = genai.Client(api_key=self.api_key)
                        print(f"已切换到新API密钥: {self.api_key[:10]}...")
                    
                    # 从优先级列表中移除当前模型
                    if self.model_name in self.model_priority.get("image_supported", []):
                        self.model_priority["image_supported"].remove(self.model_name)
                    
                    # 选择新的模型
                    new_model = self.select_best_model(task_type="image_supported")
                    if new_model != self.model_name:
                        self.model_name = new_model
                        print(f"已切换到新模型: {self.model_name}")
                    else:
                        print("没有可用的替代模型")
                        break
                elif "modality" in error_msg.lower() or "multimodal" in error_msg.lower():
                    print(f"[DEBUG] 捕获到模态错误: {error_msg}")
                    print(f"模型 {self.model_name} 不支持图片输入，尝试切换到 Gemini 3.0 Flash...")
                    current_attempt += 1
                    self.model_name = ""
                else:
                    # 其他错误，直接返回
                    print(f"[DEBUG] 捕获到非模态错误: {error_msg}")
                    return None
        
        print(f"尝试了 {current_attempt} 次后仍无法完成识别")
        return None
    
    def process_document(self, document_path, question="文档内容是什么？"):
        """
        通过Gemini API处理文档内容（PDF等）
        :param document_path: 文档路径
        :param question: 向Gemini提问的问题
        :return: 处理结果字符串
        """
        # 验证并获取绝对路径
        document_path = os.path.abspath(document_path)
        
        if not os.path.exists(document_path):
            print(f"文档文件不存在: {document_path}")
            return None
        
        # 选择适合文档处理的模型
        self.model_name = self.select_best_model(task_type="document_supported")
        print(f"开始处理文档: {document_path}")
        print(f"提问内容: {question}")
        print(f"当前使用模型: {self.model_name}")
        
        # 尝试处理文档，支持模型切换
        max_attempts = 3
        current_attempt = 0
        
        while current_attempt < max_attempts:
            try:
                # 使用内嵌方式传递文档数据
                from google.genai import types
                with open(document_path, 'rb') as f:
                    doc_bytes = f.read()
                
                # 构建消息内容
                contents = [
                    types.Part.from_bytes(
                        data=doc_bytes,
                        mime_type='application/pdf'
                    ),
                    question
                ]
                
                # 调用Gemini API
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=contents
                )
                
                # 估算使用的令牌数（简单估算）
                tokens_used = len(response.text) * 1.5  # 粗略估算：每个汉字约1.5个令牌
                
                # 更新本地使用量记录
                self.update_usage(self.model_name, int(tokens_used))
                
                print(f"使用量更新: {self.model_name} - RPM: +1, TPM: +{int(tokens_used)}")
                
                # 返回结果对象
                return {
                    "success": True,
                    "response": response.text,
                    "model": self.model_name,
                    "tokens_used": int(tokens_used),
                    "chatHistory": [
                        {"type": "user", "content": question},
                        {"type": "ai", "content": response.text}
                    ]
                }
                
            except Exception as e:
                error_msg = str(e)
                print(f"调用Gemini API时发生错误: {error_msg}")
                
                # 检查是否是配额超限错误
                if "quota exceeded" in error_msg.lower() or "429" in error_msg:
                    print(f"模型 {self.model_name} 配额已用完，尝试切换模型或API密钥...")
                    current_attempt += 1
                    
                    # 尝试切换API密钥
                    if len(GEMINI_API_KEYS) > 1:
                        self.current_key_index = (self.current_key_index + 1) % len(GEMINI_API_KEYS)
                        self.api_key = GEMINI_API_KEYS[self.current_key_index]
                        self.client = genai.Client(api_key=self.api_key)
                        print(f"已切换到新API密钥: {self.api_key[:10]}...")
                    
                    # 从优先级列表中移除当前模型
                    if self.model_name in self.model_priority.get("document_supported", []):
                        self.model_priority["document_supported"].remove(self.model_name)
                    
                    # 选择新的模型
                    new_model = self.select_best_model(task_type="document_supported")
                    if new_model != self.model_name:
                        self.model_name = new_model
                        print(f"已切换到新模型: {self.model_name}")
                    else:
                        print("没有可用的替代模型")
                        break
                else:
                    # 其他错误，直接返回
                    return None
        
        print(f"尝试了 {current_attempt} 次后仍无法完成文档处理")
        return None
    
    def get_ocr_result(self, result, question="图里有什么内容？"):
        """
        从识别结果中提取OCR识别文本
        :param result: 识别结果对象
        :param question: 向Gemini提问的问题
        :return: 识别结果字符串
        """
        if result and result.get("success"):
            return result.get("response", "识别失败")
        return "识别失败"
    

    
    def load_usage_data(self):
        """
        加载本地使用量数据
        :return: 使用量数据字典
        """
        if not os.path.exists(self.usage_file):
            return {}
        
        try:
            with open(self.usage_file, 'r', encoding='utf-8') as f:
                usage_data = json.load(f)
            
            # 检查数据格式是否为旧格式
            today = datetime.date.today().isoformat()
            if today in usage_data and isinstance(usage_data[today], dict):
                # 检查旧格式的标志：直接包含模型名称作为键
                has_old_format = False
                for key in usage_data[today]:
                    if isinstance(usage_data[today][key], dict) and "rpm_used" in usage_data[today][key]:
                        has_old_format = True
                        break
                
                if has_old_format:
                    # 转换为新格式
                    new_usage_data = {}
                    for date in usage_data:
                        new_usage_data[date] = {
                            "model_stats": {},
                            "minute_stats": {}
                        }
                        for model in usage_data[date]:
                            new_usage_data[date]["model_stats"][model] = {
                                "rpd_used": usage_data[date][model]["rpd_used"]
                            }
                    usage_data = new_usage_data
            
            return usage_data
        except json.JSONDecodeError:
            print(f"警告: {self.usage_file} 文件格式错误，将重新创建")
            return {}
    
    def save_usage_data(self, usage_data):
        """
        保存本地使用量数据
        :param usage_data: 使用量数据字典
        """
        try:
            with open(self.usage_file, 'w', encoding='utf-8') as f:
                json.dump(usage_data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"警告: 无法保存使用量数据到 {self.usage_file}: {e}")
    
    def update_usage(self, model_name, tokens_used=100):
        """
        更新本地使用量记录
        :param model_name: 模型名称
        :param tokens_used: 使用的令牌数
        """
        today = datetime.date.today().isoformat()
        now = datetime.datetime.now()
        current_minute = now.strftime("%Y-%m-%d %H:%M")
        
        usage_data = self.load_usage_data()
        
        # 初始化今天的数据
        if today not in usage_data:
            usage_data[today] = {
                "model_stats": {},
                "minute_stats": {}
            }
        
        # 初始化模型当天统计数据
        if model_name not in usage_data[today]["model_stats"]:
            usage_data[today]["model_stats"][model_name] = {
                "rpd_used": 0  # 当天总请求数
            }
        
        # 初始化当前分钟统计数据
        if current_minute not in usage_data[today]["minute_stats"]:
            usage_data[today]["minute_stats"][current_minute] = {}
        
        if model_name not in usage_data[today]["minute_stats"][current_minute]:
            usage_data[today]["minute_stats"][current_minute][model_name] = {
                "rpm_used": 0,  # 当分钟请求数
                "tpm_used": 0   # 当分钟令牌数
            }
        
        # 更新使用量
        usage_data[today]["model_stats"][model_name]["rpd_used"] += 1  # 当天总请求数+1
        usage_data[today]["minute_stats"][current_minute][model_name]["rpm_used"] += 1  # 当前分钟请求数+1
        usage_data[today]["minute_stats"][current_minute][model_name]["tpm_used"] += tokens_used  # 当前分钟令牌数增加
        
        # 清理旧的分钟统计数据（只保留最近10分钟的数据）
        self.cleanup_old_minute_stats(usage_data, today, now)
        
        # 保存数据
        self.save_usage_data(usage_data)
    
    def cleanup_old_minute_stats(self, usage_data, today, now):
        """
        清理旧的分钟统计数据，只保留最近10分钟的数据
        :param usage_data: 使用量数据字典
        :param today: 今天的日期字符串
        :param now: 当前时间对象
        """
        if today not in usage_data or "minute_stats" not in usage_data[today]:
            return
        
        minute_stats = usage_data[today]["minute_stats"]
        cutoff_time = now - datetime.timedelta(minutes=10)
        
        # 遍历并删除超过10分钟的统计数据
        for minute_str in list(minute_stats.keys()):
            minute_time = datetime.datetime.strptime(minute_str, "%Y-%m-%d %H:%M")
            if minute_time < cutoff_time:
                del minute_stats[minute_str]
    
    def get_today_usage(self, model_name):
        """
        获取今天的使用量
        :param model_name: 模型名称
        :return: 使用量字典 {"rpm_used": 0, "tpm_used": 0, "rpd_used": 0}
        """
        today = datetime.date.today().isoformat()
        now = datetime.datetime.now()
        current_minute = now.strftime("%Y-%m-%d %H:%M")
        
        usage_data = self.load_usage_data()
        
        # 初始化返回值
        rpm_used = 0
        tpm_used = 0
        rpd_used = 0
        
        # 获取当天总请求数
        if today in usage_data and "model_stats" in usage_data[today]:
            if model_name in usage_data[today]["model_stats"]:
                rpd_used = usage_data[today]["model_stats"][model_name].get("rpd_used", 0)
        
        # 获取当前分钟的请求数和令牌数
        if today in usage_data and "minute_stats" in usage_data[today]:
            if current_minute in usage_data[today]["minute_stats"]:
                if model_name in usage_data[today]["minute_stats"][current_minute]:
                    rpm_used = usage_data[today]["minute_stats"][current_minute][model_name].get("rpm_used", 0)
                    tpm_used = usage_data[today]["minute_stats"][current_minute][model_name].get("tpm_used", 0)
        
        return {"rpm_used": rpm_used, "tpm_used": tpm_used, "rpd_used": rpd_used}
    
    def is_model_available(self, model_name):
        """
        检查模型是否可用（不再进行限额检查，所有模型都可用）
        :param model_name: 模型名称
        :return: 是否可用
        """
        return True
    
    def load_model_capabilities(self):
        """
        加载模型能力配置
        :return: 模型能力配置字典
        """
        if not os.path.exists(self.model_capabilities_file):
            return {}
        
        try:
            with open(self.model_capabilities_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"警告: {self.model_capabilities_file} 文件格式错误，将重新创建")
            self.generate_model_capabilities()
            return self.load_model_capabilities()
    
    def generate_model_capabilities(self):
        """
        生成模型能力配置文件
        测试每个模型的文本生成、图像理解和文档处理能力
        """
        print(f"\n=== 生成模型能力配置文件 ===")
        print(f"将测试所有可用模型并生成 {self.model_capabilities_file}")
        
        # 测试图片和文档路径（使用默认测试文件）
        test_image_path = "/Volumes/600g/app1/doubao获取/test_valid_image.png"
        test_document_path = None  # 可以根据需要添加测试文档
        
        # 获取所有可用模型
        models = list(self.client.models.list())
        print(f"发现 {len(models)} 个可用模型")
        
        # 测试结果存储
        model_capabilities = {}
        text_only_models = []
        image_supported_models = []
        document_supported_models = []
        
        # 遍历所有模型进行测试
        for model in models:
            model_name = model.name
            print(f"\n测试模型: {model_name}")
            
            # 初始化模型能力
            capabilities = {
                "text_generation": False,
                "image_understanding": False,
                "document_processing": False
            }
            
            # 测试文本生成能力
            try:
                response = self.client.models.generate_content(
                    model=model_name,
                    contents=["你好，简单介绍一下自己。"]
                )
                capabilities["text_generation"] = True
                print(f"  ✓ 文本生成能力: 支持")
            except Exception as e:
                print(f"  ✗ 文本生成能力: 不支持 - {str(e)[:50]}...")
            
            # 测试图像理解能力（如果图片存在）
            if os.path.exists(test_image_path):
                try:
                    from google.genai import types
                    with open(test_image_path, 'rb') as f:
                        image_bytes = f.read()
                    
                    contents = [
                        types.Part.from_bytes(
                            data=image_bytes,
                            mime_type='image/jpeg' if test_image_path.endswith('.jpg') or test_image_path.endswith('.jpeg') else 'image/png'
                        ),
                        "图里有什么内容？"
                    ]
                    
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=contents
                    )
                    capabilities["image_understanding"] = True
                    print(f"  ✓ 图像理解能力: 支持")
                except Exception as e:
                    print(f"  ✗ 图像理解能力: 不支持 - {str(e)[:50]}...")
            
            # 测试文档处理能力（如果有测试文档）
            if test_document_path and os.path.exists(test_document_path):
                try:
                    from google.genai import types
                    with open(test_document_path, 'rb') as f:
                        doc_bytes = f.read()
                    
                    contents = [
                        types.Part.from_bytes(
                            data=doc_bytes,
                            mime_type='application/pdf'
                        ),
                        "文档内容是什么？"
                    ]
                    
                    response = self.client.models.generate_content(
                        model=model_name,
                        contents=contents
                    )
                    capabilities["document_processing"] = True
                    print(f"  ✓ 文档处理能力: 支持")
                except Exception as e:
                    print(f"  ✗ 文档处理能力: 不支持 - {str(e)[:50]}...")
            
            # 保存模型能力
            model_capabilities[model_name] = capabilities
            
            # 提取模型简称
            short_name = model_name.replace("models/", "")
            
            # 分类模型
            if capabilities["text_generation"]:
                text_only_models.append(short_name)
                
                if capabilities["image_understanding"]:
                    image_supported_models.append(short_name)
                
                if capabilities["document_processing"]:
                    document_supported_models.append(short_name)
        
        # 保存配置到文件
        config = {
            "model_capabilities": model_capabilities,
            "model_priority": {
                "text_only": text_only_models,
                "image_supported": image_supported_models,
                "document_supported": document_supported_models
            }
        }
        
        try:
            with open(self.model_capabilities_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            print(f"\n=== 模型能力配置文件生成完成 ===")
            print(f"配置文件已保存到: {self.model_capabilities_file}")
            print(f"文本生成模型: {len(text_only_models)} 个")
            print(f"图像支持模型: {len(image_supported_models)} 个")
            print(f"文档支持模型: {len(document_supported_models)} 个")
        except Exception as e:
            print(f"\n=== 生成模型能力配置文件失败 ===")
            print(f"错误信息: {e}")
    
    def select_best_model(self, task_type="text_only"):
        """
        根据优先级选择最优模型
        :param task_type: 任务类型，可选值：text_only, image_supported, document_supported
        :return: 最优模型名称
        """
        # 获取对应任务类型的模型优先级列表
        priority_list = self.model_priority.get(task_type, [])
        
        # 如果没有对应任务类型的模型列表，使用默认的text_only列表
        if not priority_list:
            priority_list = self.model_priority.get("text_only", [])
        
        # 遍历优先级列表，选择第一个可用的模型
        for model_name in priority_list:
            if self.is_model_available(model_name):
                return model_name
        
        # 如果没有可用模型，根据任务类型返回不同的默认模型
        if task_type == "image_supported":
            return ""
        elif task_type == "document_supported":
            return ""
        else:
            return ""
    
    def check_quota(self, show_details=False):
        """
        检查Gemini API限额
        通过发送一个小的请求并分析响应或错误信息来获取限额信息
        :param show_details: 是否显示详细的速率限制信息
        """
        print("正在检查Gemini API限额...")
        
        try:
            # 发送一个简单的文本请求来检查限额
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=["检查限额"]
            )
            print("✓ API请求成功，当前有可用限额")
            
            # 显示详细的速率限制信息
            if show_details:
                print("\n=== Gemini 模型速率限制详情 ===")
                print("\n模型名称\t\t\t\t类别\t\tRPM\t\tTPM\t\tRPD")
                print("-" * 120)
                
                # 模型速率限制数据
                rate_limits = [
                    ("gemini-2.5-flash", "文本输出模型", "2 / 5", "268 / 250K", "6 / 20"),
                    ("gemini-2.5-flash-lite", "轻量级模型", "3 / 10", "60 / 100K", "10 / 40"),
                    ("gemini-2.5-flash-native-audio-dialog", "无限制模型", "无限制", "无限制", "无限制"),
                    ("gemini-2.5-pro", "专业模型", "2 / 3", "200 / 100K", "4 / 10"),
                    ("gemma-3-12b-it", "文本模型", "4 / 10", "500 / 50K", "8 / 20"),
                    ("gemma-3-2b-it", "轻量级文本模型", "5 / 20", "1K / 100K", "10 / 40"),
                    ("gemma-3-9b-it", "文本模型", "6 / 15", "750 / 75K", "12 / 30"),
                    ("gemma-2-27b-it", "文本模型", "4 / 10", "500 / 50K", "8 / 20"),
                    ("gemma-2-9b-it", "文本模型", "5 / 20", "1K / 100K", "10 / 40"),
                    ("gemma-1.1-7b-it", "文本模型", "5 / 20", "1K / 100K", "10 / 40"),
                    ("gemma-1-7b-it", "文本模型", "5 / 20", "1K / 100K", "10 / 40"),
                    ("gemma-2-2b-it", "轻量级文本模型", "10 / 50", "2K / 200K", "20 / 100"),
                    ("gemma-1.1-2b-it", "轻量级文本模型", "10 / 50", "2K / 200K", "20 / 100"),
                    ("gemma-1-2b-it", "轻量级文本模型", "10 / 50", "2K / 200K", "20 / 100"),
                    ("gemini-nano", "移动端模型", "10 / 50", "2K / 200K", "20 / 100"),
                    ("gemini-1.5-pro", "高级模型", "1 / 5", "100 / 10K", "2 / 10"),
                    ("gemini-1.5-flash", "文本输出模型", "2 / 5", "268 / 250K", "6 / 20"),
                    ("gemini-ultra", "高级模型", "1 / 5", "100 / 10K", "2 / 10"),
                    ("gemini-nano", "移动端模型", "10 / 50", "2K / 200K", "20 / 100"),
                    ("gemini-experimental", "实验模型", "1 / 2", "50 / 5K", "2 / 5"),
                ]
                
                # 打印所有模型的速率限制
                for model, category, rpm, tpm, rpd in rate_limits:
                    print(f"{model:<40} {category:<15} {rpm:<10} {tpm:<12} {rpd:<10}")
            else:
                print("\n注意：Gemini API的Python SDK没有直接提供查询具体限额数字的方法。")
                print("使用 --quota-details 参数查看详细的速率限制信息")
                print("要查看详细的限额信息，请访问：https://ai.dev/usage?tab=rate-limit")
            
        except Exception as e:
            error_msg = str(e)
            print(f"✗ API请求失败: {error_msg}")
            
            if "quota exceeded" in error_msg.lower() or "429" in error_msg:
                print("\n原因：API限额已用完")
                print("建议：")
                print("1. 等待限额重置（通常为分钟或天级）")
                print("2. 升级到付费计划以获得更多限额")
                print("3. 检查详细限额信息：https://ai.dev/usage?tab=rate-limit")
            elif "403" in error_msg or "permission denied" in error_msg.lower():
                print("\n原因：权限错误")
                print("建议：检查API密钥是否有效且已正确配置")
            elif "404" in error_msg:
                print("\n原因：模型不存在或不可用")
                print("建议：检查模型名称是否正确")
            else:
                print("\n原因：其他API错误")
                print("建议：检查网络连接或稍后重试")
            
            return False
        
        return True


def main():
    """
    主函数，用于命令行调用
    """
    import json
    
    parser = argparse.ArgumentParser(description="Gemini图片OCR识别、文档处理和直接提问工具")
    parser.add_argument("file_path", help="文件路径（可选，不提供则直接提问），支持图片和PDF文档", nargs='?')
    parser.add_argument("--question", default="图里有什么内容？", help="提问内容（图片识别时默认为'图里有什么内容？'，文档处理时默认为'文档内容是什么？'，直接提问时为必填）")
    # 保留server参数以保持兼容性，但实际上Gemini不使用服务器
    parser.add_argument("--server", default="", help="(Gemini不使用)服务器地址")
    # 保留headless参数以保持兼容性
    parser.add_argument("--headless", type=lambda x: x.lower() in ['true', 'yes', '1'], default=True, help="(Gemini不使用)是否使用无头模式")
    parser.add_argument("--verbose", action="store_true", help="显示详细日志")
    parser.add_argument("--check-quota", action="store_true", help="检查Gemini API限额")
    parser.add_argument("--quota-details", action="store_true", help="显示详细的速率限制信息")
    parser.add_argument("--type", choices=['image', 'document', 'auto'], default='auto', help="文件类型，默认为自动检测")
    
    args = parser.parse_args()
    
    # 创建OCR实例
    ocr = GeminiOCR()
    
    # 检查限额
    if args.check_quota:
        ocr.check_quota(args.quota_details)
        return
    
    # 检查参数：直接提问时必须提供question
    if not args.file_path and args.question == "图里有什么内容？":
        parser.error("直接提问时必须使用--question参数提供问题内容")
    
    # 执行识别、文档处理或提问
    result = None
    if args.file_path:
        # 根据文件类型或自动检测选择处理方式
        file_type = args.type
        if file_type == 'auto':
            # 自动检测文件类型
            ext = os.path.splitext(args.file_path)[1].lower()
            if ext in ['.pdf']:
                file_type = 'document'
            else:
                file_type = 'image'
        
        if file_type == 'document':
            # 处理文档
            result = ocr.process_document(args.file_path, args.question)
        else:
            # 处理图片
            result = ocr.recognize_image(args.file_path, args.question)
    else:
        # 直接提问
        result = ocr.ask_question(args.question)
    
    if result:
        if args.verbose:
            # 详细模式：显示完整API响应和聊天记录
            print("\n=== 完整API响应 ===")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # 提取关键信息
        if result.get("success"):
            # 使用get_ocr_result从result中提取回答
            actual_response = ocr.get_ocr_result(result, args.question)
            print("\n=== 处理结果 ===")
            print(f"提问: {args.question}")
            print(f"回答: {actual_response}")
            
            if args.verbose:
                # 详细模式：显示聊天记录
                chat_history = result.get('chatHistory', [])
                print(f"\n聊天记录数量: {len(chat_history)}")
                
                # 打印每条聊天记录
                for i, msg in enumerate(chat_history):
                    print(f"\n消息 {i+1}:")
                    print(f"  类型: {msg.get('type', '')}")
                    print(f"  内容: {msg.get('content', '')}")
    else:
        print("处理失败")


if __name__ == "__main__":
    main()