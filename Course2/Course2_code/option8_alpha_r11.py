"""
R11: 在 iv_corr × hv_corr × intraday 结构基础上，尝试：
1. decay=5 版本 (qMmVJ3ov 证明 decay=5 会显著改变组合结构)
2. 不同时间窗口 (iv_corr 21d/42d/126d)
3. trade_when 过滤器
4. 更激进的 cap 分组
5. iv_skew 替换 hv_corr
"""

import requests, time, json, datetime, os

EMAIL = "xxxxxx@example.com"
PASSWORD = "xxxxxx"
BASE = "https://api.worldquantbrain.com"
OUT_DIR = "/Users/zhiqu/Desktop/brain/Course2/Course2_code/outputs"

# iv_corr × hv_corr × intraday_rev 核心结构变体
# Gr39lp6P (R8 best, Fit=1.22) 的表达式:
# iv_corr=ts_corr(-iv_mean_30, returns, 63)
# hv_corr=ts_corr(hv_30, -returns, 126)
# intra=ts_rank(-(close-open)/open, 63)

ALPHAS = [
    # 1. decay=5, 核心结构不变 (iv_corr×hv_corr×intra)
    ("OPT8_ivc_hvc_d5", 5, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 2. decay=7 (between 5 and 10)
    ("OPT8_ivc_hvc_d7", 7, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 3. iv_corr 21d window (vs 63d in original)
    ("OPT8_ivc21_hvc_intra", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,21);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 4. iv_corr 126d window (longer)
    ("OPT8_ivc126_hvc_intra", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,126);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 5. trade_when(volume>adv20, ...) 过滤器
    ("OPT8_ivc_hvc_tradewhen", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "trade_when(volume>adv20,group_neutralize(alpha,my_group),-1)"),

    # 6. hv_corr window 改为 63d (匹配 iv_corr)
    ("OPT8_ivc63_hvc63_intra", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,63);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 7. intraday window 改为 126d
    ("OPT8_ivc_hvc_intra126", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,126);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 8. iv_mean_60 (instead of 30)
    ("OPT8_ivc60_hvc_intra", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_60,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 9. hv_60 (instead of hv_30)
    ("OPT8_ivc_hvc60_intra", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
     "hv_corr=ts_corr(historical_volatility_60,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 10. skew_720 replaces hv_corr
    ("OPT8_ivc_skew720_intra", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
     "skew_sig=ts_zscore(ts_delta(implied_volatility_mean_skew_720,5),126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(-skew_sig,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 11. SUBINDUSTRY neutralize + decay=5
    ("OPT8_ivc_hvc_sub_d5", 5, "SUBINDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 12. overnight_gap replaces intraday_rev (open-close gap)
    ("OPT8_ivc_hvc_ovn", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "ovn=ts_rank(-(open-ts_delay(close,1))/ts_delay(close,1),63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(ovn,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 13. ts_mean smoothed signals
    ("OPT8_ivc_hvc_smth", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_mean(ts_corr(-implied_volatility_mean_30,returns,63),5);"
     "hv_corr=ts_mean(ts_corr(historical_volatility_30,-returns,126),5);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),
]

SIM_PARAMS_BASE = {
    "type": "REGULAR",
    "settings": {
        "instrumentType": "EQUITY",
        "region": "USA",
        "delay": 1,
        "truncation": 0.08,
        "pasteurization": "ON",
        "unitHandling": "VERIFY",
        "nanHandling": "OFF",
        "language": "FASTEXPR",
        "visualization": False,
    }
}

def simulate(session, name, decay, neut, universe, expr, idx, total):
    print(f"\n{'='*60}")
    print(f"▶ [{idx}/{total}] {name}  decay={decay} neut={neut} univ={universe}")
    params = json.loads(json.dumps(SIM_PARAMS_BASE))
    params["settings"]["decay"] = decay
    params["settings"]["neutralization"] = neut
    params["settings"]["universe"] = universe
    params["regular"] = expr

    r = session.post(f"{BASE}/simulations", json=params, timeout=30)
    print(f"  POST: {r.status_code}")
    if r.status_code != 201:
        print(f"  ❌ 失败: {r.text[:200]}")
        return None

    loc = r.headers.get("Location", "")
    elapsed = 0
    while True:
        time.sleep(15)
        elapsed += 15
        try:
            sr = session.get(loc, timeout=45)
            sd = sr.json()
        except Exception as e:
            print(f"  [{elapsed:4d}s] GET error: {e}")
            time.sleep(30)
            elapsed += 30
            continue
        status = sd.get("status", "")
        alpha_id = sd.get("alpha")
        print(f"  [{elapsed:4d}s] status='{status}' alpha={alpha_id}")
        if status == "COMPLETE":
            break
        if status in ("ERROR", "FAILED"):
            print(f"  ❌ 失败: {sd.get('message','')}")
            return None
        if elapsed > 1200:
            print(f"  ⏰ 超时")
            return None

    if not alpha_id:
        return None

    ar = session.get(f"{BASE}/alphas/{alpha_id}", timeout=30)
    ad = ar.json()
    is_d = ad.get("is") or {}
    sha = is_d.get("sharpe", "?")
    fit = is_d.get("fitness", "?")
    to  = is_d.get("turnover", "?")
    checks = is_d.get("checks", [])
    n_pass = sum(1 for c in checks if c.get("result") == "PASS")
    check_str = " | ".join(
        f"{c['name']}={'✅' if c['result']=='PASS' else ('⏳' if c['result']=='PENDING' else '❌')}{c.get('value','')}"
        for c in checks
    )
    print(f"  ✅ {alpha_id} Sha={sha} Fit={fit} TO={to} [{n_pass}/{len(checks)}]")
    print(f"  {check_str}")
    return {"name": name, "id": alpha_id, "sharpe": sha, "fitness": fit,
            "turnover": to, "checks": checks, "universe": universe, "decay": decay}


def main():
    session = requests.Session()
    session.post(f"{BASE}/authentication", auth=(EMAIL, PASSWORD), timeout=30).raise_for_status()
    print("✅ 认证成功")

    results = []
    total = len(ALPHAS)
    for i, (name, decay, neut, universe, expr) in enumerate(ALPHAS, 1):
        res = simulate(session, name, decay, neut, universe, expr, i, total)
        if res:
            results.append(res)
        time.sleep(3)

    print(f"\n{'='*60}")
    print(f"📊 R11 最终结果汇总")

    def sort_key(x):
        try:
            return float(str(x["sharpe"]))
        except:
            return -99

    results.sort(key=sort_key, reverse=True)
    for r in results:
        n_pass = sum(1 for c in r["checks"] if c.get("result") == "PASS")
        n_total = len(r["checks"])
        all_p = "🎉" if n_pass == n_total else "  "
        print(f"  {all_p}{r['name']}: Sha={r['sharpe']} Fit={r['fitness']} TO={r['turnover']} [{n_pass}/{n_total}] id={r['id']} decay={r['decay']}")

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = f"{OUT_DIR}/opt8_r11_final_{ts}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    main()
