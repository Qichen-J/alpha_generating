可以尝试使用的Alpha模板 置顶的
359 人关注

WL13229
1年前 已编辑于
请注意，本贴仅收集总结，优秀程度不一定。
部分存在严重overfitting风险，请参加更多顾问活动及课程解锁insight。
regression_neut(regression_neut(group_neutralize(group_zscore(\
vec_avg({data}),sector),bucket(rank(cap),range="0.1,1,0.1")),\
group_neutralize(group_zscore(cap,sector),bucket(rank(cap),range="0.1,1,0.1"))),\
ts_ir(returns-group_median(returns,sector),126))
fear = ts_mean(abs(returns - group_mean(returns,1,market))/(abs(returns)+abs(group_mean(returns,1,market))+0.1),20);\
-group_neutralize(fear*group_normalize(ts_decay_exp_window(ts_percentage(vec_count(rsk82_raw_m3g_tni_p_su_fte),60,percentage=0.9)\
-ts_percentage(vec_count({data}),60,percentage=0.1),20, factor=0.8),market)*inverse(abs(ts_entropy(volume,20)))\
,bucket(rank(cap),range="0.1,1,0.1"))
d1_level=ts_max(vec_stddev({data}),20);\
d1_stability=ts_kurtosis(vec_stddev({data}),20);\
mkt_level=group_min(d1_stability,industry);\
-group_neutralize(d1_stability<=mkt_level?-d1_level:d1_level,bucket(rank(cap),range="0.1,1,0.1"))
group = bucket(rank(cap),range='0.1,1,0.1');

risk = rank(-ts_av_diff(vec_min({Analyst Std}),360));

alpha=rank((1-risk)*group_rank(ts_scale(vec_max({OptionHighPrice})/close,120),industry));

group_neutralize(ts_mean(alpha,2),group)
Decay设置为10，Neutralize设置为industry
my_group = market;

my_group2 = bucket(rank(cap),range='0,1,0.1');

alpha=rank(group_rank(ts_decay_linear(volume/ts_sum(volume,252),10),my_group)*group_rank(ts_rank(vec_avg({Fundamental})),my_group)*group_rank(-ts_delta(close,5),my_group));

trade_when(volume>adv20,group_neutralize(alpha,my_group2),-1)
market_return = group_mean(returns,1,market);

fear = ts_mean(abs(returns - market_return)/(abs(returns)+abs(market_return)),20);

vhat = ts_regression(volume,ts_mean(vec_avg({Sentiment}),5),120);

ehat = ts_regression(returns-market_return,vhat,120);

alpha = group_neutralize(-ehat*rank(fear),bucket(rank(cap),range='0,1,0.1'));

trade_when(abs(returns)<0.075,regression_neut(alpha,volume),abs(returns)>0.1)
Decay设置为20，Neutralize设置为industry
vector_neut(group_neutralize(group_neutralize(ts_arg_max(vec_norm({datafield}), 220),bucket(rank(assets), range="0.1,1,0.1")),subindustry), group_normalize(ts_delay(cap, 220),subindustry))
sentiment = ts_backfill(ts_delay( vec_avg(SENTIMENT FROME OTHER),1),20)

vhat=ts_regression(volume,sentiment,250); 

ehat=-ts_regression(returns,vhat,750); 1

alpha=group_rank(ehat,bucket(rank(cap),range='0,0.1,0.1'))
IR = abs(ts_mean(returns,252)/ts_std_dev(returns,252));      
 
regression_neut ( vector_neut (ts_zscore( vec_max (ANALYST)/close, 126),ts_median(cap, 126) ),IR)
small_sell = vec_sum(SPECIAL SELL ORDER);

small_buy = vec_sum(SPECIAL BUY ORDER);

fac = - small_sell - small_buy;

fac_diff_mean = power(rank(fac - group_mean(fac, 1, subindustry)),D);

IR = abs(ts_mean(returns,126)/ts_std_dev(returns,126));

