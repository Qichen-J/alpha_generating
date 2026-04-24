#!/usr/bin/env python3
"""
Round 5: Focused iteration on ts_av_diff — the most promising expression.

R2_avdiff_d5 result:
  rank(ts_av_diff(close, 20)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))
  Sha=1.34✅  Fit=0.86❌  Sub=0.58✅  TO=0.1894  Ret=0.0788

Fitness ≈ Sha × √(Ret / max(TO, 0.125))
To hit Fit≥1.0: need TO ≤ ~0.125 (capped) → Fit = 1.34 × √(0.0788/0.125) = 1.06 ✅
OR much higher Sharpe with moderate TO.

Strategy: Push decay higher (7-15) to reduce TO while monitoring Sub.
Also try longer ts_av_diff windows, group_rank, and complementary signals.
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

# Base expression from R2_avdiff_d5
AVDIFF_BASE = "rank(ts_av_diff(close, 20)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))"

VARIANTS = [
    # --- Decay sweep to find TO sweet spot ---
    # 1. decay=7: moderate reduction
    ("R5_avd20_d7", AVDIFF_BASE, {**BASE_SETTINGS, "decay": 7}),

    # 2. decay=8
    ("R5_avd20_d8", AVDIFF_BASE, {**BASE_SETTINGS, "decay": 8}),

    # 3. decay=10: should push TO significantly lower
    ("R5_avd20_d10", AVDIFF_BASE, {**BASE_SETTINGS, "decay": 10}),

    # 4. decay=12: aggressive, might hit TO<0.125 cap
    ("R5_avd20_d12", AVDIFF_BASE, {**BASE_SETTINGS, "decay": 12}),

    # 5. decay=15: very aggressive
    ("R5_avd20_d15", AVDIFF_BASE, {**BASE_SETTINGS, "decay": 15}),

    # --- Longer ts_av_diff window (smoother signal, inherently lower TO) ---
    # 6. ts_av_diff(close, 30) decay=5 — same decay but smoother input
    ("R5_avd30_d5",
     "rank(ts_av_diff(close, 30)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))",
     {**BASE_SETTINGS, "decay": 5}),

    # 7. ts_av_diff(close, 30) decay=8
    ("R5_avd30_d8",
     "rank(ts_av_diff(close, 30)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))",
     {**BASE_SETTINGS, "decay": 8}),

    # 8. ts_av_diff(close, 40) decay=7
    ("R5_avd40_d7",
     "rank(ts_av_diff(close, 40)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))",
     {**BASE_SETTINGS, "decay": 7}),

    # --- Expression tweaks ---
    # 9. group_rank variant (might boost Sub)
    ("R5_grp_d7",
     "group_rank(ts_av_diff(close, 20), subindustry) * -group_rank(ts_rank(ts_std_dev(returns, 20), 252), subindustry)",
     {**BASE_SETTINGS, "decay": 7}),

    # 10. Longer vol window (40 days) for smoother vol ranking
    ("R5_vol40_d7",
     "rank(ts_av_diff(close, 20)) * -rank(ts_rank(ts_std_dev(returns, 40), 252))",
     {**BASE_SETTINGS, "decay": 7}),

    # 11. INDUSTRY neutralization (coarser, might help Sub)
    ("R5_ind_d7", AVDIFF_BASE, {**BASE_SETTINGS, "decay": 7, "neutralization": "INDUSTRY"}),

    # 12. ts_av_diff alone (no vol component) — maybe vol part hurts Fitness
    ("R5_avd_only_d7",
     "rank(ts_av_diff(close, 20))",
     {**BASE_SETTINGS, "decay": 7}),
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
                if ap:
                    print(f"\n🎉🎉🎉 找到可提交的Alpha! {name} alpha_id={alpha_id} 🎉🎉🎉")
                    print(f"  Expression: {expr}")
                    print(f"  Settings: decay={settings.get('decay')}, neut={settings.get('neutralization')}")
            else:
                print(f"  ❌ 完成但无alpha_id")
                results.append({"name": name, "status": "NO_ALPHA", "url": location})
            break
        time.sleep(max(retry_after, 3))
    else:
        print(f"  ⏰ 超时 (5min)")
        results.append({"name": name, "status": "TIMEOUT", "url": location})

print(f"\n{'='*80}")
print("Round 5 汇总:")
for r in results:
    if r["status"] == "COMPLETE":
        tag = "🎉" if r.get("all_pass") else ""
        print(f"  {r['name']}: Sha={r['sharpe']:.2f} Fit={r['fitness']:.2f} TO={r['turnover']:.4f} Ret={r['returns']:.4f} Sub={'P' if r['sub_pass'] else 'F'}({r['sub_value']}) {tag}")
    else:
        print(f"  {r['name']}: {r['status']}")

# Check if any passed
passed = [r for r in results if r.get("all_pass")]
if passed:
    print(f"\n🎉 共 {len(passed)} 个Alpha通过所有检查!")
    for p in passed:
        print(f"  ✅ {p['name']}: alpha_id={p['alpha_id']}")
else:
    print(f"\n❌ 本轮无Alpha通过所有检查")

ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
outpath = os.path.join(OUTDIR, f"avdiff_r5_{ts}.json")
with open(outpath, "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\n💾 {outpath}")
