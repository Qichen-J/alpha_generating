#!/usr/bin/env python3
"""
微调 v3: -rank(ts_zscore(close - ts_mean(close, 63), 126))
目标: Sharpe 从 1.20 提升到 1.25+
策略: 参数微调 + 设置微调 + 小改动
"""

import json
import time
import os
from pathlib import Path
from datetime import datetime, timezone

import requests
from requests.auth import HTTPBasicAuth

ROOT = Path("/Users/zhiqu/Desktop/brain")
OUTPUT_DIR = ROOT / "Course2" / "Course2_code" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BRAIN_USERNAME = os.getenv("BRAIN_USERNAME", "xxxxxx@example.com")
BRAIN_PASSWORD = os.getenv("BRAIN_PASSWORD", "xxxxxx")
REQUEST_TIMEOUT = 30

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
    "visualization": False
}

def build_session():
    sess = requests.Session()
    sess.auth = HTTPBasicAuth(BRAIN_USERNAME, BRAIN_PASSWORD)
    return sess

def authenticate(sess):
    r = sess.post("https://api.worldquantbrain.com/authentication", timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    print("✅ 认证成功\n")

def submit_and_poll(sess, expression, settings, desc, poll_timeout=90):
    payload = {
        "type": "REGULAR",
        "settings": settings,
        "regular": expression
    }
    
    try:
        r = sess.post("https://api.worldquantbrain.com/simulations", json=payload, timeout=REQUEST_TIMEOUT)
        if r.status_code >= 400:
            print(f"  ❌ HTTP {r.status_code}: {r.text[:150]}")
            return None
        
        location = r.headers.get("Location")
        if not location:
            print(f"  ❌ 无 Location")
            return None
        
        print(f"  ✅ 已提交: {location}")
        
        start = time.time()
        while time.time() - start < poll_timeout:
            pr = sess.get(location, timeout=REQUEST_TIMEOUT)
            if pr.status_code >= 400:
                time.sleep(2)
                continue
            retry_after = float(pr.headers.get("Retry-After", 0))
            if retry_after == 0:
                sim_data = pr.json()
                alpha_id = sim_data.get("alpha", "")
                if alpha_id and sim_data.get("status") == "COMPLETE":
                    # 获取 alpha 详情
                    ar = sess.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}", timeout=REQUEST_TIMEOUT)
                    if ar.status_code < 400:
                        alpha_data = ar.json()
                        is_data = alpha_data.get("is", {})
                        sharpe = is_data.get("sharpe", "N/A")
                        fitness = is_data.get("fitness", "N/A")
                        turnover = is_data.get("turnover", "N/A")
                        drawdown = is_data.get("drawdown", "N/A")
                        
                        checks = is_data.get("checks", [])
                        check_results = {}
                        for c in checks:
                            check_results[c["name"]] = c.get("result", "?")
                        
                        return {
                            "desc": desc,
                            "expression": expression,
                            "location": location,
                            "alpha_id": alpha_id,
                            "sharpe": sharpe,
                            "fitness": fitness,
                            "turnover": turnover,
                            "drawdown": drawdown,
                            "checks": check_results,
                            "settings_diff": {k: v for k, v in settings.items() 
                                             if v != BASE_SETTINGS.get(k)},
                        }
                return {"desc": desc, "expression": expression, "location": location,
                        "status": sim_data.get("status", "unknown")}
            time.sleep(max(retry_after, 1.0))
        
        return {"desc": desc, "expression": expression, "location": location, "status": "timeout"}
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        return None

