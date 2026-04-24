#!/usr/bin/env python3
"""
Target4 crowding-reversal R15
=================================
R14 FINDINGS: INDUSTRY neut (Sha=1.14), ts_rank (Sha=1.24), V3Z (Sha=1.26) — all worse than V3.
V3 SUBINDUSTRY d63 remains uniquely superior at Sha=1.28, Fit=0.98.

CORE PROBLEM: Fit ceiling at ~0.98. Need Ret/TO to go from 0.582 → 0.610.
Current: TO=0.1999, Ret=0.1163 → Ret/TO=0.582
Need:   TO=0.1880 (with same Ret) OR Ret=0.1225 (with same TO)

TWO NEW UNTESTED DIMENSIONS:

1. TRUNCATION REDUCTION (Group A):
   Current truncation=0.08 means max position weight 8%.
   Lowering to 0.04/0.05/0.06 means:
   - Extreme positions get cut more → portfolio rebalances less → lower TO
   - Returns drop slightly (extreme high-signal positions are capped)
   - But TO drops MORE than Ret (extreme positions generate noise/trading costs,
     not proportional alpha) → Ret/TO ratio improves
   
   This is a STRUCTURAL parameter change, not signal change.
   Prediction: Sha stays ~1.28, TO drops from 0.20 to ~0.15-0.17, Ret drops to ~0.10-0.11
   → Ret/TO could reach 0.65+ → Fit = 1.28 × √0.65 = 1.03 ✓

2. trade_when EVENT FILTER (Group B):
   trade_when(condition, V3_signal, -1) = hold position when no event
   Key insight from reduce_turnover.md: wasteful turnover occurs when signal 
   changes slightly but still forces a trade. trade_when holds until event fires.
   
   Event: significant volume shock — top quintile of absolute volume change
   trade_when(rank(abs(ts_delta(volume*close,3))) > 0.8, V3_signal, -1)
   
   This should:
   - Reduce TO by ~40-60% (only trade on top 20% volume events)
   - Keep similar Ret (these are the strongest alpha periods)
   → Ret/TO improves dramatically

3. TOP2000 universe (Group C):
   Smaller, more liquid universe — different signal characteristics.
   Hypothesis: in top 2000, signal may be cleaner → better Sha AND lower TO.
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
    "neutralization": "SUBINDUSTRY",
    "truncation": 0.08,
    "pasteurization": "ON",
    "unitHandling": "VERIFY",
    "nanHandling": "ON",
    "language": "FASTEXPR",
    "visualization": False,
}

V3 = "rank(ts_zscore(ts_delta(volume * close, 3), 126)) * -rank(ts_delta(close, 3))"

# Group B: trade_when event filter — trade only on top-quintile volume shocks
V3_TW = "trade_when(rank(abs(ts_delta(volume * close, 3))) > 0.8, rank(ts_zscore(ts_delta(volume * close, 3), 126)) * -rank(ts_delta(close, 3)), -1)"

VARIANTS = [
    # Group A: truncation sweep with V3 d63 SUBINDUSTRY
    # This is the most promising: lower truncation → less extreme rebalancing → lower TO
    ("T4_V3_trunc004_d63",  V3,  {**BASE_SETTINGS, "decay": 63, "truncation": 0.04}),
    ("T4_V3_trunc005_d63",  V3,  {**BASE_SETTINGS, "decay": 63, "truncation": 0.05}),
    ("T4_V3_trunc006_d63",  V3,  {**BASE_SETTINGS, "decay": 63, "truncation": 0.06}),

    # Also try truncation with d65 (next best decay)
    ("T4_V3_trunc004_d65",  V3,  {**BASE_SETTINGS, "decay": 65, "truncation": 0.04}),
    ("T4_V3_trunc005_d65",  V3,  {**BASE_SETTINGS, "decay": 65, "truncation": 0.05}),
    ("T4_V3_trunc006_d65",  V3,  {**BASE_SETTINGS, "decay": 65, "truncation": 0.06}),

    # Group B: trade_when event filter
    # Hold when no significant volume event — dramatically reduces turnover
    ("T4_V3_tradewhen_d63",  V3_TW, {**BASE_SETTINGS, "decay": 63}),
    ("T4_V3_tradewhen_d65",  V3_TW, {**BASE_SETTINGS, "decay": 65}),

    # Group C: TOP2000 universe with V3 d63/d65
    ("T4_V3_top2000_d63",  V3,  {**BASE_SETTINGS, "decay": 63, "universe": "TOP2000"}),
    ("T4_V3_top2000_d65",  V3,  {**BASE_SETTINGS, "decay": 65, "universe": "TOP2000"}),
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
            time.sleep(15)
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
    while time.time() - start < 600:
        try:
            response = session.get(location, timeout=45)
        except Exception as error:
            print(f"  GET error: {error}")
            time.sleep(15)
            try:
                authenticate(session)
            except Exception:
                time.sleep(30)
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
    print("  ⏰ 超时 (10min)")
    return {}


def extract(data: dict, session: requests.Session) -> dict | None:
    raw_alpha = data.get("alpha")
    if not raw_alpha:
        return None

    if isinstance(raw_alpha, dict):
        alpha = raw_alpha
        alpha_id = alpha.get("id")
    elif isinstance(raw_alpha, str):
        alpha_id = raw_alpha
        alpha = {}
        for attempt in range(5):
            try:
                resp = session.get(f"{BASE}/alphas/{alpha_id}", timeout=45)
                if resp.status_code == 429:
                    wait = int(float(resp.headers.get("Retry-After", 30))) + 5
                    print(f"  fetch限流, 等 {wait}s")
                    time.sleep(wait)
                    continue
                alpha = resp.json() if isinstance(resp.json(), dict) else {}
                break
            except Exception:
                time.sleep(15)
    else:
        return None

    stats_list = alpha.get("stats", [])
    if stats_list:
        stats = {s["name"]: s["value"] for s in stats_list}
    else:
        is_data = alpha.get("is", {})
        stats = {
            "sharpe": is_data.get("sharpe"),
            "fitness": is_data.get("fitness"),
            "turnover": is_data.get("turnover"),
            "returns": is_data.get("returns"),
        }
        for c in is_data.get("checks", []):
            if c["name"] == "LOW_SUB_UNIVERSE_SHARPE":
                stats["sub_sharpe"] = c.get("value")

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
    ret_to = returns / turnover if turnover else 0
    sub_str = f"{sub_sharpe:.2f}" if sub_sharpe is not None else "N/A"

    print(
        f"  {'✅' if sha_ok else '❌'} Sha={sharpe:.2f}{'✅' if sha_ok else '❌'} "
        f"Fit={fitness:.2f}{'✅' if fit_ok else '❌'} "
        f"Sub={sub_str}{'✅' if sub_ok else '❌'} "
        f"TO={turnover:.4f} Ret={returns:.4f} Ret/TO={ret_to:.3f}"
    )

    if sha_ok and fit_ok and sub_ok:
        print(f"  🎯🎯🎯 ALL PASS! alpha_id={alpha_id}")

    return {
        "id": alpha_id,
        "sharpe": sharpe,
        "fitness": fitness,
        "turnover": turnover,
        "returns": returns,
        "sub_sharpe": sub_sharpe,
        "ret_to": ret_to,
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
        print(f"  expr: {expr[:90]}...")
        print(f"  decay={settings.get('decay')} trunc={settings.get('truncation')} "
              f"neut={settings.get('neutralization')} univ={settings.get('universe')}")
        location = submit(session, expr, settings)
        if not location:
            print(f"  提交失败")
            results[name] = {"error": "submit_failed"}
            continue
        print(f"  Location: {location}")

        data = poll(session, location)
        result = extract(data, session)
        if result:
            results[name] = {**result, "expression": expr}
        else:
            results[name] = {"error": "no_result", "expression": expr}

        if idx < len(VARIANTS):
            print(f"\n--- 等待5秒避免限流 ---")
            time.sleep(5)

    print("\n" + "=" * 80)
    print("Target4 R15 汇总:")
    all_pass_list = []
    for name, r in results.items():
        if "sharpe" in r:
            flag = "  🎯 ALL PASS" if r.get("all_pass") else ""
            print(
                f"  {name}: Sha={r['sharpe']:.2f} Fit={r['fitness']:.2f} "
                f"TO={r['turnover']:.4f} Ret={r['returns']:.4f} Ret/TO={r.get('ret_to', 0):.3f}{flag}"
            )
            if r.get("all_pass"):
                all_pass_list.append((name, r["id"]))
        else:
            print(f"  {name}: {r.get('error', 'unknown')}")

    if all_pass_list:
        print("\n🎉 找到通过的Alpha:")
        for name, aid in all_pass_list:
            print(f"  {name}: alpha_id={aid}")

    out_path = os.path.join(OUTDIR, f"target4_r15_{timestamp}.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 {out_path}")


if __name__ == "__main__":
    main()
