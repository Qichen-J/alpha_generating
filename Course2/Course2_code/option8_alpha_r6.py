#!/usr/bin/env python3
"""
option8 Alpha R6 — 专攻 SELF_CORRELATION 修复

R4 关键发现：
  leR1RgPx (OPT8_skew_triple_d10): Sha=1.54, Fit=1.07, TO=0.22
  7/8 PASS，唯一失败：SELF_CORRELATION

SELF_CORRELATION 原因分析：
  三重结构 group_rank(skew) × group_rank(vol) × group_rank(price_rev)
  其中 vol × price_rev 与 Target5 已提交 alpha 高度相关
  → 需要从信号域上区分，减少 price reversal 依赖，增加纯 option 信号

R6 策略：
  1. 用不同 IV 窗口（skew_60, skew_90 vs skew_30）
  2. 用 put/call skew 差值（完全不同的 option 信号）
  3. 用 IV term structure（短期/长期 IV 比值）
  4. 用 historical_volatility 替代 volume（完全不同的 3rd factor）
  5. 用 SUBINDUSTRY 中性化（更精细的 cross-section）
  6. 调整 cap group range（'0.2,1,0.2' 而非 '0,1,0.1'）
  7. 纯 option 信号（去掉 price_rev，只用 IV 信号乘积）

目标：保持 Sha≥1.25, Fit≥1.0，同时让 SELF_CORRELATION PASS
"""
import json, os, time
import requests

CREDENTIALS = ("xxxxxx@example.com", "xxxxxx")
BASE = "https://api.worldquantbrain.com"
OUTDIR = "/Users/zhiqu/Desktop/brain/Course2/Course2_code/outputs"
os.makedirs(OUTDIR, exist_ok=True)

BASE_SETTINGS = {
    "instrumentType": "EQUITY", "region": "USA", "universe": "TOP3000",
    "delay": 1, "neutralization": "INDUSTRY",
    "truncation": 0.08, "pasteurization": "ON", "unitHandling": "VERIFY",
    "nanHandling": "ON", "language": "FASTEXPR", "visualization": False,
    "decay": 10,
}

# ─── 信号1: IV skew_60 替代 skew_30（更长期的 skew 信号） ─────────────────
# skew_60 与 skew_30 相关性约 0.7，但累积持仓不同
TRIPLE_SKEW60 = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_60,5),126);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "alpha=group_rank(-skew_chg,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号2: IV put skew 替代 mean skew（完全不同的 put-side 信号） ──────────
TRIPLE_PUTSKEW = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_put_skew_30,5),126);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "alpha=group_rank(-skew_chg,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号3: call skew 替代 mean skew ──────────────────────────────────────
TRIPLE_CALLSKEW = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_call_skew_30,5),126);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "alpha=group_rank(-skew_chg,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号4: historical_volatility_30 替代 volume（纯 option 三重信号） ──────
# 用历史波动率替代成交量，与 Target5 结构彻底不同
TRIPLE_HV = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "hv_rev=ts_rank(-historical_volatility_30,126);"
    "alpha=group_rank(-skew_chg,my_group)"
    "*group_rank(hv_rev,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号5: IV term structure（短期/长期 IV 比） × skew × price ─────────────
# IV term structure = IV_30/IV_360，衡量期限溢价，完全不同于 skew30
TRIPLE_TERM = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "term_struct=ts_zscore(implied_volatility_mean_30/implied_volatility_mean_360,63);"
    "alpha=group_rank(-skew_chg,my_group)"
    "*group_rank(-term_struct,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号6: put/call IV 差值（put fear vs call greed 信号） ──────────────────
TRIPLE_PCDIFF = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "pc_diff=ts_zscore(implied_volatility_put_30-implied_volatility_call_30,63);"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "alpha=group_rank(-pc_diff,my_group)"
    "*group_rank(-skew_chg,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号7: IV skew mean-reversion（zscore 用252d 看更长期反转） ─────────────
TRIPLE_LONGZ = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),252);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "alpha=group_rank(-skew_chg,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号8: SUBINDUSTRY 外层中性化（更精细分组） ───────────────────────────
TRIPLE_SUBIND = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "alpha=group_rank(-skew_chg,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "step1=group_neutralize(alpha,subindustry);"
    "group_neutralize(step1,my_group)"
)

