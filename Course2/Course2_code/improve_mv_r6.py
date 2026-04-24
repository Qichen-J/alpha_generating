#!/usr/bin/env python3
"""
Round 6: Completely new alpha families.

Analysis of 5 rounds:
- Momentum × vol: Sha~1.3 but Fitness stuck at 0.65-0.86, can't pass
- ts_av_diff: Fit capped at 0.86 regardless of decay (Sha drops as TO drops)
- Core problem: need BOTH Sha≥1.25 AND Fit≥1.0 AND Sub≥0.53

New strategy: Try different alpha families entirely.
1. Volume concentration / liquidity alphas
2. Short-term reversal with proper vol weighting
3. Price-volume divergence
4. VWAP deviation mean reversion
5. Earnings quality / accrual proxies (using available fundamentals)

Key constraints:
- NO regression_neut, vector_neut, ts_step, current_assets
- USE group_neutralize, group_rank, rank, ts_zscore, ts_decay_linear etc.
"""
import requests, json, time, os

CREDENTIALS = ("xxxxxx@example.com", "xxxxxx")
BASE = "https://api.worldquantbrain.com"
OUTDIR = "/Users/zhiqu/Desktop/brain/Course2/Course2_code/outputs"
os.makedirs(OUTDIR, exist_ok=True)

s = requests.Session()
# Set timeout to avoid hanging
s.timeout = 60

r = s.post(f"{BASE}/authentication", auth=CREDENTIALS)
r.raise_for_status()
print("✅ 认证成功")

BASE_SETTINGS = {
    "instrumentType": "EQUITY", "region": "USA", "universe": "TOP3000",
    "delay": 1, "neutralization": "SUBINDUSTRY",
    "truncation": 0.08, "pasteurization": "ON", "unitHandling": "VERIFY",
    "nanHandling": "ON", "language": "FASTEXPR", "visualization": False,
}

