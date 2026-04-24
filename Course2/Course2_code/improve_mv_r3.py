#!/usr/bin/env python3
"""
Round 3: Target the sweet spot between E3 (decay=2, Sha=1.38, Sub=0.7, Fit=0.67, TO=0.39)
and R2_decay12 (decay=12, Sha=1.27, Sub=0.38, Fit=0.83, TO=0.18).

Strategy:
- Moderate decay (3-5) to reduce TO without killing Sub
- Longer delta/smoothing windows for inherently lower turnover signals
- ts_mean smoothing before rank to reduce daily rank flips
- Different expression structures that preserve cross-sectional signal but change slowly
"""
import requests, json, time, os

CREDENTIALS = ("xxxxxx@example.com", "xxxxxx")
BASE = "https://api.worldquantbrain.com"
OUTDIR = "/Users/zhiqu/Desktop/brain/Course2/Course2_code/outputs"
os.makedirs(OUTDIR, exist_ok=True)

s = requests.Session()
r = s.post(f"{BASE}/authentication", auth=CREDENTIALS)
r.raise_for_status()
print("✅ 认证成功")

BASE_SETTINGS = {
    "instrumentType": "EQUITY", "region": "USA", "universe": "TOP3000",
    "delay": 1, "neutralization": "SUBINDUSTRY",
    "truncation": 0.08, "pasteurization": "ON", "unitHandling": "VERIFY",
    "nanHandling": "ON", "language": "FASTEXPR", "visualization": False,
}

# E3 original: rank(ts_zscore(ts_delta(close,5),252)) * -rank(ts_rank(ts_std_dev(returns,20),252))
ORIG = "rank(ts_zscore(ts_delta(close, 5), 252)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))"

VARIANTS = [
    # 1. Moderate decay=3 (between 2 and 8)
    ("R3_d3", ORIG, {**BASE_SETTINGS, "decay": 3}),
    
    # 2. Moderate decay=4
    ("R3_d4", ORIG, {**BASE_SETTINGS, "decay": 4}),
    
    # 3. Moderate decay=5
    ("R3_d5", ORIG, {**BASE_SETTINGS, "decay": 5}),
    
    # 4. Smooth signal with ts_mean before ranking, decay=3
    ("R3_smooth3_d3",
     "rank(ts_mean(ts_zscore(ts_delta(close, 5), 252), 3)) * -rank(ts_mean(ts_rank(ts_std_dev(returns, 20), 252), 3))",
     {**BASE_SETTINGS, "decay": 3}),
    
    # 5. Use longer delta window (10 days) — inherently smoother, decay=3
    ("R3_delta10_d3",
     "rank(ts_zscore(ts_delta(close, 10), 252)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))",
     {**BASE_SETTINGS, "decay": 3}),
    
    # 6. Use longer delta (10) + longer vol window (40), decay=4
    ("R3_d10v40_d4",
     "rank(ts_zscore(ts_delta(close, 10), 252)) * -rank(ts_rank(ts_std_dev(returns, 40), 252))",
     {**BASE_SETTINGS, "decay": 4}),
    
    # 7. ts_decay_linear(3) inside + decay=2 (light smoothing, keep Sub)
    ("R3_tsd3_d2",
     "rank(ts_decay_linear(ts_zscore(ts_delta(close, 5), 252), 3)) * -rank(ts_decay_linear(ts_rank(ts_std_dev(returns, 20), 252), 3))",
     {**BASE_SETTINGS, "decay": 2}),
    
    # 8. Original expression but with INDUSTRY neutralization + decay=4
    # (INDUSTRY is coarser than SUBINDUSTRY, might help Sub)
    ("R3_ind_d4", ORIG, {**BASE_SETTINGS, "decay": 4, "neutralization": "INDUSTRY"}),
]

results = []

