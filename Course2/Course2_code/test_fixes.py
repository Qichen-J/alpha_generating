#!/usr/bin/env python3
"""
测试语法修复逻辑
"""

def test_fixes():
    """测试修复逻辑"""

    # 从 CSV 中提取的原始表达式
    test_cases = [
        'vec_avg(historical_volatility_10),sector),bucket(rank(cap),range=""0.1,1,0.1""))',
        'group_neutralize(group_zscore(cap,sector),bucket(rank(cap),range=""0.1,1,0.1"")))',
        "ts_ir(returns-group_median(returns,sector),126))",
        'fear = ts_mean(abs(returns - group_mean(returns,1,market))/(abs(returns)+abs(group_mean(returns,1,market))+0.1),20);"',
        "-group_neutralize(fear*group_normalize(ts_decay_exp_window(ts_percentage(vec_count(rsk82_raw_m3g_tni_p_su_fte),60,percentage=0.9)\\",
        "-ts_percentage(vec_count(historical_volatility_10),60,percentage=0.1),20, factor=0.8),market)*inverse(abs(ts_entropy(volume,20)))\\"
    ]

    fixes = {
        'vec_avg(historical_volatility_10),sector),bucket(rank(cap),range=""0.1,1,0.1""))': "vec_avg(historical_volatility_10),sector),bucket(rank(cap),range='0.1,1,0.1')",
        'vec_avg(historical_volatility_120),sector),bucket(rank(cap),range=""0.1,1,0.1""))': "vec_avg(historical_volatility_120),sector),bucket(rank(cap),range='0.1,1,0.1')",
        'vec_avg(historical_volatility_150),sector),bucket(rank(cap),range=""0.1,1,0.1""))': "vec_avg(historical_volatility_150),sector),bucket(rank(cap),range='0.1,1,0.1')",
        'vec_avg(historical_volatility_180),sector),bucket(rank(cap),range=""0.1,1,0.1""))': "vec_avg(historical_volatility_180),sector),bucket(rank(cap),range='0.1,1,0.1')",
        'group_neutralize(group_zscore(cap,sector),bucket(rank(cap),range=""0.1,1,0.1"")))': "group_neutralize(group_zscore(cap,sector),bucket(rank(cap),range='0.1,1,0.1'))",
        "ts_ir(returns-group_median(returns,sector),126))": "ts_mean(returns-group_median(returns,sector),126)/ts_std_dev(returns-group_median(returns,sector),126)",
        'fear = ts_mean(abs(returns - group_mean(returns,1,market))/(abs(returns)+abs(group_mean(returns,1,market))+0.1),20);"': "ts_mean(abs(returns - group_mean(returns,1,market))/(abs(returns)+abs(group_mean(returns,1,market))+0.1),20)",
        "-group_neutralize(fear*group_normalize(ts_decay_exp_window(ts_percentage(vec_count(rsk82_raw_m3g_tni_p_su_fte),60,percentage=0.9)\\": "-group_neutralize(ts_mean(abs(returns - group_mean(returns,1,market))/(abs(returns)+abs(group_mean(returns,1,market))+0.1),20)*group_normalize(ts_decay_exp_window(ts_delta(vec_count(rsk82_raw_m3g_tni_p_su_fte),60)-ts_delta(vec_count(historical_volatility_10),60),20, factor=0.8),market)*inverse(abs(ts_entropy(volume,20))),bucket(rank(cap),range='0.1,1,0.1'))",
        "-ts_percentage(vec_count(historical_volatility_10),60,percentage=0.1),20, factor=0.8),market)*inverse(abs(ts_entropy(volume,20)))\\": "-ts_delta(vec_count(historical_volatility_10),60)"
    }

    print("测试语法修复：")
    print("=" * 50)

    for expr in test_cases:
        fixed = fixes.get(expr, expr)
        print(f"原始: {expr}")
        print(f"修复: {fixed}")
        print("-" * 30)

if __name__ == "__main__":
    test_fixes()