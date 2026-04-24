#!/usr/bin/env python3
"""
第二轮微调 - 组合第一轮最佳发现
发现: (63,100) 最佳参数, decay=5 最佳, SUBINDUSTRY 最高 Sharpe
"""

import json
import time
import os
from pathlib import Path
from datetime import datetime, timezone

import requests
from requests.auth import HTTPBasicAuth

BRAIN_USERNAME = os.getenv("BRAIN_USERNAME", "xxxxxx@example.com")
BRAIN_PASSWORD = os.getenv("BRAIN_PASSWORD", "xxxxxx")
REQUEST_TIMEOUT = 30
OUTPUT_DIR = Path("/Users/zhiqu/Desktop/brain/Course2/Course2_code/outputs")

sess = requests.Session()
sess.auth = HTTPBasicAuth(BRAIN_USERNAME, BRAIN_PASSWORD)
r = sess.post("https://api.worldquantbrain.com/authentication", timeout=REQUEST_TIMEOUT)
r.raise_for_status()
print("✅ 认证成功\n")

def make_settings(**overrides):
    base = {
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
    base.update(overrides)
    return base

def submit_and_get(sess, expr, settings, desc, poll_timeout=120):
    payload = {"type": "REGULAR", "settings": settings, "regular": expr}
    
    r = sess.post("https://api.worldquantbrain.com/simulations", json=payload, timeout=REQUEST_TIMEOUT)
    if r.status_code >= 400:
        print(f"  ❌ HTTP {r.status_code}")
        return None
    
    location = r.headers.get("Location", "")
    print(f"  → {location}")
    
    start = time.time()
    while time.time() - start < poll_timeout:
        pr = sess.get(location, timeout=REQUEST_TIMEOUT)
        if pr.status_code >= 400:
            time.sleep(2)
            continue
        retry_after = float(pr.headers.get("Retry-After", 0))
        if retry_after == 0:
            sim = pr.json()
            alpha_id = sim.get("alpha", "")
            if alpha_id and sim.get("status") == "COMPLETE":
                ar = sess.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}", timeout=REQUEST_TIMEOUT)
                a = ar.json()
                is_d = a.get("is", {})
                checks = is_d.get("checks", [])
                sub = next((c for c in checks if c["name"] == "LOW_SUB_UNIVERSE_SHARPE"), {})
                sharpe_ck = next((c for c in checks if c["name"] == "LOW_SHARPE"), {})
                fitness_ck = next((c for c in checks if c["name"] == "LOW_FITNESS"), {})
                
                sharpe = is_d.get("sharpe", "?")
                fitness = is_d.get("fitness", "?")
                marker = " ⭐⭐⭐ 过线!" if isinstance(sharpe, (int, float)) and sharpe >= 1.25 else \
                         " ⭐⭐" if isinstance(sharpe, (int, float)) and sharpe >= 1.15 else \
                         " ⭐" if isinstance(sharpe, (int, float)) and sharpe >= 1.05 else ""
                
                print(f"  📊 Sharpe={sharpe} Fitness={fitness} TO={is_d.get('turnover','?')} "
                      f"DD={is_d.get('drawdown','?')} Sub={sub.get('result','?')}({sub.get('value','?')})"
                      f" SharpeChk={sharpe_ck.get('result','?')} FitChk={fitness_ck.get('result','?')}{marker}")
                
                return {"desc": desc, "expr": expr, "sharpe": sharpe, "fitness": fitness,
                        "turnover": is_d.get("turnover"), "drawdown": is_d.get("drawdown"),
                        "sub_result": sub.get("result"), "sub_value": sub.get("value"),
                        "alpha_id": alpha_id, "location": location}
            else:
                print(f"  状态: {sim.get('status')} err={sim.get('error','')}")
                return None
        time.sleep(max(retry_after, 1.0))
    
    print(f"  ⏱ 超时")
    return {"desc": desc, "expr": expr, "location": location, "status": "timeout"}

