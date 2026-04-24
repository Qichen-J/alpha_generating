#!/usr/bin/env python3
"""
改进 alpha: rank(ts_zscore(ts_delta(close, 5), 252)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))
问题: Sharpe=1.22(<1.25), Fitness=0.81(<1.0), Sub-universe=0.33(<0.53)

策略:
1. group_rank 替代 rank —— 改善 sub-universe (避免规模偏差)
2. 流动性加权衰减 —— subinverse.md 建议
3. 降低 decay —— 提高 returns
4. SUBINDUSTRY 中性化 —— 降低波动率提高 Sharpe
5. 参数微调 —— 窗口期/截断值
"""

import requests, json, time, datetime

CREDENTIALS = ("xxxxxx@example.com", "xxxxxx")
BASE = "https://api.worldquantbrain.com"

# 基础设置
BASE_SETTINGS = {
    "instrumentType": "EQUITY",
    "region": "USA",
    "universe": "TOP3000",
    "delay": 1,
    "decay": 10,
    "neutralization": "INDUSTRY",
    "truncation": 0.08,
    "pasteurization": "ON",
    "unitHandling": "VERIFY",
    "nanHandling": "ON",
    "language": "FASTEXPR",
    "visualization": False,
}

# ── 原始表达式 ──
ORIGINAL = "rank(ts_zscore(ts_delta(close, 5), 252)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))"

# ── 改进变体 ──
VARIANTS = [
    # === 路线 A: group_rank 改善 sub-universe ===
    {
        "name": "A1_grp_rank_ind",
        "desc": "group_rank替代rank, INDUSTRY中性化",
        "expr": "group_rank(ts_zscore(ts_delta(close, 5), 252), industry) * -group_rank(ts_rank(ts_std_dev(returns, 20), 252), industry)",
        "settings": {**BASE_SETTINGS, "decay": 6},
    },
    {
        "name": "A2_grp_rank_subind",
        "desc": "group_rank替代rank, SUBINDUSTRY中性化",
        "expr": "group_rank(ts_zscore(ts_delta(close, 5), 252), subindustry) * -group_rank(ts_rank(ts_std_dev(returns, 20), 252), subindustry)",
        "settings": {**BASE_SETTINGS, "neutralization": "SUBINDUSTRY", "decay": 5},
    },
    {
        "name": "A3_grp_rank_ind_d3",
        "desc": "group_rank+INDUSTRY+低decay",
        "expr": "group_rank(ts_zscore(ts_delta(close, 5), 252), industry) * -group_rank(ts_rank(ts_std_dev(returns, 20), 252), industry)",
        "settings": {**BASE_SETTINGS, "decay": 3},
    },

    # === 路线 B: 流动性加权 (subinverse.md 建议) ===
    {
        "name": "B1_liq_weight",
        "desc": "流动性加权信号 (subinverse.md建议)",
        "expr": "(rank(ts_zscore(ts_delta(close, 5), 252)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))) * rank(volume * close)",
        "settings": {**BASE_SETTINGS, "decay": 5},
    },
    {
        "name": "B2_liq_decay",
        "desc": "流动性加权衰减 (subinverse.md具体方法)",
        "expr": "ts_decay_linear(rank(ts_zscore(ts_delta(close, 5), 252)) * -rank(ts_rank(ts_std_dev(returns, 20), 252)), 5) * rank(volume*close) + ts_decay_linear(rank(ts_zscore(ts_delta(close, 5), 252)) * -rank(ts_rank(ts_std_dev(returns, 20), 252)), 10) * (1 - rank(volume*close))",
        "settings": {**BASE_SETTINGS, "decay": 0},
    },

    # === 路线 C: 简化 + 参数优化 ===
    {
        "name": "C1_shorter_windows",
        "desc": "缩短zscore窗口126, vol窗口10",
        "expr": "rank(ts_zscore(ts_delta(close, 5), 126)) * -rank(ts_rank(ts_std_dev(returns, 10), 126))",
        "settings": {**BASE_SETTINGS, "decay": 5, "neutralization": "SUBINDUSTRY"},
    },
    {
        "name": "C2_medium_windows",
        "desc": "中等窗口 zscore=200, vol=15",
        "expr": "rank(ts_zscore(ts_delta(close, 5), 200)) * -rank(ts_rank(ts_std_dev(returns, 15), 200))",
        "settings": {**BASE_SETTINGS, "decay": 5},
    },
    {
        "name": "C3_delta10",
        "desc": "delta窗口改10天",
        "expr": "rank(ts_zscore(ts_delta(close, 10), 252)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))",
        "settings": {**BASE_SETTINGS, "decay": 5},
    },

    # === 路线 D: 组合策略 (group_rank + 流动性) ===
    {
        "name": "D1_grp_liq_ind",
        "desc": "group_rank+流动性加权+INDUSTRY",
        "expr": "(group_rank(ts_zscore(ts_delta(close, 5), 252), industry) * -group_rank(ts_rank(ts_std_dev(returns, 20), 252), industry)) * rank(volume * close)",
        "settings": {**BASE_SETTINGS, "decay": 4},
    },
    {
        "name": "D2_grp_liq_subind",
        "desc": "group_rank+流动性加权+SUBINDUSTRY",
        "expr": "(group_rank(ts_zscore(ts_delta(close, 5), 252), subindustry) * -group_rank(ts_rank(ts_std_dev(returns, 20), 252), subindustry)) * rank(volume * close)",
        "settings": {**BASE_SETTINGS, "neutralization": "SUBINDUSTRY", "decay": 4},
    },

    # === 路线 E: 降低 decay + 截断调整 ===
    {
        "name": "E1_orig_d3_subind",
        "desc": "原始表达式+decay3+SUBINDUSTRY",
        "expr": ORIGINAL,
        "settings": {**BASE_SETTINGS, "neutralization": "SUBINDUSTRY", "decay": 3},
    },
    {
        "name": "E2_orig_d5_t010",
        "desc": "原始表达式+decay5+trunc0.10",
        "expr": ORIGINAL,
        "settings": {**BASE_SETTINGS, "decay": 5, "truncation": 0.10},
    },
    {
        "name": "E3_orig_d2_subind",
        "desc": "原始表达式+decay2+SUBINDUSTRY",
        "expr": ORIGINAL,
        "settings": {**BASE_SETTINGS, "neutralization": "SUBINDUSTRY", "decay": 2},
    },

    # === 路线 F: 负号翻转 / rank 包裹整体 ===
    {
        "name": "F1_neg_rank_whole",
        "desc": "-rank(整体信号)+SUBINDUSTRY",
        "expr": "-rank(ts_zscore(ts_delta(close, 5), 252) * -ts_rank(ts_std_dev(returns, 20), 252))",
        "settings": {**BASE_SETTINGS, "neutralization": "SUBINDUSTRY", "decay": 5},
    },
    {
        "name": "F2_grp_rank_whole",
        "desc": "-group_rank(整体信号, subindustry)",
        "expr": "-group_rank(ts_zscore(ts_delta(close, 5), 252) * -ts_rank(ts_std_dev(returns, 20), 252), subindustry)",
        "settings": {**BASE_SETTINGS, "neutralization": "SUBINDUSTRY", "decay": 4},
    },
]


