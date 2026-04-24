# 基本面低相关 Alpha 模板推荐

这份文档从现有模板里挑出 5 类更适合做“低相关基本面组合”的骨架。

筛选原则：

- 优先选择经济学含义清晰的基本面模板。
- 尽量让 5 个模板来自不同的信号结构，而不是同一类模板的小改版。
- 目标不是单个模板一定最强，而是组合后更容易降低 self-correlation / PPAC。

---

## 1. 单字段双中性化模板

### 适用场景

适合跑单一含义很强的基本面字段，例如：

- ROA
- ROE
- operating margin
- gross margin
- asset turnover
- working capital / assets
- accruals

### 模板

```text
a = ts_zscore({datafield}, 252);
a1 = group_neutralize(a, bucket(rank(cap), range='0.1,1,0.1'));
a2 = group_neutralize(a1, industry);
b = ts_zscore(cap, 252);
b1 = group_neutralize(b, industry);
c = regression_neut(a2, b1);
c
```

### 核心逻辑

先对单个基本面字段做时序标准化，再做市值桶中性化和行业中性化，最后再把残余的 cap 影响回归剔除。

本质上，这是在找“某个财务特征在横截面上的异常强弱”。

### 为什么适合做低相关

这类模板主要吃的是单字段 level 信号，和下面那几类“财务关系偏离”“现金流状态分类”“综合多因子画像”不是一个风格。

### 建议优先尝试的字段

- `fnd72_s_pit_or_cf_q_cf_net_inc*2/(assets+last_diff_value(assets,300))`
- `inventory_turnover`
- `mdl175_workingcapital/assets`
- `mdl175_netassetgrowrate`

---

## 2. 财务对财务的截面残差模板

### 适用场景

适合研究两个本来应该相关、但当前横截面上出现偏离的财务变量。

### 模板

```text
A = sign(finance_var_A) * log(abs(finance_var_A) + 1);
B = sign(finance_var_B) * log(abs(finance_var_B) + 1);
regression_neut(A, B)
```

### 核心逻辑

不是看某个字段高不高，而是看 A 相对于 B 是否“异常”。

例如：

- 经营现金流相对净利润异常偏弱
- 存货相对营收异常偏高
- 资本开支相对销售异常偏大

### 为什么适合做低相关

它关注的是“财务关系偏离”，而不是单字段排序，所以和第 1 类模板通常不会太像。

### 常见可试变量对

- `operating_cashflow` 对 `net_income`
- `inventory` 对 `revenue`
- `capex` 对 `sales`
- `gross_profit` 对 `assets`

---

## 3. 财务对财务的时序残差稳定性模板

### 适用场景

适合挖“公司内部财务关系在时间上突然失衡”的信号。

### 模板

```text
residual = ts_regression(ts_zscore(A,500), ts_zscore(B,500), 500);
residual / ts_std_dev(residual, 500)
```

也可以扩展为：

```text
ts_regression(ts_zscore(A,500), ts_zscore(B,500), 500)
```

或：

```text
1 / ts_std_dev(ts_regression(ts_zscore(A,500), ts_zscore(B,500), 500), 500)
```

### 核心逻辑

它不是纯横截面因子，而是关注某家公司在较长窗口内，两个财务变量的联动关系是否发生了变化。

比如：

- 营收在增长，但利润没有同步增长
- 净利润在增长，但经营现金流没有跟上
- 存货和销售的关系开始恶化

### 为什么适合做低相关

这类模板偏时序结构，和第 1 类、第 2 类的横截面模板有明显差异，常常更有助于拉开相关性。

### 使用提醒

- 500 天窗口较长，覆盖率差的数据容易不稳定。
- 不建议一上来就跑太复杂的字段，先从高覆盖、更新相对稳定的财务字段开始。

---

## 4. 现金流结构分类模板

### 适用场景

适合做现金流画像，不再只盯利润或估值。

### 模板

```text
tmp = (group_rank(fnd72_s_pit_or_cf_q_cf_cash_from_inv_act, sector) > 0.5) * 4
    + (group_rank(fnd72_s_pit_or_cf_q_cf_cash_from_fnc_act, sector) > 0.5) * 2
    + (group_rank(fnd72_s_pit_or_cf_q_cf_cash_from_oper, sector) > 0.5) * 1;

2 * (tmp == 1) - (tmp == 2) - (tmp == 6)
```

### 核心逻辑

把公司按三类现金流的相对强弱做离散分类：

- 经营现金流
- 融资现金流
- 投资现金流

这不是连续型财务排序，而是在识别企业当前处于什么现金流状态。

### 为什么适合做低相关

它的输出更像“状态标签”，和常规的质量、成长、价值因子差别较大，天然更容易补充组合多样性。

### 适合搭配的方向

- 和 ROA / ROE 质量因子搭配
- 和 PB / BP 估值因子搭配
- 和应计项、营运效率类因子搭配

---

## 5. 多维质量-价值-营运综合模板

### 适用场景

适合做一个相对稳健的“基本面综合底仓模板”。

### 模板

```text
roa = group_zscore(fnd72_s_pit_or_cf_q_cf_net_inc*2/(assets+last_diff_value(assets,300)), sector);

pb = group_zscore(mdl175_bp, sector);

ITR = group_zscore(inventory_turnover, sector);

DtA = group_zscore(mdl175_debtsassetratio, sector);

WAtA = group_zscore(mdl175_workingcapital/assets, sector);

NAYOY = group_zscore(mdl175_netassetgrowrate, sector);

int2A = group_zscore(mdl175_intangibleassetratio, sector);

rank(regression_neut(regression_neut(regression_neut(regression_neut(regression_neut(regression_neut(regression_neut(roa,pb),ITR),DtA),WAtA),NAYOY),int2A),log(cap)))
```

### 核心逻辑

它把多个不同维度的基本面特征叠加在一起：

- 盈利能力
- 估值
- 营运效率
- 杠杆
- 营运资本
- 资产增长
- 无形资产占比

### 为什么适合做低相关

单独看，它未必比前面几类更低相关；但作为五类模板中的一类，它代表的是“综合画像”，可以和前面几种更单点、更偏结构化的模板形成互补。

### 使用提醒

- 这类模板更稳，但容易和你已有的 profitability/value alpha 重叠。
- 建议少做大量同类变体，否则容易把相关性重新拉高。

---

## 推荐的组合思路

如果你的目标是让这 5 个模板彼此尽量低相关，不建议五个都围绕“利润率”展开。更好的分工方式如下：

1. 单字段双中性化：跑营运效率或应计项
2. 截面残差模板：跑现金流 vs 利润
3. 时序残差模板：跑 capex vs sales 或 inventory vs revenue
4. 现金流结构模板：固定三大现金流
5. 综合模板：固定做质量 + 估值 + 杠杆 + 营运能力

这样五类模板分别对应：

- 单因子横截面异常
- 财务关系横截面偏离
- 财务关系时序偏离
- 现金流状态分类
- 多因子综合画像

这会明显好于“同一个模板只换 5 个相近字段”。

---

## 最后建议

- 先各模板跑少量高质量字段，不要一开始就盲目扩大量。
- 优先保留经济学解释清晰的版本，后续更容易过 OS 和描述审核。
- 如果要继续降低相关性，先换模板类别，再换字段。
- 在提交前，重点看 self-correlation、sub-universe、turnover 和最近两年稳定性。
