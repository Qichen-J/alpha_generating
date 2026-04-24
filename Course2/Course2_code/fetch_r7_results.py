#!/usr/bin/env python3
"""
Fetch R7 results after rate limit reset.
Alpha IDs extracted from terminal log.
"""
import json
import os
import time

import requests

CREDENTIALS = ("xxxxxx@example.com", "xxxxxx")
BASE = "https://api.worldquantbrain.com"
OUTDIR = "/Users/zhiqu/Desktop/brain/Course2/Course2_code/outputs"

ALPHA_IDS = {
    "T4_dolvol_subind_d50":     "6XYGYMLY",
    "T4_dolvol_subind_d60":     "e7q1dORp",
    "T4_dolvol_subind_d70":     "npO6Zdlq",
    "T4_dolvol_subind_d80":     "XgYN2vaa",
    "T4_dolvol_z252_subind_d30":"E5rmgdLr",
    "T4_dolvol_z252_subind_d40":"MP5gbolo",
    "T4_dolvol_z252_subind_d50":"78KGx0jv",
    "T4_dolvol_subind_d40_p5":  "pw1Wn7Ag",
    "T4_dolvol_subind_d40_p10": "P0XPn52p",
    "T4_dolvol_z252_subind_d60":"58qGLdG5",
}

def wait_for_rate_limit(session):
    """Poll until rate limit resets."""
    while True:
        resp = session.get(f"{BASE}/alphas/6XYGYMLY", timeout=30)
        if resp.status_code == 429:
            wait = int(float(resp.headers.get("Retry-After", 60))) + 5
            print(f"  限流中, 等 {min(wait, 120)}s ... (Retry-After={wait}s)")
            time.sleep(min(wait, 120))
        else:
            print(f"  限流已解除 (HTTP {resp.status_code})")
            return resp

def fetch_alpha(session, alpha_id):
    for attempt in range(5):
        try:
            resp = session.get(f"{BASE}/alphas/{alpha_id}", timeout=30)
        except Exception as e:
            print(f"  GET error: {e}, 重试...")
            time.sleep(10)
            continue
        if resp.status_code == 429:
            wait = int(float(resp.headers.get("Retry-After", 30))) + 5
            print(f"  限流, 等 {wait}s")
            time.sleep(wait)
            continue
        if resp.status_code != 200:
            print(f"  HTTP {resp.status_code}: {resp.text[:200]}")
            return None
        data = resp.json()
        if not isinstance(data, dict):
            return None
        return data
    return None

def main():
    session = requests.Session()

    # Authenticate
    r = session.post(f"{BASE}/authentication", auth=CREDENTIALS, timeout=30)
    r.raise_for_status()
    print("✅ 认证成功")

    # Wait for rate limit if needed
    print("\n检查限流状态...")
    first = wait_for_rate_limit(session)

    results = {}
    all_pass_list = []

    names = list(ALPHA_IDS.keys())
    for idx, name in enumerate(names):
        alpha_id = ALPHA_IDS[name]
        print(f"\n[{idx+1}/{len(names)}] {name} (id={alpha_id})")

        data = fetch_alpha(session, alpha_id)
        if not data:
            print(f"  ❌ 获取失败")
            results[name] = {"error": "fetch_failed", "alpha_id": alpha_id}
            continue

        stats = {s["name"]: s["value"] for s in data.get("stats", [])}
        sharpe = stats.get("sharpe")
        fitness = stats.get("fitness")
        turnover = stats.get("turnover")
        returns = stats.get("returns")
        sub_sharpe = stats.get("sub_sharpe")

        if sharpe is None:
            print(f"  ⚠️ 无stats数据")
            results[name] = {"error": "no_stats", "alpha_id": alpha_id, "raw": data}
            continue

        sha_ok = sharpe >= 1.25
        fit_ok = fitness >= 1.0
        sub_ok = sub_sharpe is None or sub_sharpe >= 0.5
        all_pass = sha_ok and fit_ok and sub_ok
        ret_to = returns / turnover if turnover else 0

        print(
            f"  {'✅' if sha_ok else '❌'} Sha={sharpe:.2f}  "
            f"{'✅' if fit_ok else '❌'} Fit={fitness:.2f}  "
            f"TO={turnover:.4f}  Ret={returns:.4f}  Ret/TO={ret_to:.3f}  "
            f"Sub={sub_sharpe:.2f if sub_sharpe else 'N/A'}"
        )
        if all_pass:
            print(f"  🎯🎯🎯 ALL PASS!")
            all_pass_list.append((name, alpha_id))

        results[name] = {
            "alpha_id": alpha_id,
            "sharpe": sharpe,
            "fitness": fitness,
            "turnover": turnover,
            "returns": returns,
            "sub_sharpe": sub_sharpe,
            "ret_to": ret_to,
            "sha_ok": sha_ok,
            "fit_ok": fit_ok,
            "sub_ok": sub_ok,
            "all_pass": all_pass,
        }

        time.sleep(6)  # avoid rate limit

    # Summary
    print("\n" + "=" * 80)
    print("R7 完整结果:")
    for name, r in results.items():
        if "sharpe" in r:
            flag = "  🎯 ALL PASS" if r.get("all_pass") else ""
            print(
                f"  {name}: Sha={r['sharpe']:.2f} Fit={r['fitness']:.2f} "
                f"TO={r['turnover']:.4f} Ret={r['returns']:.4f} Ret/TO={r['ret_to']:.3f}{flag}"
            )
        else:
            print(f"  {name}: {r.get('error')}")

    if all_pass_list:
        print("\n🎉 ALL PASS Alpha:")
        for name, aid in all_pass_list:
            print(f"  {name}: alpha_id={aid}")

    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out = os.path.join(OUTDIR, f"target4_r7_fetched_{ts}.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 {out}")


if __name__ == "__main__":
    main()
