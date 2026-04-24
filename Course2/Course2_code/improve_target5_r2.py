#!/usr/bin/env python3
"""
Target5 R2 — T5_conc20 decay微调
T5_conc20_ind_d7: Sha=1.59 Fit=0.98 Sub=1.28 TO=0.2778 Ret/TO=0.380
需要 Ret/TO >= 0.396 (+4.2%), Sha >= 1.25
增加decay → 降低TO → 提高Ret/TO
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
}

# 核心: volume/ts_mean(20) 短期集中度 + 价格反转，按cap分组
CONC20 = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "alpha=rank(group_rank(ts_decay_linear(volume/ts_mean(volume,20),5),my_group)"
    "*group_rank(-ts_delta(close,5),my_group));"
    "group_neutralize(alpha,my_group)"
)

# 扩展窗口版：decay_linear(10)而非5 —— 平滑更多
CONC20_DL10 = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "alpha=rank(group_rank(ts_decay_linear(volume/ts_mean(volume,20),10),my_group)"
    "*group_rank(-ts_delta(close,5),my_group));"
    "group_neutralize(alpha,my_group)"
)

# ts_mean(40)替代ts_mean(20) —— 成交量均值更稳定
CONC40 = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "alpha=rank(group_rank(ts_decay_linear(volume/ts_mean(volume,40),10),my_group)"
    "*group_rank(-ts_delta(close,5),my_group));"
    "group_neutralize(alpha,my_group)"
)

# SUBINDUSTRY版本的conc20（更精细中性化）
CONC20_SUB = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "alpha=rank(group_rank(ts_decay_linear(volume/ts_mean(volume,20),5),my_group)"
    "*group_rank(-ts_delta(close,5),my_group));"
    "group_neutralize(alpha,my_group)"
)

VARIANTS = [
    # Primary: CONC20 decay扫描
    ("T5_conc20_ind_d9",   CONC20,      {**BASE_SETTINGS, "decay": 9}),
    ("T5_conc20_ind_d10",  CONC20,      {**BASE_SETTINGS, "decay": 10}),
    ("T5_conc20_ind_d12",  CONC20,      {**BASE_SETTINGS, "decay": 12}),
    # 更宽的ts_decay_linear窗口
    ("T5_conc20dl10_ind_d7",  CONC20_DL10, {**BASE_SETTINGS, "decay": 7}),
    ("T5_conc20dl10_ind_d9",  CONC20_DL10, {**BASE_SETTINGS, "decay": 9}),
    # ts_mean(40) 版本
    ("T5_conc40_ind_d7",   CONC40,      {**BASE_SETTINGS, "decay": 7}),
    # SUBINDUSTRY版
    ("T5_conc20_sub_d7",   CONC20_SUB,  {**BASE_SETTINGS, "decay": 7, "neutralization": "SUBINDUSTRY"}),
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
    print(f"  {'✅' if sha_ok else '❌'} Sha={sharpe:.2f}{'✅' if sha_ok else '❌'} "
          f"Fit={fitness:.2f}{'✅' if fit_ok else '❌'} Sub={sub_str}{'✅' if sub_ok else '❌'} "
          f"TO={turnover:.4f} Ret={returns:.4f} Ret/TO={ret_to:.3f}")
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
        print(f"  expr: {expr[:100]}...")
        print(f"  decay={settings.get('decay')} neut={settings.get('neutralization')}")
        loc = submit(session, expr, settings)
        if not loc:
            results[name] = {"error": "submit_failed", "expression": expr}; continue
        print(f"  Location: {loc}")
        data = poll(session, loc)
        r = extract(data, session)
        results[name] = ({**r, "expression": expr} if r else {"error": "no_result", "expression": expr})
        if idx < len(VARIANTS):
            print("\n--- 等待5秒 ---"); time.sleep(5)

    print("\n" + "="*80 + "\nTarget5 R2 汇总:")
    all_pass = []
    for name, r in results.items():
        if "sharpe" in r:
            flag = "  🎯 ALL PASS" if r.get("all_pass") else ""
            print(f"  {name}: Sha={r['sharpe']:.2f} Fit={r['fitness']:.2f} "
                  f"TO={r['turnover']:.4f} Ret={r['returns']:.4f} Ret/TO={r.get('ret_to',0):.3f}{flag}")
            if r.get("all_pass"): all_pass.append((name, r["id"]))
        else:
            print(f"  {name}: {r.get('error','unknown')}")
    if all_pass:
        print("\n🎉 找到通过的Alpha:")
        for name, aid in all_pass: print(f"  {name}: alpha_id={aid}")
    out = os.path.join(OUTDIR, f"target5_r2_{ts}.json")
    with open(out, "w") as f: json.dump(results, f, indent=2)
    print(f"\n💾 {out}")

if __name__ == "__main__":
    main()