def authenticate(s):
    r = s.post(f"{BASE}/authentication", auth=CREDENTIALS)
    r.raise_for_status()
    print("✅ 认证成功")


def submit_simulation(s, expr, settings):
    payload = {"type": "REGULAR", "settings": settings, "regular": expr}
    for attempt in range(15):
        r = s.post(f"{BASE}/simulations", json=payload)
        if r.status_code == 429:
            wait = int(float(r.headers.get("Retry-After", "30"))) + 5
            print(f"  ⏳ 限流, 等待 {wait}s (尝试 {attempt+1}/15)")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.headers.get("Location", "")
    r.raise_for_status()
    return ""


def poll_simulation(s, url, timeout=150):
    t0 = time.time()
    while time.time() - t0 < timeout:
        r = s.get(url)
        if r.status_code == 200:
            data = r.json()
            retry = r.headers.get("Retry-After", "0")
            if retry == "0" or data.get("status") == "COMPLETE":
                return data
        wait = int(float(r.headers.get("Retry-After", "5")))
        time.sleep(min(max(wait, 3), 15))
    return None


def get_alpha_details(s, alpha_id):
    r = s.get(f"{BASE}/alphas/{alpha_id}")
    if r.status_code == 200:
        return r.json()
    return None


def extract_checks(alpha_data):
    checks = {}
    for c in alpha_data.get("is", {}).get("checks", []):
        checks[c["name"]] = c
    return checks


