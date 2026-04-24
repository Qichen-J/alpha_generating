#!/usr/bin/env python3
"""
Round 7: Focus on strategies most likely to pass ALL THREE criteria.

Key insight from R1-R6:
- Best so far: R2_avdiff_d5 → Sha=1.34, Fit=0.86, Sub=0.58
- Fitness formula: Sha × √(|Ret| / max(TO, 0.125))
- To get Fit≥1.0 with Sha=1.34: need Ret/TO ≥ 0.56 → TO must be much lower
  OR Sha much higher
- With Sha=1.34, TO=0.19, Ret=0.079: Fit = 1.34 × √(0.079/0.19) = 1.34 × 0.645 = 0.86
- Need: 1.0 = Sha × √(Ret/TO) → if Sha=1.4, need √(Ret/TO) ≥ 0.714 → Ret/TO ≥ 0.51

Strategy for R7:
1. Use trade_when to filter bad trades → reduce TO while keeping Ret
2. Use ts_decay_exp_window for smoother signals → lower TO
3. Try group_rank instead of rank → may boost Sub-universe
4. Try additive signals for diversification
5. Use longer lookback periods for more stable signals
"""
import requests, json, time, os

CREDENTIALS = ("xxxxxx@example.com", "xxxxxx")
BASE = "https://api.worldquantbrain.com"
OUTDIR = "/Users/zhiqu/Desktop/brain/Course2/Course2_code/outputs"
os.makedirs(OUTDIR, exist_ok=True)

s = requests.Session()
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

# Best base alpha: rank(ts_av_diff(close, 20)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))
# Sha=1.34, Fit=0.86, Sub=0.58, TO=0.19, Ret=0.079 (R2_avdiff_d5)

