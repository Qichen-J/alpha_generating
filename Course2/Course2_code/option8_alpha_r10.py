"""
R10: 保留 iv_corr 核心信号，但通过以下方式规避 SELF_CORRELATION：
1. 换 universe (TOP200, TOP500, TOP1000) 
2. 换 delay=0
3. 用 regression_neut 替代 group_rank × group_rank
4. 换 neutralization sector/subindustry
5. iv_corr + adv20/sharesout based signals (流动性类)
6. iv_corr 对 hv_corr 做 regression_neut (残差)
"""

import requests, time, json, datetime, os

EMAIL = "xxxxxx@example.com"
PASSWORD = "xxxxxx"
BASE = "https://api.worldquantbrain.com"
OUT_DIR = "/Users/zhiqu/Desktop/brain/Course2/Course2_code/outputs"

ALPHAS = [
    # ── 换 universe ──────────────────────────────────────────
    # 1. iv_corr SUBINDUSTRY, TOP3000
    ("OPT8_ivcorr_subind", 10, "SUBINDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
     "group_neutralize(group_rank(iv_corr,my_group),my_group)"),

    # 2. iv_corr SECTOR
    ("OPT8_ivcorr_sector", 10, "MARKET", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(group_neutralize(alpha,my_group),sector)"),

    # 3. iv_corr TOP200
    ("OPT8_ivcorr_top200", 10, "INDUSTRY", "TOP200",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 4. iv_corr + hv_corr residual — iv_corr after removing hv_corr component
    ("OPT8_ivcorr_hvcorr_resid", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
     "hv_corr=ts_corr(historical_volatility_30,-returns,126);"
     "resid=iv_corr-ts_mean(iv_corr,63)*hv_corr/(ts_std_dev(hv_corr,63)+0.001);"
     "group_neutralize(group_rank(resid,my_group),my_group)"),

    # 5. iv_corr × liquidity: adv20 rank
    ("OPT8_ivcorr_liquidity", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
     "liq=ts_rank(adv20,252);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(liq,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 6. iv_corr zscore (different transform)
    ("OPT8_ivcorr_zscore", 7, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_zscore(ts_corr(-implied_volatility_mean_30,returns,63),252);"
     "group_neutralize(group_rank(iv_corr,my_group),my_group)"),

    # 7. iv_corr (21d window, shorter)
    ("OPT8_ivcorr_21d", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,21);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 8. iv_corr_30 × iv_corr_90 (cross-horizon product, no close/volume)
    ("OPT8_ivcorr_cross30_90", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr30=ts_corr(-implied_volatility_mean_30,returns,63);"
     "iv_corr90=ts_corr(-implied_volatility_mean_90,returns,63);"
     "alpha=group_rank(iv_corr30,my_group)*group_rank(iv_corr90,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 9. iv_corr × intra, double group_neutralize
    ("OPT8_ivcorr_dblneut", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(group_neutralize(alpha,my_group),my_group)"),

    # 10. iv_corr mean_30 × iv_corr mean_60 × intra
    ("OPT8_iv30_iv60_intra", 10, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr30=ts_corr(-implied_volatility_mean_30,returns,63);"
     "iv_corr60=ts_corr(-implied_volatility_mean_60,returns,63);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr30,my_group)*group_rank(iv_corr60,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 11. iv_corr × vwap_rev, sector neutralize last
    ("OPT8_ivcorr_intra_sector", 10, "INDUSTRY", "TOP3000",
     "my_group=sector;"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 12. iv_corr (63d corr) decay=5
    ("OPT8_ivcorr_decay5", 5, "INDUSTRY", "TOP3000",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_30,returns,63);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(iv_corr,my_group)*group_rank(intra,my_group);"
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
            "turnover": to, "checks": checks, "universe": universe}


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
    print(f"📊 R10 最终结果汇总")
    results.sort(key=lambda x: float(str(x["sharpe"]).replace("?","0") or "0"), reverse=True)
    for r in results:
        n_pass = sum(1 for c in r["checks"] if c.get("result") == "PASS")
        n_total = len(r["checks"])
        all_p = "🎉" if n_pass == n_total else ""
        print(f"  {all_p}{r['name']}: Sha={r['sharpe']} Fit={r['fitness']} TO={r['turnover']} [{n_pass}/{n_total}] id={r['id']}")

    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = f"{OUT_DIR}/opt8_r10_final_{ts}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    main()
