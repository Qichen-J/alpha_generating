Sub-universe test is one of the robustness tests performed on an Alpha by the BRAIN before submission. In simple words, it ensures that your Alpha works not only in the universe you're trying to submit, but that it could also work in the next more liquid (or smaller) universe to some extent.

E. g. If you're trying to submit an Alpha on USA TOP3000, the platform will also check its performance on USA TOP1000. If it performs poorly, then it means that your Alpha is generating most of the profit on the non-liquid portion of stocks, which is one of the signs that your Alpha is not robust enough and most likely will not perform as well as expected in out-of-sample testing. That’s why such Alphas are not allowed to be submitted on Brain.

Technical details:

The threshold to pass the sub-universe test is defined by the formula:
subuniverse_sharpe >= 0.75 * sqrt(subuniverse_size / alpha_universe_size) * alpha_sharpe
Sub-Universe Sharpe is calculated using PnL of Alpha obtained through the following process (notice that it is similar to the Sharpe of an Alpha simulated in the sub-universe, but not exactly the same, as you will see in the example below):
Pasteurize to the target universe, that is, for all stocks not in the sub-universe, assign value of NaN
Apply market neutralization to resulting set (subtract mean of all values from each value) and then scale Alpha back to original size.
Calculate PnL using resulting Alpha values
Consider an Alpha in USA TOP3000 which fails sub-universe test:

check111.png
Subuniverse 3.png
 

Notice cutoff

0.75 * sqrt(subuniverse_size / alpha_universe_size) * alpha_sharpe = 0.75 * sqrt(1000 / 3000) * 2.73 = 1.18
Let’s check this Alpha performance on next more liquid universe, TOP1000

subuniverse 5.png
subinverse 6.png
 

As you see, Sharpe ratio degraded significantly to 1.17, less than the cutoff of 1.18.

 

Tips to help you improve your Alpha(s) and pass the sub-universe test:
Avoid using multipliers related to the size of the company in your Alphas, e.g. rank(-assets), 1–rank(cap), etc. These multipliers may significantly shift the distribution of your Alpha weights to more/less liquid side and it may affect the sub-universe performance.
Try decaying separately the liquid and non-liquid parts of your signal. As a proxy for liquidity you can use cap or volume*close, for example instead of
ts_decay_linear(signal, 10)
You can try

ts_decay_linear(signal, 5) * rank(volume*close) + ts_decay_linear(signal, 10) * (1 – rank(volume*close))
Check out your Alpha improvements step by step, maybe one of them resulted in better stats, but at the same time Alpha started to fail sub-universe test?
Try these tips to improve overall Sharpe of your Alpha.
If nothing helps - don’t get upset. Some signals are just not robust. It's always sad to discard an Alpha with good IS performance but remember: your long-term success as a quant depends on how your Alphas perform in out-of-sample, not during in-sample simulation. Most likely, you just dodged a bad Alpha.
32 comments