VARIANTS = [
    # =====================================================
    # TOP PRIORITY: VWAP reversion variants
    # R6 showed: Sha=1.34, Sub=0.69 but TO=0.577 → Fit=0.44
    # Need to crush TO from 0.577 to ~0.15 while keeping Sha≥1.25
    # =====================================================

    # VWAP + high decay to reduce TO
    ("R7_vwap_d15",
     "-rank(ts_zscore((close - vwap) / close, 60)) * rank(ts_rank(volume / adv20, 60))",
     {**BASE_SETTINGS, "decay": 15}),

    ("R7_vwap_d20",
     "-rank(ts_zscore((close - vwap) / close, 60)) * rank(ts_rank(volume / adv20, 60))",
     {**BASE_SETTINGS, "decay": 20}),

    ("R7_vwap_d25",
     "-rank(ts_zscore((close - vwap) / close, 60)) * rank(ts_rank(volume / adv20, 60))",
     {**BASE_SETTINGS, "decay": 25}),

    # VWAP + trade_when vol filter
    ("R7_vwap_tw90_d10",
     "alpha = -rank(ts_zscore((close - vwap) / close, 60)) * rank(ts_rank(volume / adv20, 60));"
     "trade_when(ts_rank(ts_std_dev(returns, 10), 252) < 0.9, alpha, -1)",
     {**BASE_SETTINGS, "decay": 10}),

    ("R7_vwap_tw85_d10",
     "alpha = -rank(ts_zscore((close - vwap) / close, 60)) * rank(ts_rank(volume / adv20, 60));"
     "trade_when(ts_rank(ts_std_dev(returns, 10), 252) < 0.85, alpha, -1)",
     {**BASE_SETTINGS, "decay": 10}),

    # VWAP + ts_decay_exp_window to smooth
    ("R7_vwap_expw_d10",
     "-rank(ts_decay_exp_window(ts_zscore((close - vwap) / close, 60), 15, factor=0.5)) * rank(ts_rank(volume / adv20, 60))",
     {**BASE_SETTINGS, "decay": 10}),

    # VWAP without volume component (simpler, lower TO)
    ("R7_vwap_simple_d10",
     "-rank(ts_zscore((close - vwap) / close, 60))",
     {**BASE_SETTINGS, "decay": 10}),

    ("R7_vwap_simple_d15",
     "-rank(ts_zscore((close - vwap) / close, 60))",
     {**BASE_SETTINGS, "decay": 15}),

    # VWAP with ts_mean smoothing
    ("R7_vwap_sm3_d10",
     "-rank(ts_mean(ts_zscore((close - vwap) / close, 60), 3)) * rank(ts_rank(volume / adv20, 60))",
     {**BASE_SETTINGS, "decay": 10}),

    # VWAP with lower truncation (more concentration → higher returns)
    ("R7_vwap_trunc05_d15",
     "-rank(ts_zscore((close - vwap) / close, 60)) * rank(ts_rank(volume / adv20, 60))",
     {**BASE_SETTINGS, "decay": 15, "truncation": 0.05}),

    # =====================================================
    # SECONDARY: ts_av_diff best variants with trade_when
    # =====================================================

    ("R7_avd_tw90_d5",
     "alpha = rank(ts_av_diff(close, 20)) * -rank(ts_rank(ts_std_dev(returns, 20), 252));"
     "trade_when(ts_rank(ts_std_dev(returns, 10), 252) < 0.9, alpha, -1)",
     {**BASE_SETTINGS, "decay": 5}),

    ("R7_avd_tw90_trunc05_d5",
     "alpha = rank(ts_av_diff(close, 20)) * -rank(ts_rank(ts_std_dev(returns, 20), 252));"
     "trade_when(ts_rank(ts_std_dev(returns, 10), 252) < 0.9, alpha, -1)",
     {**BASE_SETTINGS, "decay": 5, "truncation": 0.05}),

    # ts_av_diff + ts_decay_exp_window
    ("R7_avd_expw_d5",
     "rank(ts_decay_exp_window(ts_av_diff(close, 20), 10, factor=0.5)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))",
     {**BASE_SETTINGS, "decay": 5}),

    # Additive VWAP + avdiff
    ("R7_add_vwap_avd_d10",
     "-rank(ts_zscore((close - vwap) / close, 60)) + rank(ts_av_diff(close, 20)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))",
     {**BASE_SETTINGS, "decay": 10}),

    # VWAP with INDUSTRY neutralization
    ("R7_vwap_ind_d15",
     "-rank(ts_zscore((close - vwap) / close, 60)) * rank(ts_rank(volume / adv20, 60))",
     {**BASE_SETTINGS, "decay": 15, "neutralization": "INDUSTRY"}),
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
        results.append({"name": name, "status": "FAILED_POST"})
        continue

    print(f"  Location: {location}")

    # Poll
    alpha_id = None
    t0 = time.time()
    while time.time() - t0 < 300:
        try:
            rr = s.get(location, timeout=60)
        except Exception as e:
            print(f"  GET error: {e}")
            time.sleep(30)
            # Re-auth
            try:
                s.post(f"{BASE}/authentication", auth=CREDENTIALS, timeout=30)
            except:
                pass
            continue

        ra = rr.headers.get("Retry-After", "0")
        data = rr.json()
        alpha_id = data.get("alpha")
        elapsed = int(time.time() - t0)
        print(f"  [{elapsed}s] HTTP={rr.status_code} RA={ra} alpha={alpha_id}")

        if float(ra) == 0 and alpha_id:
            break
        time.sleep(max(int(float(ra)), 5))
    else:
        results.append({"name": name, "status": "TIMEOUT"})
        print(f"  ⏰ 超时 (5min)")
        continue

    if not alpha_id:
        results.append({"name": name, "status": "NO_ALPHA"})
        continue

    # Get alpha details
    try:
        ar = s.get(f"{BASE}/alphas/{alpha_id}", timeout=60)
        ad = ar.json()
        iss = ad.get("is", {})
        sha = iss.get("sharpe", 0)
        fit = iss.get("fitness", 0)
        to_ = iss.get("turnover", 0)
        ret = iss.get("returns", 0)
        # Sub-universe check
        checks = iss.get("checks", [])
        sub_val = None
        sub_cut = None
        for ch in checks:
            if "LOW_SUB_UNIVERSE_SHARPE" in ch.get("name", ""):
                sub_val = ch.get("value")
                sub_cut = ch.get("limit")
        sha_ok = "✅" if sha >= 1.25 else "❌"
        fit_ok = "✅" if fit >= 1.0 else "❌"
        sub_ok = "✅" if sub_val and sub_cut and float(sub_val) >= float(sub_cut) else "❌"
        sub_display = sub_val if sub_val else "?"
        cut_display = sub_cut if sub_cut else "?"
        print(f"  ✅ Sha={sha}{sha_ok} Fit={fit}{fit_ok} Sub={sub_display}{sub_ok}(cut={cut_display}) TO={to_} Ret={ret} ")

        all_pass = sha >= 1.25 and fit >= 1.0
        if sub_val and sub_cut:
            all_pass = all_pass and float(sub_val) >= float(sub_cut)

        rec = {
            "name": name, "alpha_id": alpha_id, "sharpe": sha,
            "fitness": fit, "turnover": to_, "returns": ret,
            "sub_val": sub_val, "sub_cut": sub_cut, "all_pass": all_pass,
            "expr": expr,
        }
        results.append(rec)

        if all_pass:
            print(f"\n🎉🎉🎉 ALL PASS: {name} alpha_id={alpha_id} 🎉🎉🎉")
    except Exception as e:
        print(f"  获取alpha详情失败: {e}")
        results.append({"name": name, "alpha_id": alpha_id, "status": "DETAIL_ERROR"})

# Save
ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
outpath = os.path.join(OUTDIR, f"momentum_r7_{ts}.json")
with open(outpath, "w") as f:
    json.dump(results, f, indent=2)
print(f"\n📊 结果已保存: {outpath}")

# Summary
print("\n" + "="*60)
print("R7 SUMMARY")
print("="*60)
for r in results:
    if "sharpe" in r:
        sha_ok = "✅" if r["sharpe"] >= 1.25 else "❌"
        fit_ok = "✅" if r["fitness"] >= 1.0 else "❌"
        print(f"  {r['name']}: Sha={r['sharpe']}{sha_ok} Fit={r['fitness']}{fit_ok} TO={r['turnover']} Ret={r['returns']} Pass={r.get('all_pass')}")
    else:
        print(f"  {r['name']}: {r.get('status', 'UNKNOWN')}")
