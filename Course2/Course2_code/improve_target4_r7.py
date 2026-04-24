#!/usr/bin/env python3
"""
Target4 crowding-reversal R7
=================================
R6 breakthroughs:
  T4_dolvol_subind_d40: Sha=1.25✅ Fit=0.86 TO=0.2228 Ret/TO=0.472  ← new record
  T4_dolvol_z252_subind_d10: Sha=1.50✅ Fit=0.79 TO=0.3948

Key insight: dolvol_subind Sha is PLATEAUING at 1.25 from d30→d40 (no further drop!)
             while Ret/TO keeps improving with decay.

Fit = Sha × sqrt(Ret/TO) ≥ 1.0
At d40: 1.25 × sqrt(0.472) = 0.859 ← need sqrt(Ret/TO) ≥ 0.80
Need Ret/TO ≥ 0.64 → if Ret≈0.105, need TO ≤ 0.164

Extrapolated trend (dolvol_subind):
  d40: TO=0.2228, Ret/TO=0.472  → Fit=0.86
  d50: TO≈0.195,  Ret/TO≈0.538  → Fit≈0.916
  d60: TO≈0.175,  Ret/TO≈0.600  → Fit≈0.968
  d70: TO≈0.165,  Ret/TO≈0.636  → Fit≈0.996
  d80: TO≈0.155,  Ret/TO≈0.677  → Fit≈1.028 ← potential ALL PASS!

Also: dolvol_z252_subind at d10 gave Sha=1.50 (best Sha in R6)
      Pushing z252 to d30/d40/d50 could combine high Sha + good Ret/TO

R7 strategy:
  Group A: dolvol + SUBINDUSTRY + d50/d60/d70/d80  (extreme decay sweep)
  Group B: dolvol_z252 + SUBINDUSTRY + d30/d40/d50  (high-Sha signal + heavy decay)
  Group C: dolvol + SUBINDUSTRY + d40 with different price lookback p5/p10
"""
import json
import os
import time

import requests


CREDENTIALS = ("xxxxxx@example.com", "xxxxxx")
BASE = "https://api.worldquantbrain.com"
OUTDIR = "/Users/zhiqu/Desktop/brain/Course2/Course2_code/outputs"
os.makedirs(OUTDIR, exist_ok=True)

BASE_SETTINGS = {
    "instrumentType": "EQUITY",
    "region": "USA",
    "universe": "TOP3000",
    "delay": 1,
    "neutralization": "INDUSTRY",
    "truncation": 0.08,
    "pasteurization": "ON",
    "unitHandling": "VERIFY",
    "nanHandling": "ON",
    "language": "FASTEXPR",
    "visualization": False,
}

SUBIND = {**BASE_SETTINGS, "neutralization": "SUBINDUSTRY"}

DOLVOL = "rank(ts_zscore(ts_delta(volume * close, 5), 126)) * -rank(ts_delta(close, 3))"
DOLVOL_P5 = "rank(ts_zscore(ts_delta(volume * close, 5), 126)) * -rank(ts_delta(close, 5))"
DOLVOL_P10 = "rank(ts_zscore(ts_delta(volume * close, 5), 126)) * -rank(ts_delta(close, 10))"
DOLVOL_Z252 = "rank(ts_zscore(ts_delta(volume * close, 5), 252)) * -rank(ts_delta(close, 3))"

VARIANTS = [
    # Group A: extreme decay — following the Ret/TO improvement trend
    (
        "T4_dolvol_subind_d50",
        DOLVOL,
        {**SUBIND, "decay": 50},
    ),
    (
        "T4_dolvol_subind_d60",
        DOLVOL,
        {**SUBIND, "decay": 60},
    ),
    (
        "T4_dolvol_subind_d70",
        DOLVOL,
        {**SUBIND, "decay": 70},
    ),
    (
        "T4_dolvol_subind_d80",
        DOLVOL,
        {**SUBIND, "decay": 80},
    ),
    # Group B: dolvol_z252 + heavy decay (Sha=1.50 at d10, most promising Sha)
    (
        "T4_dolvol_z252_subind_d30",
        DOLVOL_Z252,
        {**SUBIND, "decay": 30},
    ),
    (
        "T4_dolvol_z252_subind_d40",
        DOLVOL_Z252,
        {**SUBIND, "decay": 40},
    ),
    (
        "T4_dolvol_z252_subind_d50",
        DOLVOL_Z252,
        {**SUBIND, "decay": 50},
    ),
    # Group C: dolvol_subind_d40 with different price reversal lookback
    (
        "T4_dolvol_subind_d40_p5",
        DOLVOL_P5,
        {**SUBIND, "decay": 40},
    ),
    (
        "T4_dolvol_subind_d40_p10",
        DOLVOL_P10,
        {**SUBIND, "decay": 40},
    ),
    # Group D: dolvol_z252 + d60 (pushing further if B looks good)
    (
        "T4_dolvol_z252_subind_d60",
        DOLVOL_Z252,
        {**SUBIND, "decay": 60},
    ),
]


def authenticate(session: requests.Session) -> None:
    response = session.post(f"{BASE}/authentication", auth=CREDENTIALS, timeout=30)
    response.raise_for_status()
    print("✅ 认证成功")


def submit(session: requests.Session, expression: str, settings: dict) -> str | None:
    for _ in range(10):
        try:
            response = session.post(
                f"{BASE}/simulations",
                json={"type": "REGULAR", "settings": settings, "regular": expression},
                timeout=60,
            )
        except requests.exceptions.Timeout:
            print("  POST超时, 重试...")
            time.sleep(10)
            authenticate(session)
            continue
        except Exception as error:
            print(f"  POST异常: {error}, 重试...")
            time.sleep(10)
            continue

        print(f"  POST: {response.status_code} RA={response.headers.get('Retry-After')}")
        if response.status_code == 429:
            wait = int(float(response.headers.get("Retry-After", 30))) + 5
            print(f"  限流, 等 {wait}s")
            time.sleep(wait)
            continue
        if response.status_code >= 400:
            print(f"  错误: {response.status_code} {response.text[:300]}")
            return None
        return response.headers.get("Location")
    return None


