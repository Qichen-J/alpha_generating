#!/usr/bin/env python3
"""
Target5 流动性压力反转 — R1
=================================
Target5原始公式（从未成功模拟，之前超时）:
  group_neutralize(
    -rank(ts_delta(close, 5) - ts_zscore(volume, 126)) * rank(volume / ts_mean(volume, 20)),
    bucket(rank(cap), range='0.1,1,0.1'))

结构分析:
  Factor A: -rank(ts_delta(close, 5) - ts_zscore(volume, 126))
    = 做空 "价格涨幅 > 成交量异常" 的股票（涨价但成交量不支撑 → 均值回归）
    问题: ts_delta(close,5) 和 ts_zscore(volume,126) 量纲不同，直接相减不稳定
  Factor B: rank(volume / ts_mean(volume, 20))
    = 按当日成交量活跃度加权

参考已通过的 R6_vol_conc_d7 (Sha=1.53, Fit=1.02, Sub=1.12, ALL PASS):
  my_group=bucket(rank(cap),range='0,1,0.1');
  alpha=rank(group_rank(ts_decay_linear(volume/ts_sum(volume,252),10),my_group)
       *group_rank(-ts_delta(close,5),my_group));
  group_neutralize(alpha,my_group)

R1 策略:
  Group A: 原始公式不同decay
  Group B: 量纲修正（对price delta做z-score处理）
  Group C: 分离成两个独立rank再相乘（类似Target4 V3结构）
  Group D: 在R6_vol_conc_d7基础上扩展（已知有效结构）
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

IND = {**BASE_SETTINGS, "neutralization": "INDUSTRY"}
NON = {**BASE_SETTINGS, "neutralization": "NONE"}

# ── 原始Target5公式 ──────────────────────────────────────────────────────────
T5_ORIG = (
    "group_neutralize("
    "-rank(ts_delta(close, 5) - ts_zscore(volume, 126)) * rank(volume / ts_mean(volume, 20)), "
    "bucket(rank(cap), range='0.1,1,0.1'))"
)

# ── 量纲修正：把 price delta 也做 z-score，使两侧量纲一致 ─────────────────────
# -rank(zscore(delta_close,5) - zscore(volume,126)) 量纲统一后更稳定
T5_ZS = (
    "group_neutralize("
    "-rank(ts_zscore(ts_delta(close, 5), 126) - ts_zscore(volume, 126)) * rank(volume / ts_mean(volume, 20)), "
    "bucket(rank(cap), range='0.1,1,0.1'))"
)

# ── 改为相乘（不是相减）: 价格反转 × 成交量异常 ───────────────────────────────
# 逻辑: 做空"价格大涨+成交量高z-score"的股票（过热），做多"价格大跌+成交量低"（超卖）
T5_MUL = (
    "group_neutralize("
    "-rank(ts_zscore(ts_delta(close, 5), 126)) * rank(ts_zscore(volume, 126)) * rank(volume / ts_mean(volume, 20)), "
    "bucket(rank(cap), range='0.1,1,0.1'))"
)

# ── 简化版：纯价格反转 × 成交量权重（去掉成交量z-score factor） ───────────────
T5_SIMPLE = (
    "group_neutralize("
    "-rank(ts_zscore(ts_delta(close, 5), 126)) * rank(volume / ts_mean(volume, 20)), "
    "bucket(rank(cap), range='0.1,1,0.1'))"
)

# ── 基于R6_vol_conc结构（已知ALL PASS）+ 价格反转组合 ─────────────────────────
# 替换volume/ts_sum → volume/ts_mean (更短期, 20天)
T5_CONC_20 = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "alpha=rank(group_rank(ts_decay_linear(volume/ts_mean(volume,20),5),my_group)"
    "*group_rank(-ts_delta(close,5),my_group));"
    "group_neutralize(alpha,my_group)"
)

# ── R6_vol_conc原版（已知ALL PASS的anchor）——重新测试确认 ──────────────────────
T5_CONC_252 = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "alpha=rank(group_rank(ts_decay_linear(volume/ts_sum(volume,252),10),my_group)"
    "*group_rank(-ts_delta(close,5),my_group));"
    "group_neutralize(alpha,my_group)"
)

# ── vol_conc结构 + 成交量z-score替代ts_decay_linear ─────────────────────────
T5_CONC_ZS = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "alpha=rank(group_rank(ts_zscore(volume/ts_mean(volume,20),126),my_group)"
    "*group_rank(-ts_delta(close,5),my_group));"
    "group_neutralize(alpha,my_group)"
)

# ── Target4-V3 style: 成交量delta z-score × 价格反转（换成按cap分组） ─────────
T5_VZ_GRP = (
    "my_group=bucket(rank(cap),range='0,1,0.1');"
    "alpha=rank(group_rank(ts_zscore(ts_delta(volume,3),126),my_group)"
    "*group_rank(-ts_delta(close,5),my_group));"
    "group_neutralize(alpha,my_group)"
)

VARIANTS = [
    # Group A: 原始公式 baseline + decay tuning
    ("T5_orig_sub_d5",   T5_ORIG,       {**BASE_SETTINGS, "decay": 5}),
    ("T5_orig_sub_d7",   T5_ORIG,       {**BASE_SETTINGS, "decay": 7}),
    ("T5_orig_ind_d7",   T5_ORIG,       {**IND,           "decay": 7}),

    # Group B: 量纲修正（zscore价格delta）
    ("T5_zs_sub_d7",     T5_ZS,         {**BASE_SETTINGS, "decay": 7}),
    ("T5_mul_sub_d7",    T5_MUL,        {**BASE_SETTINGS, "decay": 7}),
    ("T5_simple_sub_d7", T5_SIMPLE,     {**BASE_SETTINGS, "decay": 7}),

    # Group C: vol_conc结构扩展（基于已知有效结构）
    ("T5_conc20_ind_d7", T5_CONC_20,    {**IND,           "decay": 7}),
    ("T5_conc252_ind_d7",T5_CONC_252,   {**IND,           "decay": 7}),  # anchor
    ("T5_concZS_ind_d7", T5_CONC_ZS,    {**IND,           "decay": 7}),

    # Group D: Target4-V3风格但按cap分组
    ("T5_vz_grp_ind_d7", T5_VZ_GRP,     {**IND,           "decay": 7}),
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

        ra = response.headers.get("Retry-After", "?")
        print(f"  POST: {response.status_code} RA={ra}")
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
        print(f"  expr: {expr[:100]}...")
        print(f"  decay={settings.get('decay')} neut={settings.get('neutralization')}")
        location = submit(session, expr, settings)
        if not location:
            print("  提交失败")
            results[name] = {"error": "submit_failed", "expression": expr}
            continue
        print(f"  Location: {location}")

        data = poll(session, location)
        result = extract(data, session)
        if result:
            results[name] = {**result, "expression": expr}
        else:
            results[name] = {"error": "no_result", "expression": expr}

        if idx < len(VARIANTS):
            print("\n--- 等待5秒避免限流 ---")
            time.sleep(5)

    print("\n" + "=" * 80)
    print("Target5 R1 汇总:")
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

    out_path = os.path.join(OUTDIR, f"target5_r1_{timestamp}.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 {out_path}")


if __name__ == "__main__":
    main()
