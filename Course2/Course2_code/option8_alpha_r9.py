"""
R9: 彻底换信号方向
问题诊断: ts_corr(-IV_mean_30, returns, 63) 被平台广泛使用，SELF_CORRELATION无解
R9核心方向:
  1. IV term structure (30/360比率) — 短期vs长期IV差异
  2. Parkinson volatility signals — 完全不同的波动率度量
  3. 更长窗口IV corr (120/180d)
  4. put/call IV差信号
  5. 纯IV水平zscore信号（不用corr）
结构上放弃 group_rank×group_rank×group_rank 三因子乘积，改用简洁单/双因子
"""

import requests, time, json, datetime, os

EMAIL = "xxxxxx@example.com"
PASSWORD = "xxxxxx"
BASE = "https://api.worldquantbrain.com"
OUT_DIR = "/Users/zhiqu/Desktop/brain/Course2/Course2_code/outputs"

# ── 信号表达式 ─────────────────────────────────────────────
ALPHAS = [
    # 1. IV term structure: 近期IV / 远期IV — 衡量近期恐慌/乐观程度
    ("OPT8_iv_term_single", 10, "INDUSTRY",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_term=ts_zscore(implied_volatility_mean_30/implied_volatility_mean_360-1,252);"
     "group_neutralize(group_rank(-iv_term,my_group),my_group)"),

    # 2. IV term × intraday reversal
    ("OPT8_iv_term_intra", 10, "INDUSTRY",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_term=ts_zscore(implied_volatility_mean_30/implied_volatility_mean_360-1,252);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(-iv_term,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 3. Parkinson vol change — 完全不同的波动率度量
    ("OPT8_park_chg", 10, "INDUSTRY",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "park_chg=ts_zscore(ts_delta(parkinson_volatility_30,5),126);"
     "group_neutralize(group_rank(-park_chg,my_group),my_group)"),

    # 4. Parkinson-returns corr
    ("OPT8_park_corr", 10, "INDUSTRY",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "park_corr=ts_corr(-parkinson_volatility_30,returns,63);"
     "group_neutralize(group_rank(park_corr,my_group),my_group)"),

    # 5. VRP via parkinson: IV - parkinson (正 = IV高估波动率 = 可能反转)
    ("OPT8_vrp_park", 10, "INDUSTRY",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "vrp=ts_zscore(implied_volatility_mean_30-parkinson_volatility_30,252);"
     "group_neutralize(group_rank(-vrp,my_group),my_group)"),

    # 6. IV term × park_corr × intraday (三因子，全新组合)
    ("OPT8_term_park_intra", 10, "INDUSTRY",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_term=ts_zscore(implied_volatility_mean_30/implied_volatility_mean_360-1,252);"
     "park_corr=ts_corr(-parkinson_volatility_30,returns,63);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(-iv_term,my_group)*group_rank(park_corr,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 7. IV term × park_chg (双因子)
    ("OPT8_term_park_dbl", 10, "INDUSTRY",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_term=ts_zscore(implied_volatility_mean_30/implied_volatility_mean_360-1,252);"
     "park_chg=ts_zscore(ts_delta(parkinson_volatility_30,5),126);"
     "alpha=group_rank(-iv_term,my_group)*group_rank(-park_chg,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 8. Long-horizon IV corr (120d window, 更长的评估期)
    ("OPT8_iv120_corr", 10, "INDUSTRY",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_120,returns,63);"
     "group_neutralize(group_rank(iv_corr,my_group),my_group)"),

    # 9. IV180 corr (更长期的IV)
    ("OPT8_iv180_corr", 10, "INDUSTRY",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_corr=ts_corr(-implied_volatility_mean_180,returns,63);"
     "group_neutralize(group_rank(iv_corr,my_group),my_group)"),

    # 10. IV term × park_corr (双因子，无intraday)
    ("OPT8_term_parkcorr", 10, "INDUSTRY",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "iv_term=ts_zscore(implied_volatility_mean_30/implied_volatility_mean_360-1,252);"
     "park_corr=ts_corr(-parkinson_volatility_30,returns,63);"
     "alpha=group_rank(-iv_term,my_group)*group_rank(park_corr,my_group);"
     "group_neutralize(alpha,my_group)"),

    # 11. Put IV change (不同于mean IV)
    ("OPT8_put_iv_chg", 10, "INDUSTRY",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "put_chg=ts_zscore(ts_delta(implied_volatility_put_30,5),126);"
     "group_neutralize(group_rank(-put_chg,my_group),my_group)"),

    # 12. Call IV change
    ("OPT8_call_iv_chg", 10, "INDUSTRY",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "call_chg=ts_zscore(ts_delta(implied_volatility_call_30,5),126);"
     "group_neutralize(group_rank(-call_chg,my_group),my_group)"),

    # 13. Put-call IV spread level (skew的另一种度量)
    ("OPT8_pc_spread", 10, "INDUSTRY",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "pc=ts_zscore(implied_volatility_put_30-implied_volatility_call_30,252);"
     "group_neutralize(group_rank(-pc,my_group),my_group)"),

    # 14. Parkinson term structure (30/90)
    ("OPT8_park_term", 10, "INDUSTRY",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "park_term=ts_zscore(parkinson_volatility_30/parkinson_volatility_90-1,252);"
     "group_neutralize(group_rank(-park_term,my_group),my_group)"),

    # 15. park_corr × park_chg × intraday (all parkinson, no IV corr)
    ("OPT8_park_triple", 10, "INDUSTRY",
     "my_group=bucket(rank(cap),range='0,1,0.1');"
     "park_corr=ts_corr(-parkinson_volatility_30,returns,63);"
     "park_chg=ts_zscore(ts_delta(parkinson_volatility_30,5),126);"
     "intra=ts_rank(-(close-open)/open,63);"
     "alpha=group_rank(park_corr,my_group)*group_rank(-park_chg,my_group)*group_rank(intra,my_group);"
     "group_neutralize(alpha,my_group)"),
]

SIM_PARAMS = {
    "type": "REGULAR",
    "settings": {
        "instrumentType": "EQUITY",
        "region": "USA",
        "universe": "TOP3000",
        "delay": 1,
        "decay": None,          # filled per alpha
        "neutralization": None, # filled per alpha
        "truncation": 0.08,
        "pasteurization": "ON",
        "unitHandling": "VERIFY",
        "nanHandling": "OFF",
        "language": "FASTEXPR",
        "visualization": False,
    }
}

def simulate(session, name, decay, neut, expr, idx, total):
    print(f"\n{'='*60}")
    print(f"▶ [{idx}/{total}] {name}  decay={decay} neut={neut}")
    params = json.loads(json.dumps(SIM_PARAMS))
    params["settings"]["decay"] = decay
    params["settings"]["neutralization"] = neut
    params["regular"] = expr

    r = session.post(f"{BASE}/simulations", json=params, timeout=30)
    print(f"  POST: {r.status_code} RA={r.headers.get('x-request-accounting','?')}")
    if r.status_code != 201:
        print(f"  ❌ 失败: {r.text[:200]}")
        return None

    loc = r.headers.get("Location", "")
    print(f"  Location: {loc}")

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
        msg = sd.get("message", "")
        print(f"  [{elapsed:4d}s] status='{status}' alpha={alpha_id} msg={msg}")
        if status == "COMPLETE":
            break
        if status in ("ERROR", "FAILED"):
            print(f"  ❌ 模拟失败: {msg}")
            return None
        if elapsed > 1200:
            print(f"  ⏰ 超时")
            return None

    if not alpha_id:
        print(f"  ❌ 无alpha_id")
        return None

    print(f"  ✅ alpha_id={alpha_id}")
    ar = session.get(f"{BASE}/alphas/{alpha_id}", timeout=30)
    ad = ar.json()
    is_d = ad.get("is") or {}
    sha = is_d.get("sharpe", "?")
    fit = is_d.get("fitness", "?")
    to  = is_d.get("turnover", "?")
    ret = is_d.get("returns", "?")
    print(f"  Sha={sha} Fit={fit} TO={to} Ret={ret}")
    checks = is_d.get("checks", [])
    check_str = " | ".join(
        f"{c['name']}={'✅' if c['result']=='PASS' else ('⏳' if c['result']=='PENDING' else '❌')}{c.get('value','')}"
        for c in checks
    )
    print(f"  Checks: {check_str}")
    return {"name": name, "id": alpha_id, "sharpe": sha, "fitness": fit,
            "turnover": to, "returns": ret, "checks": checks, "expr": expr}


def main():
    session = requests.Session()
    r = session.post(f"{BASE}/authentication",
                     auth=(EMAIL, PASSWORD), timeout=30)
    r.raise_for_status()
    print("✅ 认证成功")

    results = []
    total = len(ALPHAS)
    for i, (name, decay, neut, expr) in enumerate(ALPHAS, 1):
        res = simulate(session, name, decay, neut, expr, i, total)
        if res:
            results.append(res)
        time.sleep(3)

    print(f"\n{'='*60}")
    print(f"📊 R9 最终结果汇总")
    results.sort(key=lambda x: float(x["sharpe"]) if isinstance(x["sharpe"], (int, float, str)) and str(x["sharpe"]).replace('.','').replace('-','').isdigit() else -99, reverse=True)
    for r in results:
        n_pass = sum(1 for c in r["checks"] if c.get("result") == "PASS")
        n_total = len(r["checks"])
        print(f"  {r['name']}: Sha={r['sharpe']} Fit={r['fitness']} TO={r['turnover']} [{n_pass}/{n_total}] id={r['id']}")

    ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    os.makedirs(OUT_DIR, exist_ok=True)
    out_path = f"{OUT_DIR}/opt8_r9_final_{ts}.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    main()
