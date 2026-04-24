#!/usr/bin/env python3
"""
option8 Alpha R1 — IV-RV 价差 × 期限结构 × Skew
字段来源：option8 dataset (64 fields)
  - implied_volatility_mean_30/90/180：平均隐含波动率（不同到期期限）
  - historical_volatility_30：历史实现波动率
  - implied_volatility_mean_skew_30/90：偏度陡峭度
  - implied_volatility_put_30 / implied_volatility_call_30：put/call IV

Alpha 逻辑（参考模板合集思路）：
  1. IV_RV_BASE：IV-RV gap（波动率风险溢价）× 期限结构反转
  2. IV_RV_SKEW：加入 skew 信号
  3. TERM_TWIST：仅期限结构扭曲
  4. SKEW_SHOCK：偏度急剧变化
  5. PUT_CALL_SPREAD：put/call IV 分差（恐慌信号）
  6. PARKINSON_GAP：Parkinson HV 相对 close-to-close HV 的偏离（跳空恐慌）
  7. IV_LEVEL_REV：IV level 绝对高低的反转效应

设置：INDUSTRY 中性，decay=10，trade_when 过滤低流动性
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

# === Alpha 表达式 ===
# 公共乐高积木:
#   my_group = bucket(rank(cap), range='0.1,1,0.1')
#   IR = abs(ts_mean(returns,252)/ts_std_dev(returns,252))
#   最后: regression_neut(group_neutralize(raw, my_group), IR)
#        + trade_when(volume > adv20, alpha, -1)

# 目标1: IV-RV 价差 × 期限结构 (对应五目标模板 Target1 的具体字段版)
# 逻辑: IV高于RV(市场恐慌定价过高) 且 短期IV高于长期IV(期限倒挂) → 后续IV回落 → 去做多被过度定价的股票逆转
IV_RV_BASE = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "IR=abs(ts_mean(returns,252)/ts_std_dev(returns,252));"
    "iv_rv_gap=ts_zscore(implied_volatility_mean_30-historical_volatility_30,126);"
    "term_shape=ts_zscore(implied_volatility_mean_30-implied_volatility_mean_180,126);"
    "raw=-rank(iv_rv_gap)*rank(term_shape);"
    "alpha=regression_neut(group_neutralize(raw,my_group),IR);"
    "trade_when(volume>adv20,alpha,-1)"
)

# 目标2: Skew Shock 变体 (对应 Target2 的具体字段版)
# 逻辑: put-call skew 急速上升(恐慌溢价大涨) 且整体IV处于高位 → 风险重定价完成后反转
IV_RV_SKEW = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "IR=abs(ts_mean(returns,252)/ts_std_dev(returns,252));"
    "iv_rv_gap=ts_zscore(implied_volatility_mean_30-historical_volatility_30,126);"
    "skew_signal=ts_zscore(implied_volatility_mean_skew_30,126);"
    "raw=-rank(iv_rv_gap)*rank(skew_signal);"
    "alpha=regression_neut(group_neutralize(raw,my_group),IR);"
    "trade_when(volume>adv20,alpha,-1)"
)

# 目标3: 纯期限结构扭曲 (对应 Target3)
# 逻辑: 短端IV-长端IV 的斜率变化 → 风险预期切换信号
TERM_TWIST = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "IR=abs(ts_mean(returns,252)/ts_std_dev(returns,252));"
    "slope=implied_volatility_mean_30-implied_volatility_mean_180;"
    "twist=ts_zscore(ts_delta(slope,10),252);"
    "carry=ts_zscore(slope,126);"
    "raw=-rank(twist)*rank(carry);"
    "alpha=regression_neut(group_neutralize(raw,my_group),IR);"
    "trade_when(abs(returns)<0.08,alpha,-1)"
)

# 目标4: Put-Call IV 分差 恐慌反转
# 逻辑: put IV 急剧高于 call IV → 市场极端恐慌 → 短期反弹
PUT_CALL_SPREAD = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "IR=abs(ts_mean(returns,252)/ts_std_dev(returns,252));"
    "pc_spread=ts_zscore(implied_volatility_put_30-implied_volatility_call_30,126);"
    "spread_jump=ts_rank(ts_delta(pc_spread,5),60);"
    "raw=-rank(spread_jump);"
    "alpha=regression_neut(group_neutralize(raw,my_group),IR);"
    "trade_when(volume>adv20,alpha,-1)"
)

# 目标5: Parkinson HV 相对 close-to-close HV 偏离 (日内波动溢价)
# 逻辑: Parkinson用high-low估计，偏高于收盘价波动 → 日内恐慌 → 次日反转
PARKINSON_GAP = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "IR=abs(ts_mean(returns,252)/ts_std_dev(returns,252));"
    "pk_gap=ts_zscore(parkinson_volatility_30-historical_volatility_30,126);"
    "pk_jump=ts_rank(ts_delta(pk_gap,5),60);"
    "raw=-rank(pk_jump);"
    "alpha=regression_neut(group_neutralize(raw,my_group),IR);"
    "trade_when(volume>adv20,alpha,-1)"
)

# 目标6: IV Level 绝对高低的横截面反转 (参考模板里 vec_max(OptionHighPrice)/close)
# 逻辑: IV 在历史上处于高分位 → 该股被市场过度恐慌定价 → 均值回归
IV_LEVEL_REV = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "IR=abs(ts_mean(returns,252)/ts_std_dev(returns,252));"
    "iv_pct=ts_rank(implied_volatility_mean_30,252);"
    "raw=-rank(iv_pct);"
    "alpha=regression_neut(group_neutralize(raw,my_group),IR);"
    "trade_when(volume>adv20,alpha,-1)"
)

# 目标7: IV-RV + Skew 三乘 (强信号叠加版)
# 逻辑: 只有同时满足 IV-RV高、期限倒挂、skew高 的股票才触发
IV_RV_FULL = (
    "my_group=bucket(rank(cap),range='0.1,1,0.1');"
    "IR=abs(ts_mean(returns,252)/ts_std_dev(returns,252));"
    "iv_rv_gap=ts_zscore(implied_volatility_mean_30-historical_volatility_30,126);"
    "term_shape=ts_zscore(implied_volatility_mean_30-implied_volatility_mean_90,126);"
    "skew_signal=ts_zscore(implied_volatility_mean_skew_30,126);"
    "raw=-rank(iv_rv_gap)*rank(term_shape)*rank(skew_signal);"
    "alpha=regression_neut(group_neutralize(raw,my_group),IR);"
    "trade_when(volume>adv20,alpha,-1)"
)

VARIANTS = [
    ("OPT8_iv_rv_base_d10",    IV_RV_BASE,       {**BASE_SETTINGS}),
    ("OPT8_iv_rv_skew_d10",    IV_RV_SKEW,       {**BASE_SETTINGS}),
    ("OPT8_term_twist_d10",    TERM_TWIST,        {**BASE_SETTINGS}),
    ("OPT8_put_call_d10",      PUT_CALL_SPREAD,   {**BASE_SETTINGS}),
    ("OPT8_parkinson_d10",     PARKINSON_GAP,     {**BASE_SETTINGS}),
    ("OPT8_iv_level_rev_d10",  IV_LEVEL_REV,      {**BASE_SETTINGS}),
    ("OPT8_iv_rv_full_d10",    IV_RV_FULL,        {**BASE_SETTINGS}),
    # decay 变体：最有潜力的 base 多试几个 decay
    ("OPT8_iv_rv_base_d5",     IV_RV_BASE,        {**BASE_SETTINGS, "decay": 5}),
    ("OPT8_iv_rv_base_d20",    IV_RV_BASE,        {**BASE_SETTINGS, "decay": 20}),
    ("OPT8_term_twist_d5",     TERM_TWIST,        {**BASE_SETTINGS, "decay": 5}),
]


def authenticate(session):
    session.post(f"{BASE}/authentication", auth=CREDENTIALS, timeout=30).raise_for_status()
    print("✅ 认证成功")


def submit(session, expr, settings):
    for _ in range(10):
        try:
            r = session.post(f"{BASE}/simulations",
                             json={"type": "REGULAR", "settings": settings, "regular": expr}, timeout=60)
        except requests.exceptions.Timeout:
            time.sleep(10); authenticate(session); continue
        except Exception as e:
            print(f"  POST异常: {e}"); time.sleep(15); continue
        print(f"  POST: {r.status_code} RA={r.headers.get('Retry-After','?')}")
        if r.status_code == 429:
            time.sleep(int(float(r.headers.get("Retry-After", 30))) + 5); continue
        if r.status_code >= 400:
            print(f"  错误: {r.status_code} {r.text[:200]}"); return None
        return r.headers.get("Location")
    return None


def poll(session, location):
    start = time.time()
    while time.time() - start < 600:
        try:
            r = session.get(location, timeout=45)
        except Exception as e:
            print(f"  GET error: {e}"); time.sleep(15); continue
        if r.status_code == 429:
            time.sleep(int(float(r.headers.get("Retry-After", 30))) + 5); continue
        try: data = r.json()
        except: data = {}
        if not isinstance(data, dict): data = {}
        elapsed = int(time.time() - start)
        raw = data.get("alpha")
        alpha_id = raw.get("id") if isinstance(raw, dict) else (raw if isinstance(raw, str) and raw else None)
        ra = r.headers.get("Retry-After", "?")
        print(f"  [{elapsed}s] HTTP={r.status_code} RA={ra} alpha={alpha_id}")
        if alpha_id: return data
        if data.get("status") in ("ERROR", "FAILED"): return {}
        time.sleep(max(5, min(30, int(float(ra)) if ra != "?" else 30)))
    print("  ⏰ 超时"); return {}


def extract(data, session):
    raw = data.get("alpha")
    if not raw: return None
    if isinstance(raw, dict):
        alpha, alpha_id = raw, raw.get("id")
    elif isinstance(raw, str):
        alpha_id = raw; alpha = {}
        for _ in range(5):
            try:
                resp = session.get(f"{BASE}/alphas/{alpha_id}", timeout=45)
                if resp.status_code == 429: time.sleep(int(float(resp.headers.get("Retry-After",30)))+5); continue
                alpha = resp.json() if isinstance(resp.json(), dict) else {}; break
            except: time.sleep(15)
    else: return None

    is_data = alpha.get("is", {})
    sharpe = is_data.get("sharpe"); fitness = is_data.get("fitness")
    turnover = is_data.get("turnover"); returns = is_data.get("returns")
    sub_sharpe = None
    for c in is_data.get("checks", []):
        if c["name"] == "LOW_SUB_UNIVERSE_SHARPE": sub_sharpe = c.get("value")
    if sharpe is None: return None

    sha_ok = sharpe >= 1.25; fit_ok = fitness >= 1.0
    sub_ok = sub_sharpe is None or sub_sharpe >= 0.5
    ret_to = returns / turnover if turnover else 0
    sub_str = f"{sub_sharpe:.2f}" if sub_sharpe is not None else "N/A"
    print(f"  {'🎯' if sha_ok and fit_ok and sub_ok else '  '} "
          f"Sha={sharpe:.2f}{'✅' if sha_ok else '❌'} "
          f"Fit={fitness:.2f}{'✅' if fit_ok else '❌'} "
          f"Sub={sub_str}{'✅' if sub_ok else '❌'} "
          f"TO={turnover:.4f} Ret/TO={ret_to:.3f}")
    if sha_ok and fit_ok and sub_ok:
        print(f"  🎯🎯🎯 ALL PASS! alpha_id={alpha_id}")
    return {"id": alpha_id, "sharpe": sharpe, "fitness": fitness, "turnover": turnover,
            "returns": returns, "sub_sharpe": sub_sharpe, "ret_to": ret_to,
            "sha_ok": sha_ok, "fit_ok": fit_ok, "sub_ok": sub_ok,
            "all_pass": sha_ok and fit_ok and sub_ok}


def main():
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    results = {}; session = requests.Session(); authenticate(session)
    for idx, (name, expr, settings) in enumerate(VARIANTS, 1):
        print(f"\n[{idx}/{len(VARIANTS)}] {name}")
        print(f"  decay={settings.get('decay')} neut={settings.get('neutralization')}")
        loc = submit(session, expr, settings)
        if not loc:
            results[name] = {"error": "submit_failed", "expression": expr}; continue
        data = poll(session, loc)
        r = extract(data, session)
        results[name] = ({**r, "expression": expr} if r else {"error": "no_result", "expression": expr})
        if idx < len(VARIANTS):
            print("\n--- 等待5秒 ---"); time.sleep(5)

    print("\n" + "="*80 + "\nOption8 Alpha R1 汇总:")
    all_pass = []
    for name, r in results.items():
        if "sharpe" in r:
            flag = "  🎯 ALL PASS" if r.get("all_pass") else ""
            print(f"  {name:35s}: Sha={r['sharpe']:.2f} Fit={r['fitness']:.2f} "
                  f"TO={r['turnover']:.4f} Ret/TO={r.get('ret_to',0):.3f}{flag}")
            if r.get("all_pass"): all_pass.append((name, r["id"]))
        else:
            print(f"  {name:35s}: {r.get('error','unknown')}")
    if all_pass:
        print("\n🎉 找到通过的Alpha:")
        for name, aid in all_pass: print(f"  {name}: alpha_id={aid}")
    out = os.path.join(OUTDIR, f"option8_r1_{ts}.json")
    with open(out, "w") as f: json.dump(results, f, indent=2)
    print(f"\n💾 {out}")

if __name__ == "__main__":
    main()