for idx, (name, expr, settings) in enumerate(VARIANTS):
    if idx > 0:
        print(f"\n--- 等待5秒避免限流 ---")
        time.sleep(5)

    print(f"\n[{idx+1}/{len(VARIANTS)}] {name}")
    print(f"  expr: {expr[:80]}...")

    location = None
    for attempt in range(10):
        r = s.post(f"{BASE}/simulations", json={"type": "REGULAR", "settings": settings, "regular": expr})
        print(f"  POST: {r.status_code} RA={r.headers.get('Retry-After')}")
        if r.status_code == 429:
            wait = int(float(r.headers.get("Retry-After", 30))) + 5
            print(f"  限流, 等 {wait}s")
            time.sleep(wait)
            continue
        if r.status_code >= 400:
            print(f"  错误: {r.status_code} {r.text[:300]}")
            break
        location = r.headers.get("Location")
        break

    if not location:
        print(f"  ❌ 提交失败")
        results.append({"name": name, "status": "SUBMIT_FAIL"})
        continue

    print(f"  Location: {location}")

    t0 = time.time()
    while time.time() - t0 < 300:
        try:
            pr = s.get(location)
        except Exception as e:
            print(f"  GET error: {e}")
            time.sleep(5)
            continue

        retry_after = float(pr.headers.get("Retry-After", 0))
        data = pr.json() if pr.status_code == 200 else {}
        elapsed = int(time.time() - t0)
        alpha_field = data.get("alpha")

        if elapsed % 30 < 6 or retry_after == 0:
            print(f"  [{elapsed}s] HTTP={pr.status_code} RA={retry_after} alpha={alpha_field}")

        if retry_after == 0:
            alpha_id = alpha_field if isinstance(alpha_field, str) else None
            if alpha_id:
                ar = s.get(f"{BASE}/alphas/{alpha_id}")
                ad = ar.json()
                is_data = ad.get("is", {})
                sharpe = is_data.get("sharpe", 0)
                fitness = is_data.get("fitness", 0)
                turnover = is_data.get("turnover", 0)
                ret = is_data.get("returns", 0)

                checks = {c["name"]: c for c in is_data.get("checks", [])}
                sha_p = checks.get("LOW_SHARPE", {}).get("result") == "PASS"
                fit_p = checks.get("LOW_FITNESS", {}).get("result") == "PASS"
                sub = checks.get("LOW_SUB_UNIVERSE_SHARPE", {})
                sub_p = sub.get("result") == "PASS"
                sub_v = sub.get("value", "?")
                sub_c = sub.get("cutoff", "?")
                ap = sha_p and fit_p and sub_p

                tag = "🎉ALL PASS" if ap else ""
                print(f"  ✅ Sha={sharpe:.2f}{'✅' if sha_p else '❌'} Fit={fitness:.2f}{'✅' if fit_p else '❌'} Sub={sub_v}{'✅' if sub_p else '❌'}(cut={sub_c}) TO={turnover:.4f} Ret={ret:.4f} {tag}")
                results.append({"name": name, "alpha_id": alpha_id, "sharpe": sharpe,
                               "fitness": fitness, "turnover": turnover, "returns": ret,
                               "sub_pass": sub_p, "sub_value": sub_v, "all_pass": ap, "status": "COMPLETE"})
            else:
                print(f"  ❌ 完成但无alpha_id")
                results.append({"name": name, "status": "NO_ALPHA", "url": location})
            break
        time.sleep(max(retry_after, 3))
    else:
        print(f"  ⏰ 超时 (5min)")
        results.append({"name": name, "status": "TIMEOUT", "url": location})

print(f"\n{'='*80}")
print("Round 3 汇总:")
for r in results:
    if r["status"] == "COMPLETE":
        tag = "🎉" if r.get("all_pass") else ""
        print(f"  {r['name']}: Sha={r['sharpe']:.2f} Fit={r['fitness']:.2f} TO={r['turnover']:.4f} Ret={r['returns']:.4f} Sub={'P' if r['sub_pass'] else 'F'}({r['sub_value']}) {tag}")
    else:
        print(f"  {r['name']}: {r['status']}")

ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
outpath = os.path.join(OUTDIR, f"momentum_r3_{ts}.json")
with open(outpath, "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\n💾 {outpath}")
