#!/usr/bin/env python3
"""
Target4 crowding-reversal R11
=================================
R10 key findings (devastating):
  - close_delta=5: Sha drops from 1.25 → 1.05. Original close=3 is optimal.
  - close_delta=7: even worse, Sha=0.94
  - TOP1000: completely wrong universe for this signal, Sha=0.65

Current best (still): d64: Sha=1.25✅, Fit=0.96❌, Ret/TO=0.593
Need: Ret/TO ≥ 0.64 to achieve Fit=1.0 (need ~7.9% TO reduction)

All exhausted:
  - decay: maxed at d64 (d65 → Sha drops to 1.24)
  - z-window: z252 is worse, z126 is optimal
  - volume lookback: v10 terrible, v5 optimal
  - close lookback: c3 is optimal, c5/c7 kill Sha
  - truncation: no effect
  - universe: TOP3000 optimal

R11 KEY NEW IDEA: Normalize the close reversal leg
  Current:  -rank(ts_delta(close, 3))     ← raw price delta, very noisy, high TO
  New idea: -rank(ts_zscore(ts_delta(close, 3), N))  ← z-scored → stable signal → lower TO
  
  z-scoring the reversal captures: "is this 3-day return high/low RELATIVE TO recent history?"
  → less affected by daily market-level moves
  → signal changes less from day to day → positions flip less → LOWER TO
  → Sha should stay ~1.25 since we're improving signal quality

Also test: shorter z-window on volume leg (z=63 for more "fresh" signal),
and shorter volume delta (v3=ts_delta(volume*close,3)) to explore new optima.
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

# Group A: z-score the close reversal leg (PRIMARY BET)
# Current: rank(ts_zscore(ts_delta(vol*close,5),126)) * -rank(ts_delta(close,3))
# New:     rank(ts_zscore(ts_delta(vol*close,5),126)) * -rank(ts_zscore(ts_delta(close,3), N))
# Normalizing close reversal → more stable signal → lower TO → higher Fit
CZ_21 = "rank(ts_zscore(ts_delta(volume * close, 5), 126)) * -rank(ts_zscore(ts_delta(close, 3), 21))"
CZ_63 = "rank(ts_zscore(ts_delta(volume * close, 5), 126)) * -rank(ts_zscore(ts_delta(close, 3), 63))"

# Group B: shorter z-window on volume leg (z=63 instead of z=126)
# More "fresh" normalization — different signal character, might maintain Sha at higher decay
VZ63 = "rank(ts_zscore(ts_delta(volume * close, 5), 63)) * -rank(ts_delta(close, 3))"

# Group C: shorter volume delta (v3)
# ts_delta lookback=3 instead of 5 — shorter-term volume crowding signal
V3 = "rank(ts_zscore(ts_delta(volume * close, 3), 126)) * -rank(ts_delta(close, 3))"

VARIANTS = [
    # Group A: CZ21 — close z-scored over 21 days (1-month normalization)
    ("T4_CZ21_subind_d60", CZ_21, {**SUBIND, "decay": 60}),
    ("T4_CZ21_subind_d63", CZ_21, {**SUBIND, "decay": 63}),
    ("T4_CZ21_subind_d64", CZ_21, {**SUBIND, "decay": 64}),

    # Group A: CZ63 — close z-scored over 63 days (3-month normalization, even smoother)
    ("T4_CZ63_subind_d60", CZ_63, {**SUBIND, "decay": 60}),
    ("T4_CZ63_subind_d63", CZ_63, {**SUBIND, "decay": 63}),

    # Group B: shorter volume z-window (z=63)
    ("T4_VZ63_subind_d55", VZ63, {**SUBIND, "decay": 55}),
    ("T4_VZ63_subind_d60", VZ63, {**SUBIND, "decay": 60}),
    ("T4_VZ63_subind_d63", VZ63, {**SUBIND, "decay": 63}),

    # Group C: volume delta=3 (shorter-term volume crowding)
    ("T4_V3_subind_d60",   V3,   {**SUBIND, "decay": 60}),
    ("T4_V3_subind_d63",   V3,   {**SUBIND, "decay": 63}),
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
    print("Target4 R11 汇总:")
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

    out_path = os.path.join(OUTDIR, f"target4_r11_{timestamp}.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 {out_path}")


if __name__ == "__main__":
    main()
