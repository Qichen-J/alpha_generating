#!/usr/bin/env python3
"""查询所有 v3 改进版本的模拟结果 - 通过 alpha endpoint"""

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

# 所有提交的 simulation URLs
sims = [
    ("原始v3 (63,126)", "https://api.worldquantbrain.com/simulations/3zLrODayz5fIazU8jFjV717"),
    ("v1 事件触发", "https://api.worldquantbrain.com/simulations/EcWj83pT4AGaaX7cQfVDQj"),
    ("v2 多因子", "https://api.worldquantbrain.com/simulations/3Z7EXN7cU5fJbHBHwoshaU0"),
    ("v3.1 延长(126,252)", "https://api.worldquantbrain.com/simulations/1QruSj96G4Pebdg19fHbpIkl"),
    ("v3.2 波动率过滤", "https://api.worldquantbrain.com/simulations/1YMA44g0a4RJ92MRfuAHIgr"),
    ("v3.3 均衡(84,168)", "https://api.worldquantbrain.com/simulations/1vuZ7Ymd4lXbcDkHOJ1Swf"),
    ("v3.4 成交量条件", "https://api.worldquantbrain.com/simulations/21Nc0gbjx4B5cxwojP33BMu"),
    ("v3.5 高频(42,84)", "https://api.worldquantbrain.com/simulations/s3Q2Y8Lu4Dfag8171tWMZ8L"),
]

print(f"{'版本':<25} {'状态':<10} {'Sharpe':<10} {'Fitness':<10} {'Turnover':<10} {'Returns':<10} {'Drawdown':<10}")
print("=" * 95)

for name, sim_url in sims:
    try:
        # Step 1: 获取 simulation 信息
        r = sess.get(sim_url, timeout=REQUEST_TIMEOUT)
        if r.status_code >= 400:
            print(f"{name:<25} HTTP {r.status_code}")
            continue
        
        retry_after = float(r.headers.get("Retry-After", 0))
        if retry_after > 0:
            print(f"{name:<25} {'处理中...':<10}")
            continue
        
        sim_data = r.json()
        status = sim_data.get("status", "unknown")
        alpha_id = sim_data.get("alpha", "")
        
        if status != "COMPLETE" or not alpha_id:
            print(f"{name:<25} {status:<10}")
            if "error" in sim_data:
                print(f"  └─ 错误: {sim_data['error']}")
            continue
        
        # Step 2: 通过 alpha ID 获取详细指标
        alpha_url = f"https://api.worldquantbrain.com/alphas/{alpha_id}"
        ar = sess.get(alpha_url, timeout=REQUEST_TIMEOUT)
        
        if ar.status_code >= 400:
            print(f"{name:<25} {status:<10} (alpha查询失败: HTTP {ar.status_code})")
            continue
        
        alpha_data = ar.json()
        
        # 提取指标
        is_data = alpha_data.get("is", {})
        sharpe = is_data.get("sharpe", "N/A")
        fitness = is_data.get("fitness", "N/A")
        turnover = is_data.get("turnover", "N/A")
        returns_val = is_data.get("returns", "N/A")
        drawdown = is_data.get("drawdown", "N/A")
        
        # 格式化数值
        def fmt(v):
            if isinstance(v, (int, float)):
                return f"{v:.4f}"
            return str(v)
        
        print(f"{name:<25} {status:<10} {fmt(sharpe):<10} {fmt(fitness):<10} {fmt(turnover):<10} {fmt(returns_val):<10} {fmt(drawdown):<10}")
        
        # 检查 checks
        checks = alpha_data.get("is", {}).get("checks", alpha_data.get("checks", {}))
        if checks:
            for ck, cv in checks.items():
                if isinstance(cv, dict):
                    passed = cv.get("result", cv.get("passed", "?"))
                    print(f"  └─ {ck}: {'✅' if passed == 'PASS' or passed is True else '❌'} {passed}")
        
    except Exception as e:
        print(f"{name:<25} 异常: {e}")

# 打印原始 v3 alpha 的完整 JSON
print("\n" + "=" * 95)
print("📊 原始 v3 alpha 详情:")
print("=" * 95)
try:
    r = sess.get("https://api.worldquantbrain.com/simulations/3zLrODayz5fIazU8jFjV717", timeout=REQUEST_TIMEOUT)
    sim_data = r.json()
    alpha_id = sim_data.get("alpha", "")
    if alpha_id:
        ar = sess.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}", timeout=REQUEST_TIMEOUT)
        alpha_data = ar.json()
        # 只打印关键部分
        for key in ["is", "os", "checks", "dateCreated", "grade"]:
            if key in alpha_data:
                print(f"\n{key}:")
                print(json.dumps(alpha_data[key], indent=2, ensure_ascii=False))
except Exception as e:
    print(f"异常: {e}")

# 打印 v3.1 的完整 JSON
print("\n" + "=" * 95)
print("📊 v3.1 alpha 详情:")
print("=" * 95)
try:
    r = sess.get("https://api.worldquantbrain.com/simulations/1QruSj96G4Pebdg19fHbpIkl", timeout=REQUEST_TIMEOUT)
    sim_data = r.json()
    alpha_id = sim_data.get("alpha", "")
    if alpha_id:
        ar = sess.get(f"https://api.worldquantbrain.com/alphas/{alpha_id}", timeout=REQUEST_TIMEOUT)
        alpha_data = ar.json()
        for key in ["is", "os", "checks", "grade"]:
            if key in alpha_data:
                print(f"\n{key}:")
                print(json.dumps(alpha_data[key], indent=2, ensure_ascii=False))
    else:
        print(f"status={sim_data.get('status')}, no alpha id")
        print(json.dumps(sim_data, indent=2)[:1000])
except Exception as e:
    print(f"异常: {e}")
