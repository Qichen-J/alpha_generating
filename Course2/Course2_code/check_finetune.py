#!/usr/bin/env python3
"""查询 finetune 批次中所有 simulation 的最终结果"""

import json
import os
import requests
from requests.auth import HTTPBasicAuth

BRAIN_USERNAME = os.getenv("BRAIN_USERNAME", "xxxxxx@example.com")
BRAIN_PASSWORD = os.getenv("BRAIN_PASSWORD", "xxxxxx")
REQUEST_TIMEOUT = 30

sess = requests.Session()
sess.auth = HTTPBasicAuth(BRAIN_USERNAME, BRAIN_PASSWORD)
r = sess.post("https://api.worldquantbrain.com/authentication", timeout=REQUEST_TIMEOUT)
r.raise_for_status()
print("✅ 认证成功\n")

sims = [
    ("A1 参数(60,120)", "https://api.worldquantbrain.com/simulations/WZapgpp5b7auGTmWOCZFU"),
    ("A2 参数(63,120)", "https://api.worldquantbrain.com/simulations/29M5aucBC4xl9Es12dyhkcIT"),
    ("A3 参数(60,126)", "https://api.worldquantbrain.com/simulations/3btSVXgVe4Tvaxh1bbWF4wrL"),
    ("A4 参数(50,126)", "https://api.worldquantbrain.com/simulations/3jtqosdlO4Kv9iZWyTmmZse"),
    ("A5 参数(63,100)", "https://api.worldquantbrain.com/simulations/39raBr5zt4nz9GrcUTZBqct"),
    ("A6 参数(63,150)", "https://api.worldquantbrain.com/simulations/28H2bs64E4yochdvrcIKm1x"),
    ("A7 参数(63,63)",  "https://api.worldquantbrain.com/simulations/4l7B82sd4VDcvKestGe55t"),
    ("A8 参数(50,100)", "https://api.worldquantbrain.com/simulations/31CDgx1Cd5fucvWKJIpZN0a"),
    ("B decay=5",  "https://api.worldquantbrain.com/simulations/2WyNS76EV4Sn96412QHwr5ro"),
    ("B decay=8",  "https://api.worldquantbrain.com/simulations/21iMg6gqu4XC8OstruqXHOF"),
    ("B decay=12", "https://api.worldquantbrain.com/simulations/2Cg3dIet857t9ZF17bFeHRhC"),
    ("B decay=15", "https://api.worldquantbrain.com/simulations/3PD3hI1tj4Bq94wshFcB4tt"),
    ("C trunc=0.05", "https://api.worldquantbrain.com/simulations/2CAEPAgTD4SPaqY1arDyT0xd"),
    ("C trunc=0.06", "https://api.worldquantbrain.com/simulations/3OdDYi5BJ4Xpb6wLPd8iRo3"),
    ("C trunc=0.10", "https://api.worldquantbrain.com/simulations/1uipXKcKE57k9PkdBO1fiMf"),
    ("C trunc=0.12", "https://api.worldquantbrain.com/simulations/ZzZwigvE4n58Ne1esPtqNC6"),
    ("D neut=SUBINDUSTRY", "https://api.worldquantbrain.com/simulations/dajHnazF4nnaKghaNCLD5K"),
    ("D neut=MARKET", "https://api.worldquantbrain.com/simulations/35w3Lt2v95g59w41d0NhQXh"),
    ("E1 vwap替代close", "https://api.worldquantbrain.com/simulations/2HpZLZJZ4rscmSmPGCssO3"),
    ("E2 group_rank", "https://api.worldquantbrain.com/simulations/1PNJHB6Qk4AdcDzaj9usN6d"),
    ("E3 ts_rank(252)", "https://api.worldquantbrain.com/simulations/1SZM6L2Ah4IvaAs1dTIWRyp7"),
    ("E4 sign替代rank", "https://api.worldquantbrain.com/simulations/3S8FkE4ZW5iD8HF93gI2W96"),
]

results = []
print(f"{'#':<4} {'描述':<25} {'状态':<10} {'Sharpe':<8} {'Fitness':<8} {'Turnover':<8} {'Drawdown':<8} {'SubUniv'}")
print("=" * 110)

for i, (name, url) in enumerate(sims, 1):
    try:
        r = sess.get(url, timeout=REQUEST_TIMEOUT)
        retry_after = float(r.headers.get("Retry-After", 0))
        if retry_after > 0:
            print(f"{i:<4} {name:<25} {'处理中':<10}")
            continue
        
        sim = r.json()
        status = sim.get("status", "?")
        alpha_id = sim.get("alpha", "")
        
        if status != "COMPLETE" or not alpha_id:
            err = sim.get("error", "")
            print(f"{i:<4} {name:<25} {status:<10} {err}")
            continue
        
        ar = sess.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}", timeout=REQUEST_TIMEOUT)
        a = ar.json()
        is_data = a.get("is", {})
        
        sharpe = is_data.get("sharpe", "?")
        fitness = is_data.get("fitness", "?")
        turnover = is_data.get("turnover", "?")
        drawdown = is_data.get("drawdown", "?")
        
        # sub-universe check
        sub_val = ""
        checks = is_data.get("checks", [])
        for c in checks:
            if c["name"] == "LOW_SUB_UNIVERSE_SHARPE":
                sub_val = f"{c.get('result','?')} ({c.get('value','?')})"
            
        marker = " ⭐⭐⭐" if isinstance(sharpe, (int, float)) and sharpe >= 1.25 else \
                 " ⭐" if isinstance(sharpe, (int, float)) and sharpe >= 1.15 else ""
        
        def fmt(v):
            return f"{v:.4f}" if isinstance(v, float) else str(v)
        
        print(f"{i:<4} {name:<25} {status:<10} {fmt(sharpe):<8} {fmt(fitness):<8} {fmt(turnover):<8} {fmt(drawdown):<8} {sub_val}{marker}")
        
        results.append({
            "desc": name, "sharpe": sharpe, "fitness": fitness,
            "turnover": turnover, "drawdown": drawdown, "alpha_id": alpha_id,
            "url": url, "sub_universe": sub_val
        })
        
    except Exception as e:
        print(f"{i:<4} {name:<25} 异常: {e}")

# 排行榜
print("\n🏆 排行榜:")
ranked = sorted([r for r in results if isinstance(r["sharpe"], (int, float))],
                key=lambda x: x["sharpe"], reverse=True)
for i, r in enumerate(ranked[:10], 1):
    m = " ✅过线!" if r["sharpe"] >= 1.25 else ""
    print(f"  {i}. Sharpe={r['sharpe']:.2f} Fitness={r['fitness']} | {r['desc']}{m}")