group_neutralize(regression_neut(group_neutralize(fac_diff_mean,bucket(rank(cap), range='-0.1,1,0.1')),IR),sta1_top3000c10)
trade_when(ts_rank(ts_std_dev(returns,10),252)<0.9,-regression_neut(group_neutralize(ts_std_dev(vec_avg(volatility),20)/ ts_mean(vec_avg(volatility),20),bucket(rank(assets),range = '0,1,0.1')),ts_std_dev(returns,30))+group_neutralize(-ts_std_dev(vec_avg(volume)/sharesout,30)/ ts_mean(vec_avg(volume)/sharesout,30),bucket(rank(cap), range = '0,1,0.1')),-1)
e = power(group_rank(-ts_decay_exp_window(ts_sum(if_else(vwap-group_mean(vwap,1,industry)-0.01>0,1,0)*ts_corr((log(volume/sharesout)),cap,5),5),20),industry),3);
trade_when(ts_rank(ts_std_dev(returns,10),252)<0.9,e,-1)
vector_neut(power(rank(group_neutralize(-ts_decay_exp_window(ts_sum(if_else((alpha)-group_mean((alpha),1,bucket(rank(assets),range = '0,1,0.1'))-0.02>0,1,0)*ts_co_kurtosis(vec_sum(turnover),cap,5),3)/3,50),industry)),2),assets)
signal = ts_rank(vec_stddev{fnd}, 60);
signal_str = group_rank(signal, bucket(rank(cap), range='0.1,1,0.2'));
pv_info = ts_rank(close, 60);
pv_info_str = group_neutralize(close, bucket(rank(cap), range='0.1,1,0.2'));
IR = abs(ts_mean(returns,126)/ts_std_dev(returns,126));;
rank(vector_neut(vector_neut(signal_str, pv_info_str),IR))
market_pv = group_mean(adv20,1,market);
modified = vec_avg(anl);
short_term_excess_return = ts_mean(pv-market_pv,5);
long_term_excess_return = ts_delay(ts_mean(pv-market_pv,120),120);
parf = regression_neut(regression_neut(modified,short_term_excess_return),long_term_excess_return);
group_zscore(parf,subindustry)
piece_1 = group_mean(vec_stddev(anl) , 1 , subindustry) - vec_stddev(anl)
time_mean(piece_1, 60)
{ts_opr_1}({group_opr}(ts_opr_2(rank({vector_opr}({pv_field})),rank({vector_opr}({vol_field})),{days1}),{grouping}){,days2})
market_returns = group_mean(returns,cap,market);
modified = vec_sum(Analyst);
short_term_excess_return = ts_mean(returns-market_returns,5);
long_term_excess_return = ts_delay(ts_mean(returns-market_returns,20),20);
parf = regression_neut(regression_neut(modified,short_term_excess_return),long_term_excess_return);
trade_when(ts_rank(ts_std_dev(market_returns,10),252)<0.9,group_neutralize(parf,bucket(rank(cap),range='0,1,0.1')),-1)
my_group=bucket(rank(cap),range='0,1,0.1');
Alpha=group_rank(ts_decay_linear(volume/ts_sum(volume,252),20),my_group)*group_rank(ts_co_kurtosis(news_data,returns,252),my_group)*group_rank(-ts_delta(close,5),my_group)
a = ts_zscore({datafield, 252);a1 = group_neutralize(a, bucket(rank(cap), range='0.1,1,0.1'));a2 = group_neutralize(a1, industry);b = ts_zscore(cap, 252);b1 = group_neutralize(b, industry);c = regression_neut(a2,b1);c
group_neutralize(ts_co_skewness(rp_nip_inverstor,ts_co_skewness(vec_max(nws18_qep),rp_css_ratings,225),225),bucket(rank(beta_last_30_days_spy), range="0,1,0.1"))
regression_neut(vector_neut(ts_rank(vec_max({ANALYST})/close,120),ts_median(cap, 120) ),abs(ts_mean({RETURNS},252)/ts_std_dev({RETURNS},252)))
small_sell = vec_sum({sell_order});
small_buy = vec_sum({buy_order});
fac = small_sell - small_buy;
fac_diff_mean = power(rank(fac - group_mean(fac, 1, subindustry)),{days});
IR = abs(ts_mean(returns,126)/ts_std_dev(returns,126));
group_neutralize(regression_neut(group_neutralize(fac_diff_mean,bucket(rank(cap), range='-0.1,1,0.1')),IR),sta1_top3000c10)
roa = group_zscore(fnd72_s_pit_or_cf_q_cf_net_inc*2/(assets+last_diff_value(assets,300)),sector);

pb = group_zscore(mdl175_bp,sector);

ITR = group_zscore(inventory_turnover,sector);

DtA = group_zscore(mdl175_debtsassetratio,sector);

WAtA = group_zscore(mdl175_workingcapital/assets,sector);

NAYOY = group_zscore(mdl175_netassetgrowrate,sector);

int2A = group_zscore(mdl175_intangibleassetratio,sector);

rank(regression_neut(regression_neut(regression_neut(regression_neut(regression_neut(regression_neut(regression_neut(roa,pb),ITR),DtA),WAtA),NAYOY),int2A),log(cap)))
<Arithmetich_or Transformational_op>(<ts_compare_op>(<Company Fundamental Data for Equity>， <Price Volume Data for Equity>， <days>)*<Company Fundamental Data for Equity>)
系列1
A = sign(finance_var)*log(abs(finance_var)+1));

