#!/usr/bin/env python3
"""
option8 Alpha R8 — 彻底去掉 volume 和 ts_delta(close,5)

根本原因：
  R4-R7 所有失败的三重结构均含：
    group_rank(ts_decay_linear(volume/ts_sum(volume,252),10))
    group_rank(-ts_delta(close,5))
  这两个因子的组合是 Target5 冠军的核心，已提交 60+ 次
  → 任何包含这两个因子的 alpha 与现有提交 alpha 相关性 > 0.7

R8 策略：
  - 主信号: iv_corr = ts_corr(-IV_30, returns, 63) ← 最强单信号 Sha=1.64
  - 第 2 因子: hv_change / hv_level / skew360 / 等 option 信号
  - 第 3 因子: vwap 反转 / 日内收益反转 / 高低区间 / open gap
  - 完全不用 volume 和 ts_delta(close,N)

目标: 保持 Sha≥1.25, Fit≥1.0，同时让 SELF_CORRELATION PASS
"""
import json, os, time
import requests

CREDENTIALS = ("xxxxxx@example.com", "xxxxxx")
BASE = "https://api.worldquantbrain.com"
OUTDIR = "/Users/zhiqu/Desktop/brain/Course2/Course2_code/outputs"
os.makedirs(OUTDIR, exist_ok=True)

BASE_IND = {
    "instrumentType": "EQUITY", "region": "USA", "universe": "TOP3000",
    "delay": 1, "neutralization": "INDUSTRY",
    "truncation": 0.08, "pasteurization": "ON", "unitHandling": "VERIFY",
    "nanHandling": "ON", "language": "FASTEXPR", "visualization": False,
    "decay": 10,
}
BASE_SUB = {**BASE_IND, "neutralization": "SUBINDUSTRY"}

# ─── 1. iv_corr × hv_chg × vwap_rev ─────────────────────────────────────────
# 三个全新信号，完全不用 volume 和 close_delta
IV_CORR_HV_VWAP = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
    "hv_chg=ts_zscore(ts_delta(historical_volatility_30,5),126);"
    "vwap_rev=ts_rank(-(vwap-ts_delay(vwap,5))/ts_delay(vwap,5),63);"
    "alpha=group_rank(iv_corr,my_group)"
    "*group_rank(-hv_chg,my_group)"
    "*group_rank(vwap_rev,my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 2. iv_corr × hv_corr × intraday_rev ────────────────────────────────────
# hv_corr: realized vol 与 returns 时序相关性
# intraday_rev: 日内收益反转（close-open）
IV_CORR_HV_CORR_INTRA = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
    "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
    "intra_rev=ts_rank(-(close-open)/open,63);"
    "alpha=group_rank(iv_corr,my_group)"
    "*group_rank(hv_corr,my_group)"
    "*group_rank(intra_rev,my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 3. iv_corr × hv_chg (double only, no 3rd factor) ───────────────────────
IV_CORR_HV_DOUBLE = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
    "hv_chg=ts_zscore(ts_delta(historical_volatility_30,5),126);"
    "alpha=group_rank(iv_corr,my_group)*group_rank(-hv_chg,my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 4. iv_corr × hv_chg × range_rev (high-low spread reversal) ─────────────
# range_rev: 高低价区间反转（高振幅 → 过度情绪 → 反转）
IV_CORR_HV_RANGE = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
    "hv_chg=ts_zscore(ts_delta(historical_volatility_30,5),126);"
    "range_rev=ts_rank(-(high-low)/ts_delay(close,1),63);"
    "alpha=group_rank(iv_corr,my_group)"
    "*group_rank(-hv_chg,my_group)"
    "*group_rank(range_rev,my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 5. iv_corr × hv_chg × open_gap_rev (overnight gap reversal) ─────────────
# open_gap_rev: 隔夜跳空反转
IV_CORR_HV_GAP = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
    "hv_chg=ts_zscore(ts_delta(historical_volatility_30,5),126);"
    "gap_rev=ts_rank(-(open-ts_delay(close,1))/ts_delay(close,1),63);"
    "alpha=group_rank(iv_corr,my_group)"
    "*group_rank(-hv_chg,my_group)"
    "*group_rank(gap_rev,my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 6. iv_corr (pure single, SUBINDUSTRY) decay=7 ──────────────────────────
# 最纯粹的 option 信号
IV_CORR_PURE = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
    "group_neutralize(group_rank(iv_corr,my_group),my_group)"
)

# ─── 7. iv_corr × skew360_chg × vwap_rev ─────────────────────────────────────
IV_CORR_SKEW360_VWAP = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
    "skew360_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_360,5),126);"
    "vwap_rev=ts_rank(-(vwap-ts_delay(vwap,5))/ts_delay(vwap,5),63);"
    "alpha=group_rank(iv_corr,my_group)"
    "*group_rank(-skew360_chg,my_group)"
    "*group_rank(vwap_rev,my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 8. iv_corr × hv_level × intraday_rev ────────────────────────────────────