VARIANTS = [
    # === Family 1: Volume-price divergence ===
    # When price rises but volume drops (or vice versa), reversal signal
    ("R6_vpd_d5",
     "rank(ts_corr(close, volume, 20)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))",
     {**BASE_SETTINGS, "decay": 5}),

    # === Family 2: VWAP mean reversion ===
    # Stocks far from VWAP tend to revert
    ("R6_vwap_rev_d5",
     "-rank(ts_zscore((close - vwap) / close, 60)) * rank(ts_rank(volume / adv20, 60))",
     {**BASE_SETTINGS, "decay": 5}),

    ("R6_vwap_rev_d8",
     "-rank(ts_zscore((close - vwap) / close, 60)) * rank(ts_rank(volume / adv20, 60))",
     {**BASE_SETTINGS, "decay": 8}),

    # === Family 3: Short-term reversal with liquidity filter ===
    ("R6_rev3_liq_d5",
     "-rank(ts_zscore(ts_delta(close, 3), 126)) * rank(ts_rank(volume / adv60, 60))",
     {**BASE_SETTINGS, "decay": 5}),

    ("R6_rev3_liq_d3",
     "-rank(ts_zscore(ts_delta(close, 3), 126)) * rank(ts_rank(volume / adv60, 60))",
     {**BASE_SETTINGS, "decay": 3}),

    # === Family 4: Volume concentration (from forum templates) ===
    ("R6_vol_conc_d7",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "alpha=rank(group_rank(ts_decay_linear(volume/ts_sum(volume,252),10),my_group)"
     "*group_rank(-ts_delta(close,5),my_group));"
     "group_neutralize(alpha,my_group)",
     {**BASE_SETTINGS, "decay": 7, "neutralization": "INDUSTRY"}),

    # === Family 5: Earnings quality — operating income vs assets ===
    ("R6_roa_d5",
     "a = ts_zscore(operating_income/assets, 252);"
     "a1 = group_neutralize(a, bucket(rank(cap), range='0.1,1,0.1'));"
     "group_neutralize(a1, industry)",
     {**BASE_SETTINGS, "decay": 5, "neutralization": "INDUSTRY"}),

    # === Family 6: Inventory turnover quality ===
    ("R6_invt_d5",
     "a = ts_zscore(inventory_turnover, 252);"
     "a1 = group_neutralize(a, bucket(rank(cap), range='0.1,1,0.1'));"
     "group_neutralize(a1, industry)",
     {**BASE_SETTINGS, "decay": 5, "neutralization": "INDUSTRY"}),

    # === Family 7: Price-volume co-movement with decay ===
    ("R6_pv_cokurt_d5",
     "g=bucket(rank(cap),range='0,1,0.1');"
     "-rank(group_neutralize(ts_co_kurtosis(close, volume, 20), g))",
     {**BASE_SETTINGS, "decay": 5}),

    # === Family 8: Return dispersion signal ===
    # Low return dispersion (relative to sector) tends to predict momentum continuation
    ("R6_disp_d5",
     "a = ts_std_dev(returns, 20) / group_mean(ts_std_dev(returns, 20), 1, subindustry);"
     "-rank(ts_zscore(a, 252)) * rank(ts_rank(ts_delta(close, 10), 252))",
     {**BASE_SETTINGS, "decay": 5}),

    # === Family 9: Liquidity-adjusted momentum (different from original) ===
    # ts_av_diff on volume instead of close — volume mean reversion
    ("R6_vol_avdiff_d5",
     "rank(ts_av_diff(volume, 20)) * rank(ts_av_diff(close, 20))",
     {**BASE_SETTINGS, "decay": 5}),

    # === Family 10: Combined: ts_av_diff close + fundamental quality ===
    ("R6_avd_roa_d5",
     "rank(ts_av_diff(close, 20)) * rank(ts_zscore(operating_income/assets, 252))",
     {**BASE_SETTINGS, "decay": 5}),

    # === Family 11: Pure short-term reversal (3-day) with SUBINDUSTRY ===
    ("R6_rev3_sub_d4",
     "-rank(ts_zscore(ts_delta(close, 3), 126))",
     {**BASE_SETTINGS, "decay": 4}),

    # === Family 12: ts_av_diff with group_rank (boost Sub) ===
    ("R6_avd_grk_d5",
     "group_rank(ts_av_diff(close, 20), subindustry) * -group_rank(ts_rank(ts_std_dev(returns, 20), 252), subindustry)",
     {**BASE_SETTINGS, "decay": 5}),

    # === Family 13: High volume + price decline reversal ===
    ("R6_hvol_rev_d5",
     "-rank(ts_zscore(ts_delta(close, 5), 252)) * rank(ts_zscore(volume/adv20, 60))",
     {**BASE_SETTINGS, "decay": 5}),

    # === Family 14: ts_av_diff with lower truncation (more concentration = higher returns) ===
    ("R6_avd_trunc05_d5",
     "rank(ts_av_diff(close, 20)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))",
     {**BASE_SETTINGS, "decay": 5, "truncation": 0.05}),

    # === Family 15: Original best but with truncation=0.05 to boost returns ===
    ("R6_avd_trunc05_d4",
     "rank(ts_av_diff(close, 20)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))",
     {**BASE_SETTINGS, "decay": 4, "truncation": 0.05}),
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
        try:
            r = s.post(f"{BASE}/simulations",
                       json={"type": "REGULAR", "settings": settings, "regular": expr},
                       timeout=60)
        except requests.exceptions.Timeout:
            print(f"  POST超时, 重试...")
            time.sleep(10)
            # Re-auth
            try:
                s.post(f"{BASE}/authentication", auth=CREDENTIALS, timeout=30)
            except:
                pass
            continue
        except Exception as e:
            print(f"  POST异常: {e}, 重试...")
            time.sleep(10)
            continue

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
            pr = s.get(location, timeout=30)
        except Exception as e:
            print(f"  GET error: {e}")
            time.sleep(10)
            # Re-auth on network errors
            try:
                s.post(f"{BASE}/authentication", auth=CREDENTIALS, timeout=30)
            except:
                pass
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
                try:
                    ar = s.get(f"{BASE}/alphas/{alpha_id}", timeout=30)
                    ad = ar.json()
                except Exception as e:
                    print(f"  获取alpha详情失败: {e}")
                    results.append({"name": name, "status": "DETAIL_FAIL", "alpha_id": alpha_id})
                    break

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
                    print(f"  Settings: decay={settings.get('decay')}, neut={settings.get('neutralization')}, trunc={settings.get('truncation')}")
            else:
                err_msg = ""
                if isinstance(data, dict):
                    for k in ["error", "message", "detail"]:
                        if k in data:
                            err_msg = str(data[k])[:200]
                            break
                print(f"  ❌ 完成但无alpha_id {err_msg}")
                results.append({"name": name, "status": "NO_ALPHA", "error": err_msg})
            break
        time.sleep(max(retry_after, 3))
    else:
        print(f"  ⏰ 超时 (5min)")
        results.append({"name": name, "status": "TIMEOUT"})

print(f"\n{'='*80}")
print("Round 6 汇总:")
for r in results:
    if r["status"] == "COMPLETE":
        tag = "🎉" if r.get("all_pass") else ""
        print(f"  {r['name']}: Sha={r['sharpe']:.2f} Fit={r['fitness']:.2f} TO={r['turnover']:.4f} Ret={r['returns']:.4f} Sub={'P' if r['sub_pass'] else 'F'}({r['sub_value']}) {tag}")
    else:
        print(f"  {r['name']}: {r['status']}")

passed = [r for r in results if r.get("all_pass")]
if passed:
    print(f"\n🎉 共 {len(passed)} 个Alpha通过所有检查!")
    for p in passed:
        print(f"  ✅ {p['name']}: alpha_id={p['alpha_id']}")
else:
    print(f"\n❌ 本轮无Alpha通过所有检查")

ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
outpath = os.path.join(OUTDIR, f"diverse_r6_{ts}.json")
with open(outpath, "w") as f:
    json.dump(results, f, indent=2, ensure_ascii=False)
print(f"\n💾 {outpath}")
