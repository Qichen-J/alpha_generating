#!/usr/bin/env python3
"""
Alpha 语法修复工具
修复模板展开过程中产生的语法错误
"""

import re
import json
from pathlib import Path

def fix_alpha_syntax(expression: str) -> str:
    """
    修复常见的 alpha 语法错误
    """
    # 移除多余的反斜杠转义
    expression = expression.replace('\\', '')

    # 修复括号不匹配问题
    # 统计左右括号
    left_parens = expression.count('(')
    right_parens = expression.count(')')

    if left_parens > right_parens:
        # 多余左括号，移除末尾多余的左括号
        diff = left_parens - right_parens
        expression = expression.rstrip('(' * diff)
    elif right_parens > left_parens:
        # 多余右括号，移除末尾多余的右括号
        diff = right_parens - left_parens
        expression = expression.rstrip(')' * diff)

    # 修复多余逗号
    # 移除函数调用末尾的多余逗号
    expression = re.sub(r',(\s*\)\s*)$', r'\1', expression)

    # 修复 range 参数格式
    # 将 range="0.1,1,0.1" 改为 range='0.1,1,0.1'
    expression = re.sub(r'range="([^"]*)"', r"range='\1'", expression)

    # 移除末尾多余的分号
    expression = expression.rstrip(';')

    return expression.strip()

def analyze_syntax_errors(csv_file: str) -> dict:
    """
    分析 CSV 文件中的语法错误
    """
    results = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    for i, line in enumerate(lines[1:], 1):  # 跳过表头
        # 使用更简单的方法解析 CSV
        # 找到最后一个逗号前的部分和JSON部分
        last_comma_idx = line.rfind(',', 0, -1)  # 找到倒数第二个逗号
        if last_comma_idx == -1:
            continue

        prefix = line[:last_comma_idx]
        json_part = line[last_comma_idx + 1:].strip()

        # 解析前缀部分
        parts = prefix.split(',', 5)  # 分割前6个字段
        if len(parts) >= 6:
            idx = parts[0]
            template_id = parts[1]
            expression = parts[2].strip('"')
            status = parts[3]
            alpha_id = parts[4]
            location = parts[5]

            # 检查是否有错误
            if "ERROR" in json_part:
                try:
                    # 清理 JSON 字符串
                    json_str = json_part.strip('"').replace('\\"', '"')
                    error_data = json.loads(json_str)
                    message = error_data.get("message", "")
                    error_location = error_data.get("location", {})

                    results.append({
                        "idx": idx,
                        "expression": expression,
                        "error_message": message,
                        "error_location": error_location,
                        "fixed_expression": fix_alpha_syntax(expression)
                    })
                except (json.JSONDecodeError, KeyError):
                    # 如果 JSON 解析失败，至少记录基本信息
                    results.append({
                        "idx": idx,
                        "expression": expression,
                        "error_message": "JSON parse error",
                        "fixed_expression": fix_alpha_syntax(expression)
                    })

    return results

def main():
    # 分析语法错误
    csv_file = "/Users/zhiqu/Desktop/brain/Course2/Course2_code/outputs/simulation_status.csv"
    errors = analyze_syntax_errors(csv_file)

    print(f"发现 {len(errors)} 个语法错误：")
    print("=" * 50)

    for error in errors[:5]:  # 只显示前5个
        print(f"索引: {error['idx']}")
        print(f"原始表达式: {error['expression']}")
        print(f"错误信息: {error['error_message']}")
        print(f"修复后表达式: {error['fixed_expression']}")
        print("-" * 30)

    # 保存修复结果
    output_file = "/Users/zhiqu/Desktop/brain/Course2/Course2_code/outputs/fixed_expressions.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(errors, f, ensure_ascii=False, indent=2)

    print(f"\n修复结果已保存到: {output_file}")

if __name__ == "__main__":
    main()