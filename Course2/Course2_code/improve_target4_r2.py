#!/usr/bin/env python3
"""
Target4 crowding-reversal R2
=================================
R1 best:  T4_v3p3_d6  → Sha=1.37✅ Fit=0.62❌  TO=0.5335
          T4_v5p5_d6  → Sha=1.27✅ Fit=0.61❌  TO=0.4390

Fitness formula:  Fit ≈ Sha × sqrt(Ret/TO)
Need Fit≥1.0 → with Sha≈1.3, need Ret/TO ≈ 0.59 → if Ret≈0.10, TO≤0.17

R2 goals:
  Group A: heavy decay sweep on v3p3 (d8/d10/d15/d20) — reduce TO while holding Sharpe
  Group B: mixed window v5p3 and v10p3 (slow volume + fast price reversal, lower TO)
  Group C: event-driven trade_when on v3p3 signal (trade only on vol-anomaly days)
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

# Best from R1
V3P3 = "rank(ts_zscore(ts_delta(volume, 3), 126)) * -rank(ts_delta(close, 3))"
V5P5 = "rank(ts_zscore(ts_delta(volume, 5), 126)) * -rank(ts_delta(close, 5))"
V5P3 = "rank(ts_zscore(ts_delta(volume, 5), 126)) * -rank(ts_delta(close, 3))"
V10P3 = "rank(ts_zscore(ts_delta(volume, 10), 126)) * -rank(ts_delta(close, 3))"
V10P5 = "rank(ts_zscore(ts_delta(volume, 10), 126)) * -rank(ts_delta(close, 5))"

VARIANTS = [
    # Group A: Heavier decay on T4_v3p3 (best Sharpe from R1)
    (
        "T4_v3p3_d8",
        V3P3,
        {**BASE_SETTINGS, "decay": 8},
    ),
    (
        "T4_v3p3_d10",
        V3P3,
        {**BASE_SETTINGS, "decay": 10},
    ),
    (
        "T4_v3p3_d15",
        V3P3,
        {**BASE_SETTINGS, "decay": 15},
    ),
    (
        "T4_v3p3_d20",
        V3P3,
        {**BASE_SETTINGS, "decay": 20},
    ),
    # Group B: Mixed windows — slow volume + fast price (hypothesis: lower TO from slow vol)
    (
        "T4_v5p3_d6",
        V5P3,
        {**BASE_SETTINGS, "decay": 6},
    ),
    (
        "T4_v5p3_d10",
        V5P3,
        {**BASE_SETTINGS, "decay": 10},
    ),
    (
        "T4_v10p3_d6",
        V10P3,
        {**BASE_SETTINGS, "decay": 6},
    ),
    (
        "T4_v10p5_d6",
        V10P5,
        {**BASE_SETTINGS, "decay": 6},
    ),
    # Group C: Event-driven trade_when — trade only when volume anomaly is large
    # trade when |vol_zscore| > 1.0 (roughly top/bottom 32% of days)
    (
        "T4_v3p3_tw_volanom",
        (
            "trade_when("
            "abs(ts_zscore(ts_delta(volume, 3), 126)) > 1.0, "
            + V3P3 + ", "
            "-1)"
        ),
        {**BASE_SETTINGS, "decay": 6},
    ),
    # event: price reversal signal is extreme (price delta rank extreme)
    (
        "T4_v3p3_tw_bigmove",
        (
            "trade_when("
            "abs(ts_delta(close, 3)) > ts_std_dev(ts_delta(close, 3), 63), "
            + V3P3 + ", "
            "-1)"
        ),
        {**BASE_SETTINGS, "decay": 6},
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
            print(f"  ❌ 완성但无alpha_id {result.get('error', '')}")
        else:
            print("  ⏰ 超时 (5min)")

        results.append(result)

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    output_path = os.path.join(OUTDIR, f"target4_r2_{stamp}.json")
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print("Target4 R2 汇总:")
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
