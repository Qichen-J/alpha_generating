#!/usr/bin/env python3
"""
option8 Alpha R5 — 专攻双 group_rank 结构的 Fitness 提升
R3 关键发现：
  XgYMlqz5 (skew_dblgrp_d7): Sha=1.48, Fit=0.82, TO=0.35 — 只差 Fitness
  pw13EOqV  (skew_dblgrp_d10): Sha=1.44, Fit=0.89, TO=0.29 — 只差 Fitness

目标：Fitness 从 0.89 → ≥ 1.0 (只需提升 12%)
策略：
  Fitness ≈ Returns / TurnoverCost
  - 提升 returns：加入 volume turnover 信号（Target5 冠军的核心因子）
  - 三重 group_rank（如 Target5：vol_decay × price_rev × option_skew）
  - 换 subindustry 中性化（更精细，可能提升 returns 稳定性）
  - ts_mean 平滑最终 alpha（降低 TO 进一步提升 Fitness）
  - 延长价格反转窗口（10d, 20d 代替 5d）
  - 更大 decay（12, 14）用于双 group_rank 结构

底层表达式基础（R3 冠军）：
  my_group=bucket(rank(cap),range='0,1,0.1');
  skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);
  alpha=group_rank(-skew_chg,my_group)*group_rank(-ts_delta(close,5),my_group);
  group_neutralize(alpha,my_group)
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

# ─── 信号1: 三重 group_rank = skew × vol_decay × price_rev (Target5冠军结构扩展) ─
# Target5 冠军: rank(vol_decay * price_rev) → Sha=1.76, Fit=1.19
# 这里加入 skew 作为第三因子
SKEW_TRIPLE = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "alpha=group_rank(-skew_chg,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号2: 双 group_rank + ts_mean 平滑（降低 TO） ─────────────────────────
DBLGRP_SMOOTH3 = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "alpha=group_rank(-skew_chg,my_group)*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(ts_mean(alpha,3),my_group)"
)

# ─── 信号3: 双 group_rank + ts_mean 5天平滑 ────────────────────────────────
DBLGRP_SMOOTH5 = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "alpha=group_rank(-skew_chg,my_group)*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(ts_mean(alpha,5),my_group)"
)

# ─── 信号4: 双 group_rank + subindustry 中性化 ──────────────────────────────
DBLGRP_SUBIND = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "alpha=group_rank(-skew_chg,my_group)*group_rank(-ts_delta(close,5),my_group);"
    "step1=group_neutralize(alpha,subindustry);"
    "group_neutralize(step1,my_group)"
)

# ─── 信号5: 双 group_rank，价格反转用 10d ─────────────────────────────────
DBLGRP_PRET10 = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "alpha=group_rank(-skew_chg,my_group)*group_rank(-ts_delta(close,10),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号6: 双 group_rank，价格反转用 20d ─────────────────────────────────
DBLGRP_PRET20 = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "alpha=group_rank(-skew_chg,my_group)*group_rank(-ts_delta(close,20),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号7: 双 group_rank，decay=12 ──────────────────────────────────────
DBLGRP_D12 = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "alpha=group_rank(-skew_chg,my_group)*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号8: 三重 group_rank + decay=7 ────────────────────────────────────
TRIPLE_D7 = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "alpha=group_rank(-skew_chg,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号9: 双 group_rank，skew delta 用 10d 窗口（更平滑的 skew 变化） ─────
DBLGRP_SKEW10 = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,10),126);"
    "alpha=group_rank(-skew_chg,my_group)*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号10: 双 group_rank + 市值 ×sector 双层中性化 ─────────────────────
DBLGRP_SECTOR = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "alpha=group_rank(-skew_chg,my_group)*group_rank(-ts_delta(close,5),my_group);"
    "step1=group_neutralize(alpha,sector);"
    "group_neutralize(step1,my_group)"
)

# ─── 信号11: 三重 group_rank，加 parkinson vol 替代 volume ─────────────────
# parkinson_volatility 衡量日内价格区间，低 parkinson_vol + skew_shock = 超卖
TRIPLE_PARK = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "park_rev=ts_rank(-parkinson_volatility_30,63);"
    "alpha=group_rank(-skew_chg,my_group)"
    "*group_rank(park_rev,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号12: 双 group_rank + rank(alpha) 最外层 ──────────────────────────
# 类似 Target5 冠军用 rank() 包裹整个乘积
DBLGRP_RANKED = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "raw=group_rank(-skew_chg,my_group)*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(rank(raw),my_group)"
)

# ─── 信号13: 双 group_rank，zscore 252d 替换 126d ────────────────────────
DBLGRP_Z252 = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),252);"
    "alpha=group_rank(-skew_chg,my_group)*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

VARIANTS = [
    ("OPT8_triple_d10",        SKEW_TRIPLE,      {**BASE_SETTINGS}),
    ("OPT8_dblgrp_smooth3",    DBLGRP_SMOOTH3,   {**BASE_SETTINGS}),
    ("OPT8_dblgrp_smooth5",    DBLGRP_SMOOTH5,   {**BASE_SETTINGS}),
    ("OPT8_dblgrp_subind_d10", DBLGRP_SUBIND,    {**BASE_SETTINGS}),
    ("OPT8_dblgrp_pret10_d10", DBLGRP_PRET10,    {**BASE_SETTINGS}),
    ("OPT8_dblgrp_pret20_d10", DBLGRP_PRET20,    {**BASE_SETTINGS}),
    ("OPT8_dblgrp_d12",        DBLGRP_D12,       {**BASE_SETTINGS, "decay": 12}),
    ("OPT8_triple_d7",         TRIPLE_D7,        {**BASE_SETTINGS, "decay": 7}),
    ("OPT8_dblgrp_skew10_d10", DBLGRP_SKEW10,    {**BASE_SETTINGS}),
    ("OPT8_dblgrp_sector_d10", DBLGRP_SECTOR,    {**BASE_SETTINGS}),
    ("OPT8_triple_park_d10",   TRIPLE_PARK,      {**BASE_SETTINGS}),
    ("OPT8_dblgrp_ranked_d10", DBLGRP_RANKED,    {**BASE_SETTINGS}),
    ("OPT8_dblgrp_z252_d10",   DBLGRP_Z252,      {**BASE_SETTINGS}),
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


def poll(session, location):
    start = time.time()
    while time.time() - start < 720:
        try:
            r = session.get(location, timeout=45)
        except Exception as e:
            print(f"  GET error: {e}"); time.sleep(20); continue
        if r.status_code == 429:
            wait = int(float(r.headers.get("Retry-After", 30))) + 5
            time.sleep(wait); continue
        try:
            data = r.json()
        except Exception:
            data = {}
        if not isinstance(data, dict):
            time.sleep(10); continue
        raw = data.get("alpha")
        status = data.get("status", "")
        alpha_id = raw.get("id") if isinstance(raw, dict) else raw
        msg = str(data.get("message", ""))[:80]
        elapsed = int(time.time() - start)
        print(f"  [{elapsed:3d}s] status={status!r} alpha={alpha_id} msg={msg}")
        if alpha_id or status in ("ERROR", "FAILED", "COMPLETE", "DONE"):
            return data
        time.sleep(15)
    return {}


def get_stats(session, alpha_id):
    for _ in range(3):
        try:
            r = session.get(f"{BASE}/alphas/{alpha_id}", timeout=30)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(5)
    return {}


def main():
    session = requests.Session()
    authenticate(session)

    results = []
    all_pass = []

    for idx, (name, expr, settings) in enumerate(VARIANTS, 1):
        print(f"\n{'='*60}")
        print(f"▶ [{idx}/{len(VARIANTS)}] {name}  decay={settings.get('decay')} neut={settings.get('neutralization')}")

        loc = submit(session, expr, settings)
        if not loc:
            print("  ❌ 提交失败"); results.append({"name": name, "error": "submit_failed"}); continue

        data = poll(session, loc)
        raw = data.get("alpha")
        alpha_id = raw.get("id") if isinstance(raw, dict) else raw

        if not alpha_id:
            print(f"  ❌ 无 alpha_id，status={data.get('status')} msg={data.get('message','')[:100]}")
            results.append({"name": name, "error": "no_result", "data": data}); continue

        info = get_stats(session, alpha_id)
        is_data = info.get("is", {}) or {}
        sha = is_data.get("sharpe", "?")
        fit = is_data.get("fitness", "?")
        to  = is_data.get("turnover", "?")
        ret = is_data.get("returns", "?")
        checks = is_data.get("checks", [])

        passed = all(c.get("result") == "PASS" for c in checks) if checks else False
        check_str = " | ".join(f"{c['name']}={'✅' if c.get('result')=='PASS' else '❌'}{c.get('value','')}" for c in checks)

        print(f"  ✅ alpha_id={alpha_id}")
        print(f"  Sha={sha} Fit={fit} TO={to} Ret={ret}")
        print(f"  Checks: {check_str}")
        if passed:
            print(f"  🎉🎉🎉 ALL PASS: {name} → {alpha_id}")
            all_pass.append({"name": name, "id": alpha_id, "sharpe": sha, "fitness": fit})

        results.append({
            "name": name, "id": alpha_id,
            "sharpe": sha, "fitness": fit, "turnover": to, "returns": ret,
            "all_pass": passed, "checks": checks,
        })

        ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        with open(f"{OUTDIR}/opt8_r5_{ts}.json", "w") as f:
            json.dump({"results": results, "all_pass": all_pass}, f, indent=2)

    print("\n" + "="*60)
    print("📊 R5 最终结果汇总")
    results_sorted = sorted(
        [r for r in results if "error" not in r],
        key=lambda x: float(x.get("sharpe", -99) or -99), reverse=True
    )
    for r in results_sorted:
        flag = "🎉" if r.get("all_pass") else "  "
        print(f"  {flag} {r['name']}: Sha={r['sharpe']} Fit={r['fitness']} TO={r['turnover']} id={r['id']}")

    if all_pass:
        print(f"\n🏆 找到 {len(all_pass)} 个 ALL PASS！")
        for a in all_pass:
            print(f"  {a['id']}: {a['name']} Sha={a['sharpe']} Fit={a['fitness']}")
    else:
        print("\n⚠️ R5 无 ALL PASS，需进一步分析")

    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    final_path = f"{OUTDIR}/opt8_r5_final_{ts}.json"
    with open(final_path, "w") as f:
        json.dump({"results": results, "all_pass": all_pass}, f, indent=2)
    print(f"\n结果已保存: {final_path}")


if __name__ == "__main__":
    main()
