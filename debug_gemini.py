#!/usr/bin/env python3
"""
Gemini API调试脚本

用于测试Gemini API连接和基本功能，确保模型能正常工作
"""

import os
import sys
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

def test_gemini_api():
    """
    测试Gemini API连接和生成功能
    
    Returns:
        bool: API测试是否成功
    """
    try:
        # 导入Google Gemini库
        import google.generativeai as genai
        
        # 获取API密钥
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            print("错误: 未设置GOOGLE_API_KEY环境变量")
            return False
        
        print("API密钥配置完成")
        
        # 配置API密钥
        genai.configure(api_key=api_key)
        print("Gemini API配置完成")
        
        # 获取可用模型列表
        print("正在获取可用模型列表...")
        models = genai.list_models()
        
        # 过滤支持生成内容的模型
        text_models = [model for model in models if 'generateContent' in model.supported_generation_methods]
        print(f"找到 {len(text_models)} 个支持generateContent的模型:")
        for model in text_models:
            print(f"- {model.name}")
        
        # 使用指定的模型进行测试（gemma-3-27b-it）
        test_model_name = "gemma-3-27b-it"
        test_model = next((model for model in text_models if test_model_name in model.name), None)
        
        if not test_model:
            print(f"错误: 没有找到模型 {test_model_name}")
            # 改用第一个可用模型
            if text_models:
                test_model = text_models[0]
                test_model_name = test_model.name
                print(f"改用模型 {test_model_name} 进行测试")
            else:
                return False
        
        print(f"\n使用模型 {test_model_name} 进行测试...")
        
        # 初始化模型
        model = genai.GenerativeModel(test_model_name)
        print("模型初始化完成")
        
        # 生成回复
        print("正在生成回复...")
        response = model.generate_content("你好")
        
        print(f"\n测试结果:")
        print(f"输入: 你好")
        print(f"输出: {response.text}")
        
        return True
        
    except Exception as e:
        print(f"错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== Gemini API调试脚本 ===\n")
    
    success = test_gemini_api()
    
    if success:
        print("\n✅ API测试成功!")
        sys.exit(0)
    else:
        print("\n❌ API测试失败!")
        sys.exit(1)