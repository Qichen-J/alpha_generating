#!/usr/bin/env python3
"""
改进 alpha: rank(ts_zscore(ts_delta(close, 5), 252)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))
问题: Sharpe=1.22(<1.25), Fitness=0.81(<1.0), Sub-universe=0.33(<0.53)

策略:
1. group_rank 替代 rank —— 改善 sub-universe
2. 流动性加权 —— subinverse.md 建议
3. 降低 decay —— 提高 returns
4. SUBINDUSTRY 中性化 —— 降低波动率
5. 参数微调 —— 窗口期/截断值
"""

import requests, json, time, datetime

CREDENTIALS = ("xxxxxx@example.com", "xxxxxx")
BASE = "https://api.worldquantbrain.com"
REQUEST_TIMEOUT = 30
POLL_TIMEOUT = 180

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

ORIGINAL = "rank(ts_zscore(ts_delta(close, 5), 252)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))"

VARIANTS = [
    # === A: group_rank 替代 rank ===
    {
        "name": "A1_grp_ind_d6",
        "expr": "group_rank(ts_zscore(ts_delta(close, 5), 252), industry) * -group_rank(ts_rank(ts_std_dev(returns, 20), 252), industry)",
        "settings": {**BASE_SETTINGS, "decay": 6},
    },
    {
        "name": "A2_grp_subind_d5",
        "expr": "group_rank(ts_zscore(ts_delta(close, 5), 252), subindustry) * -group_rank(ts_rank(ts_std_dev(returns, 20), 252), subindustry)",
        "settings": {**BASE_SETTINGS, "neutralization": "SUBINDUSTRY", "decay": 5},
    },
    {
        "name": "A3_grp_ind_d3",
        "expr": "group_rank(ts_zscore(ts_delta(close, 5), 252), industry) * -group_rank(ts_rank(ts_std_dev(returns, 20), 252), industry)",
        "settings": {**BASE_SETTINGS, "decay": 3},
    },

    # === B: 流动性加权 (subinverse.md) ===
    {
        "name": "B1_liq_weight_d5",
        "expr": "(rank(ts_zscore(ts_delta(close, 5), 252)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))) * rank(volume * close)",
        "settings": {**BASE_SETTINGS, "decay": 5},
    },
    {
        "name": "B2_liq_decay",
        "expr": "ts_decay_linear(rank(ts_zscore(ts_delta(close, 5), 252)) * -rank(ts_rank(ts_std_dev(returns, 20), 252)), 5) * rank(volume*close) + ts_decay_linear(rank(ts_zscore(ts_delta(close, 5), 252)) * -rank(ts_rank(ts_std_dev(returns, 20), 252)), 10) * (1 - rank(volume*close))",
        "settings": {**BASE_SETTINGS, "decay": 0},
    },

    # === C: 参数优化 ===
    {
        "name": "C1_win126_subind",
        "expr": "rank(ts_zscore(ts_delta(close, 5), 126)) * -rank(ts_rank(ts_std_dev(returns, 10), 126))",
        "settings": {**BASE_SETTINGS, "decay": 5, "neutralization": "SUBINDUSTRY"},
    },
    {
        "name": "C2_win200_d5",
        "expr": "rank(ts_zscore(ts_delta(close, 5), 200)) * -rank(ts_rank(ts_std_dev(returns, 15), 200))",
        "settings": {**BASE_SETTINGS, "decay": 5},
    },
    {
        "name": "C3_delta10_d5",
        "expr": "rank(ts_zscore(ts_delta(close, 10), 252)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))",
        "settings": {**BASE_SETTINGS, "decay": 5},
    },

    # === D: group_rank + 流动性 ===
    {
        "name": "D1_grp_liq_ind",
        "expr": "(group_rank(ts_zscore(ts_delta(close, 5), 252), industry) * -group_rank(ts_rank(ts_std_dev(returns, 20), 252), industry)) * rank(volume * close)",
        "settings": {**BASE_SETTINGS, "decay": 4},
    },
    {
        "name": "D2_grp_liq_subind",
        "expr": "(group_rank(ts_zscore(ts_delta(close, 5), 252), subindustry) * -group_rank(ts_rank(ts_std_dev(returns, 20), 252), subindustry)) * rank(volume * close)",
        "settings": {**BASE_SETTINGS, "neutralization": "SUBINDUSTRY", "decay": 4},
    },

    # === E: 原始表达式 + 设置调整 ===
    {
        "name": "E1_orig_d3_subind",
        "expr": ORIGINAL,
        "settings": {**BASE_SETTINGS, "neutralization": "SUBINDUSTRY", "decay": 3},
    },
    {
        "name": "E2_orig_d5_t010",
        "expr": ORIGINAL,
        "settings": {**BASE_SETTINGS, "decay": 5, "truncation": 0.10},
    },
    {
        "name": "E3_orig_d2_subind",
        "expr": ORIGINAL,
        "settings": {**BASE_SETTINGS, "neutralization": "SUBINDUSTRY", "decay": 2},
    },

    # === F: 整体 rank/group_rank ===
    {
        "name": "F1_neg_rank_subind",
        "expr": "-rank(ts_zscore(ts_delta(close, 5), 252) * -ts_rank(ts_std_dev(returns, 20), 252))",
        "settings": {**BASE_SETTINGS, "neutralization": "SUBINDUSTRY", "decay": 5},
    },
    {
        "name": "F2_grp_whole_subind",
        "expr": "-group_rank(ts_zscore(ts_delta(close, 5), 252) * -ts_rank(ts_std_dev(returns, 20), 252), subindustry)",
        "settings": {**BASE_SETTINGS, "neutralization": "SUBINDUSTRY", "decay": 4},
    },
]