B = sign(finance_var)*log(abs(finance_var)+1));

regression_neut(A,B)
系列2
ts_regression (ts_zscore(A,500), ts_zscore(B,500),500)
系列3
1/ts_std_dev(ts_regression (ts_zscore(A,500), ts_zscore(B,500),500)，500)
系列4
residual = ts_regression (ts_zscore(A,500), ts_zscore(B,500),500);

residual/ts_std_dev(residual ，500)
系列5
ts_regression (ts_zscore(A,500), timestep(500),500);
上述5个系列后续可以尝试同时结合截面回归和时序回归。通过截面回归处理财务数据的分布，通过时序回归找出robust的signal
缩小space。上述财务数据并没用限制，因此空间非常大；建议从盈利成长、成本、经营、安全性等重要维度先进行搜索，另外，可以先不考虑覆盖率较低的datafield
可以用分析师数据代替财务数据，比如净利润
基本面量化建议从经济逻辑出发，也不建议使用很复杂的公式，容易overfitting（因为数据点较少，很容易fit噪音）
注意窗口设置时的500天，这实际上会导致回归时变量的方差被低估
注意口径问题/数据及时利用问题。口径问题是指：在财报发布的月份中，比如4月，A公司比B公司先发，此时B公司还是t-1期的财务数据，而A公司是t期的财务数据，由于Brain是日频调仓，可能不具备可比性；但如果不及时利用数据，收益也会被其他交易者兑现，因此需要权衡。但大多数情况下，口径问题<<<<<<<<数据及时利用问题，因此该问题建议注意而不是规避
在计量经济学中，还有“互为因果”的问题，我对这个问题的了解没有那么深入，不过直觉上很好理解。我们拿到的财务数据，是静态的，也就是说，我们不清楚这样的财务数据是如何形成的。例如成本越高，收益越高，互为因果现象会是：成本越高，我的收益理应变高，收益变高，我就会更激进地投入生产，提高成本，这也会导致估计量有误。传统的解决方法为引入额外的工具变量，在做alpha中，我们也许可以融合另类数据，比如财务附注中的语气，判断公司是激进扩张还是稳扎稳打，从而决定 变量在回归中的位置
shout out to YW93864
<group_compare_op>(
  <transform_op>(
    <logical_op>(
      greater(
        ts_zscore(<ts_compare_op>(<news_metric>, <days>), <lookback_days>),
        <threshold>
      ),
      ts_zscore(<news_metric>, <days>),
      <default_value>
    )
  ),
  <parameters>
), <group>
)

e.g
group_rank(
  filter(
    sigmoid(
      if_else(
        greater(ts_zscore(news_sentiment, 30), 1),
        ts_zscore(news_sentiment, 30),
        0
      )
    ),
    h="1 2 3 4",
    t="0.5"
  ),
  industry
)

tmp = (group_rank(fnd72_s_pit_or_cf_q_cf_cash_from_inv_act, sector) > 0.5) * 4 + (group_rank(fnd72_s_pit_or_cf_q_cf_cash_from_fnc_act, sector) > 0.5) * 2 + (group_rank(fnd72_s_pit_or_cf_q_cf_cash_from_oper, sector) > 0.5) * 1;

2 * (tmp == 1) - (tmp == 2) - (tmp == 6)
(((ts_rank(ts_backfill({i}, 30), 504) < 0.5) && (ts_rank(ts_backfill({j}, 30), 504) > 0.5)) ? ts_rank(ts_backfill({i}, 30), 504) : -ts_rank(ts_backfill({i}, 30), 504))
目前已在GLB测试了 {i} 和 {j} 都是 fundamental72 的情况。
power(ts_std_dev(abs(returns),30),2)-power(ts_std_dev(returns,30),2) 
IR = abs(ts_mean(returns,252)/ts_std_dev(returns,252));
r=returns;
a=power(ts_std_dev(abs(r)+r,30),2);
b=power(ts_std_dev((abs(r)-r),30),2);
c=regression_neut(b-a,IR);
group_neutralize(group_neutralize(c,bucket(rank(cap),range='0.2,1,0.2')),country)
- ts_delta(A, 3)，用于挖掘反转因子（时间参数可以根据dataset/datafield调整）。通过遍历pv1, model77两个dataset共计12+536=548个datafield，筛选只显示sharp>2的alpha