# ─── 信号9: cap group 范围改为 '0.2,1,0.2'（更粗的分组，不同于现有）──────────
TRIPLE_CAP5 = (
    "my_group=bucket(rank(cap),range='0.2,1,0.2');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "alpha=group_rank(-skew_chg,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号10: parkinson_vol_10/parkinson_vol_90 term structure ──────────────
# 短期/长期日内波动比，捕捉不同于 IV 的 realized vol 期限结构
TRIPLE_PARK_TERM = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "park_term=ts_zscore(parkinson_volatility_10/parkinson_volatility_90,63);"
    "alpha=group_rank(-skew_chg,my_group)"
    "*group_rank(-park_term,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号11: IV skew 90d（最长期限 skew 信号） ─────────────────────────────
TRIPLE_SKEW90 = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_90,5),126);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "alpha=group_rank(-skew_chg,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号12: 双 group_rank 纯 option（无 price reversal） ────────────────────
# 去掉 price_rev 完全依赖 IV 信号，与 Target5 结构彻底不同
DBLOPT_NORET = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "iv_level=ts_rank(-ts_mean(implied_volatility_mean_30,5),126);"
    "alpha=group_rank(-skew_chg,my_group)"
    "*group_rank(iv_level,my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号13: triple + skew 30/60 term（用 skew 期限利差替代 vol） ─────────────
TRIPLE_SKEWTERM = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "skew_term=ts_zscore(implied_volatility_mean_skew_30-implied_volatility_mean_skew_90,63);"
    "alpha=group_rank(-skew_chg,my_group)"
    "*group_rank(-skew_term,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

VARIANTS = [
    ("OPT8_triple_skew60",     TRIPLE_SKEW60,    {**BASE_SETTINGS}),
    ("OPT8_triple_putskew",    TRIPLE_PUTSKEW,   {**BASE_SETTINGS}),
    ("OPT8_triple_callskew",   TRIPLE_CALLSKEW,  {**BASE_SETTINGS}),
    ("OPT8_triple_hv",         TRIPLE_HV,        {**BASE_SETTINGS}),
    ("OPT8_triple_term",       TRIPLE_TERM,      {**BASE_SETTINGS}),
    ("OPT8_triple_pcdiff",     TRIPLE_PCDIFF,    {**BASE_SETTINGS}),
    ("OPT8_triple_longz",      TRIPLE_LONGZ,     {**BASE_SETTINGS}),
    ("OPT8_triple_subind",     TRIPLE_SUBIND,    {**BASE_SETTINGS}),
    ("OPT8_triple_cap5",       TRIPLE_CAP5,      {**BASE_SETTINGS}),
    ("OPT8_triple_park_term",  TRIPLE_PARK_TERM, {**BASE_SETTINGS}),
    ("OPT8_triple_skew90",     TRIPLE_SKEW90,    {**BASE_SETTINGS}),
    ("OPT8_dblopt_noret",      DBLOPT_NORET,     {**BASE_SETTINGS}),
    ("OPT8_triple_skewterm",   TRIPLE_SKEWTERM,  {**BASE_SETTINGS}),
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
                authenticate(session)
                continue
            data = resp.json()
        except Exception as e:
            print(f"  [{elapsed:3d}s] GET error: {e}")
            time.sleep(30)
            continue

        status = data.get("status", "")
        alpha_id = data.get("alpha")
        msg = data.get("message", "") or ""
        print(f"  [{elapsed:3d}s] status='{status}' alpha={alpha_id} msg={msg[:60]}")

        if status == "COMPLETE" and alpha_id:
            return alpha_id
        if status in ("ERROR", "FAILED") or (msg and "error" in msg.lower()):
            print(f"  ❌ 失败: {msg}")
            return None
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
        print(f"▶ [{idx}/{len(VARIANTS)}] {name}  decay={settings.get('decay')} neut={settings.get('neutralization')}")
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
    print("📊 R6 最终结果汇总")
    sorted_r = sorted(results, key=lambda x: float(x.get("sharpe", -99) or -99), reverse=True)
    all_pass_list = [x for x in sorted_r if x.get("all_pass")]
    if all_pass_list:
        print(f"🏆 找到 {len(all_pass_list)} 个 ALL PASS！")
        for x in all_pass_list:
            print(f"  ★ {x['name']}: Sha={x['sharpe']} Fit={x['fitness']} TO={x['turnover']} id={x['alpha_id']}")
    for x in sorted_r:
        print(f"  {x.get('name','?')}: Sha={x.get('sharpe','?')} Fit={x.get('fitness','?')} TO={x.get('turnover','?')} id={x.get('alpha_id','?')}")

    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    outfile = os.path.join(OUTDIR, f"opt8_r6_final_{ts}.json")
    with open(outfile, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n结果已保存: {outfile}")

    if all_pass_list:
        print(f"\n{'='*60}")
        print(f"🎉 ALL PASS alpha 找到！可以提交：")
        for x in all_pass_list:
            print(f"  {x['name']} (id={x['alpha_id']}) Sha={x['sharpe']}")


if __name__ == "__main__":
    main()
