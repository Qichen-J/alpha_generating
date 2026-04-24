#!/usr/bin/env python3
"""
基于 option8 数据字段生成 5 个可提交的 alpha 表达式
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

def get_datafields(sess: requests.Session, search_term: str = "option") -> pd.DataFrame:
    """获取包含搜索词的数据字段"""
    datafields = []
    offset = 0
    
    while True:
        url = (
            f"https://api.worldquantbrain.com/data-fields"
            f"?instrumentType=EQUITY&region=USA&delay=1&universe=TOP3000"
            f"&limit=100&offset={offset}&search={search_term}"
        )
        
        r = sess.get(url, timeout=REQUEST_TIMEOUT)
        if r.status_code >= 400:
            break
        
        results = r.json()
        if not results:
            break
        
        for item in results:
            datafields.append({
                "name": item.get("name"),
                "description": item.get("description", ""),
                "type": item.get("type")
            })
        
        if len(results) < 100:
            break
        
        offset += 100
        time.sleep(0.5)
    
    return pd.DataFrame(datafields)

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
        while True:
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
    
    except Exception as ex:
        return {"status": "exception", "error": str(ex)}

def main():
    print("=" * 60)
    print("基于 option8 生成 5 个可提交的 Alpha")
    print("=" * 60)
    
    # 建立会话
    sess = build_session(BRAIN_USERNAME, BRAIN_PASSWORD)
    auth_info = authenticate(sess)
    print(f"✅ 认证成功: {auth_info.get('user', {}).get('id', 'N/A')}\n")
    
    # 查询 option 相关数据字段
    print("🔍 查询 option 相关数据字段...")
    df_fields = get_datafields(sess, search_term="option")
    print(f"找到 {len(df_fields)} 个 option 相关字段:\n")
    
    if len(df_fields) > 0:
        print(df_fields[["name"]].head(15).to_string(index=False))
    else:
        print("  未找到 option 相关字段，将使用通用字段生成 alpha\n")
    
    # 定义 5 个基于 option8 的 alpha 表达式
    # 如果找到 option 字段，使用第一个
    option_field = df_fields.iloc[0]["name"] if len(df_fields) > 0 else "close"
    
    print(f"\n📌 使用数据字段: {option_field}\n")
    
    alphas = [
        {
            "name": "Alpha 1: Option Momentum",
            "expression": f"rank(ts_rank({option_field}, 20))"
        },
        {
            "name": "Alpha 2: Option Mean Reversion",
            "expression": f"rank(-ts_zscore({option_field}, 63))"
        },
        {
            "name": "Alpha 3: Option Group Neutralize",
            "expression": f"group_neutralize(rank({option_field}), bucket(rank(cap), range='0.1,1,0.1'))"
        },
        {
            "name": "Alpha 4: Option Decay Factor",
            "expression": f"ts_decay_linear(rank(ts_delta({option_field}, 5)), 20)"
        },
        {
            "name": "Alpha 5: Option Sector Mean",
            "expression": f"rank({option_field} - group_mean({option_field}, sector))"
        }
    ]
    
    results = []
    print("🚀 提交 5 个 alpha 表达式...\n")
    
    for i, alpha in enumerate(alphas, 1):
        print(f"{i}. {alpha['name']}")
        print(f"   表达式: {alpha['expression'][:70]}...")
        
        resp = submit_simulation(sess, alpha['expression'])
        
        results.append({
            "idx": i,
            "name": alpha['name'],
            "expression": alpha['expression'],
            "status": resp.get('status'),
            "location": resp.get('location'),
            "error": resp.get('error'),
            "result": json.dumps(resp.get('result', {}), ensure_ascii=False)
        })
        
        if resp.get('status') == 'done':
            print(f"   ✅ 提交成功")
        else:
            print(f"   ❌ 状态: {resp.get('status')}")
        
        time.sleep(1)
    
    # 保存结果
    results_df = pd.DataFrame(results)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    
    csv_path = OUTPUT_DIR / f"option8_alphas_{timestamp}.csv"
    results_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    
    json_path = OUTPUT_DIR / f"option8_alphas_{timestamp}.json"
    json_path.write_text(results_df.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")
    
    print("\n" + "=" * 60)
    print("✅ 生成完成！")
    print(f"📄 CSV 结果: {csv_path}")
    print(f"📄 JSON 结果: {json_path}")
    print("=" * 60)
    
    # 显示简要结果
    print("\n📊 提交结果汇总:")
    success = (results_df['status'] == 'done').sum()
    total = len(results_df)
    print(f"  总提交: {total} 个")
    print(f"  成功: {success} 个")
    print(f"  失败: {total - success} 个")

if __name__ == "__main__":
    main()
