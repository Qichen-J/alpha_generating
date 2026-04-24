"""
R12: 基于 R11 两个 Fit-PASS 结构设计更多变体：
- RRkPOdkb: iv_corr_126d × hv_corr_126d × intraday   → Sha=1.6, Fit=1.19 [7/8]
- XgYM0Lxz: iv_corr_60   × hv_corr_30  × intraday   → Sha=1.53, Fit=1.05 [7/8]

R12 目标：找到 SELF_CORR 能通过的变体
策略：改变 decay、universe、窗口、第三信号，生成不同 portfolio 组成
"""

import requests, time, json, datetime, os

EMAIL = "xxxxxx@example.com"
PASSWORD = "xxxxxx"
BASE = "https://api.worldquantbrain.com"
OUT_DIR = "/Users/zhiqu/Desktop/brain/Course2/Course2_code/outputs"

ALPHAS = [
    # ===== ivc126 分支 (decay=5 版) =====
    # 1. ivc126 + hv126 + intra, decay=5 (强Sharpe)
    ("OPT8_ivc126_d5", 5, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,126);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 2. ivc126 + hv60 + intra, decay=10
    ("OPT8_ivc126_hv60", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,126);"
     "hv_corr=ts_corr(historical_volatility_60,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 3. ivc126 + hv126 + intra126, decay=10
    ("OPT8_ivc126_intra126", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,126);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,126);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 4. ivc126 + hv126 + intra, SUBINDUSTRY, decay=10
    ("OPT8_ivc126_subind", 10, "SUBINDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,126);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 5. ivc126 + hv126 + intra, SECTOR, decay=10
    ("OPT8_ivc126_sector", 10, "SECTOR", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,126);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # ===== iv60 分支 =====
    # 6. iv60 + hv30 + intra, decay=5
    ("OPT8_ivc60_d5", 5, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_60,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 7. iv60 + hv60 + intra, decay=10
    ("OPT8_ivc60_hv60", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_60,returns,63);"
     "hv_corr=ts_corr(historical_volatility_60,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 8. iv60 + hv30 + intra126, decay=10
    ("OPT8_ivc60_intra126", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_60,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,126);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 9. iv60 + hv30 + intra, decay=7
    ("OPT8_ivc60_d7", 7, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_60,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # ===== iv90 和 iv120 (全新IV期限) =====
    # 10. iv90 + hv30 + intra, decay=10
    ("OPT8_ivc90_hv30", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_90,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 11. iv120 + hv30 + intra, decay=10
    ("OPT8_ivc120_hv30", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_120,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 12. iv90 + hv60 + intra, decay=5
    ("OPT8_ivc90_hv60_d5", 5, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_90,returns,63);"
     "hv_corr=ts_corr(historical_volatility_60,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 13. iv60 put分支 (implied_volatility_put_60) + hv + intra
    ("OPT8_ivput60_hv_intra", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_put_60,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 14. iv_call_60 分支
    ("OPT8_ivcall60_hv_intra", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_call_60,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
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
    print(f"📊 R12 最终结果汇总")

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
    out_path = f"{OUT_DIR}/opt8_r12_final_{ts}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    main()