def authenticate(sess):
    r = sess.post(f"{BASE}/authentication", auth=CREDENTIALS, timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    print("✅ 认证成功")


def submit_and_poll(sess, expr, settings):
    """提交模拟并等待完成。返回 (alpha_id, alpha_data) 或 (None, None)"""
    payload = {"type": "REGULAR", "settings": settings, "regular": expr}

    # 提交（带限流重试）
    location = None
    for attempt in range(15):
        r = sess.post(f"{BASE}/simulations", json=payload, timeout=REQUEST_TIMEOUT)
        if r.status_code == 429:
            wait = int(float(r.headers.get("Retry-After", 30))) + 5
            print(f"  ⏳ 限流 {wait}s ({attempt+1}/15)")
            time.sleep(wait)
            continue
        r.raise_for_status()
        location = r.headers.get("Location", "")
        break

    if not location:
        print("  ❌ 无 Location")
        return None, None, ""

    # 轮询
    start = time.time()
    while time.time() - start < POLL_TIMEOUT:
        try:
            pr = sess.get(location, timeout=REQUEST_TIMEOUT)
        except Exception:
            time.sleep(5)
            continue

        if pr.status_code >= 400:
            time.sleep(3)
            continue

        retry_after = float(pr.headers.get("Retry-After", 0))
        if retry_after == 0:
            sim_data = pr.json()
            alpha_id = sim_data.get("alpha", "")
            if alpha_id:
                # 获取 alpha 详情
                ar = sess.get(f"{BASE}/alphas/{alpha_id}", timeout=REQUEST_TIMEOUT)
                if ar.status_code < 400:
                    return alpha_id, ar.json(), location
            return None, None, location
        time.sleep(max(retry_after, 3))

    print("  ⏰ 超时")
    return None, None, location


def main():
    sess = requests.Session()
    authenticate(sess)

    results = []
    ts = datetime.datetime.now(datetime.UTC).strftime("%Y%m%dT%H%M%SZ")

    for i, v in enumerate(VARIANTS):
        name = v["name"]
        print(f"\n[{i+1}/{len(VARIANTS)}] {name}")
        print(f"  {v['expr'][:90]}...")

        # 间隔避免限流
        if i > 0:
            time.sleep(3)

        alpha_id, alpha_data, sim_url = submit_and_poll(sess, v["expr"], v["settings"])

        if not alpha_data:
            status = "TIMEOUT" if sim_url else "ERROR"
            print(f"  ❌ {status}")
            results.append({"name": name, "status": status, "url": sim_url})
            continue

        is_data = alpha_data.get("is", {})
        sharpe = is_data.get("sharpe", 0)
        fitness = is_data.get("fitness", 0)
        turnover = is_data.get("turnover", 0)
        returns_ = is_data.get("returns", 0)

        checks = {c["name"]: c for c in is_data.get("checks", [])}
        sharpe_pass = checks.get("LOW_SHARPE", {}).get("result") == "PASS"
        fitness_pass = checks.get("LOW_FITNESS", {}).get("result") == "PASS"
        sub = checks.get("LOW_SUB_UNIVERSE_SHARPE", {})
        sub_pass = sub.get("result") == "PASS"
        sub_val = sub.get("value", "?")
        sub_cut = sub.get("cutoff", "?")
        all_pass = sharpe_pass and fitness_pass and sub_pass

        tag = " 🎉ALL PASS" if all_pass else ""
        print(f"  Sharpe={sharpe:.2f}{'✅' if sharpe_pass else '❌'} Fit={fitness:.2f}{'✅' if fitness_pass else '❌'} Sub={sub_val}{'✅' if sub_pass else '❌'}(cut={sub_cut}) TO={turnover:.4f} Ret={returns_:.4f}{tag}")

        results.append({
            "name": name, "expr": v["expr"],
            "settings_diff": {k: v["settings"][k] for k in v["settings"] if v["settings"][k] != BASE_SETTINGS.get(k)},
            "status": "COMPLETE", "alpha_id": alpha_id, "url": sim_url,
            "sharpe": sharpe, "fitness": fitness, "turnover": turnover, "returns": returns_,
            "sharpe_pass": sharpe_pass, "fitness_pass": fitness_pass,
            "sub_pass": sub_pass, "sub_value": sub_val, "sub_cutoff": sub_cut,
            "all_pass": all_pass,
        })

    # 保存
    out = f"outputs/momentum_vol_improve_{ts}.json"
    with open(out, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n💾 {out}")

    # 汇总
    print(f"\n{'='*110}")
    print(f"{'名称':<24} {'Sharpe':>7} {'Fit':>7} {'TO':>7} {'Ret':>8} {'Sub':>15} {'Sha':>5} {'Fit':>5}")
    print(f"{'='*110}")
    for r in results:
        if r["status"] == "COMPLETE":
            s = f"{'P' if r['sub_pass'] else 'F'}({r['sub_value']})"
            tag = " 🎉" if r.get("all_pass") else ""
            print(f"{r['name']:<24} {r['sharpe']:>7.2f} {r['fitness']:>7.2f} {r['turnover']:>7.4f} {r['returns']:>8.4f} {s:>15} {'P' if r['sharpe_pass'] else 'F':>5} {'P' if r['fitness_pass'] else 'F':>5}{tag}")
        else:
            print(f"{r['name']:<24} {r['status']}")


if __name__ == "__main__":
    main()