a = -ts_delta(datafield,3);

b=abs(ts_mean(returns,252)/ts_std_dev(returns,252));

group_neutralize(vector_neut(a,b),subindustry)
- A * ts_std_dev(A, 30)，我称其为“小而稳”（时间参数可根据Dataset/Datafield调整）。

a = - A * ts_std_dev(A, 20);

b=abs(ts_mean(returns,252)/ts_std_dev(returns,252));

vector_neut(a,b)
nss = ts_backfill(se_score,20);

processed_news_sentiment = (nss - ts_mean(nss,250))/ts_std_dev(nss,250);

monthly_returns = ts_ir(returns,20);

processed_returns = ts_backfill(monthly_returns, 20);

ranked_sentiment = ts_mean(group_rank(processed_news_sentiment,industry), 20);

ranked_returns = ts_mean(group_rank(-processed_returns,industry), 20);  // Negative to rank low returns higher

lrhs = add(ranked_sentiment, ranked_returns);  // Assuming delay mimics the holding until realization

hrls = add(inverse(ranked_sentiment), inverse(ranked_returns));  // Inverse to get the opposite characteristics

alpha = subtract(lrhs, hrls);

alpha

TOP3000 INDUSTRY DECAY 60 30
# day1
d1_mean = ts_mean(close/ts_delay(close, 1)-1,20);
d1_std = ts_std_dev(close/ts_delay(close, 1)-1,20);
d1_mkt_mean = group_mean(d1_std, 1, market);
d1_std_rev = d1_std<d1_mkt_mean?-d1_mean:d1_mean;
tnv = volume/(sharesout*1000000);
tnv_diff = ts_delta(tnv, 1);
mkt_tnv_mean = group_mean(tnv_diff, 1, market);
rev_return = tnv_diff<mkt_tnv_mean?-(returns): (returns);
d1_tnv_rev = ts_mean(rev_return, 20);
# dayo
do_return = close/open-1;
do_mean = ts_mean(d0_return, 20);
do_std = ts_std_dev(do_return, 20);
do_mkt_mean = group_mean(d0_std, 1, market);
do_std_rev = d0_std<d0_mkt_mean?-d0_mean:d0_mean;
do_rev = tnv_diff<mkt_tnv_mean?- (do_return): (d0_return);
d0_tnv_rev = ts_mean(do_rev, 20);
# day night
night_ret = open/ts_delay(close, 1);
night_mkt_mean = group_mean(night_ret, 1, market);
night_dist = abs (night_ret - night_mkt_mean);
dist_mean = ts_mean(night_dist,20);
dist_std = ts_std_dev(night_dist,20);
night_mean = group_mean(dist_std, 1, market);
night_std_rev = dist_std<night_mean?-dist_mean:dist_mean;
delay_tnv_change = ts_delay(tnv_diff, 1);
delay_market_tnv_mean = group_mean(delay_tnv_change, 1, market);
tnv_dist = abs (delay_tnv_change-delay_market_tnv_mean);
tnv_dist_mkt_mean = group_mean(tnv_dist, 1, market);
night_reverse = tnv_dist<tnv_dist_mkt_mean?-night_dist:night_dist;
night_tnv_rev = ts_mean(night_reverse, 20);
ballteam_coin = -d1_std_rev-d1_tnv_rev-d0_std_rev-d0_tnv_rev-night_tnv_rev-night_std_rev;
group_neutralize(ballteam_coin,bucket(rank(cap),range='0.1,1,0.1'))
turnover = volume / sharesout;
avg_turn = ts_mean(turnover, 30);
nor_turn = ts_delay(turnover - avg_turn, 3);
change = (close - open) / open;
avg_change = ts_mean(change, 30);
nor_change = change - avg_change;
ts_corr(nor_turn, abs(nor_change), 10) 
triggerTradeexp = (ts_arg_min(volume, 5) > 3) || (volume >= ts_sum(volume, 5) / 5);
alphaexp = rank(rank((high + low) / 2 - close) * rank((mdl175_roediluted*mdl175_cashrateofsales)));
tradeExitexp = -1;  
trade_when(triggerTradeexp, alphaexp, tradeExitexp)
overnight_ret = (open - ts_delay(close,1))/ts_delay(close,1);
abs_ovn_ret = abs (overnight_ret);
turn = volume/sharesout;
turn_d1 = ts_delay(turn, 1);
corr = ts_corr (abs_ovn_ret, turn_d1,7);
-(corr)
Turn20_ = ts_mean(volume/sharesout, 20);
Turn20 = group_neutralize(Turn20_, bucket(rank(cap), range="0.1,1,0.1"));

