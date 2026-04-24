# 期权数据低相关 Alpha 模板（五个最不一样的目标）

设计依据：
- 参考“可以尝试使用的Alpha模板.md”的模板化写法（先做信号，再做中性化/回归去风险，再加交易触发）。
- 参考“如何用乐高的方式增加 Alpha 模板.md”的积木化思路（固定若干算子块，围绕目标分层组合，避免盲目加深层数）。

使用建议：
- 先在 USA / TOP3000 / Delay=1 测试，test period 建议先 2Y，降低过拟合风险。
- 每个模板只改少量参数（窗口、group、阈值），先做 20-50 个变体，再筛选。
- 期权字段名请按你账号可用数据字段替换，下文用大写占位符表示。

## 乐高积木定义（固定不变）

- `G_CAP = bucket(rank(cap), range='0.1,1,0.1')`
- `RISK = abs(ts_mean(returns,252)/ts_std_dev(returns,252))`
- `BASE_NEUT(x) = group_neutralize(x, G_CAP)`
- `RISK_NEUT(x) = regression_neut(BASE_NEUT(x), RISK)`

---

## 目标1：波动率风险溢价（IV-RV）均值回归

核心想法：隐含波动率相对实现波动率显著偏高时，后续更倾向回归。

```fast
iv_rv_gap = ts_zscore(OPTION_IV_30D - ts_std_dev(returns,20), 126);
term_shape = ts_zscore(OPTION_IV_30D - OPTION_IV_90D, 126);
raw = -rank(iv_rv_gap) * rank(term_shape);
alpha = RISK_NEUT(raw);
trade_when(volume > adv20, alpha, -1)
```

---

## 目标2：偏度/尾部恐慌错价（Skew Shock）

核心想法：认沽偏度急剧抬升常对应尾部恐慌，后续存在风险重定价。

```fast
skew_shock = ts_zscore(ts_delta(OPTION_PUT_CALL_SKEW_25D,5), 252);
panic = ts_rank(OPTION_PUT_CALL_VOLUME_RATIO, 60);
rv_state = ts_rank(ts_std_dev(returns,20), 252);
raw = rank(skew_shock) * rank(panic) * rank(rv_state);
alpha = RISK_NEUT(raw);
trade_when(rv_state < 0.95, alpha, -1)
```

---

## 目标3：期限结构扭曲（Term Structure Twist）

核心想法：短端与长端IV的斜率变化可反映风险预期切换，和纯价格动量相关性通常较低。

```fast
slope = OPTION_IV_30D - OPTION_IV_180D;
twist = ts_zscore(ts_delta(slope,10), 252);
carry = ts_zscore(slope, 126);
raw = -rank(twist) * rank(carry);
alpha = RISK_NEUT(raw);
trade_when(abs(returns) < 0.08, alpha, -1)
```

---

## 目标4：期权成交/持仓拥挤反转（Flow Crowding Reversal）

核心想法：期权端成交量和持仓量的异常拥挤，常对应短期交易拥堵，后续有反转概率。

```fast
flow = ts_zscore(OPTION_VOLUME / (OPTION_OPEN_INTEREST + 1), 126);
flow_jump = ts_rank(ts_delta(flow,3), 60);
price_ext = ts_rank(ts_delta(close,5), 60);
raw = -rank(flow_jump) * rank(price_ext);
alpha = RISK_NEUT(raw);
trade_when(OPTION_OPEN_INTEREST > ts_mean(OPTION_OPEN_INTEREST,20), alpha, -1)
```

---

## 目标5：Delta/Gamma 对冲压力（Hedging Pressure）

核心想法：做市商对冲压力变化（delta/gamma proxy）会反馈到现货微观价格行为。

```fast
delta_pressure = ts_zscore(OPTION_NET_DELTA_EXPOSURE, 126);
gamma_pressure = ts_zscore(OPTION_NET_GAMMA_EXPOSURE, 126);
hedge_imbalance = ts_rank(delta_pressure - gamma_pressure, 60);
liq_state = ts_rank(volume/sharesout, 60);
raw = -rank(hedge_imbalance) * rank(liq_state);
alpha = RISK_NEUT(raw);
trade_when(volume > adv20, alpha, -1)
```

---

## 为什么这5个目标“最不一样”

- 目标1：定价偏离（IV-RV）
- 目标2：分布形态（Skew/尾部概率）
- 目标3：跨期限结构（term structure）
- 目标4：交易行为（flow/open interest 拥挤）
- 目标5：微观机制（做市商对冲压力）

它们分别来自不同经济机制，通常能显著降低模板之间自相关。

## 参数扩展建议（用于乐高批量展开）

- 时间窗层：`[20, 60, 126, 252]`
- 变化层：`ts_delta(x, [3,5,10])`
- 归一层：`rank / ts_zscore / ts_rank`
- 中性层：`group_neutralize(..., industry)` 与 `bucket(rank(cap))` 两套并行
- 触发层：`trade_when(volume>adv20, ...)` / `trade_when(ts_rank(ts_std_dev(returns,10),252)<0.9, ...)`

建议先固定一个目标做 2-3 层积木扩展，单目标保留前20%，再做跨目标融合。