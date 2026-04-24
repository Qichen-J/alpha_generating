#!/usr/bin/env python3
"""
Round 4: Completely different alpha families.
The momentum*vol expression has a fundamental Fitness/Sub tradeoff.
Try diverse signal structures from templates that may naturally pass all criteria.

Families:
1. Realized vol asymmetry (downside vs upside vol)
2. Short-term reversal with IR neutralization
3. Fundamental: ROA double-neutralization
4. Working capital / assets fundamental
5. Volume concentration + reversal
6. Cross-sectional regression residual (momentum unexplained by vol)
7. ts_delta reversal on vwap
8. Momentum with regression_neut instead of multiplication
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

# Common settings
PV_SETTINGS = {
    "instrumentType": "EQUITY", "region": "USA", "universe": "TOP3000",
    "delay": 1, "neutralization": "SUBINDUSTRY",
    "truncation": 0.08, "pasteurization": "ON", "unitHandling": "VERIFY",
    "nanHandling": "ON", "language": "FASTEXPR", "visualization": False,
}

FND_SETTINGS = {
    "instrumentType": "EQUITY", "region": "USA", "universe": "TOP3000",
    "delay": 1, "neutralization": "INDUSTRY",
    "truncation": 0.08, "pasteurization": "ON", "unitHandling": "VERIFY",
    "nanHandling": "ON", "language": "FASTEXPR", "visualization": False,
}

VARIANTS = [
    # 1. Realized vol asymmetry: downside vol > upside vol → bearish signal
    # Uses only returns and cap — very clean signal
    ("R4_vol_asym",
     "IR = abs(ts_mean(returns,252)/ts_std_dev(returns,252));"
     "r=returns;"
     "a=power(ts_std_dev(abs(r)+r,30),2);"
     "b=power(ts_std_dev(abs(r)-r,30),2);"
     "c=regression_neut(b-a,IR);"
     "group_neutralize(c,bucket(rank(cap),range='0.2,1,0.2'))",
     {**PV_SETTINGS, "decay": 6, "neutralization": "SUBINDUSTRY"}),

    # 2. Short-term price reversal with IR neutralization
    ("R4_reversal_ir",
     "a = -ts_delta(close,3);"
     "b=abs(ts_mean(returns,252)/ts_std_dev(returns,252));"
     "group_neutralize(vector_neut(a,b),subindustry)",
     {**PV_SETTINGS, "decay": 4, "neutralization": "SUBINDUSTRY"}),

    # 3. ROA double-neutralization (fundamental)
    ("R4_roa_neut",
     "a = ts_zscore(operating_income/assets, 252);"
     "a1 = group_neutralize(a, bucket(rank(cap), range='0.1,1,0.1'));"
     "a2 = group_neutralize(a1, industry);"
     "b = ts_zscore(cap, 252);"
     "b1 = group_neutralize(b, industry);"
     "regression_neut(a2, b1)",
     {**FND_SETTINGS, "decay": 8}),

    # 4. Working capital ratio — fundamental
    ("R4_wc_assets",
     "a = ts_zscore(current_assets/assets, 252);"
     "a1 = group_neutralize(a, bucket(rank(cap), range='0.1,1,0.1'));"
     "a2 = group_neutralize(a1, industry);"
     "b = ts_zscore(cap, 252);"
     "b1 = group_neutralize(b, industry);"
     "regression_neut(a2, b1)",
     {**FND_SETTINGS, "decay": 8}),

    # 5. Volume concentration * reversal
    ("R4_vol_conc",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "alpha=rank(group_rank(ts_decay_linear(volume/ts_sum(volume,252),10),market)"
     "*group_rank(-ts_delta(close,5),market));"
     "trade_when(volume>adv20,group_neutralize(alpha,my_group),-1)",
     {**PV_SETTINGS, "decay": 6}),

    # 6. Regression residual: momentum unexplained by vol
    # Instead of multiplying rank(mom) * -rank(vol), use regression_neut
    ("R4_mom_resid_vol",
     "mom = ts_zscore(ts_delta(close, 5), 252);"
     "vol = ts_rank(ts_std_dev(returns, 20), 252);"
     "regression_neut(rank(mom), rank(vol))",
     {**PV_SETTINGS, "decay": 4, "neutralization": "SUBINDUSTRY"}),

    # 7. VWAP reversal with industry neutralization
    ("R4_vwap_rev",
     "a = -ts_delta(vwap, 5);"
     "b = abs(ts_mean(returns,252)/ts_std_dev(returns,252));"
     "regression_neut(group_neutralize(rank(a),bucket(rank(cap),range='0.1,1,0.1')),b)",
     {**PV_SETTINGS, "decay": 5, "neutralization": "INDUSTRY"}),

    # 8. Original signal but additive instead of multiplicative
    # rank(mom_zscore) + rank(-vol_rank) instead of *
    ("R4_additive",
     "rank(ts_zscore(ts_delta(close, 5), 252)) + rank(-ts_rank(ts_std_dev(returns, 20), 252))",
     {**PV_SETTINGS, "decay": 4, "neutralization": "SUBINDUSTRY"}),

    # 9. Inventory turnover fundamental
    ("R4_inv_turn",
     "a = ts_zscore(inventory_turnover, 252);"
     "a1 = group_neutralize(a, bucket(rank(cap), range='0.1,1,0.1'));"
     "a2 = group_neutralize(a1, industry);"
     "b = ts_zscore(cap, 252);"
     "b1 = group_neutralize(b, industry);"
     "regression_neut(a2, b1)",
     {**FND_SETTINGS, "decay": 8}),

    # 10. ts_corr between volume and returns (information flow)
    ("R4_vol_ret_corr",
     "a = ts_corr(volume, returns, 20);"
     "b = abs(ts_mean(returns,252)/ts_std_dev(returns,252));"
     "group_neutralize(regression_neut(rank(a),b),bucket(rank(cap),range='0.1,1,0.1'))",
     {**PV_SETTINGS, "decay": 5, "neutralization": "SUBINDUSTRY"}),
]

results = []

for idx, (name, expr, settings) in enumerate(VARIANTS):
    if idx > 0:
        print(f"\n--- 等待5秒避免限流 ---")
        time.sleep(5)

    print(f"\n[{idx+1}/{len(VARIANTS)}] {name}")
    print(f"  expr: {expr[:90]}...")

    location = None
    for attempt in range(10):
        r = s.post(f"{BASE}/simulations",
                   json={"type": "REGULAR", "settings": settings, "regular": expr})
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
                # Fetch alpha details
                for att in range(5):
                    ar = s.get(f"{BASE}/alphas/{alpha_id}")
                    if ar.status_code == 429:
                        time.sleep(int(float(ar.headers.get("Retry-After", 10))) + 3)
                        continue
                    if ar.status_code == 200:
                        break
                if ar.status_code == 200:
                    ad = ar.json()
                    iss = ad.get("is", {})
                    sharpe = iss.get("sharpe", 0)
                    fitness = iss.get("fitness", 0)
                    turnover = iss.get("turnover", 0)
                    ret = iss.get("returns", 0)
                    checks = {c["name"]: c for c in iss.get("checks", [])}
                    sub_check = checks.get("IQC_SUBUNIVERSE", {})
                    sub_val = sub_check.get("value", "?")
                    sub_cut = sub_check.get("limit", "?")
                    sha_pass = "✅" if sharpe >= 1.25 else "❌"
                    fit_pass = "✅" if fitness >= 1.0 else "❌"
                    sub_pass = "✅" if isinstance(sub_val, (int,float)) and isinstance(sub_cut,(int,float)) and sub_val >= sub_cut else "❌"
                    all_checks = all(c.get("result") == "PASS" for c in iss.get("checks", []))
                    all_tag = "🎉 ALL PASS" if all_checks else ""
                    print(f"  ✅ Sha={sharpe}{sha_pass} Fit={fitness}{fit_pass} Sub={sub_val}{sub_pass}(cut={sub_cut}) TO={turnover} Ret={ret} {all_tag}")
                    results.append({
                        "name": name, "alpha_id": alpha_id,
                        "sharpe": sharpe, "fitness": fitness,
                        "turnover": turnover, "returns": ret,
                        "sub_value": sub_val, "sub_cutoff": sub_cut,
                        "all_pass": all_checks, "expression": expr,
                    })
                    if all_checks:
                        print(f"\n{'='*60}")
                        print(f"🎉🎉🎉 FOUND SUBMITTABLE ALPHA: {name} 🎉🎉🎉")
                        print(f"  Alpha ID: {alpha_id}")
                        print(f"  Sharpe={sharpe} Fitness={fitness} Sub={sub_val}")
                        print(f"  Expression: {expr}")
                        print(f"{'='*60}")
                else:
                    print(f"  ⚠️ 无法获取alpha详情: {ar.status_code}")
                    results.append({"name": name, "alpha_id": alpha_id, "status": "DETAIL_FAIL"})
            else:
                err = data.get("error", data.get("message", "unknown"))
                print(f"  ❌ 模拟失败: {err}")
                results.append({"name": name, "status": "SIM_FAIL", "error": str(err)[:200]})
            break

        wait = max(int(retry_after), 5)
        time.sleep(wait)
    else:
        print(f"  ⏰ 超时")
        results.append({"name": name, "status": "TIMEOUT"})

# Save
outfile = os.path.join(OUTDIR, "r4_results.json")
with open(outfile, "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n{'='*60}")
print("R4 SUMMARY")
print(f"{'='*60}")
for r in results:
    if r.get("all_pass"):
        tag = "🎉 ALL PASS"
    elif r.get("sharpe"):
        tag = f"Sha={r['sharpe']} Fit={r['fitness']} Sub={r['sub_value']} TO={r['turnover']}"
    else:
        tag = r.get("status", "?")
    print(f"  {r['name']}: {tag}")

passers = [r for r in results if r.get("all_pass")]
if passers:
    print(f"\n🎉 {len(passers)} SUBMITTABLE ALPHA(S) FOUND!")
else:
    print(f"\n❌ No passing alphas in R4. Consider R5 with more variations.")
