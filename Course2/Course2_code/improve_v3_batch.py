#!/usr/bin/env python3
"""
v3 版本稍微改进 - 多个变体提交
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

def submit_simulation(sess: requests.Session, expression: str, description: str):
    """提交单个 alpha 表达式"""
    payload = {
        "type": SETTINGS["type"],
        "settings": SETTINGS["settings"],
        "regular": expression
    }
    
    print(f"\n提交: {description}")
    print(f"表达式: {expression}")
    
    try:
        r = sess.post("https://api.worldquantbrain.com/simulations", json=payload, timeout=REQUEST_TIMEOUT)
        if r.status_code >= 400:
            print(f"❌ 提交失败: HTTP {r.status_code}: {r.text[:200]}")
            return {
                "version": description.split()[0],
                "description": description,
                "expression": expression,
                "status": "error",
                "location": "",
                "error": f"HTTP {r.status_code}",
                "result_summary": {}
            }
        
        location = r.headers.get("Location")
        if not location:
            print(f"❌ 提交失败: 无 Location 头")
            return {
                "version": description.split()[0],
                "description": description,
                "expression": expression,
                "status": "error",
                "location": "",
                "error": "Missing Location header",
                "result_summary": {}
            }
        
        print(f"✅ 已提交: {location}")
        
        # 轮询获取结果
        start_time = time.time()
        while time.time() - start_time < 60:
            pr = sess.get(location, timeout=REQUEST_TIMEOUT)
            if pr.status_code >= 400:
                print(f"⏳ 等待中... (HTTP {pr.status_code})")
                time.sleep(2)
                continue
            
            retry_after = float(pr.headers.get("Retry-After", 0))
            if retry_after == 0:
                data = pr.json()
                print(f"✅ 完成: {data.get('status', 'unknown')}")
                return {
                    "version": description.split()[0],
                    "description": description,
                    "expression": expression,
                    "status": "done",
                    "location": location,
                    "error": "",
                    "result_summary": data
                }
            
            print(f"⏳ 等待 {retry_after}s...")
            time.sleep(max(retry_after, 1.0))
        
        print(f"⏱ 超时")
        return {
            "version": description.split()[0],
            "description": description,
            "expression": expression,
            "status": "timeout",
            "location": location,
            "error": "Timeout waiting for result",
            "result_summary": {}
        }
    
    except Exception as ex:
        print(f"❌ 异常: {ex}")
        return {
            "version": description.split()[0],
            "description": description,
            "expression": expression,
            "status": "exception",
            "location": "",
            "error": str(ex),
            "result_summary": {}
        }

def main():
    print("=" * 80)
    print("🚀 v3 改进版本批量提交 - 目标提升 Sharpe 0.05")
    print("=" * 80)
    
    sess = build_session(BRAIN_USERNAME, BRAIN_PASSWORD)
    authenticate(sess)

    # 多个改进变体 - 都基于原始 v3 稍作调整
    improvements = [
        # 最激进 - 参数延长
        (
            "-rank(ts_zscore(close - ts_mean(close, 126), 252))",
            "v3.1 参数延长版 - 更长周期提高稳定性"
        ),
        # 保守 - 双重验证
        (
            "momentum = ts_zscore(close - ts_mean(close, 63), 126); volatility = ts_std_dev(returns, 20); normalized_vol = ts_rank(volatility, 252); trade_when(normalized_vol > 0.3, -rank(momentum), 0)",
            "v3.2 保守版 - 波动率过滤"
        ),
        # 均衡 - 混合参数
        (
            "-rank(ts_zscore(close - ts_mean(close, 84), 168))",
            "v3.3 均衡版 - 中间参数组合"
        ),
        # 趋势友好 - 增加成交量
        (
            "signal = ts_zscore(close - ts_mean(close, 63), 126); vol_filter = volume > ts_mean(volume, 20); trade_when(vol_filter, -rank(signal), 0)",
            "v3.4 成交量条件版 - 流动性驱动"
        ),
        # 高频友好 - 短周期
        (
            "-rank(ts_zscore(close - ts_mean(close, 42), 84))",
            "v3.5 高频版 - 更敏感响应"
        ),
    ]

    results = []
    for i, (expr, desc) in enumerate(improvements, 1):
        result = submit_simulation(sess, expr, desc)
        results.append(result)
        if i < len(improvements):
            time.sleep(2)  # 避免请求过快

    # 保存结果
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_file = OUTPUT_DIR / f"v3_improved_batch_{timestamp}.csv"

    df = pd.DataFrame(results)
    df.to_csv(output_file, index=False, encoding='utf-8')

    print(f"\n" + "=" * 80)
    print(f"📄 结果已保存到: {output_file}")

    # 同时保存 JSON 格式
    json_file = OUTPUT_DIR / f"v3_improved_batch_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"📄 JSON 结果已保存到: {json_file}")
    print(f"✅ 提交了 {len(results)} 个改进版本！")
    print("=" * 80)

if __name__ == "__main__":
    main()
