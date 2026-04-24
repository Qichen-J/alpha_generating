#!/usr/bin/env python3
"""
option8 Alpha R2 — 纯 FASTEXPR 兼容版
修正 R1 的致命错误：regression_neut 在 FASTEXPR 中不可用

option8 字段（已验证可直接使用，无需 vec_avg 包装）：
  - implied_volatility_mean_30/90/180/360 : 平均IV（call+put均值）
  - historical_volatility_30/60/90        : 历史实现波动率
  - implied_volatility_mean_skew_30/90    : IV偏度陡峭度
  - implied_volatility_put_30 / call_30   : put/call IV
  - parkinson_volatility_30               : Parkinson高低估计HV

信号设计：
  1. IV-RV 价差反转（波动率风险溢价，VRP）
  2. 期限结构扭曲（IV斜率变化）
  3. Skew 急剧变化反转
  4. Put-Call IV 分差跳升
  5. Parkinson vs close-to-close HV 分差
  6. IV term carry (长短期差值横截面信号)
  7. IV-RV × 期限结构 × cap group 三层组合
  8-10. 上述最佳候选的不同decay值

中性化结构（纯FASTEXPR）：
  my_group = bucket(rank(cap), range='0.1,1,0.1')
  raw = <signal>
  group_neutralize(raw, my_group)
  
  不用 regression_neut, 不用 trade_when
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

# ─── 信号1: IV-RV 价差 × 期限结构 ───────────────────────────────────────
# 逻辑：IV高于RV(恐慌溢价高) 且 短期IV > 长期IV(期限倒挂) → 两个恐慌信号共振 → 反转
IV_RV_TERM = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "iv_rv=ts_zscore(implied_volatility_mean_30-historical_volatility_30,126);"
    "term=ts_zscore(implied_volatility_mean_30-implied_volatility_mean_180,126);"
    "raw=-rank(iv_rv)*rank(term);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号2: 纯 VRP 信号（IV-RV gap 横截面反转） ──────────────────────────
# 逻辑：IV-RV 异常高 → 市场过度恐慌 → 均值回归
VRP_ONLY = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "iv_rv=ts_zscore(implied_volatility_mean_30-historical_volatility_30,126);"
    "raw=-rank(iv_rv);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号3: 期限结构扭曲（斜率变化 × 期限carry） ────────────────────────
# 逻辑：IV斜率的快速变化(短期内发生了什么事件预期) × 当前斜率(期限premium)
TERM_TWIST = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "slope=implied_volatility_mean_30-implied_volatility_mean_180;"
    "twist=ts_zscore(ts_delta(slope,10),252);"
    "carry=ts_zscore(slope,126);"
    "raw=-rank(twist)*rank(carry);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号4: Skew 急剧变化反转 ────────────────────────────────────────────
# 逻辑：put-call skew 5日内急剧上升 → 短期恐慌购买 → 反转
SKEW_SHOCK = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "skew_chg=ts_zscore(ts_delta(implied_volatility_mean_skew_30,5),252);"
    "raw=-rank(skew_chg);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号5: Put-Call IV 分差（恐慌方向） ─────────────────────────────────
# 逻辑：put IV - call IV 急剧扩大 → 定向恐慌 → 短期反弹
PUT_CALL_DELTA = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "pc_gap=implied_volatility_put_30-implied_volatility_call_30;"
    "pc_chg=ts_zscore(ts_delta(pc_gap,5),252);"
    "raw=-rank(pc_chg);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号6: Parkinson vs close-to-close HV 偏离 ──────────────────────────
# 逻辑：Parkinson(high-low)明显高于收盘波动 → 日内恐慌(high-low宽) → 次日反转
PARKINSON_GAP = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "pk_gap=ts_zscore(parkinson_volatility_30-historical_volatility_30,126);"
    "raw=-rank(pk_gap);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号7: VRP × 期限结构 × cap组内排名（三层乘积） ─────────────────────
# 逻辑：cap组内同时有高VRP + 期限倒挂 + 高cap排名(大盘价值型) → 精准反转
VRP_TERM_GRP = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "iv_rv=ts_zscore(implied_volatility_mean_30-historical_volatility_30,126);"
    "term=ts_zscore(implied_volatility_mean_30-implied_volatility_mean_90,126);"
    "raw=-group_rank(iv_rv,my_group)*group_rank(term,my_group);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号8: 长窗口 IV-RV（90日更稳定） ───────────────────────────────────
VRP_90D = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "iv_rv=ts_zscore(implied_volatility_mean_90-historical_volatility_90,126);"
    "term=ts_zscore(implied_volatility_mean_90-implied_volatility_mean_360,126);"
    "raw=-rank(iv_rv)*rank(term);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号9: IV change momentum（IV动量而非level）────────────────────────
# 逻辑：IV的5日变化 → 短期预期变化快 → 反转或动量
IV_MOMENTUM = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "iv_chg=ts_zscore(ts_delta(implied_volatility_mean_30,5),126);"
    "raw=-rank(iv_chg);"
    "group_neutralize(raw,my_group)"
)

# ─── 信号10: IV-RV × Skew（恐慌三重信号） ───────────────────────────────
VRP_SKEW = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "iv_rv=ts_zscore(implied_volatility_mean_30-historical_volatility_30,126);"
    "skew=ts_zscore(implied_volatility_mean_skew_30,126);"
    "raw=-rank(iv_rv)*rank(skew);"
    "group_neutralize(raw,my_group)"
)

VARIANTS = [
    ("OPT8_iv_rv_term_d10",    IV_RV_TERM,    {**BASE_SETTINGS}),
    ("OPT8_vrp_only_d10",      VRP_ONLY,      {**BASE_SETTINGS}),
    ("OPT8_term_twist_d10",    TERM_TWIST,    {**BASE_SETTINGS}),
    ("OPT8_skew_shock_d10",    SKEW_SHOCK,    {**BASE_SETTINGS}),
    ("OPT8_put_call_d10",      PUT_CALL_DELTA,{**BASE_SETTINGS}),
    ("OPT8_parkinson_d10",     PARKINSON_GAP, {**BASE_SETTINGS}),
    ("OPT8_vrp_term_grp_d10",  VRP_TERM_GRP,  {**BASE_SETTINGS}),
    ("OPT8_vrp_90d_d10",       VRP_90D,       {**BASE_SETTINGS}),
    ("OPT8_iv_momentum_d10",   IV_MOMENTUM,   {**BASE_SETTINGS}),
    ("OPT8_vrp_skew_d10",      VRP_SKEW,      {**BASE_SETTINGS}),
    # Decay variants for most promising
    ("OPT8_iv_rv_term_d5",     IV_RV_TERM,    {**BASE_SETTINGS, "decay": 5}),
    ("OPT8_iv_rv_term_d20",    IV_RV_TERM,    {**BASE_SETTINGS, "decay": 20}),
    ("OPT8_term_twist_d5",     TERM_TWIST,    {**BASE_SETTINGS, "decay": 5}),
]


def authenticate(session):
    session.post(f"{BASE}/authentication", auth=CREDENTIALS, timeout=30).raise_for_status()
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
        except:
            data = {}
        if not isinstance(data, dict):
            data = {}
        elapsed = int(time.time() - start)
        raw = data.get("alpha")
        alpha_id = raw.get("id") if isinstance(raw, dict) else (raw if isinstance(raw, str) and raw else None)
        status = data.get("status", "")
        ra = r.headers.get("Retry-After", "?")
        print(f"  [{elapsed}s] HTTP={r.status_code} RA={ra} status={status!r} alpha={alpha_id}")
        if alpha_id:
            return data
        if status in ("ERROR", "FAILED"):
            msg = data.get("message", "")
            print(f"  ⚠️ {status}: {msg[:150]}")
            return {}
        # 等待下一次poll
        wait = max(10, min(30, int(float(ra)) if ra not in ("?", None) else 30))
        time.sleep(wait)
    print("  ⏰ 超时")
    return {}


def extract(data, session):
    raw = data.get("alpha")
    if not raw:
        return None
    if isinstance(raw, dict):
        alpha, alpha_id = raw, raw.get("id")
    elif isinstance(raw, str):
        alpha_id = raw
        alpha = {}
        for _ in range(5):
            try:
                resp = session.get(f"{BASE}/alphas/{alpha_id}", timeout=45)
                if resp.status_code == 429:
                    time.sleep(int(float(resp.headers.get("Retry-After", 30))) + 5)
                    continue
                alpha = resp.json() if isinstance(resp.json(), dict) else {}
                break
            except:
                time.sleep(15)
    else:
        return None

    is_data = alpha.get("is", {})
    sharpe = is_data.get("sharpe")
    fitness = is_data.get("fitness")
    turnover = is_data.get("turnover")
    returns = is_data.get("returns")
    sub_sharpe = None
    for c in is_data.get("checks", []):
        if c["name"] == "LOW_SUB_UNIVERSE_SHARPE":
            sub_sharpe = c.get("value")
    if sharpe is None:
        return None

    sha_ok = sharpe >= 1.25
    fit_ok = fitness >= 1.0
    sub_ok = sub_sharpe is None or sub_sharpe >= 0.5
    ret_to = returns / turnover if turnover else 0
    sub_str = f"{sub_sharpe:.2f}" if sub_sharpe is not None else "N/A"
    flag = "🎯" if sha_ok and fit_ok and sub_ok else "  "
    print(f"  {flag} Sha={sharpe:.2f}{'✅' if sha_ok else '❌'} "
          f"Fit={fitness:.2f}{'✅' if fit_ok else '❌'} "
          f"Sub={sub_str}{'✅' if sub_ok else '❌'} "
          f"TO={turnover:.4f} Ret/TO={ret_to:.3f}")
    if sha_ok and fit_ok and sub_ok:
        print(f"  🎯🎯🎯 ALL PASS! alpha_id={alpha_id}")
    return {
        "id": alpha_id, "sharpe": sharpe, "fitness": fitness,
        "turnover": turnover, "returns": returns, "sub_sharpe": sub_sharpe,
        "ret_to": ret_to, "sha_ok": sha_ok, "fit_ok": fit_ok, "sub_ok": sub_ok,
        "all_pass": sha_ok and fit_ok and sub_ok,
    }


def main():
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    results = {}
    session = requests.Session()
    authenticate(session)

    for idx, (name, expr, settings) in enumerate(VARIANTS, 1):
        print(f"\n[{idx}/{len(VARIANTS)}] {name}")
        print(f"  decay={settings.get('decay')} neut={settings.get('neutralization')}")
        loc = submit(session, expr, settings)
        if not loc:
            results[name] = {"error": "submit_failed", "expression": expr}
            continue
        data = poll(session, loc)
        r = extract(data, session)
        results[name] = ({**r, "expression": expr} if r else {"error": "no_result", "expression": expr})
        if idx < len(VARIANTS):
            print("\n--- 等待8秒 ---")
            time.sleep(8)

    print("\n" + "=" * 80 + "\nOption8 Alpha R2 汇总:")
    all_pass = []
    for name, r in results.items():
        if "sharpe" in r:
            flag = "  🎯 ALL PASS" if r.get("all_pass") else ""
            print(f"  {name:35s}: Sha={r['sharpe']:.2f} Fit={r['fitness']:.2f} "
                  f"TO={r['turnover']:.4f} Ret/TO={r.get('ret_to', 0):.3f}{flag}")
            if r.get("all_pass"):
                all_pass.append((name, r["id"]))
        else:
            print(f"  {name:35s}: {r.get('error', 'unknown')}")
    if all_pass:
        print("\n🎉 找到通过的Alpha:")
        for name, aid in all_pass:
            print(f"  {name}: alpha_id={aid}")
    out = os.path.join(OUTDIR, f"option8_r2_{ts}.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 {out}")


if __name__ == "__main__":
    main()
