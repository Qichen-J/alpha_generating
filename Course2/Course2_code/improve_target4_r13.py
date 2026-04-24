#!/usr/bin/env python3
"""
Target4 crowding-reversal R13
=================================
R12 CRITICAL FINDING — STRUCTURAL CEILING IDENTIFIED:
  V3 signal (volume*close delta=3) has a Fit ceiling at ~0.98, regardless of decay.
  
  The math reveals why: as decay increases,
    Sha decreases at exactly the same rate that Ret/TO increases,
    so Fit = Sha × sqrt(Ret/TO) ≈ constant ≈ 0.98 for all decay values.
  
  This is a structural property of the dolvol×close_reversal signal family.
  No decay tuning can overcome this ceiling.

  Full evidence:
    d63: Sha=1.28, Ret/TO=0.582 → Fit=0.98  (need Ret/TO≥0.610)
    d70: Sha=1.26, Ret/TO=0.603 → Fit=0.98  (need Ret/TO≥0.629)
    d72: Sha=1.25, Ret/TO=0.608 → Fit=0.97  (need Ret/TO≥0.640)
    d75: Sha=1.24, Ret/TO=0.615 → Fit=0.97  (Sha fails anyway)

NEED: A different signal family with fundamentally different Sha/Ret/TO tradeoff.

R13 strategy — 4 new structural approaches:

Group A: V1/V2 (shorter volume delta)
  V1 = rank(ts_zscore(ts_delta(volume*close, 1), 126)) * -rank(ts_delta(close, 3))
  V2 = rank(ts_zscore(ts_delta(volume*close, 2), 126)) * -rank(ts_delta(close, 3))
  Hypothesis: 1-day or 2-day volume shock is more predictive → higher Sha
  If Sha headroom is larger (e.g., 1.40+), decay can be pushed much further → Ret/TO ≥ 0.64

Group B: VWAP reversal
  V3_VWAP = rank(ts_zscore(ts_delta(volume*close, 3), 126)) * -rank(ts_delta(vwap, 3))
  Hypothesis: VWAP is smoother than close → reversal signal less noisy → lower TO → better Ret/TO
  VWAP incorporates intraday price discovery, potentially better quality signal

Group C: Raw volume (no close multiplication) — back to original structure
  RAWV3 = rank(ts_zscore(ts_delta(volume, 3), 126)) * -rank(ts_delta(close, 3))
  With heavy decay d60+, raw volume might hit different Sha/Fit tradeoff
  
Group D: Volume ratio (relative volume)
  RELV = rank(ts_zscore(volume / adv(20), 126)) * -rank(ts_delta(close, 3))
  Hypothesis: normalizing by 20-day ADV creates a "volume surprise" measure
  Different normalization → different Sha/TO structure
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

# Group A: shorter volume delta
V1 = "rank(ts_zscore(ts_delta(volume * close, 1), 126)) * -rank(ts_delta(close, 3))"
V2 = "rank(ts_zscore(ts_delta(volume * close, 2), 126)) * -rank(ts_delta(close, 3))"

# Group B: VWAP reversal
V3_VWAP = "rank(ts_zscore(ts_delta(volume * close, 3), 126)) * -rank(ts_delta(vwap, 3))"

# Group C: raw volume (no close multiplication)
RAWV3 = "rank(ts_zscore(ts_delta(volume, 3), 126)) * -rank(ts_delta(close, 3))"
RAWV5 = "rank(ts_zscore(ts_delta(volume, 5), 126)) * -rank(ts_delta(close, 3))"

# Group D: volume ratio relative to ADV
RELV = "rank(ts_zscore(volume / adv(20), 126)) * -rank(ts_delta(close, 3))"

VARIANTS = [
    # Group A1: V1 (1-day volume delta) — likely higher Sha but also higher TO
    # Testing at d70/d80 to find where its Sha/Fit curve peaks
    ("T4_V1_subind_d60",  V1,  {**SUBIND, "decay": 60}),
    ("T4_V1_subind_d70",  V1,  {**SUBIND, "decay": 70}),

    # Group A2: V2 (2-day volume delta) — between V1 and V3
    ("T4_V2_subind_d63",  V2,  {**SUBIND, "decay": 63}),
    ("T4_V2_subind_d70",  V2,  {**SUBIND, "decay": 70}),

    # Group B: VWAP reversal — smoother close substitute
    ("T4_V3vwap_subind_d63",  V3_VWAP, {**SUBIND, "decay": 63}),
    ("T4_V3vwap_subind_d70",  V3_VWAP, {**SUBIND, "decay": 70}),

    # Group C: raw volume, no close multiplication
    ("T4_RAWV3_subind_d63",  RAWV3,  {**SUBIND, "decay": 63}),
    ("T4_RAWV5_subind_d63",  RAWV5,  {**SUBIND, "decay": 63}),

    # Group D: relative volume (volume / ADV20) — anomalous volume signal
    ("T4_RELV_subind_d60",  RELV,  {**SUBIND, "decay": 60}),
    ("T4_RELV_subind_d70",  RELV,  {**SUBIND, "decay": 70}),
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
    print("Target4 R13 汇总:")
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

    out_path = os.path.join(OUTDIR, f"target4_r13_{timestamp}.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 {out_path}")


if __name__ == "__main__":
    main()
