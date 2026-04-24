#!/usr/bin/env python3
"""
Submit a few key variants with verbose polling to diagnose API behavior.
"""
import requests, json, time

CREDENTIALS = ("xxxxxx@example.com", "xxxxxx")
BASE = "https://api.worldquantbrain.com"

s = requests.Session()
r = s.post(f"{BASE}/authentication", auth=CREDENTIALS)
r.raise_for_status()
print("✅ 认证成功")

SETTINGS_IND = {
    "instrumentType": "EQUITY", "region": "USA", "universe": "TOP3000",
    "delay": 1, "decay": 5, "neutralization": "INDUSTRY",
    "truncation": 0.08, "pasteurization": "ON", "unitHandling": "VERIFY",
    "nanHandling": "ON", "language": "FASTEXPR", "visualization": False,
}

SETTINGS_SUBIND = {**SETTINGS_IND, "neutralization": "SUBINDUSTRY"}

VARIANTS = [
    ("E3_orig_d2_subind", "rank(ts_zscore(ts_delta(close, 5), 252)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))", {**SETTINGS_SUBIND, "decay": 2}),
    ("A1_grp_ind_d5", "group_rank(ts_zscore(ts_delta(close, 5), 252), industry) * -group_rank(ts_rank(ts_std_dev(returns, 20), 252), industry)", {**SETTINGS_IND, "decay": 5}),
    ("D1_grp_liq_ind_d4", "(group_rank(ts_zscore(ts_delta(close, 5), 252), industry) * -group_rank(ts_rank(ts_std_dev(returns, 20), 252), industry)) * rank(volume * close)", {**SETTINGS_IND, "decay": 4}),
    ("B1_liq_d5", "(rank(ts_zscore(ts_delta(close, 5), 252)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))) * rank(volume * close)", {**SETTINGS_IND, "decay": 5}),
    ("F1_neg_rank", "-rank(ts_zscore(ts_delta(close, 5), 252) * -ts_rank(ts_std_dev(returns, 20), 252))", {**SETTINGS_SUBIND, "decay": 5}),
    ("C1_win126", "rank(ts_zscore(ts_delta(close, 5), 126)) * -rank(ts_rank(ts_std_dev(returns, 10), 126))", {**SETTINGS_SUBIND, "decay": 5}),
]

results = []

for idx, (name, expr, settings) in enumerate(VARIANTS):
    if idx > 0:
        print(f"\n--- 等待5秒避免限流 ---")
        time.sleep(5)

    print(f"\n[{idx+1}/{len(VARIANTS)}] {name}")
    print(f"  expr: {expr[:80]}...")

    # Submit with retry
    location = None
    for attempt in range(10):
        r = s.post(f"{BASE}/simulations", json={"type": "REGULAR", "settings": settings, "regular": expr})
        print(f"  POST: {r.status_code} Retry-After={r.headers.get('Retry-After')}")
        if r.status_code == 429:
            wait = int(float(r.headers.get("Retry-After", 30))) + 5
            print(f"  限流, 等 {wait}s")
            time.sleep(wait)
            continue
        if r.status_code >= 400:
            print(f"  错误: {r.status_code} {r.text[:200]}")
            break
        location = r.headers.get("Location")
        break

    if not location:
        print(f"  ❌ 提交失败")
        results.append({"name": name, "status": "SUBMIT_FAIL"})
        continue

    print(f"  Location: {location}")

    # Poll with verbose logging
    t0 = time.time()
    while time.time() - t0 < 300:  # 5 min max
        try:
            pr = s.get(location)
        except Exception as e:
            print(f"  GET error: {e}")
            time.sleep(5)
            continue

        retry_after = float(pr.headers.get("Retry-After", 0))
        data = pr.json() if pr.status_code == 200 else {}
        elapsed = int(time.time() - t0)

        # Print full response every 30s or when done
        alpha_field = data.get("alpha")
        if elapsed % 30 < 6 or retry_after == 0:
            print(f"  [{elapsed}s] HTTP={pr.status_code} RA={retry_after} alpha={alpha_field} keys={list(data.keys())[:5]}")

        if retry_after == 0:
            alpha_id = alpha_field if isinstance(alpha_field, str) else None
            if alpha_id:
                ar = s.get(f"{BASE}/alphas/{alpha_id}")
                ad = ar.json()
                is_data = ad.get("is", {})
                sharpe = is_data.get("sharpe", 0)
                fitness = is_data.get("fitness", 0)
                turnover = is_data.get("turnover", 0)

                checks = {c["name"]: c for c in is_data.get("checks", [])}
                sha_p = checks.get("LOW_SHARPE", {}).get("result") == "PASS"
                fit_p = checks.get("LOW_FITNESS", {}).get("result") == "PASS"
                sub = checks.get("LOW_SUB_UNIVERSE_SHARPE", {})
                sub_p = sub.get("result") == "PASS"
                sub_v = sub.get("value", "?")
                sub_c = sub.get("cutoff", "?")
                ap = sha_p and fit_p and sub_p

                print(f"  ✅ Sharpe={sharpe:.2f}{'✅' if sha_p else '❌'} Fit={fitness:.2f}{'✅' if fit_p else '❌'} Sub={sub_v}{'✅' if sub_p else '❌'}(cut={sub_c}) TO={turnover:.4f} {'🎉ALL PASS' if ap else ''}")
                results.append({"name": name, "alpha_id": alpha_id, "sharpe": sharpe, "fitness": fitness,
                                "sub_pass": sub_p, "sub_value": sub_v, "all_pass": ap, "status": "COMPLETE"})
            else:
                print(f"  ❌ 完成但无alpha_id, data={json.dumps(data)[:300]}")
                results.append({"name": name, "status": "NO_ALPHA", "url": location})
            break
        time.sleep(max(retry_after, 3))
    else:
        print(f"  ⏰ 超时 (5min)")
        results.append({"name": name, "status": "TIMEOUT", "url": location})

# Summary
print(f"\n{'='*80}")
print("汇总:")
for r in results:
    if r["status"] == "COMPLETE":
        tag = "🎉" if r.get("all_pass") else ""
        print(f"  {r['name']}: Sharpe={r['sharpe']:.2f} Fit={r['fitness']:.2f} Sub={'P' if r['sub_pass'] else 'F'}({r['sub_value']}) {tag}")
    else:
        print(f"  {r['name']}: {r['status']}")

ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
with open(f"outputs/momentum_improve_{ts}.json", "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\n💾 outputs/momentum_improve_{ts}.json")
