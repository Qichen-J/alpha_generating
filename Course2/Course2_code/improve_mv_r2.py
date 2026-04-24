#!/usr/bin/env python3
"""
Round 2: Focus on boosting FITNESS from E3 baseline.
E3 had Sharpe=1.38, Fitness=0.67, Sub=0.7, Turnover=0.39.
Fitness ≈ Sharpe * sqrt(|returns| / max(turnover, 0.125)).
Strategy: reduce turnover via higher decay / ts_decay_linear / smoothing.
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

# E3 baseline was: rank(ts_zscore(ts_delta(close,5),252)) * -rank(ts_rank(ts_std_dev(returns,20),252))
# with SUBINDUSTRY, decay=2.  Sharpe=1.38, Fit=0.67, TO=0.39
# Key insight: need to reduce turnover dramatically to boost fitness

ORIG = "rank(ts_zscore(ts_delta(close, 5), 252)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))"

VARIANTS = [
    # 1. Higher decay to reduce turnover
    ("R2_decay8_subind", ORIG, {**BASE_SETTINGS, "decay": 8}),
    # 2. Much higher decay
    ("R2_decay12_subind", ORIG, {**BASE_SETTINGS, "decay": 12}),
    # 3. Use ts_decay_linear inside the expression to smooth signal
    ("R2_tsdecay5", 
     "rank(ts_decay_linear(ts_zscore(ts_delta(close, 5), 252), 5)) * -rank(ts_decay_linear(ts_rank(ts_std_dev(returns, 20), 252), 5))",
     {**BASE_SETTINGS, "decay": 5}),
    # 4. ts_decay_linear with higher window (10 day smoothing)
    ("R2_tsdecay10",
     "rank(ts_decay_linear(ts_zscore(ts_delta(close, 5), 252), 10)) * -rank(ts_decay_linear(ts_rank(ts_std_dev(returns, 20), 252), 10))",
     {**BASE_SETTINGS, "decay": 5}),
    # 5. Lower truncation to reduce extreme positions + higher decay
    ("R2_trunc01_d8",
     ORIG,
     {**BASE_SETTINGS, "decay": 8, "truncation": 0.01}),
    # 6. group_rank + SUBINDUSTRY + high decay (combine best from R1)
    ("R2_grp_subind_d8",
     "group_rank(ts_zscore(ts_delta(close, 5), 252), subindustry) * -group_rank(ts_rank(ts_std_dev(returns, 20), 252), subindustry)",
     {**BASE_SETTINGS, "decay": 8}),
    # 7. ts_step + higher decay for super-smooth signal
    ("R2_step5_d10",
     "rank(ts_zscore(ts_delta(close, 5), 252)) * -rank(ts_step(5, ts_rank(ts_std_dev(returns, 20), 252)))",
     {**BASE_SETTINGS, "decay": 10}),
    # 8. Use ts_av_diff (moving avg crossover, inherently lower turnover)
    ("R2_avdiff_d5",
     "rank(ts_av_diff(close, 20)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))",
     {**BASE_SETTINGS, "decay": 5}),
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
print("Round 2 汇总:")
for r in results:
    if r["status"] == "COMPLETE":
        tag = "🎉" if r.get("all_pass") else ""
        print(f"  {r['name']}: Sha={r['sharpe']:.2f} Fit={r['fitness']:.2f} TO={r['turnover']:.4f} Ret={r['returns']:.4f} Sub={'P' if r['sub_pass'] else 'F'}({r['sub_value']}) {tag}")
    else:
        print(f"  {r['name']}: {r['status']}")

ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
outpath = os.path.join(OUTDIR, f"momentum_r2_{ts}.json")
with open(outpath, "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\n💾 {outpath}")
