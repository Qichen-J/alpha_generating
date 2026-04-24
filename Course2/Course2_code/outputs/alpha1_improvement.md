# Alpha 1 改进方案

## 原始版本
```
group_neutralize(-rank(ts_zscore(ts_std_dev(returns,20), 126)) * rank(ts_zscore(close - ts_mean(close,126), 126)), bucket(rank(cap), range='0.1,1,0.1'))
```

## 问题分析

### 1. **经济逻辑不清晰**
- 原版本同时使用两个不同维度的信号（波动率变化 + 价格偏离），但没有清楚说明为什么要相乘
- 复杂的嵌套 zscore 操作容易过度拟合

### 2. **Sub-universe Test 风险** ⚠️
- 使用 `bucket(rank(cap))` 作为中性化分组会导致对流动性的依赖
- 在 TOP1000 vs TOP3000 测试中可能失败
- 建议用 `industry` 替代

### 3. **Turnover 过高**
- 每天都会重新排名和调整，成本高
- 没有使用 `trade_when` 等事件触发机制

### 4. **算子数量过多**
- 嵌套深度太深（3-4 层），违反了 PPAC 最佳实践（1-3 个平均算子）

### 5. **缺少实证根据**
- 根据 extra-standard-rubric，需要说明：
  - 为什么这个信号有效
  - 如何与现有 alpha 池多样化
  - 稳定性证据

---

## 改进方案 v1：简化 + 事件触发

**核心思想**：当波动率上升时（市场恐慌），价格偏离均值的因子更可靠

```fast
# v1: 简化 + 流动性友好
signal = ts_zscore(close - ts_mean(close, 63), 126)
vol_state = ts_rank(ts_std_dev(returns, 20), 252)
alpha = group_neutralize(-rank(signal), industry)
trade_when(vol_state > 0.6, alpha, -1)
```

**改进点**：
✅ 单一清晰信号（价格均值回归）  
✅ 条件触发（降低 turnover）  
✅ 使用 `industry` 中性化（通过 sub-universe test）  
✅ 简化的算子链（3 步）  
✅ 明确的触发逻辑：高波动时启动

---

## 改进方案 v2：中等复杂度（平衡性能与鲁棒性）

**核心思想**：结合短期价格动量反转和流动性过滤

```fast
# v2: 保留原信号但简化
momentum_signal = ts_zscore(ts_delta(close, 5), 126)
volatility_filter = ts_rank(ts_std_dev(returns, 20), 252)
raw_alpha = -rank(momentum_signal) * rank(volatility_filter)
alpha = group_neutralize(raw_alpha, industry)
trade_when(volume > ts_mean(volume, 20), alpha, -1)
```

**改进点**：
✅ 用 `ts_delta` 替代 `close - mean`（更标准）  
✅ 流动性过滤（避免 illiquid 股票）  
✅ `industry` 中性化  
✅ 成交量触发（同时控制 turnover 和流动性风险）  

---

## 改进方案 v3：最简版（高稳定性）

如果追求最高的 sub-universe 通过率和跨区域稳定性：

```fast
# v3: 极简 + 高鲁棒性
alpha = -rank(ts_zscore(close - ts_mean(close, 63), 126))
trade_when(volume > adv20, alpha, -1)
```

**优点**：
✅ 无中性化参数（市场级信号）  
✅ 单一清晰逻辑：价格均值回归  
✅ 最低 sub-universe 失败风险  
✅ 最简的参数（1 个时间窗，无其他超参数）  
✅ 易于跨数据集验证  

**缺点**：
❌ 无 sector 隔离  
❌ 可能相关性高

---

## 建议选择

根据 `extra-standard-rubric.md` 和 `improvement-roadmap.md`：

**优先级 1**（推荐提交）：**v3 极简版**
- 通过 sub-universe test 的概率最高
- 符合 PPAC 最佳实践（简单算子）
- 易于验证，避免过度拟合

**优先级 2**（如需更高收益）：**v2 中等版**  
- 保留多因子结构
- 流动性友好
- 但需要更多验证

**不推荐**：保留原版本
- 复杂度高导致 sub-universe test 失败风险
- 难以解释的多层嵌套

---

## 实施建议

1. **先提交 v3**：最稳妥的版本
2. **生成自相关矩阵**：检查与其他 4 个 alpha 的 correlation（< 0.4 为佳）
3. **验证 sub-universe**：在 TOP1000 上测试性能
4. **记录决策**：按 extra-standard-rubric 的模板填写：
   - `idea_summary`: 价格均值回归
   - `rationale`: 均值偏离后的回归概率
   - `stability_notes`: sub-universe 稳定性
   - `diversification_notes`: 与其他 4 个 alpha 的低相关特性

---

## 关键参考文件

- `extra-standard-rubric.md`: 要求清晰的经济逻辑和简单实现
- `subinverse.md`: 避免 cap 相关的权重
- `reduce_turnover.md`: 使用 `trade_when` 控制交易频率
- `improvement-roadmap.md`: Phase 3 建议添加算子分布检查
