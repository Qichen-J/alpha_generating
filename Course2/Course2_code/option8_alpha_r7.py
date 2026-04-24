#!/usr/bin/env python3
"""
option8 Alpha R7 — 完全放弃 skew_chg，攻克 SELF_CORRELATION

根本原因分析：
  R2-R6 共提交 ~60 个含 implied_volatility_mean_skew_30/60/90 ts_delta 的 alpha
  → 这些 alpha 形成密集相关性簇，任何新变体都超过 0.7 阈值
  → SELF_CORRELATION 是与所有已提交 alpha 比较，不限于 ALL PASS 的

R7 策略：完全不同的 option 信号方向
  1. VRP (IV - HV): 方差风险溢价，经济逻辑完全不同
     - implied_volatility_mean_30 - historical_volatility_30
  2. Put/Call IV 直接字段（非 skew）: implied_volatility_put_30, implied_volatility_call_30
     - R6 triple_pcdiff 确认这两个字段有效（Sha=1.23，虽然还用了 skew_chg）
  3. HV change: ts_delta(historical_volatility_30,5) — realized vol，非 implied
  4. 长期 IV skew（360/720d）: 与 30/60/90 相关性低
  5. ts_corr 结构: ts_corr(IV_signal, returns, N)
  6. SUBINDUSTRY 设置（API 级别）: 改变组合结构
  7. 完全不同的价格信号: overnight return, vwap reversal

所有变体不使用 implied_volatility_mean_skew_{30/60/90} 的 ts_delta！
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

# ─── 1. VRP triple (INDUSTRY) ────────────────────────────────────────────────
# 方差风险溢价: IV > HV → 期权过贵 → 短期内卖方获利 → 做多低 VRP 股票
# buy: low IV relative to HV (cheap options → price suppressed → reversal)
VRP_TRIPLE = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "vrp=ts_zscore(implied_volatility_mean_30-historical_volatility_30,126);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "alpha=group_rank(-vrp,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 2. VRP triple (SUBINDUSTRY setting) ─────────────────────────────────────
VRP_TRIPLE_SUB = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "vrp=ts_zscore(implied_volatility_mean_30-historical_volatility_30,126);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "alpha=group_rank(-vrp,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 3. Put IV change triple ──────────────────────────────────────────────────
# implied_volatility_put_30: 纯 put 期权 IV，与 mean_skew 信号完全不同
PUT_IV_TRIPLE = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "put_chg=ts_zscore(ts_delta(implied_volatility_put_30,5),126);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "alpha=group_rank(-put_chg,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 4. Call IV change triple ─────────────────────────────────────────────────
# implied_volatility_call_30: 纯 call 期权 IV，与 put 信号方向不同
CALL_IV_TRIPLE = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "call_chg=ts_zscore(ts_delta(implied_volatility_call_30,5),126);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "alpha=group_rank(-call_chg,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 5. HV change triple ──────────────────────────────────────────────────────
# historical_volatility_30 change: realized vol 变化，非 implied
# 当 HV 上升（刚经历高波动期）→ 股票可能超卖 → 做多
HV_TRIPLE = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "hv_chg=ts_zscore(ts_delta(historical_volatility_30,5),126);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "alpha=group_rank(-hv_chg,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 6. Long-term skew change (360d) ─────────────────────────────────────────
# implied_volatility_mean_skew_360: 与 30/60/90 相关性低，结构性 skew 信号
SKEW360_TRIPLE = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew360_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_360,5),126);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "alpha=group_rank(-skew360_chg,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 7. Long-term skew change (720d) ─────────────────────────────────────────
SKEW720_TRIPLE = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew720_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_720,5),126);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "alpha=group_rank(-skew720_chg,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 8. Put IV level × vol × price_rev ───────────────────────────────────────
# 用 put IV 水平（非变化）作为主因子
# 高 put IV → 市场恐慌 → 做多（逆向）
PUT_LEVEL_TRIPLE = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "put_level=ts_rank(-implied_volatility_put_30,252);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "alpha=group_rank(put_level,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 9. VRP × put_iv_level × price_rev ───────────────────────────────────────
# 三重纯 option 信号，不用 volume（彻底不同于 Target5 结构）
VRP_PUT_TRIPLE = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "vrp=ts_zscore(implied_volatility_mean_30-historical_volatility_30,126);"
    "put_level=ts_rank(-implied_volatility_put_30,252);"
    "alpha=group_rank(-vrp,my_group)"
    "*group_rank(put_level,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 10. Overnight return signal ──────────────────────────────────────────────
# 用隔夜收益（开盘/昨收）替代日内价格变化
# 与 ts_delta(close,5) 使用的信息不同
OVN_TRIPLE = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "vrp=ts_zscore(implied_volatility_mean_30-historical_volatility_30,126);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "ovn_rev=ts_rank(-ts_mean((open-ts_delay(close,1))/ts_delay(close,1),5),63);"
    "alpha=group_rank(-vrp,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(ovn_rev,my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 11. ts_corr based signal ────────────────────────────────────────────────
# ts_corr(IV, returns, 63): 时序相关性，完全不同的数学结构
# 买入那些"高 IV 时期收益好"的股票
IV_CORR_TRIPLE = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "alpha=group_rank(iv_corr,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 12. Pure VRP level triple (no volume, no price_rev) ─────────────────────
# 三重纯 option 信号，平滑后降低 TO
PURE_VRP = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "vrp=ts_rank(implied_volatility_mean_30-historical_volatility_30,252);"
    "put_lev=ts_rank(-implied_volatility_put_30,252);"
    "call_lev=ts_rank(-implied_volatility_call_30,252);"
    "alpha=group_rank(-vrp,my_group)*group_rank(put_lev,my_group)*group_rank(call_lev,my_group);"
    "group_neutralize(ts_mean(alpha,5),my_group)"
)

# ─── 13. VRP + put_chg + price_rev (three completely new signals) ─────────────
# 同时用 VRP 和 put IV 变化（两个不同的 option 维度）+ 价格反转
VRP_PUTCHG = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "vrp=ts_zscore(implied_volatility_mean_30-historical_volatility_30,63);"
    "put_chg=ts_zscore(ts_delta(implied_volatility_put_30,5),126);"
    "alpha=group_rank(-vrp,my_group)"
    "*group_rank(-put_chg,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

VARIANTS = [
    ("OPT8_vrp_triple_ind",    VRP_TRIPLE,       {**BASE_IND}),
    ("OPT8_vrp_triple_sub",    VRP_TRIPLE_SUB,   {**BASE_SUB}),
    ("OPT8_put_iv_triple",     PUT_IV_TRIPLE,    {**BASE_IND}),
    ("OPT8_call_iv_triple",    CALL_IV_TRIPLE,   {**BASE_IND}),
    ("OPT8_hv_triple",         HV_TRIPLE,        {**BASE_IND}),
    ("OPT8_skew360_triple",    SKEW360_TRIPLE,   {**BASE_IND}),
    ("OPT8_skew720_triple",    SKEW720_TRIPLE,   {**BASE_IND}),
    ("OPT8_put_level_triple",  PUT_LEVEL_TRIPLE, {**BASE_IND}),
    ("OPT8_vrp_put_triple",    VRP_PUT_TRIPLE,   {**BASE_IND}),
    ("OPT8_ovn_triple",        OVN_TRIPLE,       {**BASE_IND}),
    ("OPT8_iv_corr_triple",    IV_CORR_TRIPLE,   {**BASE_IND}),
    ("OPT8_pure_vrp",          PURE_VRP,         {**BASE_IND, "decay": 7}),
    ("OPT8_vrp_putchg",        VRP_PUTCHG,       {**BASE_IND}),
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
        name = c.get("name", "?")
        result = c.get("result", "?")
        val = c.get("value", "")
        icon = "✅" if result == "PASS" else "❌"
        parts.append(f"{name}={icon}{val}")
    return sha, fit, to, ret, " | ".join(parts)


def main():
    session = requests.Session()
    authenticate(session)

    results = []
    sep = "=" * 60

    for idx, (name, expr, settings) in enumerate(VARIANTS, 1):
        print(f"\n{sep}")
        neut = settings.get("neutralization")
        print(f"▶ [{idx}/{len(VARIANTS)}] {name}  decay={settings.get('decay')} neut={neut}")
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
    print("📊 R7 最终结果汇总")
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
    outfile = os.path.join(OUTDIR, f"opt8_r7_final_{ts}.json")
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
