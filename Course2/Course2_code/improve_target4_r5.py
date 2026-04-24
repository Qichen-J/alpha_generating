#!/usr/bin/env python3
"""
Target4 crowding-reversal R5
=================================
R4 finding: Fitness plateaus at ~0.79 for ALL SUBINDUSTRY variants
Root cause: Ret/TO stays ~0.34 regardless of decay → Sha × sqrt(0.34) ≈ 0.79

To break the ceiling, need Ret/TO to increase beyond 0.55+.
Strategy: change signal structure so turnover drops FASTER than returns.

R5 approaches:
  A: Heavy decay d30/d40 continuation (check if curve continues)
  B: Hump operation — only trade when signal changes significantly (ts_delay)
  C: Slow-changing price signals — sign(returns) sum, std-normalized
  D: Completely different signal structure — ts_corr, dollar-volume, Amihud
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

VARIANTS = [
    # Group A: Heavy decay continuation — does Fit keep rising past 0.79?
    (
        "T4_v5p3_subind_d30",
        V5P3,
        {**SUBIND, "decay": 30},
    ),
    (
        "T4_v5p3_subind_d40",
        V5P3,
        {**SUBIND, "decay": 40},
    ),
    # Group B: Hump operation — only trade when signal changes > threshold
    # Idea: skip micro-rebalancing, hold position through small signal drifts
    (
        "T4_hump05_subind_d10",
        (
            "s = rank(ts_zscore(ts_delta(volume, 5), 126)) * -rank(ts_delta(close, 3));"
            "trade_when(abs(s - ts_delay(s, 1)) > 0.05, s, -1)"
        ),
        {**SUBIND, "decay": 10},
    ),
    (
        "T4_hump10_subind_d10",
        (
            "s = rank(ts_zscore(ts_delta(volume, 5), 126)) * -rank(ts_delta(close, 3));"
            "trade_when(abs(s - ts_delay(s, 1)) > 0.10, s, -1)"
        ),
        {**SUBIND, "decay": 10},
    ),
    # Group C: Slow-changing price signals
    # sign(returns) only changes from -1/0/+1 — ts_sum changes only ±2/day → very low TO
    (
        "T4_signret3_subind_d10",
        "rank(ts_zscore(ts_delta(volume, 5), 126)) * -rank(ts_sum(sign(returns), 3))",
        {**SUBIND, "decay": 10},
    ),
    (
        "T4_signret5_subind_d10",
        "rank(ts_zscore(ts_delta(volume, 5), 126)) * -rank(ts_sum(sign(returns), 5))",
        {**SUBIND, "decay": 10},
    ),
    # volatility-normalized price: dividing by rolling std stabilizes signal changes
    (
        "T4_volnorm_subind_d10",
        (
            "rank(ts_zscore(ts_delta(volume, 5), 126))"
            " * -rank(ts_delta(close, 3) / ts_std_dev(returns, 21))"
        ),
        {**SUBIND, "decay": 10},
    ),
    # Group D: Completely different signal structures
    # Log volume: log-differencing → signal more stationary, less extreme spikes
    (
        "T4_logvol_subind_d10",
        "rank(ts_zscore(ts_delta(log(volume), 5), 126)) * -rank(ts_delta(close, 3))",
        {**SUBIND, "decay": 10},
    ),
    # Dollar volume: captures flow value not just share count
    (
        "T4_dolvol_subind_d10",
        "rank(ts_zscore(ts_delta(volume * close, 5), 126)) * -rank(ts_delta(close, 3))",
        {**SUBIND, "decay": 10},
    ),
    # ts_corr structure: negative corr between recent volume and returns → crowding
    (
        "T4_corr_subind_d10",
        "rank(-ts_corr(ts_delta(volume, 5), returns, 21))",
        {**SUBIND, "decay": 10},
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
    output_path = os.path.join(OUTDIR, f"target4_r5_{stamp}.json")
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)

    print("\n" + "=" * 80)
    print("Target4 R5 汇总:")
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
