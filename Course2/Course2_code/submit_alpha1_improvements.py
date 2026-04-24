#!/usr/bin/env python3
"""
Alpha 1 改进版本 - 基于 Extra Submission Rubric 和 Sub-universe Test 优化
"""

import json
import time
import os
from pathlib import Path
from datetime import datetime, timezone

import requests
from requests.auth import HTTPBasicAuth
import pandas as pd

# 配置
ROOT = Path("/Users/zhiqu/Desktop/brain")
OUTPUT_DIR = ROOT / "Course2" / "Course2_code" / "outputs"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

BRAIN_USERNAME = os.getenv("BRAIN_USERNAME", "xxxxxx@example.com")
BRAIN_PASSWORD = os.getenv("BRAIN_PASSWORD", "xxxxxx")

SETTINGS = {
    "type": "REGULAR",
    "settings": {
        "instrumentType": "EQUITY",
        "region": "USA",
        "universe": "TOP3000",
        "delay": 1,
        "decay": 10,
        "neutralization": "INDUSTRY",
        "truncation": 0.08,
        "pasteurization": "ON",
        "unitHandling": "VERIFY",
        "nanHandling": "ON",
        "language": "FASTEXPR",
        "visualization": False
    }
}

REQUEST_TIMEOUT = 30

def build_session(username: str, password: str):
    sess = requests.Session()
    sess.auth = HTTPBasicAuth(username, password)
    return sess

def authenticate(sess: requests.Session):
    r = sess.post("https://api.worldquantbrain.com/authentication", timeout=REQUEST_TIMEOUT)
    r.raise_for_status()
    return r.json()

def submit_simulation(sess: requests.Session, expression: str):
    """提交单个 alpha 表达式"""
    payload = {
        "type": SETTINGS["type"],
        "settings": SETTINGS["settings"],
        "regular": expression
    }
    
    try:
        r = sess.post("https://api.worldquantbrain.com/simulations", json=payload, timeout=REQUEST_TIMEOUT)
        if r.status_code >= 400:
            return {"status": "error", "error": f"HTTP {r.status_code}: {r.text[:200]}"}
        
        location = r.headers.get("Location")
        if not location:
            return {"status": "error", "error": "Missing Location header"}
        
        # 轮询获取结果
        start_time = time.time()
        while time.time() - start_time < 60:
            pr = sess.get(location, timeout=REQUEST_TIMEOUT)
            if pr.status_code >= 400:
                return {"status": "error", "location": location, "error": f"HTTP {pr.status_code}"}
            
            retry_after = float(pr.headers.get("Retry-After", 0))
            if retry_after == 0:
                data = pr.json()
                return {
                    "status": "done",
                    "location": location,
                    "result": data
                }
            
            time.sleep(max(retry_after, 1.0))
        
        return {"status": "timeout", "location": location}
    
    except Exception as ex:
        return {"status": "exception", "error": str(ex)}

def main():
    print("=" * 80)
    print("Alpha 1 改进版本提交")
    print("基于 Extra Submission Rubric、Sub-universe Test、Turnover 优化")
    print("=" * 80)
    
    # 建立会话
    sess = build_session(BRAIN_USERNAME, BRAIN_PASSWORD)
    auth_info = authenticate(sess)
    print(f"\n✅ 认证成功: {auth_info.get('user', {}).get('id', 'N/A')}\n")
    
    # 定义改进版本
    improvements = [
        {
            "version": "v1: 简化+事件触发",
            "description": "流动性友好，条件触发降低 turnover",
            "expression": "signal = ts_zscore(close - ts_mean(close, 63), 126); vol_state = ts_rank(ts_std_dev(returns, 20), 252); alpha = group_neutralize(-rank(signal), industry); trade_when(vol_state > 0.6, alpha, -1)"
        },
        {
            "version": "v2: 中等复杂度",
            "description": "保留多因子但简化，流动性过滤",
            "expression": "momentum_signal = ts_zscore(ts_delta(close, 5), 126); volatility_filter = ts_rank(ts_std_dev(returns, 20), 252); raw_alpha = -rank(momentum_signal) * rank(volatility_filter); alpha = group_neutralize(raw_alpha, industry); trade_when(volume > ts_mean(volume, 20), alpha, -1)"
        },
        {
            "version": "v3: 极简版（推荐）",
            "description": "最高 sub-universe 通过率，单一清晰逻辑",
            "expression": "-rank(ts_zscore(close - ts_mean(close, 63), 126))"
        }
    ]
    
    results = []
    print("🚀 开始提交 3 个改进版本...\n")
    
    for i, imp in enumerate(improvements, 1):
        print(f"\n{i}. {imp['version']}")
        print(f"   描述: {imp['description']}")
        print(f"   表达式: {imp['expression'][:60]}...")
        
        resp = submit_simulation(sess, imp['expression'])
        
        results.append({
            "version": imp['version'],
            "description": imp['description'],
            "expression": imp['expression'],
            "status": resp.get('status'),
            "location": resp.get('location', ''),
            "error": resp.get('error', ''),
            "result_summary": json.dumps(resp.get('result', {}), ensure_ascii=False)
        })
        
        if resp.get('status') == 'done':
            result = resp.get('result', {})
            sim_status = result.get('status', 'UNKNOWN')
            print(f"   ✅ 提交成功 - 平台状态: {sim_status}")
            if sim_status == 'ERROR':
                msg = result.get('message', '')
                print(f"      错误: {msg[:80]}")
        elif resp.get('status') == 'timeout':
            print(f"   ⏱️  提交超时，等待平台处理中")
        else:
            print(f"   ❌ 状态: {resp.get('status')}")
            if resp.get('error'):
                print(f"      错误: {resp.get('error')[:80]}")
        
        time.sleep(2)
    
    # 保存结果
    results_df = pd.DataFrame(results)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    
    csv_path = OUTPUT_DIR / f"alpha1_improvements_{timestamp}.csv"
    results_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    
    json_path = OUTPUT_DIR / f"alpha1_improvements_{timestamp}.json"
    json_path.write_text(results_df.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")
    
    print("\n" + "=" * 80)
    print("✅ Alpha 1 改进版本提交完成！")
    print(f"📄 分析文档: {OUTPUT_DIR / 'alpha1_improvement.md'}")
    print(f"📄 CSV 结果: {csv_path}")
    print(f"📄 JSON 结果: {json_path}")
    print("=" * 80)
    
    print("\n📊 改进建议总结:")
    print("""
根据参考文件的最佳实践：

✅ 推荐：v3 极简版
   - 最高 sub-universe test 通过率（避免 cap 权重）
   - 符合 PPAC 简单算子原则
   - 清晰的经济逻辑：价格均值回归
   - 最小过拟合风险

⚠️  备选：v1 或 v2
   - 若需要更高 Sharpe，可尝试这些版本
   - 但需额外验证 sub-universe 稳定性
   - 注意 turnover 和流动性成本

❌ 不推荐：保留原版本
   - 复杂度高，sub-universe 测试失败风险
   - 原生 cap bucket 中性化违反最佳实践
    """)

if __name__ == "__main__":
    main()
