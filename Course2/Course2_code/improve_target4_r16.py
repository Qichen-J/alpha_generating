#!/usr/bin/env python3
"""
Target4 crowding-reversal R16
=================================
R15 FINAL CONFIRMATION: truncation has ZERO effect (TO stays exactly 0.1999 for all trunc values).
This means V3's positions are all well below 4% weight — truncation is completely inactive.
trade_when destroyed the signal (Sha=-0.10). TOP2000 universe collapsed (Sha=0.80).

EXHAUSTIVE PARAMETER SPACE SUMMARY:
  - Decay: d40-d75 fully explored → V3 d63 is optimal
  - Signal delta window: 1,2,3,5,7 → 3 is uniquely best
  - z-score window: 63, 126 → 126 is best
  - Neutralization: MARKET, INDUSTRY, SUBINDUSTRY → SUBINDUSTRY is best
  - Truncation: 0.04-0.08 → no effect
  - Universe: TOP2000, TOP3000 → TOP3000 is best
  - Alternative signals: VWAP, RAW, REL → all worse

REMAINING UNEXPLORED: SIGNAL INTERNAL STRUCTURE
The formula is: rank(ts_zscore(ts_delta(volume*close, 3), 126)) * -rank(ts_delta(close, 3))
                         └─── volume leg ───┘               └─── reversal leg ───┘

Three structural changes that haven't been tried:

1. ts_SUM instead of ts_DELTA for volume leg (Group A)
   ts_delta = (vol*close)[t] - (vol*close)[t-3]  ← "acceleration of volume activity"
   ts_sum   = (vol*close)[t] + [t-1] + [t-2]     ← "total dollar volume flow in 3 days"
   
   Different market microstructure hypothesis:
   ts_delta → abnormal SURGE in daily volume (vs 3 days ago)
   ts_sum   → abnormal SUSTAINED volume over 3 days
   
   ts_sum changes more slowly (each day, only the oldest day drops off)
   → potentially more stable signal → lower TO or different Sha structure

2. Longer z-score normalization window = 252 (Group B)
   Currently 126 = 6-month lookback for historical percentile
   252 = 1-year lookback for historical percentile
   
   Longer window = more stable historical mean/std → more stable z-scores
   → potentially less rank flipping day-to-day → lower TO
   Also: captures full-year seasonality in volume patterns

3. Smoothed z-score before ranking (Group C)
   Current: rank(ts_zscore(ts_delta(vc,3), 126)) — rank daily z-score
   New:     rank(ts_mean(ts_zscore(ts_delta(vc,3), 126), 3)) — rank 3-day avg z-score
   
   By averaging the z-score over 3 days BEFORE ranking:
   - Day-to-day z-score noise is smoothed out
   - The rank() applied to the smoothed value changes less often
   → potentially significant TO reduction with minimal signal degradation
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

SUBIND = {**BASE_SETTINGS}

# Group A: ts_sum variant (total 3-day dollar volume flow)
VSUM = "rank(ts_zscore(ts_sum(volume * close, 3), 126)) * -rank(ts_delta(close, 3))"

# Group B: z-score window 252 (full-year normalization)
VZ252 = "rank(ts_zscore(ts_delta(volume * close, 3), 252)) * -rank(ts_delta(close, 3))"

# Also try z-score 189 (9-month) as intermediate between 126 and 252
VZ189 = "rank(ts_zscore(ts_delta(volume * close, 3), 189)) * -rank(ts_delta(close, 3))"

# Group C: smoothed z-score (3-day average of z-score before ranking)
SMVZ3 = "rank(ts_mean(ts_zscore(ts_delta(volume * close, 3), 126), 3)) * -rank(ts_delta(close, 3))"

# Also try 5-day smoothing
SMVZ5 = "rank(ts_mean(ts_zscore(ts_delta(volume * close, 3), 126), 5)) * -rank(ts_delta(close, 3))"

VARIANTS = [
    # Group A: ts_sum
    ("T4_VSUM_subind_d55",  VSUM,  {**SUBIND, "decay": 55}),
    ("T4_VSUM_subind_d60",  VSUM,  {**SUBIND, "decay": 60}),
    ("T4_VSUM_subind_d63",  VSUM,  {**SUBIND, "decay": 63}),

    # Group B: z-score window 252
    ("T4_VZ252_subind_d60",  VZ252,  {**SUBIND, "decay": 60}),
    ("T4_VZ252_subind_d63",  VZ252,  {**SUBIND, "decay": 63}),

    # Group B2: z-score window 189
    ("T4_VZ189_subind_d60",  VZ189,  {**SUBIND, "decay": 60}),
    ("T4_VZ189_subind_d63",  VZ189,  {**SUBIND, "decay": 63}),

    # Group C: smoothed z-score before ranking (3-day avg)
    ("T4_SMVZ3_subind_d60",  SMVZ3,  {**SUBIND, "decay": 60}),
    ("T4_SMVZ3_subind_d63",  SMVZ3,  {**SUBIND, "decay": 63}),

    # Group C2: smoothed z-score before ranking (5-day avg)
    ("T4_SMVZ5_subind_d60",  SMVZ5,  {**SUBIND, "decay": 60}),
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
            "turnover": is_data.get("returns"),
            "returns": is_data.get("returns"),
        }
        stats["turnover"] = is_data.get("turnover")
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
    print("Target4 R16 汇总:")
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

    out_path = os.path.join(OUTDIR, f"target4_r16_{timestamp}.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 {out_path}")


if __name__ == "__main__":
    main()