STR_ = ts_std_dev(volume/sharesout, 20);
STR = group_neutralize(STR_, bucket(rank(cap), range="0.1,1,0.1"));

score2 = rank(- nan_mask(Turn20, if_else(rank(STR) < 0.5, 1, -1))) * 0.5;
score3 = rank(nan_mask(Turn20, if_else(rank(STR) >= 0.5, 1, -1))) * 0.5;

signal_ = add(rank(STR), score2, score3, filter = true);
signal = left_tail(rank(signal_), maximum=0.98);
- group_rank(signal, bucket(rank(cap), range="0.1,1,0.1"))
my_group=bucket(rank(cap), range="0,1,0.1");
shock=(high-ts_delay(low, 1))/ts_delay(low, 1);
talor_shock=(shock-log(shock+1))*2-log(shock+1)**2;
alpha=-group_rank(ts_mean(talor_shock, 24), my_group);
group_neutralize(alpha,my_group)
turnover_rank = ts_mean(rank(volume / (sharesout * 1000000)), 22);
spe = rank(vec_avg(anl17_d1_spe_tse));
bp = rank(vec_avg(anl17_d1_bp_tse));
alpha = spe - bp;
# alpha
turnover_rank > 0.1 ? alpha : 0
# CHN模板
turn = volume/sharesout ;
turn20 = rank(regression_neut(-ts_mean(turn,20),densify(cap)));
STR = regression_neut(-ts_std_dev(turn,20),densify(cap));
UTR = STR+ turn20 * (STR/(1+abs(STR)));
regression_neut(regression_neut(regression_neut(sign(UTR) * power(abs(UTR),0.
5),turn20),vwap),ts_delta(retained_earnings / sharesout, 120))
internal=ts_delay(ts_percentage(returns, 60, percentage=0.9)-ts_percentage
(returns, 60, percentage=0.1),40);
CV=ts_std_dev((close/open - 1), 20)/ts_mean((close/open - 1),20);
alpha=ts_sum(-returns,20)*rank(internal)*abs (1/CV);
group_neutralize (alpha, bucket(rank(cap), range='0.1,1,0.1'))
industry_open = group_mean(open, cap, subindustry);
industry_close = group_mean(close, cap, subindustry);
industry_high = group_mean(high, cap, subindustry);
industry_low = group_mean(low, cap, subindustry);

Trends = if_else(industry_close > ts_delay(industry_close, 40),
industry_close/ts_max(industry_high, 100), rank(industry_close/ts_min
(industry_low, 500))-1);
OTSM = ts_sum((industry_high-ts_delay(industry_close, 1)) / (ts_delay
(industry_close, 1)-industry_low+1), 90);
DTSM = ts_sum((industry_high-industry_open) / (industry_open-industry_low+1),
5);

TSM = rank(OTSM) + rank(DTSM);

rank(Trends) + rank(TSM)
small_sell = vec_avg(pv27_sell_value_small_order);
small_buy = vec_avg(pv27_buy_value_small_order);
large_sell = vec_avg(pv27_sell_value_exlarge_order);
large_buy = vec_avg(pv27_buy_value_exlarge_order);

fac_small = small_sell + small_buy;
fac_large = large_sell + large_buy;

fac_small_diff_mean = fac_small - group_mean(fac_small, 1, subindustry);
fac_large_diff_mean = fac_large - group_mean(fac_large, 1, subindustry);

factor = if_else(rank(cap)<0.05, fac_small_diff_mean, fac_large_diff_mean);
if_else(rank(factor) <0.45, rank(factor)*0.55, factor, -1)
 

请注意，本贴仅收集总结，优秀程度不一定。感谢所有作者的贡献，如果您希望展示昵称，欢迎随时评论。


195
评论
45 条评论排序方式 

PN39025
Osmosis AllocatorMaster consultant
1年前
The ideas you implement have quite solid logic. From the ideas you share, I have followed some good performance alpha. Thank you.


18


CT68712
Osmosis AllocatorGrandMaster consultant
1年前
感谢楼主的分享，这些Alpha模板涵盖了多种思路和方法，不仅有截面回归和时序回归的结合，还包括对数据窗口、行业中性化和因子筛选的细致处理。特别是对财务数据与市场数据的结合应用，逻辑清晰且具有很好的参考价值。

一些模板如“小而稳”因子、反转因子和新闻情绪结合市场波动的思路都非常有启发性，尤其适合进一步调整和优化。虽然部分公式可能存在过拟合风险，但整体框架非常扎实，提供了很多可以实验和探索的方向。

