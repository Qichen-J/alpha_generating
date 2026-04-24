Broadly speaking, a high capacity alpha can be associated with three major norms: high liquidity, low correlation and low turnover. Of these, the most significant contributor to the increase in capacity is low turnover. By definition, low turnover means that the alpha is trading with less frequency — which means fewer transactions are being processed and in that way we have the capability to trade more easily. Hence, we are increasing the capacity of the alpha. There are many ways of reducing wasteful turnover of an alpha. A very basic method is the hump operation. This operation is supposed to analyze the alpha values of an existing alpha and then manipulate some of them to reduce the turnover of that alpha.

Basic Idea: In general, for a normal alpha the value changes every day per its formula. Many times the alpha’s value doesn’t change significantly, yet the alpha still has to simulate a trade. The simulated PnL generated in these transactions is not that great, but the transaction costs involved are still pretty high. This is wasteful turnover that can be reduced smartly with simple techniques. We can define a threshold in terms of the percentage of change in the alpha value and simulate a trade only when the percentage change crosses that threshold value.

Improvement: The single threshold value could be variable depending upon market conditions (different ways of evaluating — e.g., movement/volatility of index).

Each instrument could have a variable threshold (liquidity/market-cap/volatility).

There can also be a single threshold value for a group (subindustry/sector/custom group).

Increasing the threshold values either uniformly or not uniformly after ranking the instruments on the basis of a few factors (market-cap/volatility) can help.

Future direction: The impact of volatility is much more important than any other factor for deciding the capacity of the alpha, and also the individual thresholds of stocks in the hump operation. Looking at it a bit differently, try to think in line with an event alpha. Keep monitoring the short-term volatility of the stock, and also keep a sense of average long-term stock volatility. Whenever the stock volatility has a spike and crosses a certain (customizable) threshold, the alpha starts simulating a trade as per its values, with the idea that this is the period in which the alpha might generate simulated profits. For the other times, we keep holding the stock, or alternatively we can continue with the previous hump operation during these times but with a much stricter threshold.


21
You can use the following targeting to create event-driven alphas and low turnover alphas.

Concept:
If (event) {
Assign alpha values;
} else {
Hold alpha values;
}
Expression:

trade_when(Event_condition, Alpha_expression, -1)

Pros:

Good alpha coverage
Flexible in determining events
Can be used to enhance signals by trading at the right time
Low turnover and low cost alpha

 

Cons:

Not easy to get high Sharpe alpha
Not easy to get high return alpha

Approach:
Define events: Any spike in returns, data values and technical indicators can be used to define events.
Alpha assignment: Look for signals that are aligned with the abnormality of an event — that is, alphas that need to be executed when such events happen.

Note:
Hold alpha can be replaced by decaying alpha linearly or exponentially.
Check alpha coverage to make sure events are not so rare.


37
The Decay function in the Alpha settings block is a linear decay function over a period of n days where the value on day "t" is equal to the weighted average of the values from day "t" to day "t-n". 

What exactly does this do to the alpha? Does this linear decay function change all input data being used in the alpha? So the actual values are not being used, but rather every input value is changed to a weighted average? In this case, why is the default decay set to 4? 