# hv_level: realized vol 水平（ts_rank），而非变化
IV_CORR_HVLEVEL_INTRA = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
    "hv_level=ts_rank(-historical_volatility_30,252);"
    "intra_rev=ts_rank(-(close-open)/open,63);"
    "alpha=group_rank(iv_corr,my_group)"
    "*group_rank(hv_level,my_group)"
    "*group_rank(intra_rev,my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 9. iv_corr × vrp × vwap_rev (VRP 替代 hv_chg) ──────────────────────────
IV_CORR_VRP_VWAP = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
    "vrp=ts_zscore(implied_volatility_mean_30-historical_volatility_30,126);"
    "vwap_rev=ts_rank(-(vwap-ts_delay(vwap,5))/ts_delay(vwap,5),63);"
    "alpha=group_rank(iv_corr,my_group)"
    "*group_rank(-vrp,my_group)"
    "*group_rank(vwap_rev,my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 10. hv_chg × iv_level × vwap_rev (三重，无 iv_corr) ─────────────────────
HV_CHG_IVLEVEL_VWAP = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "hv_chg=ts_zscore(ts_delta(historical_volatility_30,5),126);"
    "iv_level=ts_rank(-implied_volatility_mean_30,252);"
    "vwap_rev=ts_rank(-(vwap-ts_delay(vwap,5))/ts_delay(vwap,5),63);"
    "alpha=group_rank(-hv_chg,my_group)"
    "*group_rank(iv_level,my_group)"
    "*group_rank(vwap_rev,my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 11. iv_corr × hv_chg × vwap_rev (SUBINDUSTRY) ──────────────────────────
IV_CORR_HV_VWAP_SUB = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
    "hv_chg=ts_zscore(ts_delta(historical_volatility_30,5),126);"
    "vwap_rev=ts_rank(-(vwap-ts_delay(vwap,5))/ts_delay(vwap,5),63);"
    "alpha=group_rank(iv_corr,my_group)"
    "*group_rank(-hv_chg,my_group)"
    "*group_rank(vwap_rev,my_group);"
    "step1=group_neutralize(alpha,subindustry);"
    "group_neutralize(step1,my_group)"
)

# ─── 12. iv_corr × hv_chg × close_vwap_rev ──────────────────────────────────
# close vs vwap 偏离度（价格相对 vwap 的反转）
IV_CORR_HV_CLOSEVWAP = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
    "hv_chg=ts_zscore(ts_delta(historical_volatility_30,5),126);"
    "closevwap_rev=ts_rank(-(close-vwap)/vwap,63);"
    "alpha=group_rank(iv_corr,my_group)"
    "*group_rank(-hv_chg,my_group)"
    "*group_rank(closevwap_rev,my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 13. iv_corr_63 × iv_corr_126 (two timeframes of same signal) ────────────
# 短期和长期 IV-return 相关性的交叉
IV_CORR_DUAL = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "iv_corr_s=ts_corr(-implied_volatility_mean_30,returns,63);"
    "iv_corr_l=ts_corr(-implied_volatility_mean_30,returns,126);"
    "alpha=group_rank(iv_corr_s,my_group)*group_rank(iv_corr_l,my_group);"
    "group_neutralize(alpha,my_group)"
)

VARIANTS = [
    ("OPT8_iv_hv_vwap",        IV_CORR_HV_VWAP,        {**BASE_IND}),
    ("OPT8_iv_hvcorr_intra",   IV_CORR_HV_CORR_INTRA,  {**BASE_IND}),
    ("OPT8_iv_hv_dbl",         IV_CORR_HV_DOUBLE,       {**BASE_IND}),
    ("OPT8_iv_hv_range",       IV_CORR_HV_RANGE,        {**BASE_IND}),
    ("OPT8_iv_hv_gap",         IV_CORR_HV_GAP,          {**BASE_IND}),
    ("OPT8_iv_corr_pure",      IV_CORR_PURE,            {**BASE_SUB, "decay": 7}),
    ("OPT8_iv_skew360_vwap",   IV_CORR_SKEW360_VWAP,   {**BASE_IND}),
    ("OPT8_iv_hvlevel_intra",  IV_CORR_HVLEVEL_INTRA,  {**BASE_IND}),
    ("OPT8_iv_vrp_vwap",       IV_CORR_VRP_VWAP,       {**BASE_IND}),
    ("OPT8_hv_ivlevel_vwap",   HV_CHG_IVLEVEL_VWAP,    {**BASE_IND}),
    ("OPT8_iv_hv_vwap_sub",    IV_CORR_HV_VWAP_SUB,    {**BASE_IND}),
    ("OPT8_iv_hv_closevwap",   IV_CORR_HV_CLOSEVWAP,   {**BASE_IND}),
    ("OPT8_iv_corr_dual",      IV_CORR_DUAL,            {**BASE_IND, "decay": 7}),
]


def authenticate(session):
    r = session.post(f"{BASE}/authentication", auth=CREDENTIALS, timeout=30)
    r.raise_for_status()
    print("✅ 认证成功")


