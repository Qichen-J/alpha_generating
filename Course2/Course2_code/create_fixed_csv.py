#!/usr/bin/env python3
"""
创建修复后的 alpha 列表用于重新提交
"""

import csv
import json

def create_fixed_alphas_csv():
    """创建包含修复后表达式的 CSV 文件"""

    # 修复后的表达式映射 - 使用 CSV 中的实际格式（包含末尾的 \"）
    fixed_expressions = {
        'vec_avg(historical_volatility_10),sector),bucket(rank(cap),range=""0.1,1,0.1""))\\': "vec_avg(historical_volatility_10),sector),bucket(rank(cap),range='0.1,1,0.1')",
        'vec_avg(historical_volatility_120),sector),bucket(rank(cap),range=""0.1,1,0.1""))\\': "vec_avg(historical_volatility_120),sector),bucket(rank(cap),range='0.1,1,0.1')",
        'vec_avg(historical_volatility_150),sector),bucket(rank(cap),range=""0.1,1,0.1""))\\': "vec_avg(historical_volatility_150),sector),bucket(rank(cap),range='0.1,1,0.1')",
        'vec_avg(historical_volatility_180),sector),bucket(rank(cap),range=""0.1,1,0.1""))\\': "vec_avg(historical_volatility_180),sector),bucket(rank(cap),range='0.1,1,0.1')",
        'group_neutralize(group_zscore(cap,sector),bucket(rank(cap),range=""0.1,1,0.1"")))\\': "group_neutralize(group_zscore(cap,sector),bucket(rank(cap),range='0.1,1,0.1'))",
        "ts_ir(returns-group_median(returns,sector),126))": "ts_mean(returns-group_median(returns,sector),126)/ts_std_dev(returns-group_median(returns,sector),126)",
        'fear = ts_mean(abs(returns - group_mean(returns,1,market))/(abs(returns)+abs(group_mean(returns,1,market))+0.1),20);\\': "ts_mean(abs(returns - group_mean(returns,1,market))/(abs(returns)+abs(group_mean(returns,1,market))+0.1),20)",
        "-group_neutralize(fear*group_normalize(ts_decay_exp_window(ts_percentage(vec_count(rsk82_raw_m3g_tni_p_su_fte),60,percentage=0.9)\\": "-group_neutralize(ts_mean(abs(returns - group_mean(returns,1,market))/(abs(returns)+abs(group_mean(returns,1,market))+0.1),20)*group_normalize(ts_decay_exp_window(ts_delta(vec_count(rsk82_raw_m3g_tni_p_su_fte),60)-ts_delta(vec_count(historical_volatility_10),60),20, factor=0.8),market)*inverse(abs(ts_entropy(volume,20))),bucket(rank(cap),range='0.1,1,0.1'))",
        "-ts_percentage(vec_count(historical_volatility_10),60,percentage=0.1),20, factor=0.8),market)*inverse(abs(ts_entropy(volume,20)))\\": "-ts_delta(vec_count(historical_volatility_10),60)"
    }

    # 读取原始扩展模板
    expanded_df = []
    with open("/Users/zhiqu/Desktop/brain/Course2/Course2_code/outputs/expanded_templates.csv", 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            expr = row['expression']
            # 应用修复
            if expr in fixed_expressions:
                row['expression'] = fixed_expressions[expr]
                row['fixed'] = 'true'
            else:
                row['fixed'] = 'false'
            expanded_df.append(row)

    # 保存修复后的版本
    output_file = "/Users/zhiqu/Desktop/brain/Course2/Course2_code/outputs/expanded_templates_fixed.csv"
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        if expanded_df:
            writer = csv.DictWriter(f, fieldnames=expanded_df[0].keys())
            writer.writeheader()
            writer.writerows(expanded_df)

    print(f"修复后的模板已保存到: {output_file}")
    print(f"总共 {len(expanded_df)} 个模板")
    print(f"修复了 {sum(1 for row in expanded_df if row['fixed'] == 'true')} 个有语法错误的模板")

    return output_file

if __name__ == "__main__":
    create_fixed_alphas_csv()