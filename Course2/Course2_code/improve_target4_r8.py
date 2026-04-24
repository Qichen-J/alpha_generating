#!/usr/bin/env python3
"""
Target4 crowding-reversal R8
=================================
R7 key finding:
  dolvol_subind_d60: Sha=1.25✅ Fit=0.95 TO=0.1935 Ret=0.1115 Ret/TO=0.576
  dolvol_subind_d70: Sha=1.23❌ Fit=0.96 (Sha dropped below threshold)

The Sha=1.25 plateau holds from d40→d60, then drops at d70.
To get ALL PASS we need BOTH: Sha≥1.25 AND Fit≥1.0

At d60: Fit=1.25×sqrt(0.576)=0.949 — need either:
  (a) Boost Sha to 1.32+ at same d60 decay: 1.32×sqrt(0.576)=1.002 ✅
  (b) Find a sweep around d60 where Sha dips to 1.25 but Ret/TO reaches 0.64+

R8 strategy:
  Group A: dolvol + SUBINDUSTRY + d60 + truncation sweep (0.04/0.05/0.06)
           Lower truncation = more diversified = potentially higher Sha, lower TO
  Group B: volume/adv20 relative volume signal + SUBINDUSTRY + d50/d60
           adv20-normalized signal removes market-cap/size effects → cleaner signal → better Sha
  Group C: Fine-grained decay d55/d63 between the d60(pass Sha) and d70(fail Sha) zone
  Group D: dolvol + SECTOR (between INDUSTRY and SUBINDUSTRY) at d60 — find neutralization sweet spot
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
SECTOR = {**BASE_SETTINGS, "neutralization": "SECTOR"}

DOLVOL = "rank(ts_zscore(ts_delta(volume * close, 5), 126)) * -rank(ts_delta(close, 3))"
# volume/adv20 = relative volume change (size-normalized)
RELVOL = "rank(ts_zscore(ts_delta(volume / adv20, 5), 126)) * -rank(ts_delta(close, 3))"
# adv20 based signal (pre-smoothed)
ADV20 = "rank(ts_zscore(ts_delta(adv20, 5), 126)) * -rank(ts_delta(close, 3))"

VARIANTS = [
    # Group A: truncation sweep at d60 (best decay found in R7)
    (
        "T4_dolvol_subind_d60_tr06",
        DOLVOL,
        {**SUBIND, "decay": 60, "truncation": 0.06},
    ),
    (
        "T4_dolvol_subind_d60_tr05",
        DOLVOL,
        {**SUBIND, "decay": 60, "truncation": 0.05},
    ),
    (
        "T4_dolvol_subind_d60_tr04",
        DOLVOL,
        {**SUBIND, "decay": 60, "truncation": 0.04},
    ),
    # Group B: relative volume signal (volume/adv20) — remove size effect
    (
        "T4_relvol_subind_d50",
        RELVOL,
        {**SUBIND, "decay": 50},
    ),
    (
        "T4_relvol_subind_d60",
        RELVOL,
        {**SUBIND, "decay": 60},
    ),
    # Group C: adv20 (pre-smoothed dollar volume) signal
    (
        "T4_adv20_subind_d50",
        ADV20,
        {**SUBIND, "decay": 50},
    ),
    (
        "T4_adv20_subind_d60",
        ADV20,
        {**SUBIND, "decay": 60},
    ),
    # Group D: fine-grain sweep d55/d63
    (
        "T4_dolvol_subind_d55",
        DOLVOL,
        {**SUBIND, "decay": 55},
    ),
    (
        "T4_dolvol_subind_d63",
        DOLVOL,
        {**SUBIND, "decay": 63},
    ),
    # Group E: SECTOR neutralization at d60 (between INDUSTRY and SUBINDUSTRY)
    (
        "T4_dolvol_sector_d60",
        DOLVOL,
        {**SECTOR, "decay": 60},
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
    while time.time() - start < 480:
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
        # Fetch full alpha data
        for attempt in range(5):
            try:
                resp = session.get(f"{BASE}/alphas/{alpha_id}", timeout=30)
                if resp.status_code == 429:
                    wait = int(float(resp.headers.get("Retry-After", 30))) + 5
                    print(f"  fetch限流, 等 {wait}s")
                    time.sleep(wait)
                    continue
                alpha = resp.json() if isinstance(resp.json(), dict) else {}
                break
            except Exception:
                time.sleep(10)
        else:
            alpha = {}
    else:
        return None

    # Try stats field first, then is field
    stats_list = alpha.get("stats", [])
    if stats_list:
        stats = {s["name"]: s["value"] for s in stats_list}
    else:
        # Use is field
        is_data = alpha.get("is", {})
        stats = {
            "sharpe": is_data.get("sharpe"),
            "fitness": is_data.get("fitness"),
            "turnover": is_data.get("turnover"),
            "returns": is_data.get("returns"),
        }
        # Extract sub_sharpe from checks
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
        print(f"  expr: {expr[:80]}...")
        print(f"  trunc={settings.get('truncation', 0.08)} decay={settings.get('decay', 0)} neut={settings.get('neutralization')}")
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

    # Summary
    print("\n" + "=" * 80)
    print("Target4 R8 汇总:")
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

    out_path = os.path.join(OUTDIR, f"target4_r8_{timestamp}.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 {out_path}")


if __name__ == "__main__":
    main()
