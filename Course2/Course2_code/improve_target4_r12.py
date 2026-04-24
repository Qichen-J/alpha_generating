#!/usr/bin/env python3
"""
Target4 crowding-reversal R12
=================================
R11 KEY DISCOVERY: V3 (volume delta=3) is a BREAKTHROUGH!
  V3 = rank(ts_zscore(ts_delta(volume*close, 3), 126)) * -rank(ts_delta(close, 3))
  
  V3 d63: Sha=1.28✅, Fit=0.98❌, TO=0.1999, Ret=0.1163, Ret/TO=0.582
  V5 d63: Sha=1.25✅, Fit=0.96❌, TO=0.1904, Ret=0.1121, Ret/TO=0.589
  
  V3 has HIGHER Sha (1.28 vs 1.25) and HIGHER Fit (0.98 vs 0.96)!
  The Sha buffer of 1.28 vs 1.25 gives MORE room to push decay.

  For Fit=1.0 at Sha=1.28: need Ret/TO ≥ (1.0/1.28)² = 0.6104
  V3 extrapolation (Δ=0.0036/day): need ~7-8 more days → d70-d71

  V3 Ret/TO progression:
    d60: 0.5709
    d63: 0.5818  Δ=0.0036/day

  Projected:
    d70: ~0.607  Fit = 1.28*√0.607 ≈ 0.997 (borderline)
    d71: ~0.610  Fit = 1.28*√0.610 ≈ 0.999
    d72: ~0.614  Fit = 1.28*√0.614 ≈ 1.003  ← ALL PASS if Sha holds!

  Critical unknown: does V3 Sha hold at 1.28 as decay increases?
  V5 Sha was stable from d40→d64, then dropped at d65.
  V3 might have a different cliff point.

R12 plan:
  Group A: V3 decay push d65/d67/d70/d72/d75 — find Sha cliff + Fit≥1.0
  Group B: V3_VZ63 (V3 signal with volume z-window=63) d63/d65/d68
           — if z=63 allows Sha to stay higher at more decay
  Group C: VZ63 d65/d68 — push the other strong signal
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

# V3: volume delta=3, z=126 — NEW BEST SIGNAL
V3    = "rank(ts_zscore(ts_delta(volume * close, 3), 126)) * -rank(ts_delta(close, 3))"
# V3_VZ63: same V3 signal but with z-window=63 on volume leg
V3VZ63 = "rank(ts_zscore(ts_delta(volume * close, 3), 63)) * -rank(ts_delta(close, 3))"
# VZ63: original V5 with z=63 on volume leg
VZ63  = "rank(ts_zscore(ts_delta(volume * close, 5), 63)) * -rank(ts_delta(close, 3))"

VARIANTS = [
    # Group A: V3 decay sweep — PRIMARY BET
    # Sha=1.28 at d63. Need Ret/TO≥0.61 → predict d70-d72 hits ALL PASS
    ("T4_V3_subind_d65",  V3,    {**SUBIND, "decay": 65}),
    ("T4_V3_subind_d67",  V3,    {**SUBIND, "decay": 67}),
    ("T4_V3_subind_d70",  V3,    {**SUBIND, "decay": 70}),
    ("T4_V3_subind_d72",  V3,    {**SUBIND, "decay": 72}),
    ("T4_V3_subind_d75",  V3,    {**SUBIND, "decay": 75}),
    # Group B: V3 with shorter volume z-window
    ("T4_V3VZ63_subind_d63", V3VZ63, {**SUBIND, "decay": 63}),
    ("T4_V3VZ63_subind_d65", V3VZ63, {**SUBIND, "decay": 65}),
    ("T4_V3VZ63_subind_d68", V3VZ63, {**SUBIND, "decay": 68}),
    # Group C: VZ63 continued push
    ("T4_VZ63_subind_d65", VZ63, {**SUBIND, "decay": 65}),
    ("T4_VZ63_subind_d68", VZ63, {**SUBIND, "decay": 68}),
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
    while time.time() - start < 480:
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
    print("  ⏰ 超时 (8min)")
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
        print(f"  decay={settings.get('decay')} neut={settings.get('neutralization')}")
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
    print("Target4 R12 汇总:")
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

    out_path = os.path.join(OUTDIR, f"target4_r12_{timestamp}.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 {out_path}")


if __name__ == "__main__":
    main()