# ============================================================
# 第二轮: 组合最佳因子
# ============================================================
variants = [
    # 组合1: 最佳参数(63,100) + 最佳decay=5
    ("-rank(ts_zscore(close - ts_mean(close, 63), 100))",
     make_settings(decay=5),
     "combo1: (63,100)+decay5"),
    
    # 组合2: 最佳参数(63,100) + decay=6
    ("-rank(ts_zscore(close - ts_mean(close, 63), 100))",
     make_settings(decay=6),
     "combo2: (63,100)+decay6"),

    # 组合3: 最佳参数(63,100) + decay=7
    ("-rank(ts_zscore(close - ts_mean(close, 63), 100))",
     make_settings(decay=7),
     "combo3: (63,100)+decay7"),

    # 组合4: 最佳参数(63,100) + decay=4
    ("-rank(ts_zscore(close - ts_mean(close, 63), 100))",
     make_settings(decay=4),
     "combo4: (63,100)+decay4"),

    # 组合5: (63,100) + decay=5 + SUBINDUSTRY
    ("-rank(ts_zscore(close - ts_mean(close, 63), 100))",
     make_settings(decay=5, neutralization="SUBINDUSTRY"),
     "combo5: (63,100)+decay5+SUBIND"),

    # 组合6: (60,100) + decay=5
    ("-rank(ts_zscore(close - ts_mean(close, 60), 100))",
     make_settings(decay=5),
     "combo6: (60,100)+decay5"),

    # 组合7: (50,100) + decay=5
    ("-rank(ts_zscore(close - ts_mean(close, 50), 100))",
     make_settings(decay=5),
     "combo7: (50,100)+decay5"),

    # 组合8: (63,80) + decay=5
    ("-rank(ts_zscore(close - ts_mean(close, 63), 80))",
     make_settings(decay=5),
     "combo8: (63,80)+decay5"),

    # 组合9: (63,100) + group_rank + decay=5
    ("-group_rank(ts_zscore(close - ts_mean(close, 63), 100), industry)",
     make_settings(decay=5),
     "combo9: group_rank+decay5"),

    # 组合10: (63,100) + decay=5 + universe=TOP2000
    ("-rank(ts_zscore(close - ts_mean(close, 63), 100))",
     make_settings(decay=5, universe="TOP2000"),
     "combo10: (63,100)+decay5+TOP2K"),

    # 组合11: (63,100) + decay=3
    ("-rank(ts_zscore(close - ts_mean(close, 63), 100))",
     make_settings(decay=3),
     "combo11: (63,100)+decay3"),
     
    # 组合12: 原始(63,126) + decay=5 (简单组合)
    ("-rank(ts_zscore(close - ts_mean(close, 63), 126))",
     make_settings(decay=5),
     "combo12: 原始+decay5"),
]

print(f"总共 {len(variants)} 个组合变体\n")

results = []
for i, (expr, settings, desc) in enumerate(variants, 1):
    print(f"\n[{i}/{len(variants)}] {desc}")
    result = submit_and_get(sess, expr, settings, desc)
    if result:
        results.append(result)
    time.sleep(1)

# 排行榜
print("\n\n" + "=" * 100)
print("🏆 第二轮排行榜:")
print("=" * 100)
ranked = sorted([r for r in results if isinstance(r.get("sharpe"), (int, float))],
                key=lambda x: x["sharpe"], reverse=True)
for i, r in enumerate(ranked, 1):
    m = " ✅✅✅ 过线!" if r["sharpe"] >= 1.25 else ""
    sub = f"Sub={r.get('sub_result','?')}({r.get('sub_value','?')})"
    print(f"  {i}. Sharpe={r['sharpe']:.2f} Fitness={r.get('fitness','?')} {sub} | {r['desc']}{m}")

# 保存
ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
with open(OUTPUT_DIR / f"v3_finetune_r2_{ts}.json", 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n📄 已保存: v3_finetune_r2_{ts}.json")
