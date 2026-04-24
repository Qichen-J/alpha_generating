#!/usr/bin/env python3
"""快速调试：检查 Brain API 的实际返回格式"""
import requests, time

CREDENTIALS = ("xxxxxx@example.com", "xxxxxx")
BASE = "https://api.worldquantbrain.com"

s = requests.Session()
s.post(f"{BASE}/authentication", auth=CREDENTIALS).raise_for_status()
print("✅ 认证成功")

# 提交一个简单的 alpha
expr = "rank(ts_zscore(ts_delta(close, 5), 252)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))"
settings = {
    "instrumentType": "EQUITY", "region": "USA", "universe": "TOP3000",
    "delay": 1, "decay": 5, "neutralization": "SUBINDUSTRY",
    "truncation": 0.08, "pasteurization": "ON", "unitHandling": "VERIFY",
    "nanHandling": "ON", "language": "FASTEXPR", "visualization": False,
}

for attempt in range(15):
    r = s.post(f"{BASE}/simulations", json={"type": "REGULAR", "settings": settings, "regular": expr})
    print(f"POST status={r.status_code}, Retry-After={r.headers.get('Retry-After')}")
    if r.status_code == 429:
        wait = int(float(r.headers.get("Retry-After", "30"))) + 5
        print(f"  限流, 等 {wait}s ({attempt+1}/15)")
        time.sleep(wait)
        continue
    break

sim_url = r.headers.get("Location", "")
print(f"Location: {sim_url}")

# Poll 并打印原始响应
for i in range(30):
    r = s.get(sim_url)
    retry_after = r.headers.get("Retry-After")
    data = r.json() if r.status_code == 200 else {}
    status_field = data.get("status")
    alpha_field = data.get("alpha")
    print(f"  [{i}] HTTP {r.status_code} | Retry-After='{retry_after}' (type={type(retry_after)}) | status='{status_field}' | alpha={type(alpha_field).__name__}={str(alpha_field)[:60]}")
    
    if retry_after is None or float(retry_after) == 0:
        print(f"\n✅ 模拟完成! 完整响应键: {list(data.keys())}")
        # 获取 alpha 详情
        alpha_id = alpha_field if isinstance(alpha_field, str) else (alpha_field.get("id") if isinstance(alpha_field, dict) else None)
        if alpha_id:
            ar = s.get(f"{BASE}/alphas/{alpha_id}")
            ad = ar.json()
            is_data = ad.get("is", {})
            print(f"  alpha_id={alpha_id}")
            print(f"  Sharpe={is_data.get('sharpe')}, Fitness={is_data.get('fitness')}, TO={is_data.get('turnover')}")
            checks = {c["name"]: c for c in is_data.get("checks", [])}
            for name, c in checks.items():
                print(f"  Check: {name} = {c.get('result')} (val={c.get('value')}, cutoff={c.get('cutoff')})")
        break
    
    wait = max(int(float(retry_after)), 3)
    time.sleep(wait)
