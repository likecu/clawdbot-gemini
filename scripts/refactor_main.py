import os

def refactor():
    """
    重构 src/main.py 文件
    
    主要功能：
    1. 读取 src/main.py 文件内容
    2. 查找特定的代码块（从 "2. Ignore self messages logic" 到 "[Debug] 发送调试信息"）
    3. 将该代码块替换为调用 message_processor.process 的新逻辑
    4. 将修改后的内容写回文件
    """
    file_path = "src/main.py"
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except FileNotFoundError:
        print(f"错误：找不到文件 {file_path}")
        return

    start_idx = -1
    end_idx = -1

    # 定义要查找的起始和结束标记
    start_marker = "# 2. Ignore self messages logic"
    end_marker = "# [Debug] 发送调试信息"

    # 遍历所有行以找到标记的位置
    for i, line in enumerate(lines):
        if start_marker in line:
            start_idx = i
        if end_marker in line and i > start_idx and start_idx != -1:
            end_idx = i
            break
    
    # 如果找到完整的代码块，进行替换
    if start_idx != -1 and end_idx != -1:
        print(f"在第 {start_idx+1} 行到第 {end_idx} 行找到目标代码块")
        
        # 保留起始标记之前的内容
        new_lines = lines[:start_idx]
        
        # 插入新的逻辑代码
        new_lines.append("            # 2. Process via Service (OCR + Session + Agent)\n")
        new_lines.append("            result = await self.message_processor.process(message)\n")
        new_lines.append("\n") # 添加空行以提高可读性
        
        # 保留结束标记之后的内容
        new_lines.extend(lines[end_idx:])
        
        # 将新内容写回文件
        with open(file_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print("成功重构 main.py")
    else:
        print("未找到标记")
        print(f"起始标记位置: {start_idx}")
        print(f"结束标记位置: {end_idx}")

if __name__ == "__main__":
    refactor()
