#!/usr/bin/env python3
"""
option8 Alpha R4 — 修复 Fitness 不足的问题
R3 发现：OPT8_skew_pret_d10 (Sha=1.21, Fit=0.5, TO=0.49) 是最强信号
核心问题：Fit=0.5 远低于阈值1.0，根源是 TO=49% 太高（returns/TO 效率低）

R4 策略：降低换手率 + 强化 returns
  1. 加大 decay (15/20) — 平滑持仓，降低 TO
  2. ts_mean 平滑信号 — 进一步降 TO
  3. 用 ts_rank 代替 rank — 基于历史分位，更稳定的信号
  4. 结合 adv20 filter — 只做流动性好的股票（精选持仓）
  5. 调整 zscore 窗口 — 126d (半年) 更合适
  6. 双 group_rank + 价格反转 — 模仿 Target5 的最强结构
  7. 增加 subindustry 中性化 — 减少行业暴露提升 sub-sharpe
  8. 用 ts_rank(signal, 60) 替代 rank — 更平滑
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

# ─── R3最强信号基线（供参考）──────────────────────────────────────────────
# OPT8_skew_pret_d10: Sha=1.21 Fit=0.50 TO=0.49  Sub=0.76
# my_group=bucket(rank(cap),range='0.1,1,0.1');
# skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),252);
# pret=rank(-ts_delta(close,5));
# raw=rank(-skew_chg)*pret;
# group_neutralize(raw,my_group)

# ─── 信号1: skew_pret，decay=15 (提高 fitness，降低 TO) ──────────────────
SKEW_PRET_D15 = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),252);"
    "pret=rank(-ts_delta(close,5));"
    "raw=rank(-skew_chg)*pret;"
    "group_neutralize(raw,my_group)"
)

# ─── 信号2: skew_pret，decay=20 ───────────────────────────────────────────
SKEW_PRET_D20 = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),252);"
    "pret=rank(-ts_delta(close,5));"
    "raw=rank(-skew_chg)*pret;"
    "group_neutralize(raw,my_group)"
)

# ─── 信号3: ts_mean 平滑，decay=10 ───────────────────────────────────────
# ts_mean(signal, 5) 减少噪声和换手
SKEW_PRET_SMOOTH = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),252);"
    "pret=rank(-ts_delta(close,5));"
    "raw=ts_mean(rank(-skew_chg)*pret,3);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号4: ts_rank 代替 rank (更平稳的截面信号) ─────────────────────────
SKEW_PRET_TSRANK = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_rank(ts_delta(implied_volatility_mean_skew_30,5),63);"
    "pret=ts_rank(-ts_delta(close,5),63);"
    "raw=ts_mean(skew_chg*pret,5);"
    "group_neutralize(-raw,my_group)"
)

# ─── 信号5: zscore窗口缩短为126天 ────────────────────────────────────────
SKEW_PRET_Z126 = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "pret=rank(-ts_delta(close,5));"
    "raw=rank(-skew_chg)*pret;"
    "group_neutralize(raw,my_group)"
)

# ─── 信号6: 双 group_rank + 价格反转（Target5最强结构） ──────────────────
# Target5 冠军: group_rank(signal1,cap)*group_rank(signal2,cap)
SKEW_PRET_DBLGRP = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "alpha=group_rank(-skew_chg,my_group)*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号7: skew_pret + subindustry 双层中性化 ───────────────────────────
# 先做行业内，再做市值内，减少 sub-universe 暴露
SKEW_PRET_SUBIND = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),252);"
    "pret=rank(-ts_delta(close,5));"
    "raw=rank(-skew_chg)*pret;"
    "step1=group_neutralize(raw,subindustry);"
    "group_neutralize(step1,my_group)"
)

# ─── 信号8: skew_pret + volume 确认（高成交量时信号更可信） ──────────────
SKEW_PRET_VOL_CONFIRM = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),252);"
    "pret=rank(-ts_delta(close,5));"
    "vol_confirm=rank(ts_delta(volume,3));"
    "raw=rank(-skew_chg)*pret*vol_confirm;"
    "group_neutralize(raw,my_group)"
)

# ─── 信号9: skew × 价格反转 × 期权到期结构（三重信号）───────────────────
# 当 skew 跳升 + 价格下跌 + 短期期限溢价高 → 超卖
SKEW_PRET_TERM = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),252);"
    "pret=rank(-ts_delta(close,5));"
    "term=rank(implied_volatility_mean_30-implied_volatility_mean_90);"
    "raw=rank(-skew_chg)*pret*term;"
    "group_neutralize(raw,my_group)"
)

# ─── 信号10: 用 skew_90d 替代 skew_30d（更稳定）─────────────────────────
SKEW90_PRET = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_90,5),252);"
    "pret=rank(-ts_delta(close,5));"
    "raw=rank(-skew_chg)*pret;"
    "group_neutralize(raw,my_group)"
)

# ─── 信号11: 双 group_rank，decay=7 ─────────────────────────────────────
SKEW_DBLGRP_D7 = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "alpha=group_rank(-skew_chg,my_group)*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

# ─── 信号12: skew_pret，decay=7 ──────────────────────────────────────────
SKEW_PRET_D7 = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),252);"
    "pret=rank(-ts_delta(close,5));"
    "raw=rank(-skew_chg)*pret;"
    "group_neutralize(raw,my_group)"
)

# ─── 信号13: 三重 group_rank（仿 Target5 三乘结构）─────────────────────
# Target5: group_rank(vol_decay)*group_rank(price_rev)
# 这里加入 skew 的 group_rank
SKEW_TRIPLE_GRP = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "vol_signal=ts_decay_linear(volume/ts_sum(volume,252),10);"
    "alpha=group_rank(-skew_chg,my_group)"
    "*group_rank(vol_signal,my_group)"
    "*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

VARIANTS = [
    ("OPT8_skew_pret_d15",     SKEW_PRET_D15,        {**BASE_SETTINGS, "decay": 15}),
    ("OPT8_skew_pret_d20",     SKEW_PRET_D20,        {**BASE_SETTINGS, "decay": 20}),
    ("OPT8_skew_pret_smooth",  SKEW_PRET_SMOOTH,     {**BASE_SETTINGS}),
    ("OPT8_skew_pret_tsrank",  SKEW_PRET_TSRANK,     {**BASE_SETTINGS}),
    ("OPT8_skew_pret_z126",    SKEW_PRET_Z126,       {**BASE_SETTINGS}),
    ("OPT8_skew_dblgrp_d10",   SKEW_PRET_DBLGRP,     {**BASE_SETTINGS}),
    ("OPT8_skew_pret_subind",  SKEW_PRET_SUBIND,     {**BASE_SETTINGS}),
    ("OPT8_skew_pret_volcfm",  SKEW_PRET_VOL_CONFIRM,{**BASE_SETTINGS}),
    ("OPT8_skew_pret_term",    SKEW_PRET_TERM,       {**BASE_SETTINGS}),
    ("OPT8_skew90_pret_d10",   SKEW90_PRET,          {**BASE_SETTINGS}),
    ("OPT8_skew_dblgrp_d7",    SKEW_DBLGRP_D7,       {**BASE_SETTINGS, "decay": 7}),
    ("OPT8_skew_pret_d7",      SKEW_PRET_D7,         {**BASE_SETTINGS, "decay": 7}),
    ("OPT8_skew_triple_d10",   SKEW_TRIPLE_GRP,      {**BASE_SETTINGS}),
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
            print(f"  GET error: {e}"); time.sleep(15); continue
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

        # 保存中间结果
        ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        with open(f"{OUTDIR}/opt8_r4_{ts}.json", "w") as f:
            json.dump({"results": results, "all_pass": all_pass}, f, indent=2)

    # 最终报告
    print("\n" + "="*60)
    print("📊 R4 最终结果汇总")
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
        print("\n⚠️ R4 无 ALL PASS，需进一步分析")

    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    final_path = f"{OUTDIR}/opt8_r4_final_{ts}.json"
    with open(final_path, "w") as f:
        json.dump({"results": results, "all_pass": all_pass}, f, indent=2)
    print(f"\n结果已保存: {final_path}")


if __name__ == "__main__":
    main()
