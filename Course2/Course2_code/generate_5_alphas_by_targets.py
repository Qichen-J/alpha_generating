#!/usr/bin/env python3
"""
基于期权数据低相关Alpha模板的5个目标思路
使用标准数据字段生成5个可提交的alpha
"""

import csv
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
        while time.time() - start_time < 60:  # 最多等待60秒
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
    print("=" * 70)
    print("基于期权低相关Alpha模板的5个目标 - 标准字段实现")
    print("=" * 70)
    
    # 建立会话
    sess = build_session(BRAIN_USERNAME, BRAIN_PASSWORD)
    auth_info = authenticate(sess)
    print(f"\n✅ 认证成功: {auth_info.get('user', {}).get('id', 'N/A')}\n")
    
    # 定义 5 个 alpha，基于期权模板的 5 个目标思路
    # 但使用标准数据字段实现
    
    alphas = [
        {
            "name": "Target 1: 波动率风险溢价均值回归",
            "description": "价格波动相对均值偏离后的回归",
            "expression": "group_neutralize(-rank(ts_zscore(ts_std_dev(returns,20), 126)) * rank(ts_zscore(close - ts_mean(close,126), 126)), bucket(rank(cap), range='0.1,1,0.1'))"
        },
        {
            "name": "Target 2: 尾部恐慌反转",
            "description": "急速价格变化的反转信号",
            "expression": "rank(ts_zscore(ts_delta(close, 5), 252)) * -rank(ts_rank(ts_std_dev(returns, 20), 252))"
        },
        {
            "name": "Target 3: 期限结构扭曲",
            "description": "短期与中期动量的差异",
            "expression": "group_neutralize(-rank(ts_delta(ts_zscore(returns, 20) - ts_zscore(returns, 63), 10)) * rank(ts_zscore(returns, 63)), industry)"
        },
        {
            "name": "Target 4: 成交拥挤反转",
            "description": "成交量拥挤后的反转",
            "expression": "rank(ts_zscore(ts_delta(volume, 3), 126)) * -rank(ts_delta(close, 5))"
        },
        {
            "name": "Target 5: 流动性压力反转",
            "description": "价格动量与成交量的不匹配",
            "expression": "group_neutralize(-rank(ts_delta(close, 5) - ts_zscore(volume, 126)) * rank(volume / ts_mean(volume, 20)), bucket(rank(cap), range='0.1,1,0.1'))"
        }
    ]
    
    results = []
    print("🚀 开始提交 5 个 alpha 表达式...\n")
    
    for i, alpha in enumerate(alphas, 1):
        print(f"\n{i}. {alpha['name']}")
        print(f"   描述: {alpha['description']}")
        print(f"   表达式: {alpha['expression'][:60]}...")
        
        resp = submit_simulation(sess, alpha['expression'])
        
        results.append({
            "idx": i,
            "name": alpha['name'],
            "expression": alpha['expression'],
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
    
    csv_path = OUTPUT_DIR / f"five_alphas_by_targets_{timestamp}.csv"
    results_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    
    json_path = OUTPUT_DIR / f"five_alphas_by_targets_{timestamp}.json"
    json_path.write_text(results_df.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")
    
    print("\n" + "=" * 70)
    print("✅ 生成并提交完成！")
    print(f"📄 CSV 结果: {csv_path}")
    print(f"📄 JSON 结果: {json_path}")
    print("=" * 70)
    
    # 显示简要结果
    print("\n📊 提交结果汇总:")
    done = (results_df['status'] == 'done').sum()
    timeout = (results_df['status'] == 'timeout').sum()
    error = (results_df['status'] == 'error').sum()
    exception = (results_df['status'] == 'exception').sum()
    
    total = len(results_df)
    print(f"  总提交: {total} 个")
    print(f"  ✅ 完成: {done} 个")
    print(f"  ⏱️  超时: {timeout} 个")
    print(f"  ❌ 错误: {error} 个")
    print(f"  💥 异常: {exception} 个")

if __name__ == "__main__":
    main()