def poll(session: requests.Session, location: str) -> dict:
    start = time.time()
    while time.time() - start < 420:
        try:
            response = session.get(location, timeout=30)
        except Exception as error:
            print(f"  GET error: {error}")
            time.sleep(10)
            authenticate(session)
            continue

        if response.status_code == 429:
            wait = int(float(response.headers.get("Retry-After", 30))) + 5
            print(f"  GET限流, 等 {wait}s")
            time.sleep(wait)
            continue

        try:
            data = response.json()
        except Exception:
            data = {}
        if not isinstance(data, dict):
            data = {}
        elapsed = int(time.time() - start)
        raw_alpha = data.get("alpha")
        if isinstance(raw_alpha, dict):
            alpha_id = raw_alpha.get("id")
        elif isinstance(raw_alpha, str) and raw_alpha:
            alpha_id = raw_alpha
        else:
            alpha_id = None
        ra = response.headers.get("Retry-After", "?")
        print(f"  [{elapsed}s] HTTP={response.status_code} RA={ra} alpha={alpha_id}")

        if alpha_id:
            return data
        if data.get("status") in ("ERROR", "FAILED"):
            print(f"  模拟失败: {data}")
            return {}

        wait = max(5, min(30, int(float(ra)) if ra != "?" else 30))
        time.sleep(wait)
    print("  ⏰ 超时 (7min)")
    return {}


def extract(data: dict, session: requests.Session) -> dict | None:
    raw_alpha = data.get("alpha")
    if not raw_alpha:
        return None
    # alpha can be a string (ID only) or a full dict
    if isinstance(raw_alpha, str):
        alpha_id = raw_alpha
        # fetch full alpha data from API
        try:
            resp = session.get(f"{BASE}/alphas/{alpha_id}", timeout=30)
            alpha = resp.json() if isinstance(resp.json(), dict) else {}
        except Exception:
            alpha = {}
    else:
        alpha = raw_alpha
    if not alpha:
        return None
    stats = {s["name"]: s["value"] for s in alpha.get("stats", [])}
    sharpe = stats.get("sharpe")
    fitness = stats.get("fitness")
    turnover = stats.get("turnover")
    returns = stats.get("returns")
    sub_sharpe = stats.get("sub_sharpe")

    if sharpe is None:
        return None

    sha_ok = sharpe >= 1.25
    fit_ok = fitness >= 1.0
    sub_ok = sub_sharpe is None or sub_sharpe >= 0.5

    print(
        f"  {'✅' if sha_ok else '❌'} Sha={sharpe:.2f}{'✅' if sha_ok else '❌'} "
        f"Fit={fitness:.2f}{'✅' if fit_ok else '❌'} "
        f"Sub={sub_sharpe:.2f if sub_sharpe else 'N/A'}{'✅' if sub_ok else '❌'}"
        f"(cut=?) TO={turnover:.4f} Ret={returns:.4f}"
    )

    if sha_ok and fit_ok and sub_ok:
        print(f"  🎯🎯🎯 ALL PASS! alpha_id={alpha.get('id')}")

    return {
        "id": alpha.get("id"),
        "sharpe": sharpe,
        "fitness": fitness,
        "turnover": turnover,
        "returns": returns,
        "sub_sharpe": sub_sharpe,
        "sha_ok": sha_ok,
        "fit_ok": fit_ok,
        "sub_ok": sub_ok,
        "all_pass": sha_ok and fit_ok and sub_ok,
    }


def main():
    timestamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    results = {}
    session = requests.Session()
    authenticate(session)

    for idx, (name, expr, settings) in enumerate(VARIANTS, 1):
        print(f"\n[{idx}/{len(VARIANTS)}] {name}")
        print(f"  expr: {expr[:80]}...")
        location = submit(session, expr, settings)
        if not location:
            print(f"  提交失败")
            results[name] = {"error": "submit_failed"}
            continue
        print(f"  Location: {location}")

        data = poll(session, location)
        result = extract(data, session)
        if result:
            results[name] = {**result, "expression": expr, "settings": settings}
        else:
            results[name] = {"error": "no_result", "expression": expr}

        if idx < len(VARIANTS):
            print(f"\n--- 等待5秒避免限流 ---")
            time.sleep(5)

    # Summary
    print("\n" + "=" * 80)
    print("Target4 R7 汇总:")
    all_pass_list = []
    for name, r in results.items():
        if "sharpe" in r:
            flag = "🎯 ALL PASS" if r.get("all_pass") else ""
            sub_str = f"Sub=P({r['sub_sharpe']:.2f})" if r.get("sub_sharpe") else "Sub=N/A"
            print(
                f"  {name}: Sha={r['sharpe']:.2f} Fit={r['fitness']:.2f} "
                f"TO={r['turnover']:.4f} Ret={r['returns']:.4f} {sub_str} {flag}"
            )
            if r.get("all_pass"):
                all_pass_list.append((name, r["id"]))
        else:
            print(f"  {name}: {r.get('error', 'unknown')}")

    if all_pass_list:
        print("\n🎉 找到通过的Alpha:")
        for name, aid in all_pass_list:
            print(f"  {name}: alpha_id={aid}")

    out_path = os.path.join(OUTDIR, f"target4_r7_{timestamp}.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 {out_path}")


if __name__ == "__main__":
    main()