def main():
    s = requests.Session()
    authenticate(s)

    results = []
    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    for i, v in enumerate(VARIANTS):
        name = v["name"]
        print(f"\n[{i+1}/{len(VARIANTS)}] {name}: {v['desc']}")
        print(f"  表达式: {v['expr'][:80]}...")

        # 每个变体之间间隔避免限流
        if i > 0:
            time.sleep(3)

        try:
            sim_url = submit_simulation(s, v["expr"], v["settings"])
            if not sim_url:
                print(f"  ❌ 无 Location header")
                results.append({"name": name, "status": "NO_URL"})
                continue

            print(f"  ⏳ 等待模拟...")
            sim_data = poll_simulation(s, sim_url)

            if not sim_data:
                print(f"  ⏰ 超时")
                results.append({"name": name, "status": "TIMEOUT", "url": sim_url})
                continue

            # 获取 alpha 详情
            alpha_field = sim_data.get("alpha")
            alpha_id = alpha_field if isinstance(alpha_field, str) else (alpha_field.get("id") if isinstance(alpha_field, dict) else None)

            if not alpha_id:
                print(f"  ❌ 无 alpha_id")
                results.append({"name": name, "status": "NO_ALPHA_ID", "url": sim_url})
                continue

            alpha_data = get_alpha_details(s, alpha_id)
            if not alpha_data:
                print(f"  ❌ 无法获取 alpha 详情")
                results.append({"name": name, "status": "NO_DETAILS", "alpha_id": alpha_id, "url": sim_url})
                continue

            is_data = alpha_data.get("is", {})
            sharpe = is_data.get("sharpe", 0)
            fitness = is_data.get("fitness", 0)
            turnover = is_data.get("turnover", 0)
            returns_ = is_data.get("returns", 0)

            checks = extract_checks(alpha_data)
            sharpe_pass = checks.get("LOW_SHARPE", {}).get("result") == "PASS"
            fitness_pass = checks.get("LOW_FITNESS", {}).get("result") == "PASS"

            sub_check = checks.get("LOW_SUB_UNIVERSE_SHARPE", {})
            sub_pass = sub_check.get("result") == "PASS"
            sub_val = sub_check.get("value", "?")
            sub_cutoff = sub_check.get("cutoff", "?")

            all_pass = sharpe_pass and fitness_pass and sub_pass

            status_str = "🎉ALL PASS" if all_pass else ""
            print(f"  Sharpe={sharpe:.2f} {'✅' if sharpe_pass else '❌'} | Fitness={fitness:.2f} {'✅' if fitness_pass else '❌'} | Sub={sub_val}{'✅' if sub_pass else '❌'}(cutoff={sub_cutoff}) | TO={turnover:.4f} | Ret={returns_:.4f} {status_str}")

            results.append({
                "name": name,
                "desc": v["desc"],
                "expr": v["expr"],
                "settings_diff": {k: v["settings"][k] for k in v["settings"] if v["settings"][k] != BASE_SETTINGS.get(k)},
                "status": "COMPLETE",
                "alpha_id": alpha_id,
                "url": sim_url,
                "sharpe": sharpe,
                "fitness": fitness,
                "turnover": turnover,
                "returns": returns_,
                "sharpe_pass": sharpe_pass,
                "fitness_pass": fitness_pass,
                "sub_pass": sub_pass,
                "sub_value": sub_val,
                "sub_cutoff": sub_cutoff,
                "all_pass": all_pass,
            })

        except Exception as e:
            print(f"  ❌ 错误: {e}")
            results.append({"name": name, "status": "ERROR", "error": str(e)})

    # 保存结果
    out_file = f"outputs/momentum_vol_improve_{ts}.json"
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n💾 结果已保存: {out_file}")

    # 打印汇总
    print(f"\n{'='*120}")
    print(f"{'名称':<25} {'状态':<10} {'Sharpe':>7} {'Fit':>7} {'TO':>7} {'Ret':>8} {'Sub':>15} {'ShaChk':>7} {'FitChk':>7}")
    print(f"{'='*120}")
    for r in results:
        if r["status"] == "COMPLETE":
            sub_str = f"{'PASS' if r['sub_pass'] else 'FAIL'}({r['sub_value']})"
            all_str = " 🎉ALL PASS" if r.get("all_pass") else ""
            print(f"{r['name']:<25} {r['status']:<10} {r['sharpe']:>7.2f} {r['fitness']:>7.2f} {r['turnover']:>7.4f} {r['returns']:>8.4f} {sub_str:>15} {'PASS' if r['sharpe_pass'] else 'FAIL':>7} {'PASS' if r['fitness_pass'] else 'FAIL':>7}{all_str}")
        else:
            print(f"{r['name']:<25} {r['status']:<10}")


if __name__ == "__main__":
    main()
