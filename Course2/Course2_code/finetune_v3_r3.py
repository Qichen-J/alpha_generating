#!/usr/bin/env python3
"""
第三轮微调 - 两条路线冲线
路线A: combo5基础(SUBIND)，提升sub-universe sharpe 0.05
路线B: combo11基础(decay=3)，提升main sharpe 0.03
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
        print(f"  ❌ HTTP {r.status_code}: {r.text[:100]}")
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
                sub_r = sub.get("result", "?")
                sub_v = sub.get("value", "?")
                
                all_pass = (sharpe_ck.get("result") == "PASS" and 
                           fitness_ck.get("result") == "PASS" and
                           sub.get("result") == "PASS")
                
                marker = " 🎉🎉🎉 ALL PASS!" if all_pass else \
                         " ⭐⭐" if isinstance(sharpe, (int, float)) and sharpe >= 1.25 else \
                         " ⭐" if isinstance(sharpe, (int, float)) and sharpe >= 1.15 else ""
                
                print(f"  📊 Sharpe={sharpe} Fitness={fitness} TO={is_d.get('turnover','?')} "
                      f"Sub={sub_r}({sub_v}) Sharpe:{sharpe_ck.get('result','?')} "
                      f"Fit:{fitness_ck.get('result','?')}{marker}")
                
                return {"desc": desc, "expr": expr, "sharpe": sharpe, "fitness": fitness,
                        "turnover": is_d.get("turnover"), "drawdown": is_d.get("drawdown"),
                        "sub_result": sub_r, "sub_value": sub_v,
                        "sharpe_check": sharpe_ck.get("result"),
                        "fitness_check": fitness_ck.get("result"),
                        "all_pass": all_pass,
                        "alpha_id": alpha_id, "location": location}
            else:
                print(f"  状态: {sim.get('status')} err={sim.get('error','')}")
                return {"desc": desc, "status": sim.get("status"), "error": sim.get("error","")}
        time.sleep(max(retry_after, 1.0))
    
    print(f"  ⏱ 超时")
    return {"desc": desc, "expr": expr, "location": location, "status": "timeout"}

variants = [
    # ========== 路线A: SUBINDUSTRY 基础，提升 sub-universe ==========
    # A1: SUBINDUSTRY + decay=5 + 更短zscore窗口（让信号更通用）
    ("-rank(ts_zscore(close - ts_mean(close, 63), 80))",
     make_settings(decay=5, neutralization="SUBINDUSTRY"),
     "A1: SUBIND+(63,80)+d5"),
    
    # A2: SUBINDUSTRY + decay=5 + 更长均线（信号更稳定）
    ("-rank(ts_zscore(close - ts_mean(close, 63), 100))",
     make_settings(decay=4, neutralization="SUBINDUSTRY"),
     "A2: SUBIND+(63,100)+d4"),

    # A3: SUBINDUSTRY + decay=5 + truncation更紧
    ("-rank(ts_zscore(close - ts_mean(close, 63), 100))",
     make_settings(decay=5, neutralization="SUBINDUSTRY", truncation=0.05),
     "A3: SUBIND+(63,100)+d5+t0.05"),

    # A4: SUBINDUSTRY + decay=5 + truncation更松
    ("-rank(ts_zscore(close - ts_mean(close, 63), 100))",
     make_settings(decay=5, neutralization="SUBINDUSTRY", truncation=0.10),
     "A4: SUBIND+(63,100)+d5+t0.10"),

    # A5: SUBINDUSTRY + decay=6
    ("-rank(ts_zscore(close - ts_mean(close, 63), 100))",
     make_settings(decay=6, neutralization="SUBINDUSTRY"),
     "A5: SUBIND+(63,100)+d6"),

    # A6: SUBINDUSTRY + group_rank 替代 rank
    ("-group_rank(ts_zscore(close - ts_mean(close, 63), 100), subindustry)",
     make_settings(decay=5, neutralization="SUBINDUSTRY"),
     "A6: SUBIND+grp_rank+d5"),

    # A7: SUBINDUSTRY + 加 ts_scale 平滑
    ("-rank(ts_zscore(close - ts_mean(close, 63), 100)) * ts_scale(volume, 20)",
     make_settings(decay=5, neutralization="SUBINDUSTRY"),
     "A7: SUBIND+vol_scale+d5"),
     
    # ========== 路线B: INDUSTRY + decay=3 基础，提升 main Sharpe ==========
    # B1: decay=2 更激进
    ("-rank(ts_zscore(close - ts_mean(close, 63), 100))",
     make_settings(decay=2),
     "B1: IND+(63,100)+d2"),

    # B2: decay=3 + 参数微调(60,100)
    ("-rank(ts_zscore(close - ts_mean(close, 60), 100))",
     make_settings(decay=3),
     "B2: IND+(60,100)+d3"),

    # B3: decay=3 + 参数微调(63,90)
    ("-rank(ts_zscore(close - ts_mean(close, 63), 90))",
     make_settings(decay=3),
     "B3: IND+(63,90)+d3"),

    # B4: decay=3 + 参数微调(63,80)
    ("-rank(ts_zscore(close - ts_mean(close, 63), 80))",
     make_settings(decay=3),
     "B4: IND+(63,80)+d3"),

    # B5: decay=4 (combo4之前timeout的)
    ("-rank(ts_zscore(close - ts_mean(close, 63), 100))",
     make_settings(decay=4),
     "B5: IND+(63,100)+d4"),

    # B6: decay=3 + group_rank
    ("-group_rank(ts_zscore(close - ts_mean(close, 63), 100), industry)",
     make_settings(decay=3),
     "B6: IND+grp_rank+d3"),

    # B7: decay=3 + group_rank + (63,90)
    ("-group_rank(ts_zscore(close - ts_mean(close, 63), 90), industry)",
     make_settings(decay=3),
     "B7: IND+grp_rank(63,90)+d3"),

    # B8: decay=4 + group_rank
    ("-group_rank(ts_zscore(close - ts_mean(close, 63), 100), industry)",
     make_settings(decay=4),
     "B8: IND+grp_rank+d4"),
]

print(f"总共 {len(variants)} 个变体\n")

results = []
for i, (expr, settings, desc) in enumerate(variants, 1):
    print(f"\n[{i}/{len(variants)}] {desc}")
    result = submit_and_get(sess, expr, settings, desc)
    if result:
        results.append(result)
    time.sleep(1)

# 排行榜
print("\n\n" + "=" * 110)
print("🏆 第三轮排行榜:")
print("=" * 110)
ranked = sorted([r for r in results if isinstance(r.get("sharpe"), (int, float))],
                key=lambda x: x["sharpe"], reverse=True)
for i, r in enumerate(ranked, 1):
    ap = " 🎉 ALL PASS!" if r.get("all_pass") else ""
    print(f"  {i}. Sharpe={r['sharpe']:.2f} Fit={r.get('fitness','?')} "
          f"Sub={r.get('sub_result','?')}({r.get('sub_value','?')}) "
          f"SharpeChk={r.get('sharpe_check','?')} FitChk={r.get('fitness_check','?')} "
          f"| {r['desc']}{ap}")

# 检查有没有 all pass 的
winners = [r for r in results if r.get("all_pass")]
if winners:
    print(f"\n🎉🎉🎉 找到 {len(winners)} 个全部通过的 alpha!")
    for w in winners:
        print(f"  表达式: {w['expr']}")
        print(f"  alpha_id: {w.get('alpha_id')}")
else:
    print(f"\n⚠️ 暂无全部通过的版本")
    # 找最接近的
    close = [r for r in ranked if r.get("sharpe_check") == "PASS" or r.get("sub_result") == "PASS"]
    if close:
        print("最接近的版本:")
        for c in close[:3]:
            print(f"  Sharpe={c['sharpe']:.2f} Sub={c.get('sub_result')}({c.get('sub_value')}) | {c['desc']}")

ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
with open(OUTPUT_DIR / f"v3_finetune_r3_{ts}.json", 'w') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)
print(f"\n📄 已保存: v3_finetune_r3_{ts}.json")
