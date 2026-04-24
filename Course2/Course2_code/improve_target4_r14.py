#!/usr/bin/env python3
"""
Target4 crowding-reversal R14
=================================
R13 FINDINGS: All alternative signal structures (V1/V2/VWAP/RAW) gave Sha≤1.22.
  V3 (volume*close delta=3) remains uniquely superior — the close multiplication
  is critical for the Sha=1.28 advantage.

ROOT CAUSE ANALYSIS:
  V3 d63: Sha=1.28, Ret/TO=0.582 → Fit = 1.28 × √0.582 = 0.977
  Target:  Fit ≥ 1.00
  
  Two paths to breakthrough:
  (A) Sha ≥ 1.30 with current Ret/TO=0.582  → Fit = 1.30 × √0.582 = 0.992... not enough
      Actually need: Sha ≥ 1.0/√0.582 = 1.310  
  (B) Ret/TO ≥ 0.610 with current Sha=1.28   → Fit = 1.28 × √0.610 = 1.000 ✓
  (C) Both improve slightly

R14 THREE UNTESTED DIMENSIONS:

1. INDUSTRY neutralization (Group A):
   All previous rounds used SUBINDUSTRY — strict peer-group comparison.
   INDUSTRY is coarser (fewer groups ~24 vs ~69 sub-industries).
   Hypothesis: INDUSTRY allows the signal more cross-group expression,
   potentially raising Sha OR improving Ret/TO ratio.
   Testing V3 at d55/d60/d63/d65 with INDUSTRY neutralization.

2. Z-scored reversal leg (Group B):
   Current: V3 = rank(ts_zscore(vol*close,3),126)) * -rank(ts_delta(close,3))
   New V3Z:  rank(ts_zscore(ts_delta(vol*close,3),126)) * rank(ts_zscore(-ts_delta(close,3),126))
   Hypothesis: z-scoring the reversal leg normalizes its distribution,
   potentially reducing noise in the reversal component → better Ret quality.
   Testing V3Z at d60/d63/d65.

3. ts_rank instead of ts_zscore for volume leg (Group C):
   Current: ts_zscore(ts_delta(vol*close,3), 126) — z-score gives [-inf, +inf]
   New V3TR: ts_rank(ts_delta(vol*close,3), 126) — rank gives [0, 1], bounded
   Hypothesis: Different distributional assumption → different Sha/Fit structure.
   Testing V3TR at d60/d63.
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
    "truncation": 0.08,
    "pasteurization": "ON",
    "unitHandling": "VERIFY",
    "nanHandling": "ON",
    "language": "FASTEXPR",
    "visualization": False,
}

SUBIND   = {**BASE_SETTINGS, "neutralization": "SUBINDUSTRY"}
INDUSTRY = {**BASE_SETTINGS, "neutralization": "INDUSTRY"}

# Core V3 signal (best so far: Sha=1.28 at d63 with SUBINDUSTRY)
V3   = "rank(ts_zscore(ts_delta(volume * close, 3), 126)) * -rank(ts_delta(close, 3))"

# Group B: z-scored reversal leg
V3Z  = "rank(ts_zscore(ts_delta(volume * close, 3), 126)) * rank(ts_zscore(-ts_delta(close, 3), 126))"

# Group C: ts_rank instead of ts_zscore
V3TR = "rank(ts_rank(ts_delta(volume * close, 3), 126)) * -rank(ts_delta(close, 3))"

VARIANTS = [
    # Group A: V3 with INDUSTRY neutralization
    # Less granular grouping → signal has broader cross-group freedom
    ("T4_V3_indus_d55",  V3,   {**INDUSTRY, "decay": 55}),
    ("T4_V3_indus_d60",  V3,   {**INDUSTRY, "decay": 60}),
    ("T4_V3_indus_d63",  V3,   {**INDUSTRY, "decay": 63}),
    ("T4_V3_indus_d65",  V3,   {**INDUSTRY, "decay": 65}),

    # Group B: z-scored reversal leg, SUBINDUSTRY
    # Normalizes both legs uniformly
    ("T4_V3Z_subind_d60",  V3Z,  {**SUBIND, "decay": 60}),
    ("T4_V3Z_subind_d63",  V3Z,  {**SUBIND, "decay": 63}),
    ("T4_V3Z_subind_d65",  V3Z,  {**SUBIND, "decay": 65}),

    # Group C: ts_rank instead of ts_zscore, SUBINDUSTRY
    # Bounded signal distribution (0-1) instead of unbounded z-scores
    ("T4_V3TR_subind_d60",  V3TR, {**SUBIND, "decay": 60}),
    ("T4_V3TR_subind_d63",  V3TR, {**SUBIND, "decay": 63}),
    ("T4_V3TR_subind_d65",  V3TR, {**SUBIND, "decay": 65}),
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
    print("Target4 R14 汇总:")
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

    out_path = os.path.join(OUTDIR, f"target4_r14_{timestamp}.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 {out_path}")


if __name__ == "__main__":
    main()
