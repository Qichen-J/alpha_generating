#!/usr/bin/env python3
"""
手动修复已知语法错误的 alpha 表达式
"""

def fix_known_expressions():
    """修复已知的语法错误表达式"""

    fixes = [
        {
            "original": 'vec_avg(historical_volatility_10),sector),bucket(rank(cap),range=""0.1,1,0.1""))',
            "fixed": "vec_avg(historical_volatility_10),sector),bucket(rank(cap),range='0.1,1,0.1')"
        },
        {
            "original": 'vec_avg(historical_volatility_120),sector),bucket(rank(cap),range=""0.1,1,0.1""))',
            "fixed": "vec_avg(historical_volatility_120),sector),bucket(rank(cap),range='0.1,1,0.1')"
        },
        {
            "original": 'vec_avg(historical_volatility_150),sector),bucket(rank(cap),range=""0.1,1,0.1""))',
            "fixed": "vec_avg(historical_volatility_150),sector),bucket(rank(cap),range='0.1,1,0.1')"
        },
        {
            "original": 'vec_avg(historical_volatility_180),sector),bucket(rank(cap),range=""0.1,1,0.1""))',
            "fixed": "vec_avg(historical_volatility_180),sector),bucket(rank(cap),range='0.1,1,0.1')"
        },
        {
            "original": 'group_neutralize(group_zscore(cap,sector),bucket(rank(cap),range=""0.1,1,0.1"")))',
            "fixed": "group_neutralize(group_zscore(cap,sector),bucket(rank(cap),range='0.1,1,0.1'))"
        },
        {
            "original": "ts_ir(returns-group_median(returns,sector),126))",
            "fixed": "ts_mean(returns-group_median(returns,sector),126)/ts_std_dev(returns-group_median(returns,sector),126)"
        },
        {
            "original": 'fear = ts_mean(abs(returns - group_mean(returns,1,market))/(abs(returns)+abs(group_mean(returns,1,market))+0.1),20);"',
            "fixed": "ts_mean(abs(returns - group_mean(returns,1,market))/(abs(returns)+abs(group_mean(returns,1,market))+0.1),20)"
        },
        {
            "original": "-group_neutralize(fear*group_normalize(ts_decay_exp_window(ts_percentage(vec_count(rsk82_raw_m3g_tni_p_su_fte),60,percentage=0.9)",
            "fixed": "-group_neutralize(ts_mean(abs(returns - group_mean(returns,1,market))/(abs(returns)+abs(group_mean(returns,1,market))+0.1),20)*group_normalize(ts_decay_exp_window(ts_delta(vec_count(rsk82_raw_m3g_tni_p_su_fte),60)-ts_delta(vec_count(historical_volatility_10),60),20, factor=0.8),market)*inverse(abs(ts_entropy(volume,20))),bucket(rank(cap),range='0.1,1,0.1'))"
        },
        {
            "original": "-ts_percentage(vec_count(historical_volatility_10),60,percentage=0.1),20, factor=0.8),market)*inverse(abs(ts_entropy(volume,20)))",
            "fixed": "-ts_delta(vec_count(historical_volatility_10),60)"
        }
    ]

    print("已知语法错误修复方案：")
    print("=" * 60)

    for i, fix in enumerate(fixes, 1):
        print(f"{i}. 原始表达式:")
        print(f"   {fix['original']}")
        print(f"   修复后:")
        print(f"   {fix['fixed']}")
        print("-" * 40)

    return fixes

def create_fixed_csv(original_csv: str, fixes: list) -> str:
    """创建修复后的 CSV 文件"""

    import csv

    output_file = original_csv.replace('.csv', '_fixed.csv')

    with open(original_csv, 'r', encoding='utf-8') as infile, \
         open(output_file, 'w', encoding='utf-8', newline='') as outfile:

        reader = csv.reader(infile)
        writer = csv.writer(outfile)

        # 写入表头
        header = next(reader)
        writer.writerow(header)

        # 处理每一行
        for row in reader:
            if len(row) >= 3:
                expression = row[2].strip('"')
                # 查找对应的修复
                for fix in fixes:
                    if fix['original'] in expression or expression in fix['original']:
                        row[2] = f'"{fix["fixed"]}"'
                        break

            writer.writerow(row)

    return output_file

if __name__ == "__main__":
    fixes = fix_known_expressions()

    # 创建修复后的 CSV
    original_csv = "/Users/zhiqu/Desktop/brain/Course2/Course2_code/outputs/simulation_status.csv"
    fixed_csv = create_fixed_csv(original_csv, fixes)

    print(f"\n修复后的 CSV 已保存到: {fixed_csv}")
    print("\n建议：")
    print("1. 检查修复后的表达式是否正确")
    print("2. 使用 judge_alpha.py 工具验证修复结果")
    print("3. 重新提交修复后的 alpha 进行模拟")