def submit(session, expr, settings):
    for attempt in range(10):
        try:
            r = session.post(f"{BASE}/simulations",
                             json={"type": "REGULAR", "settings": settings, "regular": expr}, timeout=60)
        except requests.exceptions.Timeout:
            time.sleep(10); authenticate(session); continue
        except Exception as e:
            print(f"  POST异常: {e}"); time.sleep(15); continue
        ra = r.headers.get("Retry-After", "?")
        print(f"  POST: {r.status_code} RA={ra}")
        if r.status_code == 429:
            wait = int(float(ra)) + 5 if ra != "?" else 35
            time.sleep(wait); continue
        if r.status_code >= 400:
            print(f"  错误: {r.status_code} {r.text[:200]}"); return None
        loc = r.headers.get("Location")
        print(f"  Location: {loc}")
        return loc
    return None


def poll(session, loc, name):
    start = time.time()
    while True:
        elapsed = int(time.time() - start)
        try:
            resp = session.get(loc, timeout=45)
            if resp.status_code == 401:
                authenticate(session); continue
            data = resp.json()
        except Exception as e:
            print(f"  [{elapsed:3d}s] GET error: {e}")
            time.sleep(30); continue

        status = data.get("status", "")
        alpha_id = data.get("alpha")
        msg = data.get("message", "") or ""
        print(f"  [{elapsed:3d}s] status='{status}' alpha={alpha_id} msg={msg[:60]}")

        if status == "COMPLETE" and alpha_id:
            return alpha_id
        if status in ("ERROR", "FAILED") or (msg and "error" in msg.lower()):
            print(f"  ❌ 失败: {msg}"); return None
        time.sleep(15)


def fetch_alpha(session, alpha_id):
    r = session.get(f"{BASE}/alphas/{alpha_id}", timeout=30)
    return r.json()


def check_summary(alpha_data):
    is_data = alpha_data.get("is") or {}
    checks = is_data.get("checks", [])
    sha = is_data.get("sharpe", "?")
    fit = is_data.get("fitness", "?")
    to = is_data.get("turnover", "?")
    ret = is_data.get("returns", "?")
    parts = []
    for c in checks:
        n = c.get("name", "?")
        result = c.get("result", "?")
        val = c.get("value", "")
        icon = "✅" if result == "PASS" else "❌"
        parts.append(f"{n}={icon}{val}")
    return sha, fit, to, ret, " | ".join(parts)


def main():
    session = requests.Session()
    authenticate(session)

    results = []
    sep = "=" * 60

    for idx, (name, expr, settings) in enumerate(VARIANTS, 1):
        print(f"\n{sep}")
        neut = settings.get("neutralization")
        decay = settings.get("decay")
        print(f"▶ [{idx}/{len(VARIANTS)}] {name}  decay={decay} neut={neut}")
        loc = submit(session, expr, settings)
        if not loc:
            print(f"  ⚠️ 跳过 {name}")
            results.append({"name": name, "error": "submit_failed"})
            continue

        alpha_id = poll(session, loc, name)
        if not alpha_id:
            results.append({"name": name, "error": "sim_failed"})
            continue

        print(f"  ✅ alpha_id={alpha_id}")
        alpha_data = fetch_alpha(session, alpha_id)
        sha, fit, to, ret, checks_str = check_summary(alpha_data)
        print(f"  Sha={sha} Fit={fit} TO={to} Ret={ret}")
        print(f"  Checks: {checks_str}")

        is_data = alpha_data.get("is") or {}
        all_checks = is_data.get("checks", [])
        all_pass = all(c.get("result") == "PASS" for c in all_checks) if all_checks else False
        if all_pass:
            print(f"  🎉🎉🎉 ALL PASS！{name} alpha_id={alpha_id}")

        results.append({
            "name": name, "alpha_id": alpha_id,
            "sharpe": sha, "fitness": fit, "turnover": to, "returns": ret,
            "all_pass": all_pass, "checks": checks_str
        })

    print(f"\n{sep}")
    print("📊 R8 最终结果汇总")
    sorted_r = sorted(results, key=lambda x: float(x.get("sharpe", -99) or -99), reverse=True)
    all_pass_list = [x for x in sorted_r if x.get("all_pass")]
    if all_pass_list:
        print(f"🏆 找到 {len(all_pass_list)} 个 ALL PASS！")
        for x in all_pass_list:
            print(f"  ★ {x['name']}: Sha={x['sharpe']} Fit={x['fitness']} TO={x['turnover']} id={x['alpha_id']}")
    for x in sorted_r:
        sc = x.get('checks','')
        sc_pass = sc.count('✅') if sc else 0
        sc_total = sc.count('✅') + sc.count('❌') if sc else 0
        print(f"  {x.get('name','?')}: Sha={x.get('sharpe','?')} Fit={x.get('fitness','?')} TO={x.get('turnover','?')} [{sc_pass}/{sc_total}] id={x.get('alpha_id','?')}")

    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    outfile = os.path.join(OUTDIR, f"opt8_r8_final_{ts}.json")
    with open(outfile, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n结果已保存: {outfile}")

    if all_pass_list:
        print(f"\n{'='*60}")
        print(f"🎉 ALL PASS alpha！可以提交：")
        for x in all_pass_list:
            print(f"  {x['name']} (id={x['alpha_id']}) Sha={x['sharpe']}")


if __name__ == "__main__":
    main()
