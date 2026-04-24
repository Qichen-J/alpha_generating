#!/usr/bin/env python3
"""
使用修复后的模板重新运行 alpha 模拟
"""

import csv
import json
import time
from pathlib import Path

# 导入必要的模块（与原 notebook 相同）
import itertools
import os
import re
import requests
from requests.auth import HTTPBasicAuth
import pandas as pd
from datetime import datetime, timezone

# 配置（使用修复后的模板）
ROOT = Path("/Users/zhiqu/Desktop/brain")
FIXED_TEMPLATES_CSV = ROOT / "Course2" / "Course2_code" / "outputs" / "expanded_templates_fixed.csv"
OUTPUT_DIR = ROOT / "Course2" / "Course2_code" / "outputs"

BRAIN_USERNAME = "xxxxxx@example.com"
BRAIN_PASSWORD = "xxxxxx"

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
    payload = {"type": SETTINGS["type"], "settings": SETTINGS["settings"], "regular": expression}

    try:
        r = sess.post("https://api.worldquantbrain.com/simulations", json=payload, timeout=REQUEST_TIMEOUT)
        if r.status_code >= 400:
            return {"status": "submit_error", "error": f"HTTP {r.status_code}: {r.text[:300]}"}
        location = r.headers.get("Location")
        if not location:
            return {"status": "submit_no_location", "error": "Missing Location header"}

        while True:
            pr = sess.get(location, timeout=REQUEST_TIMEOUT)
            if pr.status_code >= 400:
                return {"status": "poll_error", "location": location, "error": f"HTTP {pr.status_code}: {pr.text[:300]}"}

            retry_after = float(pr.headers.get("Retry-After", 0))
            if retry_after == 0:
                data = pr.json()
                return {
                    "status": "done",
                    "location": location,
                    "alpha_id": data.get("alpha"),
                    "result": data
                }

            time.sleep(max(retry_after, 1.0))

    except Exception as ex:
        return {"status": "exception", "error": str(ex)}

def main():
    print("🔧 使用修复后的模板重新运行 alpha 模拟")
    print("=" * 50)

    # 建立会话
    sess = build_session(BRAIN_USERNAME, BRAIN_PASSWORD)
    auth_info = authenticate(sess)
    print(f"✅ 认证成功: {auth_info['user']['id']}")

    # 读取修复后的模板
    fixed_templates = []
    with open(FIXED_TEMPLATES_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        print(f"CSV 列名: {reader.fieldnames}")  # 调试信息
        for row in reader:
            # 处理 BOM 字符
            clean_row = {k.lstrip('\ufeff'): v for k, v in row.items()}
            if clean_row.get('fixed', '').strip() == 'true':  # 只使用修复后的模板
                fixed_templates.append({
                    'template_id': clean_row['template_id'],
                    'expression': clean_row['expression']
                })

    print(f"📋 找到 {len(fixed_templates)} 个修复后的模板")

    # 提交模拟
    results = []
    for i, template in enumerate(fixed_templates, 1):
        expr = template['expression']
        print(f"🚀 提交模板 {i}/{len(fixed_templates)}: {expr[:50]}...")

        resp = submit_simulation(sess, expr)
        results.append({
            "idx": i,
            "template_id": template["template_id"],
            "expression": expr,
            "status": resp.get("status"),
            "alpha_id": resp.get("alpha_id"),
            "location": resp.get("location"),
            "error": resp.get("error"),
            "result": json.dumps(resp.get("result", {}), ensure_ascii=False)
        })

        if (i) % 2 == 0:
            print(f"📊 进度: {i}/{len(fixed_templates)}")

        # 避免请求过于频繁
        time.sleep(1)

    # 保存结果
    results_df = pd.DataFrame(results)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    results_path = OUTPUT_DIR / f"simulation_status_fixed_{timestamp}.csv"
    results_df.to_csv(results_path, index=False, encoding="utf-8-sig")

    json_path = OUTPUT_DIR / f"simulation_status_fixed_{timestamp}.json"
    json_path.write_text(results_df.to_json(orient="records", force_ascii=False, indent=2), encoding="utf-8")

    # 生成总结
    summary = (
        results_df.groupby("status", dropna=False)
        .agg({
            "status": ["count", lambda x: x.eq("done").sum()],
            "result": [lambda x: (~x.fillna("{}").eq("{}")).sum()],
            "location": [lambda x: (~x.isna()).sum()]
        })
        .reset_index()
        .sort_values(("status", "count"), ascending=False)
    )

    # 重命名列
    summary.columns = ["status", "cnt", "done_cnt", "with_result_cnt", "with_location_cnt"]

    summary_path = OUTPUT_DIR / f"simulation_summary_fixed_{timestamp}.csv"
    summary.to_csv(summary_path, index=False, encoding="utf-8-sig")

    print("\n✅ 模拟完成！")
    print(f"📄 结果文件: {results_path}")
    print(f"📄 总结文件: {summary_path}")
    print(f"📊 总计提交: {len(results)} 个 alpha")

    # 显示总结
    print("\n📈 模拟结果总结:")
    for _, row in summary.iterrows():
        print(f"  {row['status']}: {int(row['cnt'])} 个")

if __name__ == "__main__":
    main()