def main():
    sess = build_session()
    authenticate(sess)

    # ============================================================
    # 微调策略
    # ============================================================
    variants = []
    
    # --- A. 参数微调（表达式层面）---
    param_variants = [
        ("-rank(ts_zscore(close - ts_mean(close, 60), 120))", "A1 参数(60,120)"),
        ("-rank(ts_zscore(close - ts_mean(close, 63), 120))", "A2 参数(63,120)"),
        ("-rank(ts_zscore(close - ts_mean(close, 60), 126))", "A3 参数(60,126)"),
        ("-rank(ts_zscore(close - ts_mean(close, 50), 126))", "A4 参数(50,126)"),
        ("-rank(ts_zscore(close - ts_mean(close, 63), 100))", "A5 参数(63,100)"),
        ("-rank(ts_zscore(close - ts_mean(close, 63), 150))", "A6 参数(63,150)"),
        ("-rank(ts_zscore(close - ts_mean(close, 63), 63))",  "A7 参数(63,63)"),
        ("-rank(ts_zscore(close - ts_mean(close, 50), 100))", "A8 参数(50,100)"),
    ]
    for expr, desc in param_variants:
        variants.append((expr, BASE_SETTINGS.copy(), desc))
    
    # --- B. Decay 微调 ---
    for decay_val in [5, 8, 12, 15]:
        s = BASE_SETTINGS.copy()
        s["decay"] = decay_val
        variants.append((
            "-rank(ts_zscore(close - ts_mean(close, 63), 126))",
            s,
            f"B decay={decay_val}"
        ))
    
    # --- C. Truncation 微调 ---
    for trunc_val in [0.05, 0.06, 0.10, 0.12]:
        s = BASE_SETTINGS.copy()
        s["truncation"] = trunc_val
        variants.append((
            "-rank(ts_zscore(close - ts_mean(close, 63), 126))",
            s,
            f"C trunc={trunc_val}"
        ))

    # --- D. Neutralization 微调 ---
    for neut in ["SUBINDUSTRY", "MARKET"]:
        s = BASE_SETTINGS.copy()
        s["neutralization"] = neut
        variants.append((
            "-rank(ts_zscore(close - ts_mean(close, 63), 126))",
            s,
            f"D neut={neut}"
        ))

    # --- E. 表达式小改动 ---
    expr_variants = [
        # vwap 替代 close
        ("-rank(ts_zscore(vwap - ts_mean(vwap, 63), 126))", "E1 vwap替代close"),
        # 加 group_rank
        ("-group_rank(ts_zscore(close - ts_mean(close, 63), 126), industry)", "E2 group_rank"),
        # 用 ts_rank 替代 rank
        ("-ts_rank(ts_zscore(close - ts_mean(close, 63), 126), 252)", "E3 ts_rank(252)"),
        # 加 sign
        ("-sign(ts_zscore(close - ts_mean(close, 63), 126))", "E4 sign替代rank"),
    ]
    for expr, desc in expr_variants:
        variants.append((expr, BASE_SETTINGS.copy(), desc))

    print(f"总共 {len(variants)} 个变体\n")
    print(f"{'#':<4} {'描述':<25} {'Sharpe':<10} {'Fitness':<10} {'Turnover':<10} {'Checks'}")
    print("=" * 100)

    results = []
    for i, (expr, settings, desc) in enumerate(variants, 1):
        print(f"\n[{i}/{len(variants)}] {desc}")
        result = submit_and_poll(sess, expr, settings, desc)
        if result:
            results.append(result)
            sharpe = result.get("sharpe", "?")
            fitness = result.get("fitness", "?")
            turnover = result.get("turnover", "?")
            checks = result.get("checks", {})
            sharpe_check = checks.get("LOW_SHARPE", "?")
            fitness_check = checks.get("LOW_FITNESS", "?")
            
            marker = " ⭐" if isinstance(sharpe, (int, float)) and sharpe >= 1.25 else ""
            print(f"  📊 Sharpe={sharpe} Fitness={fitness} Turnover={turnover} "
                  f"SHARPE_CHECK={sharpe_check} FITNESS_CHECK={fitness_check}{marker}")
        else:
            results.append({"desc": desc, "expression": expr, "status": "failed"})
        
        time.sleep(1)

    # 保存结果
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    
    json_file = OUTPUT_DIR / f"v3_finetune_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # 打印排行榜
    print("\n\n" + "=" * 100)
    print("🏆 排行榜（按 Sharpe 降序）:")
    print("=" * 100)
    
    ranked = [r for r in results if isinstance(r.get("sharpe"), (int, float))]
    ranked.sort(key=lambda x: x["sharpe"], reverse=True)
    
    for i, r in enumerate(ranked, 1):
        marker = " ✅ 过线!" if r["sharpe"] >= 1.25 else ""
        print(f"  {i}. Sharpe={r['sharpe']:.2f} Fitness={r.get('fitness','?')} "
              f"| {r['desc']}{marker}")
        print(f"     表达式: {r['expression']}")
        if r.get("settings_diff"):
            print(f"     设置变更: {r['settings_diff']}")
    
    print(f"\n📄 完整结果: {json_file}")

if __name__ == "__main__":
    main()
