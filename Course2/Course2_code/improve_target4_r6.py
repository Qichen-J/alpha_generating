#!/usr/bin/env python3
"""
Target4 crowding-reversal R6
=================================
R5 breakthroughs:
  T4_v5p3_subind_d40: Sha=1.23❌ Fit=0.83 TO=0.2288 — Ret/TO=0.458 (broke 0.34 ceiling!)
  T4_dolvol_subind_d10: Sha=1.53✅ Fit=0.81 TO=0.3950 Ret=0.1096

Key insight: At d40, Ret/TO ratio improved from 0.34 → 0.46. The ceiling breaks at heavy decay.
Dollar volume gives higher Ret (0.11) which is the other lever.

Fit = Sha × sqrt(Ret/TO) ≥ 1.0
For Sha=1.3, need Ret/TO ≥ 0.59 → if Ret=0.10, need TO ≤ 0.17
For Sha=1.5 (dolvol), need Ret/TO ≥ 0.44 → if Ret=0.11, need TO ≤ 0.25

R6 strategy:
  Group A: dolvol + SUBINDUSTRY + d15/d20/d25/d30 (primary attack — high Sha base)
  Group B: v5p3 + SUBINDUSTRY + d35 (find sweet spot between d30✅ Sha and d40 Ret/TO gain)
  Group C: logvol + SUBINDUSTRY + d20/d25 (Sha=1.45 at d10, similar to dolvol)
  Group D: dolvol + zscore window 252 + SUBINDUSTRY (stable vol signal + dollar normalization)
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

V5P3 = "rank(ts_zscore(ts_delta(volume, 5), 126)) * -rank(ts_delta(close, 3))"
DOLVOL = "rank(ts_zscore(ts_delta(volume * close, 5), 126)) * -rank(ts_delta(close, 3))"
LOGVOL = "rank(ts_zscore(ts_delta(log(volume), 5), 126)) * -rank(ts_delta(close, 3))"
DOLVOL_Z252 = "rank(ts_zscore(ts_delta(volume * close, 5), 252)) * -rank(ts_delta(close, 3))"

VARIANTS = [
    # Group A: dolvol + SUBINDUSTRY — main attack
    (
        "T4_dolvol_subind_d15",
        DOLVOL,
        {**SUBIND, "decay": 15},
    ),
    (
        "T4_dolvol_subind_d20",
        DOLVOL,
        {**SUBIND, "decay": 20},
    ),
    (
        "T4_dolvol_subind_d25",
        DOLVOL,
        {**SUBIND, "decay": 25},
    ),
    (
        "T4_dolvol_subind_d30",
        DOLVOL,
        {**SUBIND, "decay": 30},
    ),
    (
        "T4_dolvol_subind_d40",
        DOLVOL,
        {**SUBIND, "decay": 40},
    ),
    # Group B: v5p3 subind d35 — interpolate
    (
        "T4_v5p3_subind_d35",
        V5P3,
        {**SUBIND, "decay": 35},
    ),
    # Group C: logvol + SUBINDUSTRY heavy decay
    (
        "T4_logvol_subind_d20",
        LOGVOL,
        {**SUBIND, "decay": 20},
    ),
    (
        "T4_logvol_subind_d30",
        LOGVOL,
        {**SUBIND, "decay": 30},
    ),
    # Group D: dolvol + z252 + SUBINDUSTRY
    (
        "T4_dolvol_z252_subind_d10",
        DOLVOL_Z252,
        {**SUBIND, "decay": 10},
    ),
    (
        "T4_dolvol_z252_subind_d20",
        DOLVOL_Z252,
        {**SUBIND, "decay": 20},
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
    while time.time() - start < 300:
        try:
            response = session.get(location, timeout=30)
        except Exception as error:
            print(f"  GET error: {error}")
            time.sleep(10)
            authenticate(session)
            continue

        retry_after = float(response.headers.get("Retry-After", 0))
        data = response.json() if response.status_code == 200 else {}
        elapsed = int(time.time() - start)
        alpha_id = data.get("alpha")

        if elapsed % 30 < 6 or retry_after == 0:
            print(f"  [{elapsed}s] HTTP={response.status_code} RA={retry_after} alpha={alpha_id}")

        if retry_after == 0:
            if not alpha_id:
                error_message = ""
                if isinstance(data, dict):
                    for key in ["error", "message", "detail"]:
                        if key in data:
                            error_message = str(data[key])[:300]
                            break
                return {"status": "NO_ALPHA", "error": error_message}

            detail = session.get(f"{BASE}/alphas/{alpha_id}", timeout=30).json()
            is_data = detail.get("is", {})
            checks = {check["name"]: check for check in is_data.get("checks", [])}
            sub = checks.get("LOW_SUB_UNIVERSE_SHARPE", {})
            return {
                "status": "COMPLETE",
                "alpha_id": alpha_id,
                "sharpe": is_data.get("sharpe", 0),
                "fitness": is_data.get("fitness", 0),
                "turnover": is_data.get("turnover", 0),
                "returns": is_data.get("returns", 0),
                "sub_value": sub.get("value", "?"),
                "sub_cutoff": sub.get("cutoff", "?"),
                "sha_pass": checks.get("LOW_SHARPE", {}).get("result") == "PASS",
                "fit_pass": checks.get("LOW_FITNESS", {}).get("result") == "PASS",
                "sub_pass": sub.get("result") == "PASS",
            }

        time.sleep(max(retry_after, 3))

    return {"status": "TIMEOUT"}


def main() -> None:
    session = requests.Session()
    authenticate(session)
    results = []

    for index, (name, expression, settings) in enumerate(VARIANTS, start=1):
        if index > 1:
            print("\n--- 等待5秒避免限流 ---")
            time.sleep(5)

        print(f"\n[{index}/{len(VARIANTS)}] {name}")
        print(f"  expr: {expression[:120]}...")
        location = submit(session, expression, settings)
        if not location:
            print("  ❌ 提交失败")
            results.append({"name": name, "status": "SUBMIT_FAIL", "expression": expression, "settings": settings})
            continue

        print(f"  Location: {location}")
        result = poll(session, location)
        result.update({"name": name, "expression": expression, "settings": settings, "location": location})

        if result["status"] == "COMPLETE":
            all_pass = result["sha_pass"] and result["fit_pass"] and result["sub_pass"]
            result["all_pass"] = all_pass
            tag = " 🎉ALL PASS" if all_pass else ""
            print(
                f"  ✅ Sha={result['sharpe']:.2f}{'✅' if result['sha_pass'] else '❌'}"
                f" Fit={result['fitness']:.2f}{'✅' if result['fit_pass'] else '❌'}"
                f" Sub={result['sub_value']}{'✅' if result['sub_pass'] else '❌'}(cut={result['sub_cutoff']})"
                f" TO={result['turnover']:.4f} Ret={result['returns']:.4f}{tag}"
            )
        elif result["status"] == "NO_ALPHA":
            print(f"  ❌ 完成但无alpha_id {result.get('error', '')}")
        else:
            print("  ⏰ 超时 (5min)")

        results.append(result)

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    output_path = os.path.join(OUTDIR, f"target4_r6_{stamp}.json")
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print("Target4 R6 汇总:")
    for result in results:
        if result["status"] == "COMPLETE":
            print(
                f"  {result['name']}: Sha={result['sharpe']:.2f} Fit={result['fitness']:.2f}"
                f" TO={result['turnover']:.4f} Ret={result['returns']:.4f}"
                f" Sub={'P' if result['sub_pass'] else 'F'}({result['sub_value']})"
                f" {'🎉' if result.get('all_pass') else ''}"
            )
        else:
            print(f"  {result['name']}: {result['status']}")
    print(f"\n💾 {output_path}")


if __name__ == "__main__":
    main()