感谢各位作者的贡献！希望未来能看到更多高质量的Alpha分享，一起交流和进步！🚀


17


LY88401
Master consultant
1年前
a = ts_zscore({datafield, 252);
a1 = group_neutralize(a, bucket(rank(cap), range='0.1,1,0.1'));
a2 = group_neutralize(a1, industry);b = ts_zscore(cap, 252);
b1 = group_neutralize(b, industry);c = regression_neut(a2,b1);
c

这个模块设计非常出色，充分展现了灵活性和实用性！🎉  

1. **数据标准化与中和处理**：  
   首先使用 `ts_zscore` 对数据进行 252 天的标准化（如 a 和 b），提升数据的可比较性。接着通过 `group_neutralize`，分别对资本分组（`bucket(rank(cap))`）和行业进行中和处理（a1 和 a2），有效降低异常值和行业波动的影响，显着提高数据稳健性。  

2. **回归中和的创新应用**：  
   最后使用 `regression_neut` 将 a2 和 b1 进行回归中和，这一步进一步消除资本和行业等干扰因素，专注于核心变量，为生成更准确的 Alpha 信号提供了强大支持。  

3. **逻辑结构清晰**：  
   整个模块从标准化到中和再到回归中和，结构严谨，逻辑清晰，便于用户灵活应用并根据需求进行调整。  

总之，这个模块功能强大，设计精巧，是开发高质量 Alpha 信号的理想工具，值得广泛应用！💡


24


XL50418
Gold consultant
1年前
请问下‘regression_neut’ 是哪个operator？做什么的？我在文档里好像没见到它


18


DN41247
Osmosis AllocatorMaster consultant
1年前
感谢分享这些Alpha模板！您的总结非常详细，对于构建复杂信号的过程提供了宝贵的参考。这些方法虽然可能存在一定的overfitting风险，但通过更多的顾问活动和课程深入理解，能够进一步优化使用效果。非常期待您分享更多类似的洞见！


11


ZX27801
Gold consultant
1年前
可否请您对模板中的参数进行一些解释，比如

{group_opr}、{vector_opr}、{Sentiment}、{OptionHighPrice}、{Analyst Std}等

13


KJ42842
1年前
ZX27801

{group_opr}、{vector_opr} 为操作符
{Sentiment}、{OptionHighPrice}、{Analyst Std} 为数据字段类型

11


NO56320
Osmosis AllocatorGold consultant
1年前
Thank you so much. These frameworks will be so helpful in my research to explore more datasets


9


PN39025
Osmosis AllocatorMaster consultant
1年前
你好，我的等级较低，受到一些运算符的限制，因此无法尝试你提供的那些想法。请问有没有办法将基本函数进行变换，以便能够使用上述的想法呢？感谢你的帮助！


11


YW93864
Osmosis AllocatorMaster consultantConversation starter
1年前
PN39025

对于模板alpha：1. 理解模板的含义；2. 尝试复现；3. 如果复现不了（比如受制于运算符的限制），尝试迭代它的运算符，例如将原本group_mean替换为其他的group operator，诸如此类；4. 如果发现无效，那么优化它或者直接放弃它，找下一个模板。Good Luck.


16


YW93864
Osmosis AllocatorMaster consultantConversation starter
1年前
XL50418

如果您没有找到regression neut，说明您可能被限制使用该运算符了。

您可以试着找一找regression_proj(Y,X)这个运算符，它的结果是bx+a；而regression_neut(Y,X)是Y-(bx+a)，您可以考虑使用Y-regression(Y,X)代替它


10


PM70927
1年前
都没有具体参数

 

 


9


JR87773
1年前
使用是直接复制粘贴上去吗？小白刚刚开始，还没摸明白


8


LL87164
Osmosis AllocatorMaster consultant
1年前 已编辑于
LY88401

a1和a2的顺序换一下，即先做按行业中性化再做按市值中性化，效果会不同吗？

a = ts_zscore({datafield, 252);
a1 = group_neutralize(a, industry);
a2 = group_neutralize(a1, bucket(rank(cap), range='0.1,1,0.1'));


9


YC92090
Osmosis AllocatorExpert consultant
1年前
LL87164

diff=regression_neut(data1, data2);可以使用以下實作

g = country;
mean_x = group_mean(data2, 1, g);
mean_y = group_mean(data1, 1, g);
mean_diff_x = (data2 - mean_x);
mean_diff_y = (data1 - mean_y);
S_xy = group_sum((mean_diff_x) * (mean_diff_y), g);
S_xx = group_sum((mean_diff_x) * (mean_diff_x), g);
w = S_xy / S_xx ;
b = mean_y - w * mean_x;
diff = data1 - (data2 * w + b);


18


EM11875
Osmosis AllocatorExpert consultant
1年前
很高兴收到这篇文章。这非常有帮助。我从共享的框架中学到了很多东西,并且仍在探索如何最好地保持良好的Alpha性能。谢谢


8


TD37298
Osmosis AllocatorExpert consultant
1年前
这些Alpha公式的风险各异，我该如何评估和筛选出更稳健的策略？有没有什么通用的风险评估指标或方法.


11


EF66710
10个月前
很高兴收到这篇文章。这非常有帮助。我从共享的框架中学到了很多东西,并且仍在探索如何最好地保持良好的Alpha性能。谢谢


7


PX70901
Gold consultant
10个月前
my_group = market;

my_group2 = bucket(rank(cap),range='0,1,0.1');

alpha=rank(group_rank(ts_decay_linear(volume/ts_sum(volume,252),10),my_group)*group_rank(ts_rank(vec_avg({Fundamental}),这里少了日期...),my_group)*group_rank(-ts_delta(close,5),my_group));

trade_when(volume>adv20,group_neutralize(alpha,my_group2),-1)为什么会这样

10


LY45126
10个月前
helpful !


7


LW67640
Osmosis AllocatorMaster consultant
10个月前
现在顾问的六维指标里有operator count和datafield count，如果大家使用这些模版，可以让GPT帮忙减少运算符和数据字段，比如保留核心逻辑，比如不改变经济学含义的情况下减少。。。

这里面的模版很多顾问都在使用，前提是不要生搬硬套的去用，现在有了GPT，即使很多基础知识不熟悉，一样可以优化和修改，本质上还是要理解模版所代表的经济学含义。盲目的套模版，即使有提交的alpha，一段时间后还是原地踏步，对自己的提升没有任何的帮助。

-------------------------------------------------------


62


ST57347
Gold consultant
9个月前
这些模板需要使用区分吗？

 


5


HL92654
Gold consultant
8个月前
感谢感谢，先研究研究


2


SZ20589
Master consultant
8个月前
感谢分享，我现在还停留在使用新人模板挖因子阶段，这个帖子给了我新的思路，要想长期能坚持下去，一定要能看懂其中的含义，从共享的模板里找到高质量和良好性能的alpha


39


ZL15100
Osmosis AllocatorGold consultant
8个月前
很好用，我一天提交了几十个阿尔法


2


ZL15100
Osmosis AllocatorGold consultant
8个月前
my_group = market;
my_group2 = bucket(rank(cap),range='0,1,0.1');
alpha=rank(group_rank(ts_decay_linear(volume/ts_sum(volume,252),10),my_group)*group_rank(ts_rank(vec_avg({Fundamental})),my_group)*group_rank(-ts_delta(close,5),my_group));
trade_when(volume>adv20,group_neutralize(alpha,my_group2),-1)
这个模板里ts_delta(close,5)修改为：(ts_delay(close,5) - close)/ts_delay(close,5)是不是更合理了
我使用这个模板，跑了fundamental6,fundamental2数据集
另外将vec_avg去掉直接取matrix类型字段，分别把vector,matrix类型的字段都跑了，跑出至少50个阿尔法
感觉使用基本面model16的数据集应该也可以跑出一些阿尔法，可以尝试尝试
 


11


SG46247
Gold consultant
7个月前
LY88401

a1和a2的顺序换一下，即先做按行业中性化再做按市值中性化，效果会不同吗？

a = ts_zscore({datafield, 252);
a1 = group_neutralize(a, industry);
a2 = group_neutralize(a1, bucket(rank(cap), range='0.1,1,0.1'));

这个效果是不同的

1.
残留效应不同：

行业→市值顺序：市值分组内仍保留跨行业信息
市值→行业顺序：行业内仍保留跨市值信息
2.
行业-市值交互作用：

先处理行业：强化行业内不同市值股票的差异
先处理市值：突出同市值组内不同行业的差异
3.
极端值处理：

行业优先：更有效过滤行业龙头股的市值偏差
市值优先：更好处理小盘股中的行业异常值

42


XG98059
Osmosis AllocatorGold consultant
6个月前
受益匪浅。


2


YQ51506
Osmosis AllocatorMaster consultant
6个月前
这个帖子收集的alpha模板挺有意思，特别是那个用group_neutralize和bucket处理cap分组的思路，在WorldQuant Brain上回测应该能避免一些市值偏差。不过大佬们要注意overfitting风险，像那个用ts_regression做volume和sentiment回归的因子，参数设置到750天，回测时得小心数据窥探。这些模板作为因子挖掘的起点还不错，但需要进一步优化中性化和衰减参数。


76


WL20457
Osmosis AllocatorMaster consultant
6个月前
感谢分享，评论区也很精彩，作为一个新人，尝试去理解大佬们讲的东西，真的获益匪浅，非常感谢！！

CC85858
Osmosis AllocatorGrandMaster consultant
6个月前
可以在原本要提交的alpha上增加双中性化有时能大幅度提高原有信号，比如原有表达式为alpha，

加上双中性化后为group_neutralize(group_neutralize(alpha,group),group)，group可选择：sector、

exchange、industry、subindustry、currency、country、market等数据类型为group的字段


81

JC84638
Osmosis AllocatorGrandMaster consultant
6个月前
ZL15100 這麼好用 !? 有推薦的嗎 ^-^ ? 


4

ML47973
Osmosis AllocatorMaster consultant
6个月前 已编辑于
- A * ts_std_dev(A, 30)，我称其为“小而稳”（时间参数可根据Dataset/Datafield调整）。

a = - A * ts_std_dev(A, 20);

b=abs(ts_mean(returns,252)/ts_std_dev(returns,252));

vector_neut(a,b)

关于以上alpha模板我的理解与思考：

核心逻辑：-A * ts_std_dev(A, 20) 这个结构非常精彩 . 它本质上是一个动态的、经过波动率调整的均值回复因子 .

-A 捕捉了反转效应；

ts_std_dev(A, 20) 衡量的近期波动率；

当波动率大时，反转的“力度”也被放大，这很符合逻辑：在不确定性高的股票上做反转，需要更大的“信心”或风险暴露，这个乘法结构恰好实现了这一点 .

“小而稳”的命名非常贴切 . 这个因子很可能倾向于筛选出那些近期波动率较低、价格相对平稳的股票进行反转交易，避开了高波动的“噪音”，从而可能获得更稳健的收益 .

后续处理：用vector_neut对标普500的年化夏普比率 (b) 进行中性化是点睛之笔。这相当于在建模时，就主动剔除了市场长期质量因子的影响，让Alpha更纯粹地捕捉到你设计的这个“小而稳”反转效应，减少了与其他风格因子的共线性 .

对我个人的启发：
        这个模板给了我一个很好的示范，即如何将一个简单的想法（如反转）与风险调整（波动率）、风格中性化结合起来，构建出一个逻辑完整、结构优雅的Alpha . 我正在尝试借鉴这个思路，应用到其他数据域上 .

感谢WeiLie老师分享这么有价值的模板，让我对Alpha的理解又深了一层！


57

ZL15100
Osmosis AllocatorGold consultant
6个月前
@JC84638  带带我


1

WD63718
5个月前
受益匪浅！多谢分享，
ts_regression (ts_zscore(A,500), timestep(500),500);
上述5个系列后续可以尝试同时结合截面回归和时序回归。通过截面回归处理财务数据的分布，通过时序回归找出robust的signal
缩小space。上述财务数据并没用限制，因此空间非常大；建议从盈利成长、成本、经营、安全性等重要维度先进行搜索，另外，可以先不考虑覆盖率较低的datafield
可以用分析师数据代替财务数据，比如净利润
基本面量化建议从经济逻辑出发，也不建议使用很复杂的公式，容易overfitting（因为数据点较少，很容易fit噪音）
注意窗口设置时的500天，这实际上会导致回归时变量的方差被低估

1

HT19604
5个月前
ZL15100我学校有个比赛，但我刚接触，可以多解释你那个留言怎么跑50个alpha吗？


1

HT19604
5个月前
ZL15100 求带，赢了有赏

 


1

MW39826
Osmosis AllocatorGold consultant
4个月前
感谢！根据这些模版可以挖掘出更多优秀的因子


1

WZ33694
Gold consultant
4个月前
感谢分享，学习很多。


0

HY66508
Osmosis AllocatorGold consultant
2个月前
-                                                                                                                                                                                            感谢分享，提供了那么多模板                                                                                                                                                                                                                                   -


56

MT73464
2个月前
感谢分享


0

JJ11850
Osmosis AllocatorGold consultant
1个月前
mark，尝试一下


1

TT73161
24天前
谢谢分享！我将马上进行修改与尝试


0

CJ35772
14天前
代码搞下来学习研究一下，谢谢


0

LiYiShu(YL50199)
13天前
感谢分享，给新人提供了思路，站在巨人肩膀上慢慢修改


0
