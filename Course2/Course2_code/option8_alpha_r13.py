"""
R13: 基于 R12 极佳结果（12/14 Fit-PASS）继续拓展
核心确认:
- iv_corr_126d × hv_corr × intra → 最强信号组合
- decay=5 显著提升 Sharpe
- SUBINDUSTRY neutralize 有效
- iv_put_60 也有效 (Sha=1.59, Fit=1.14)

R13 新探索:
1. ivc126 + decay=3 (更激进)
2. iv_put_126d (put期权更长期相关性)
3. iv_mean_180/270 (更长期IV期限)
4. ivc126 + hv126 + intra + SECTOR/SUBIND + decay=5
5. ivc126 + intra252 (更长窗口日内)
6. iv60 + hv60 + intra + decay=5
"""

import requests, time, json, datetime, os

EMAIL = "xxxxxx@example.com"
PASSWORD = "xxxxxx"
BASE = "https://api.worldquantbrain.com"
OUT_DIR = "/Users/zhiqu/Desktop/brain/Course2/Course2_code/outputs"

ALPHAS = [
    # 1. ivc126 + decay=3 (极速翻仓，完全不同组合)
    ("OPT8_ivc126_d3", 3, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,126);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 2. iv_put_126 (put分支，126d窗口)
    ("OPT8_ivput126_hv_intra", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_put_60,returns,126);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 3. iv_put_60 + decay=5
    ("OPT8_ivput60_d5", 5, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_put_60,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 4. iv_mean_180 (从未用过的期限)
    ("OPT8_ivc180_hv_intra", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_180,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 5. iv_mean_270
    ("OPT8_ivc270_hv_intra", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_270,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 6. ivc126 + SUBINDUSTRY + decay=5 (最强单品组合: 1.70,decay5可能到1.9?)
    ("OPT8_ivc126_sub_d5", 5, "SUBINDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,126);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 7. ivc126 + intra252 (更长日内窗口)
    ("OPT8_ivc126_intra252", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,126);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,252);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 8. iv60 + hv60 + intra, decay=5 (全60天版)
    ("OPT8_iv60hv60_d5", 5, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_60,returns,63);"
     "hv_corr=ts_corr(historical_volatility_60,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 9. ivc126 + SECTOR + decay=5
    ("OPT8_ivc126_sec_d5", 5, "SECTOR", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,126);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 10. ivc60 + SUBINDUSTRY + decay=10
    ("OPT8_ivc60_subind", 10, "SUBINDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_60,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 11. iv90 + hv60 + intra, decay=10 (90/60 组合)
    ("OPT8_ivc90_hv60", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_90,returns,63);"
     "hv_corr=ts_corr(historical_volatility_60,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 12. iv_mean_30 126d corr + hv_60 126d corr + intra, decay=5 (全126d窗口)
    ("OPT8_full126_d5", 5, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,126);"
     "hv_corr=ts_corr(historical_volatility_60,-returns,126);"
     "intra=ts_rank(-(close-open)/open,126);"
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
    print(f"📊 R13 最终结果汇总")

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
        lf = next((c for c in r["checks"] if c.get("name")=="LOW_FITNESS"), {})
        sc = next((c for c in r["checks"] if c.get("name")=="SELF_CORRELATION"), {})
        print(f"  {all_p}{r['name']}: Sha={r['sharpe']} Fit={r['fitness']} TO={r['turnover']} [{n_pass}/{n_total}] LF={lf.get('result','?')} SC={sc.get('result','?')} id={r['id']} decay={r['decay']}")

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = f"{OUT_DIR}/opt8_r13_final_{ts}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    main()
