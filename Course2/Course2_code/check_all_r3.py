#!/usr/bin/env python3
"""查询第三轮所有超时的结果 + 验证两个 ALL PASS winner"""

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

# R3 所有 simulation
r3_sims = [
    ("A2: SUBIND+(63,100)+d4", "https://api.worldquantbrain.com/simulations/2Rgr2E6IW4DP9EI10kMAmDZX"),
    ("A4: SUBIND+(63,100)+d5+t0.10", "https://api.worldquantbrain.com/simulations/48KPpUcLA4RXchdwxoBoXa1"),
    ("A7: SUBIND+vol_scale+d5", "https://api.worldquantbrain.com/simulations/4tdD5g5OT5i8caZ34eJ0VHO"),
    ("B2: IND+(60,100)+d3", "https://api.worldquantbrain.com/simulations/3MFnwJ1U74Ii9xquE0ns2O3"),
    ("B3: IND+(63,90)+d3", "https://api.worldquantbrain.com/simulations/1KdGuG5Y85ihaRDjCYt6uhK"),
    ("B4: IND+(63,80)+d3", "https://api.worldquantbrain.com/simulations/3vyKaZft64kCblNPToS7wXV"),
    ("B5: IND+(63,100)+d4", "https://api.worldquantbrain.com/simulations/1TvHoN9eS4tf9NGouloJBYh"),
    ("B6: IND+grp_rank+d3", "https://api.worldquantbrain.com/simulations/2ev3tlQP5b0bicGUqnTZdW"),
    ("B8: IND+grp_rank+d4", "https://api.worldquantbrain.com/simulations/hTZlYagF5gobFk15zb2EGzm"),
]

# R2 超时的
r2_sims = [
    ("R2-combo2: (63,100)+d6", "https://api.worldquantbrain.com/simulations/4FQ6XKded540bD0acZ1gRAW"),
    ("R2-combo3: (63,100)+d7", "https://api.worldquantbrain.com/simulations/2aGZ2V5Cw4Iy8SuIELvt2zL"),
    ("R2-combo4: (63,100)+d4", "https://api.worldquantbrain.com/simulations/3R7bwz8YX4uab1YWuBQc4TD"),
    ("R2-combo6: (60,100)+d5", "https://api.worldquantbrain.com/simulations/441Sqyb5K4FDasYCEdLOb2T"),
    ("R2-combo8: (63,80)+d5", "https://api.worldquantbrain.com/simulations/2qHF8Gb1b4S3b6GpYlEcZcs"),
]

# Winners
winners = [
    ("🏆 A6: SUBIND+grp_rank+d5", "https://api.worldquantbrain.com/simulations/G1OBC3U94Dj9Q4HnfLgn2d"),
    ("🏆 B1: IND+(63,100)+d2", "https://api.worldquantbrain.com/simulations/4k0X4acyq4Hda5P6a9CLoJ4"),
]

all_sims = winners + r3_sims + r2_sims

print(f"{'描述':<35} {'状态':<10} {'Sharpe':<8} {'Fit':<8} {'TO':<8} {'Sub':<15} {'SharpeChk':<10} {'FitChk'}")
print("=" * 120)

for name, url in all_sims:
    try:
        r = sess.get(url, timeout=REQUEST_TIMEOUT)
        if r.status_code >= 400:
            print(f"{name:<35} HTTP {r.status_code}")
            continue
        retry_after = float(r.headers.get("Retry-After", 0))
        if retry_after > 0:
            print(f"{name:<35} {'处理中...'}")
            continue
        sim = r.json()
        status = sim.get("status", "?")
        alpha_id = sim.get("alpha", "")
        if status != "COMPLETE" or not alpha_id:
            print(f"{name:<35} {status}")
            continue
        ar = sess.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}", timeout=REQUEST_TIMEOUT)
        a = ar.json()
        is_d = a.get("is", {})
        checks = is_d.get("checks", [])
        sub = next((c for c in checks if c["name"] == "LOW_SUB_UNIVERSE_SHARPE"), {})
        sharpe_ck = next((c for c in checks if c["name"] == "LOW_SHARPE"), {})
        fitness_ck = next((c for c in checks if c["name"] == "LOW_FITNESS"), {})
        
        sharpe = is_d.get("sharpe", "?")
        fitness = is_d.get("fitness", "?")
        all_pass = (sharpe_ck.get("result") == "PASS" and 
                   fitness_ck.get("result") == "PASS" and
                   sub.get("result") == "PASS")
        marker = " 🎉ALL PASS" if all_pass else ""
        
        def fmt(v):
            return f"{v:.4f}" if isinstance(v, float) else str(v)
        
        print(f"{name:<35} {status:<10} {fmt(sharpe):<8} {fmt(fitness):<8} "
              f"{fmt(is_d.get('turnover','?')):<8} "
              f"{sub.get('result','?')}({sub.get('value','?')}){'':>3} "
              f"{sharpe_ck.get('result','?'):<10} {fitness_ck.get('result','?')}{marker}")
    except Exception as e:
        print(f"{name:<35} 异常: {e}")
