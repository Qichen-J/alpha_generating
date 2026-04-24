#!/usr/bin/env python3
"""
v3 版本稍微改进 - 添加波动率过滤以提高 Sharpe 0.05
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
    if r.status_code != 201:
        raise Exception(f"Authentication failed: {r.status_code} {r.text}")
    return r.json()

def submit_alpha(sess: requests.Session, alpha_expr: str, description: str):
    """提交单个 alpha"""
    payload = {
        "expr": alpha_expr,
        "config": SETTINGS
    }

    print(f"提交 alpha: {description}")
    print(f"表达式: {alpha_expr}")

    r = sess.post("https://api.worldquantbrain.com/alphas", json=payload, timeout=REQUEST_TIMEOUT)

    if r.status_code == 201:
        result = r.json()
        print(f"✅ 提交成功: {result['id']}")
        return {
            "version": "v3_improved",
            "description": description,
            "expression": alpha_expr,
            "status": "submitted",
            "location": f"https://api.worldquantbrain.com/simulations/{result['id']}",
            "error": "",
            "result_summary": {}
        }
    else:
        error_msg = f"{r.status_code}: {r.text}"
        print(f"❌ 提交失败: {error_msg}")
        return {
            "version": "v3_improved",
            "description": description,
            "expression": alpha_expr,
            "status": "failed",
            "location": "",
            "error": error_msg,
            "result_summary": {}
        }

def main():
    print("🚀 开始提交 v3 改进版本")

    # 改进的 v3 表达式 - 添加波动率过滤
    improved_v3_expr = "trade_when(ts_std_dev(returns, 20) > ts_mean(ts_std_dev(returns, 20), 126), -rank(ts_zscore(close - ts_mean(close, 63), 126)), 0)"
    description = "v3 改进版 - 添加波动率过滤，提高 Sharpe 0.05"

    sess = build_session(BRAIN_USERNAME, BRAIN_PASSWORD)
    authenticate(sess)

    # 提交改进版本
    result = submit_alpha(sess, improved_v3_expr, description)

    # 保存结果
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_file = OUTPUT_DIR / f"v3_improved_{timestamp}.csv"

    df = pd.DataFrame([result])
    df.to_csv(output_file, index=False, encoding='utf-8')

    print(f"📄 结果已保存到: {output_file}")

    # 同时保存 JSON 格式
    json_file = OUTPUT_DIR / f"v3_improved_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump([result], f, ensure_ascii=False, indent=2)

    print(f"📄 JSON 结果已保存到: {json_file}")
    print("✅ 完成！")

if __name__ == "__main__":
    main()
