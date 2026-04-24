#!/usr/bin/env python3
"""
option8 Alpha R3 — 聚焦 skew shock 信号增强
R2 发现：OPT8_skew_shock_d10 是最好信号 (Sha=0.46)
R3 策略：
  1. skew shock 配不同 delta 窗口 (3/5/10/20d)
  2. skew shock × price reversal 双信号乘积
  3. industry group_rank 版 skew shock
  4. skew shock × put-call spread 组合
  5. 短期 zscore 窗口 (63d 代替 252d)
  6. SUBINDUSTRY 中性化版
  7. 加 cap filter（只做大盘股）
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

# ─── 信号1: Skew shock d3（更短）────────────────────────────────────────
# 原版 d5 Sha=0.46，试更短窗口
SKEW_SHOCK_D3 = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,3),252);"
    "raw=-rank(skew_chg);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号2: Skew shock d10（更长）───────────────────────────────────────
SKEW_SHOCK_D10WIN = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,10),252);"
    "raw=-rank(skew_chg);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号3: Skew shock d20（月度）──────────────────────────────────────
SKEW_SHOCK_D20WIN = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,20),252);"
    "raw=-rank(skew_chg);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号4: Skew shock × price reversal（双信号）──────────────────────
# 逻辑：IV偏度跳升 AND 近期价格下跌 → 恐慌买入 → 反弹
SKEW_PRET = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),252);"
    "pret=rank(-ts_delta(close,5));"
    "raw=rank(-skew_chg)*pret;"
    "group_neutralize(raw,my_group)"
)

# ─── 信号5: Skew shock，industry group_rank 版 ───────────────────────
# 用 industry 内排名而非 cap 分组，更好的行业对齐
SKEW_IND_GRP = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),252);"
    "raw=group_rank(-skew_chg,industry);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号6: Skew shock，短 zscore 窗口（63天）──────────────────────────
# 252天 zscore 太长，63天更及时
SKEW_ZSCORE_63 = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),63);"
    "raw=-rank(skew_chg);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号7: Skew shock × Put-Call spread（双向恐慌放大）──────────────
SKEW_PC = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),252);"
    "pc_chg=ts_zscore(ts_delta(implied_volatility_put_30-implied_volatility_call_30,5),252);"
    "raw=rank(-skew_chg)*rank(-pc_chg);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号8: 纯 Put IV 变化反转（更干净的信号）──────────────────────────
# skew = put/call 隐含波动率结构，put IV 直接跳升 → 恐慌 → 反转
PUT_IV_DELTA = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "put_chg=ts_zscore(ts_delta(implied_volatility_put_30,5),252);"
    "raw=-rank(put_chg);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号9: skew 90天版（更稳定的期权结构）─────────────────────────────
SKEW_90D = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_90,5),252);"
    "raw=-rank(skew_chg);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号10: skew shock × IV level（高IV环境下skew反转更强）─────────────
SKEW_IV_COMBO = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),252);"
    "iv_level=ts_zscore(implied_volatility_mean_30,126);"
    "raw=rank(-skew_chg)*rank(iv_level);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号11: skew shock，去掉 ts_zscore（直接用 ts_delta 的 rank）────────
# 原版用 ts_zscore 标准化，可能过拟合；直接 rank(ts_delta) 更稳健
SKEW_RANK_DELTA = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_delta(implied_volatility_mean_skew_30,5);"
    "raw=-rank(skew_chg);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号12: skew shock × volume（高成交量 + skew 跳升 → 更可信的反转）─
SKEW_VOL = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),252);"
    "vol_rank=rank(ts_delta(volume,3));"
    "raw=rank(-skew_chg)*(1+vol_rank);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号13: 双 group_rank（模仿 Target5 最强结构）──────────────────────
# Target5 最强：group_rank(signal1,cap_group)*group_rank(signal2,cap_group)
SKEW_DOUBLE_GRP = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),126);"
    "alpha=group_rank(-skew_chg,my_group)*group_rank(-ts_delta(close,5),my_group);"
    "group_neutralize(alpha,my_group)"
)

VARIANTS = [
    ("OPT8_skew_d3_d10",       SKEW_SHOCK_D3,    {**BASE_SETTINGS}),
    ("OPT8_skew_d10win_d10",   SKEW_SHOCK_D10WIN, {**BASE_SETTINGS}),
    ("OPT8_skew_d20win_d10",   SKEW_SHOCK_D20WIN, {**BASE_SETTINGS}),
    ("OPT8_skew_pret_d10",     SKEW_PRET,         {**BASE_SETTINGS}),
    ("OPT8_skew_indgrp_d10",   SKEW_IND_GRP,      {**BASE_SETTINGS}),
    ("OPT8_skew_zscore63_d10", SKEW_ZSCORE_63,    {**BASE_SETTINGS}),
    ("OPT8_skew_pc_d10",       SKEW_PC,           {**BASE_SETTINGS}),
    ("OPT8_put_iv_delta_d10",  PUT_IV_DELTA,      {**BASE_SETTINGS}),
    ("OPT8_skew_90d_d10",      SKEW_90D,          {**BASE_SETTINGS}),
    ("OPT8_skew_iv_combo_d10", SKEW_IV_COMBO,     {**BASE_SETTINGS}),
    ("OPT8_skew_rnk_d10",      SKEW_RANK_DELTA,   {**BASE_SETTINGS}),
    ("OPT8_skew_vol_d10",      SKEW_VOL,          {**BASE_SETTINGS}),
    ("OPT8_skew_dblgrp_d10",   SKEW_DOUBLE_GRP,   {**BASE_SETTINGS}),
    # 最优 skew 信号不同 decay 扫描
    ("OPT8_skew_pret_d5",      SKEW_PRET,         {**BASE_SETTINGS, "decay": 5}),
    ("OPT8_skew_indgrp_d5",    SKEW_IND_GRP,      {**BASE_SETTINGS, "decay": 5}),
    ("OPT8_skew_dblgrp_d7",    SKEW_DOUBLE_GRP,   {**BASE_SETTINGS, "decay": 7}),
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

    for name, expr, settings in VARIANTS:
        print(f"\n{'='*60}")
        print(f"▶ {name}  decay={settings.get('decay')} neut={settings.get('neutralization')}")

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
        checks = is_data.get("checks", [])

        passed = all(c.get("result") == "PASS" for c in checks) if checks else False
        check_str = " | ".join(f"{c['name']}={'✅' if c.get('result')=='PASS' else '❌'}{c.get('value','')}" for c in checks)

        print(f"  ✅ alpha_id={alpha_id}")
        print(f"  Sha={sha} Fit={fit} TO={to}")
        print(f"  Checks: {check_str}")
        if passed:
            print(f"  🎉🎉 ALL PASS: {name} → {alpha_id}")
            all_pass.append({"name": name, "id": alpha_id, "sharpe": sha, "fitness": fit})

        results.append({
            "name": name, "id": alpha_id,
            "sharpe": sha, "fitness": fit, "turnover": to,
            "all_pass": passed, "checks": checks,
        })

        # 保存中间结果
        ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        with open(f"{OUTDIR}/opt8_r3_{ts}.json", "w") as f:
            json.dump({"results": results, "all_pass": all_pass}, f, indent=2)

    # 最终报告
    print("\n" + "="*60)
    print("📊 R3 最终结果汇总")
    results_sorted = sorted(
        [r for r in results if "error" not in r],
        key=lambda x: float(x.get("sharpe", -99) or -99), reverse=True
    )
    for r in results_sorted:
        flag = "🎉" if r.get("all_pass") else "  "
        print(f"  {flag} {r['name']}: Sha={r['sharpe']} Fit={r['fitness']} TO={r['turnover']} id={r['id']}")

    if all_pass:
        print(f"\n🏆 找到 {len(all_pass)} 个 ALL PASS alpha！")
        for a in all_pass:
            print(f"  {a['id']}: {a['name']} Sha={a['sharpe']} Fit={a['fitness']}")
    else:
        print("\n⚠️  R3 无 ALL PASS，需进一步迭代")

    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    final_path = f"{OUTDIR}/opt8_r3_final_{ts}.json"
    with open(final_path, "w") as f:
        json.dump({"results": results, "all_pass": all_pass}, f, indent=2)
    print(f"\n结果已保存: {final_path}")


if __name__ == "__main__":
    main()
