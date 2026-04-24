"""
R14: 继续扩展，重点在:
1. ivput 分支的更多变体 (SC命中率最低，因为最新颖)
2. ivc126 decay=3 的进一步变体
3. iv_mean_skew 作为第三因子 (R10 skew720 失败，但 skew_30/60 未试)
4. hv_corr 窗口更长 (252d)
"""

import requests, time, json, datetime, os

EMAIL = "xxxxxx@example.com"
PASSWORD = "xxxxxx"
BASE = "https://api.worldquantbrain.com"
OUT_DIR = "/Users/zhiqu/Desktop/brain/Course2/Course2_code/outputs"

ALPHAS = [
    # 1. ivput126 + decay=5
    ("OPT8_ivput126_d5", 5, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_put_60,returns,126);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 2. ivput126 + SUBINDUSTRY
    ("OPT8_ivput126_subind", 10, "SUBINDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_put_60,returns,126);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 3. ivput126 + decay=7
    ("OPT8_ivput126_d7", 7, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_put_60,returns,126);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 4. ivput126 + hv60
    ("OPT8_ivput126_hv60", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_put_60,returns,126);"
     "hv_corr=ts_corr(historical_volatility_60,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 5. ivput126 + intra126
    ("OPT8_ivput126_intra126", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_put_60,returns,126);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,126);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 6. ivc126_d3 + SUBINDUSTRY
    ("OPT8_ivc126_d3_sub", 3, "SUBINDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,126);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 7. ivc126 + hv252 (超长历史波动率)
    ("OPT8_ivc126_hv252", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,126);"
     "hv_corr=ts_corr(historical_volatility_60,-returns,252);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 8. ivc126_d5 + SECTOR (R12 sector用d10, 这里用d5)
    ("OPT8_ivc126_sec_d5b", 5, "SECTOR", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,126);"
     "hv_corr=ts_corr(historical_volatility_60,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 9. ivput60 + hv60 + intra (put × hv60)
    ("OPT8_ivput60_hv60", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_put_60,returns,63);"
     "hv_corr=ts_corr(historical_volatility_60,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 10. ivput60 SUBINDUSTRY decay=10
    ("OPT8_ivput60_subind", 10, "SUBINDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_put_60,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 11. ivput126 + SECTOR + decay=5
    ("OPT8_ivput126_sec_d5", 5, "SECTOR", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_put_60,returns,126);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(hv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 12. full put126 d5: ivput126 + hv60 + intra126 + d5
    ("OPT8_fullput126_d5", 5, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_put_60,returns,126);"
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
    print(f"▶ [{idx}/{total}] {name}  decay={decay} neut={neut}")
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
    for i, (name, decay, neut, universe, expr) in enumerate(ALPHAS, 1):
        res = simulate(session, name, decay, neut, universe, expr, i, len(ALPHAS))
        if res:
            results.append(res)
        time.sleep(3)

    print(f"\n{'='*60}")
    print(f"📊 R14 最终结果汇总")

    results.sort(key=lambda x: float(str(x.get("sharpe", -99))), reverse=True)
    for r in results:
        n_pass = sum(1 for c in r["checks"] if c.get("result") == "PASS")
        n_total = len(r["checks"])
        lf = next((c for c in r["checks"] if c.get("name")=="LOW_FITNESS"), {})
        sc = next((c for c in r["checks"] if c.get("name")=="SELF_CORRELATION"), {})
        flag = "🎉" if n_pass == n_total else "  "
        print(f"  {flag}{r['name']}: Sha={r['sharpe']} Fit={r['fitness']} [{n_pass}/{n_total}] LF={lf.get('result','?')} SC={sc.get('result','?')} id={r['id']}")

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = f"{OUT_DIR}/opt8_r14_final_{ts}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    main()
